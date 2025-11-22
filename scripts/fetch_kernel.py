#!/usr/bin/env python3
"""
fetch_kernel.py (final)

- Uses KERNEL_EMAIL from environment (no hardcoded email in the code)
- Scrapes git.kernel.org author search (list-style pages)
- Scrapes lore.kernel.org author search
- Converts relative ages ("3 weeks ago") -> UTC ISO timestamps using M3 (month = 30.44 days)
- Stores UTC ISO timestamps (no 'approx' flags)
- Merges with existing data files (data/linux_commits.json, data/linux_patches.json)
- Deduplicates by URL
- Early-stop heuristic: stop when encountering many already-known items in a row
- Config via env:
    KERNEL_EMAIL (required; do not put literal email in repo — store as Actions secret)
    MAX_PAGES (optional; default 12)
    SLEEP_BETWEEN_REQUESTS (optional; default 0.8)
    EXISTING_CONTIGUOUS_STOP (optional; default 6)
"""
from __future__ import annotations
import os
import time
import json
import re
from urllib.parse import quote_plus
from datetime import datetime, timedelta, timezone
from typing import Tuple, List, Dict, Set, Optional

import requests
from bs4 import BeautifulSoup

# ----------------- Configuration (from env only) -----------------
KERNEL_EMAIL = os.environ.get("KERNEL_EMAIL")  # MUST be provided as secret in Actions
if not KERNEL_EMAIL:
    # be explicit: script will still run but will fetch nothing if email not set
    print("[fetch_kernel] WARNING: KERNEL_EMAIL not set. Exiting without fetching.")
    # Exit with success (no-op) to avoid failing workflow unexpectedly
    exit(0)

MAX_PAGES = int(os.environ.get("MAX_PAGES", "12"))
SLEEP = float(os.environ.get("SLEEP_BETWEEN_REQUESTS", "0.8"))
EXISTING_CONTIGUOUS_STOP = int(os.environ.get("EXISTING_CONTIGUOUS_STOP", "6"))
HEADERS = {"User-Agent": os.environ.get("USER_AGENT", "Mozilla/5.0 (compatible; fetch_kernel/1.0)")}
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

OUT_COMMITS = os.path.join(DATA_DIR, "linux_commits.json")
OUT_PATCHES = os.path.join(DATA_DIR, "linux_patches.json")
OUT_GITK = os.path.join(DATA_DIR, "gitkernel.json")  # compatibility

# ----------------- HTTP helper with retries -----------------
def safe_get(url: str, params: dict | None = None, tries: int = 3) -> Optional[str]:
    delay = 1.0
    for _ in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            # non-200: wait and retry
            time.sleep(delay)
            delay *= 2
        except Exception:
            time.sleep(delay)
            delay *= 2
    return None

# ----------------- Load existing data (for merge & early-stop) -----------------
def load_existing(path: str, key: str) -> Tuple[Set[str], List[dict]]:
    if not os.path.exists(path):
        return set(), []
    try:
        j = json.load(open(path, "r", encoding="utf-8"))
        items = j.get(key, []) if isinstance(j, dict) else []
        urls = set()
        for it in items:
            u = it.get("url") or it.get("link") or it.get("id") or ""
            if u:
                urls.add(u)
        return urls, items
    except Exception:
        return set(), []

