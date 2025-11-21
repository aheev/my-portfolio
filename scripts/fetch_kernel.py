#!/usr/bin/env python3
"""
scripts/fetch_kernel.py

Fetch commits from git.kernel.org (author search) and patches from lore.kernel.org (a:author).
Writes:
 - data/linux_commits.json   -> { "commits": [ ... ] }
 - data/linux_patches.json   -> { "patches": [ ... ] }

Config via env:
 - KERNEL_EMAIL (optional) default 'allyheev@gmail.com'
 - MAX_PAGES (optional) default 8
 - SLEEP_BETWEEN_REQUESTS (optional) default 0.8
"""
import os, time, json, re
from urllib.parse import quote_plus
from datetime import datetime
import requests
from bs4 import BeautifulSoup

KERNEL_EMAIL = os.environ.get("KERNEL_EMAIL", "allyheev@gmail.com")
MAX_PAGES = int(os.environ.get("MAX_PAGES", "8"))
SLEEP = float(os.environ.get("SLEEP_BETWEEN_REQUESTS", "0.8"))
HEADERS = {"User-Agent": os.environ.get("USER_AGENT", "Mozilla/5.0 (compatible; fetch_kernel/1.0)")}
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def safe_get(url, params=None, tries=3):
    delay = 1.0
    for _ in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            time.sleep(delay)
            delay *= 2
        except Exception:
            time.sleep(delay)
            delay *= 2
    return None

def parse_commit_row(row):
    """Given a BeautifulSoup row, extract commit info if present"""
    # commit message anchor
    a = row.select_one("td.commitmsg a")
    if not a:
        return None
    title = a.get_text(strip=True)
    href = a.get("href")
    url = "https://git.kernel.org" + href if href.startswith("/") else href
    # date in td.committime or time tag
    date_el = row.select_one("td.committime")
    date_text = date_el.get_text(strip=True) if date_el else None
    # try to normalize date text; best-effort
    date_iso = None
    if date_text:
        # common format: "2024-01-12 10:15:41 -0400"
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?: [+-]\d{4})?)", date_text)
        if m:
            date_iso = m.group(1)
    # subsystem heuristic
    subsys = "unknown"
    m = re.search(r"\[([^]]+)\]", title)
    if m:
        subsys = m.group(1)
    return {"title": title, "url": url, "date": date_iso, "subsystem": subsys}

def fetch_gitkernel_by_email(email, max_pages=8):
    commits = []
    seen = set()
    q = quote_plus(email)
    base = "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/log/"
    for pg in range(max_pages):
        url = f"{base}?qt=author&q={q}&pg={pg}"
        html = safe_get(url)
        if not html:
            # try fallback page param
            url = f"{base}?qt=author&q={q}&page={pg}"
            html = safe_get(url)
            if not html:
                break
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("tr.commit")
        if not rows:
            # try fallback anchors scanning
            anchors = soup.select("a[href*='/commit/']")
            if not anchors:
                break
            # create faux rows
            for a in anchors:
                title = a.get_text(strip=True)
                href = a.get("href")
                url2 = "https://git.kernel.org" + href if href.startswith("/") else href
                if url2 in seen:
                    continue
                seen.add(url2)
                commits.append({"title": title, "url": url2, "date": None, "subsystem": "unknown"})
            break

        new_count = 0
        for row in rows:
            item = parse_commit_row(row)
            if not item:
                continue
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            commits.append(item)
            new_count += 1
        if new_count == 0:
            break
        time.sleep(SLEEP)
    return commits

def fetch_lore_patches_by_email(email, max_pages=8):
    patches = []
    seen = set()
    base = "https://lore.kernel.org/all/"
    q = quote_plus(f"a:{email}")
    for page in range(max_pages):
        url = f"{base}?q={q}&page={page}"
        html = safe_get(url)
        if not html:
            # page 0 fallback
            if page == 0:
                url = f"{base}?q={q}"
                html = safe_get(url)
            if not html:
                break
        soup = BeautifulSoup(html, "lxml")
        # entries with snippet-subject
        entries = soup.select("a.snippet-subject")
        if not entries:
            # fallback to anchors under /r/
            entries = soup.select("a[href^='/r/']")
        new_count = 0
        for a in entries:
            href = a.get("href")
            title = a.get_text(strip=True)
            if not href:
                continue
            url2 = "https://lore.kernel.org" + href if href.startswith("/") else href
            if url2 in seen:
                continue
            seen.add(url2)
            # try fetch patch page for date/status
            date_iso = None
            state = "patch"
            try:
                page_html = safe_get(url2)
                if page_html:
                    sp = BeautifulSoup(page_html, "lxml")
                    # find lines like "Date: 2024-01-11 10:15:41 -0500"
                    txt = sp.get_text(separator="\n")
                    m = re.search(r"Date:\s*([0-9T:\- +Z]+)", txt)
                    if m:
                        date_iso = m.group(1).strip()
                    m2 = re.search(r"\[(v\d+|RFC)\]", title, re.IGNORECASE)
                    if m2:
                        state = m2.group(1)
            except Exception:
                pass
            patches.append({"title": title, "url": url2, "date": date_iso, "state": state})
            new_count += 1
        if new_count == 0:
            break
        time.sleep(SLEEP)
    return patches

def main():
    print("[fetch_kernel] starting")
    commits = fetch_gitkernel_by_email(KERNEL_EMAIL, max_pages=MAX_PAGES)
    print(f"[fetch_kernel] commits found: {len(commits)}")
    patches = fetch_lore_patches_by_email(KERNEL_EMAIL, max_pages=MAX_PAGES)
    print(f"[fetch_kernel] patches found: {len(patches)}")
    # write outputs (no email fields)
    with open(os.path.join(DATA_DIR, "linux_commits.json"), "w", encoding="utf-8") as f:
        json.dump({"commits": commits}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(DATA_DIR, "linux_patches.json"), "w", encoding="utf-8") as f:
        json.dump({"patches": patches}, f, indent=2, ensure_ascii=False)
    print("[fetch_kernel] written files")

if __name__ == "__main__":
    main()