# ----------------- Time parsing / relative -> UTC ISO (M3 month = 30.44 days) -----------------
def relative_to_utc_iso(text: str) -> Optional[str]:
    if not text:
        return None
    s = text.strip().lower()
    now = datetime.now(timezone.utc)

    if s in ("yesterday", "a day ago"):
        dt = now - timedelta(days=1)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if s in ("an hour ago", "an hr ago"):
        dt = now - timedelta(hours=1)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if s in ("just now", "moments ago", "a few seconds ago"):
        return now.strftime("%Y-%m-%dT%H:%M:%SZ")

    m = re.match(r'(\d+)\s+(second|seconds|minute|minutes|min|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago', s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("second"):
            dt = now - timedelta(seconds=n)
        elif unit.startswith("min"):
            dt = now - timedelta(minutes=n)
        elif unit.startswith("hour"):
            dt = now - timedelta(hours=n)
        elif unit.startswith("day"):
            dt = now - timedelta(days=n)
        elif unit.startswith("week"):
            dt = now - timedelta(days=n * 7)
        elif unit.startswith("month"):
            dt = now - timedelta(days=n * 30.44)   # M3 average month
        elif unit.startswith("year"):
            dt = now - timedelta(days=n * 365.25)
        else:
            return None
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    m2 = re.match(r'(about|over|around)?\s*(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago', s)
    if m2:
        n = int(m2.group(2))
        unit = m2.group(3)
        return relative_to_utc_iso(f"{n} {unit} ago")

    return None

def extract_iso_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    # ISO-like: 2024-01-02T12:34:56Z or with +00:00
    m = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+\-]\d{2}:?\d{2}))', text)
    if m:
        v = m.group(1)
        try:
            v2 = v.replace("Z", "+00:00")
            dt = datetime.fromisoformat(v2)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
    # fallback: "YYYY-MM-DD HH:MM:SS ±ZZZZ"
    m2 = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?: [+\-]\d{4})?)', text)
    if m2:
        raw = m2.group(1)
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            try:
                dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass
    return None

# ----------------- git.kernel.org scraping (list-based) -----------------
def fetch_gitkernel_commits(email: str, max_pages: int = 12, existing_urls: Optional[Set[str]] = None) -> List[Dict]:
    commits: List[Dict] = []
    existing_urls = existing_urls or set()
    seen = set(existing_urls)
    base = "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/log/"
    q = quote_plus(email)
    contiguous_known = 0

    for pg in range(max_pages):
        url = f"{base}?qt=author&q={q}&pg={pg}"
        html = safe_get(url)
        if not html:
            # fallback
            url = f"{base}?qt=author&q={q}&page={pg}"
            html = safe_get(url)
            if not html:
                break

        soup = BeautifulSoup(html, "lxml")
        # find list items that contain commit links
        lis = soup.find_all("li")
        found_on_page = 0
        for li in lis:
            a = li.find("a", href=re.compile(r"/commit/"))
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            url2 = "https://git.kernel.org" + href if href.startswith("/") else href

            # find age/time text near the anchor
            date_text = None
            # try <time datetime="..."> or span with 'ago'
            time_el = li.find(lambda tag: tag.name in ("time","span") and (tag.has_attr("datetime") or "ago" in (tag.get_text() or "").lower()))
            if time_el:
                if time_el.has_attr("datetime"):
                    date_text = time_el["datetime"]
                    date_iso = extract_iso_from_text(date_text) or relative_to_utc_iso(time_el.get_text(strip=True))
                else:
                    date_text = time_el.get_text(strip=True)
                    date_iso = extract_iso_from_text(date_text) or relative_to_utc_iso(date_text)
            else:
                # fallback: try the whole li text
                li_text = li.get_text(" ", strip=True)
                date_iso = extract_iso_from_text(li_text) or relative_to_utc_iso(li_text)

            # subsystem heuristic
            subsys = "unknown"
            m = re.search(r"\[([^]]+)\]", title)
            if m:
                subsys = m.group(1)

            found_on_page += 1
            if url2 in seen:
                contiguous_known += 1
                if contiguous_known >= EXISTING_CONTIGUOUS_STOP:
                    return commits
                continue
            else:
                contiguous_known = 0

            seen.add(url2)
            commits.append({"title": title, "url": url2, "date": date_iso, "subsystem": subsys})

        if found_on_page == 0:
            break
        time.sleep(SLEEP)
    return commits

# ----------------- lore.kernel.org patches scraping -----------------
def fetch_lore_patches(email: str, max_pages: int = 12, existing_urls: Optional[Set[str]] = None) -> List[Dict]:
    patches: List[Dict] = []
    existing_urls = existing_urls or set()
    seen = set(existing_urls)
    base = "https://lore.kernel.org/all/"
    q = quote_plus(f"a:{email}")
    contiguous_known = 0

    for page in range(max_pages):
        url = f"{base}?q={q}&page={page}"
        html = safe_get(url)
        if not html:
            if page == 0:
                url = f"{base}?q={q}"
                html = safe_get(url)
            if not html:
                break

        soup = BeautifulSoup(html, "lxml")
        entries = soup.select("a.snippet-subject") or soup.select("a[href^='/r/']")
        found_on_page = 0
        for a in entries:
            href = a.get("href")
            if not href:
                continue
            title = a.get_text(strip=True)
            url2 = "https://lore.kernel.org" + href if href.startswith("/") else href

            found_on_page += 1
            if url2 in seen:
                contiguous_known += 1
                if contiguous_known >= EXISTING_CONTIGUOUS_STOP:
                    return patches
                continue
            else:
                contiguous_known = 0

            # fetch patch page for a better date and state
            date_iso = None
            state = "patch"
            page_html = safe_get(url2)
            if page_html:
                sp = BeautifulSoup(page_html, "lxml")
                full_text = sp.get_text("\n", strip=True)
                date_iso = extract_iso_from_text(full_text) or relative_to_utc_iso(full_text)
                m2 = re.search(r"\[(v\d+|RFC)\]", title, re.IGNORECASE)
                if m2:
                    state = m2.group(1)
            patches.append({"title": title, "url": url2, "date": date_iso, "state": state})
            seen.add(url2)
        if found_on_page == 0:
            break
        time.sleep(SLEEP)
    return patches

# ----------------- Merge new results with existing, dedupe, write -----------------
def merge_and_write(new_items: List[Dict], existing_items: List[Dict], key_name: str) -> Tuple[int, List[Dict]]:
    existing_by_url = { (it.get("url") or it.get("link") or ""): it for it in existing_items }
    merged = existing_items[:]  # preserve existing order (older at end)
    added = 0
    for it in new_items:
        u = it.get("url") or ""
        if u and u not in existing_by_url:
            merged.insert(0, it)  # newest first
            existing_by_url[u] = it
            added += 1
    path = OUT_COMMITS if key_name == "commits" else OUT_PATCHES
    out = { key_name: merged }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("[fetch_kernel] ERROR writing", path, e)
    return added, merged

# ----------------- main -----------------
def main():
    print("[fetch_kernel] starting")
    existing_commit_urls, existing_commits = load_existing(OUT_COMMITS, "commits")
    existing_patch_urls, existing_patches = load_existing(OUT_PATCHES, "patches")

    new_commits = fetch_gitkernel_commits(KERNEL_EMAIL, max_pages=MAX_PAGES, existing_urls=existing_commit_urls)
    print(f"[fetch_kernel] new commits found: {len(new_commits)}")
    new_patches = fetch_lore_patches(KERNEL_EMAIL, max_pages=MAX_PAGES, existing_urls=existing_patch_urls)
    print(f"[fetch_kernel] new patches found: {len(new_patches)}")

    added_commits, merged_commits = merge_and_write(new_commits, existing_commits, "commits")
    added_patches, merged_patches = merge_and_write(new_patches, existing_patches, "patches")
    print(f"[fetch_kernel] commits added: {added_commits} (total now {len(merged_commits)})")
    print(f"[fetch_kernel] patches added: {added_patches} (total now {len(merged_patches)})")

    # write compatibility
    try:
        with open(OUT_GITK, "w", encoding="utf-8") as f:
            json.dump({"items": merged_commits, "count": len(merged_commits)}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    print("[fetch_kernel] done")

if __name__ == "__main__":
    main()
