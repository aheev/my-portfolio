#!/usr/bin/env python3
"""
fetch_kernel.py

Robust fetcher for Linux kernel commits and patches.

- Queries git.kernel.org commit logs by author:
  https://git.kernel.org/.../log/?qt=author&q=URLENCODED_EMAIL&pg=0

- Queries lore.kernel.org for patches by author:
  https://lore.kernel.org/all/?q=a%3AURLENCODED_EMAIL&page=0

Writes (safe-for-site) JSON files into ./data/:
- data/gitkernel.json         (existing site JSON for commits)
- data/kernel_commits.json    (detailed commits)
- data/linux_patches.json     (existing site JSON for patches)
- data/kernel_patches.json    (detailed patches)

Environment:
- KERNEL_EMAIL: email to search
- MAX_PAGES (optional): int, max pages to fetch per source (default 8)
"""

import os, sys, time, json, re
from urllib.parse import quote_plus
from datetime import datetime
import requests

# ------------------ Configuration ------------------
KERNEL_EMAIL = os.environ.get("KERNEL_EMAIL", "")
MAX_PAGES = int(os.environ.get("MAX_PAGES", "8"))   # per source
SLEEP_BETWEEN_REQUESTS = float(os.environ.get("SLEEP_BETWEEN_REQUESTS", "0.8"))
USER_AGENT = os.environ.get("USER_AGENT", "Mozilla/5.0 (compatible; fetch_kernel/1.0; +https://github.com/aheev)")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

# ------------------ Helpers ------------------
def safe_get(url, params=None, max_tries=3):
    delay = 1.0
    for attempt in range(max_tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            # Rate-limited or error: backoff
            time.sleep(delay)
            delay *= 2
        except Exception as e:
            time.sleep(delay)
            delay *= 2
    return None

def iso_now():
    return datetime.utcnow().isoformat() + "Z"

def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

# ------------------ git.kernel.org commits (log search) ------------------
def fetch_gitkernel_commits(email, max_pages=8):
    """
    Fetch commit log pages searching by author email.
    Returns list of items: {id, title, url, author, date, source}
    """
    base = "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/log/"
    q = quote_plus(email)
    items = []
    seen_urls = set()

    # git.kernel.org uses ?qt=author&q=... and pagination via &page= or &pg= ?
    # Observed pattern: ?qt=author&q=...&pg=N  (some instances use 'pg')
    # We'll try both: &pg=N first; if no results try &page=N fallback.
    for pg in range(max_pages):
        url = f"{base}?qt=author&q={q}&pg={pg}"
        html = safe_get(url)
        if not html:
            # try fallback
            url = f"{base}?qt=author&q={q}&page={pg}"
            html = safe_get(url)
            if not html:
                break

        # find commit entries — capture link and title and date snippet
        # commit entries usually have <a href="/.../commit/COMMITID">Title</a>
        # and nearby a <relative-time datetime="..."> or a line "Date: ..."
        # We'll try a few regexes to be permissive.
        # Regex1: <a href="(.*?)".*?>(.*?)</a>
        entries = re.findall(r'<a\s+href="(/[^"]+/commit/[^"]+)"[^>]*>([^<]+)</a>', html, re.I)
        if not entries:
            # alternative pattern: <a href=".../log/?qt=..." title="...">...</a>
            entries = re.findall(r'<a\s+href="(/[^"]+)"[^>]*>([^<]+)</a>', html, re.I)

        if not entries:
            # no entries on this page -> stop paginating
            break

        new_found = 0
        for href, title in entries:
            full_url = "https://git.kernel.org" + href
            if full_url in seen_urls:
                continue
            # try to extract date around this link (naive)
            # look for datetime attr in surrounding html near title
            # search for <relative-time datetime="..."> or <time datetime="...">
            # fallback to now
            date_match = re.search(re.escape(href) + r'[^>]{0,200}?(?:<relative-time[^>]*datetime="([^"]+)")', html, re.I)
            if not date_match:
                date_match = re.search(re.escape(href) + r'[^>]{0,200}?(?:<time[^>]*datetime="([^"]+)")', html, re.I)
            date = date_match.group(1) if date_match else iso_now()

            item = {
                "id": href.split("/")[-1],
                "title": title.strip(),
                "url": full_url,
                "author_query": email,
                "date": date,
                "source": "git.kernel.org"
            }
            items.append(item)
            seen_urls.add(full_url)
            new_found += 1

        # nothing new on this page -> stop
        if new_found == 0:
            break
        time.sleep(SLEEP_BETWEEN_REQUESTS)
    return items

# ------------------ lore.kernel.org patches (search by author 'a:') ------------------
def fetch_lore_patches(email, max_pages=8):
    """
    Search lore.kernel.org for 'a:EMAIL' author results.
    Returns list of items: {id, subject, url, date, source}
    """
    base = "https://lore.kernel.org/all/"
    q = quote_plus(f"a:{email}")
    items = []
    seen_urls = set()

    for page in range(max_pages):
        url = f"{base}?q={q}&page={page}"
        html = safe_get(url)
        if not html:
            # try without page param for page 0
            if page == 0:
                url = f"{base}?q={q}"
                html = safe_get(url)
            if not html:
                break

        # Parse result entries. The site shows snippet items with class "snippet-subject"
        # We'll use regex to find <a class="snippet-subject" href="/r/...">Subject</a>
        entries = re.findall(r'<a[^>]*class="snippet-subject"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html, re.I)
        if not entries:
            # fallback: search for general anchors to /r/ or /patch
            entries = re.findall(r'<a[^>]*href="(/r/[^"]+)"[^>]*>([^<]+)</a>', html, re.I)

        if not entries:
            break

        new_found = 0
        for href, subj in entries:
            full_url = "https://lore.kernel.org" + href
            if full_url in seen_urls:
                continue
            # attempt to extract date snippet near the entry (simple heuristic)
            date_match = re.search(re.escape(href) + r'[^>]{0,300}?<time[^>]*datetime="([^"]+)"', html, re.I)
            date = date_match.group(1) if date_match else iso_now()
            item = {
                "id": href.split("/")[-1] if "/" in href else href,
                "subject": subj.strip(),
                "url": full_url,
                "date": date,
                "source": "lore.kernel.org"
            }
            items.append(item)
            seen_urls.add(full_url)
            new_found += 1

        if new_found == 0:
            break
        time.sleep(SLEEP_BETWEEN_REQUESTS)
    return items

# ------------------ Dedupe + normalization ------------------
def normalize_date(s):
    if not s:
        return iso_now()
    # try common formats; fall back to string
    try:
        # some datetime strings include timezone Z or +00:00; attempt isoformat parse
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d.isoformat()
    except Exception:
        return s

def main():
    print("fetch_kernel.py starting")
    print("Searching for kernel contributions for:", KERNEL_EMAIL)

    commits = fetch_gitkernel_commits(KERNEL_EMAIL, max_pages=MAX_PAGES)
    print("git.kernel.org commits found:", len(commits))

    patches = fetch_lore_patches(KERNEL_EMAIL, max_pages=MAX_PAGES)
    print("lore.kernel.org patches found:", len(patches))

    # normalize dates
    for c in commits:
        c["date"] = normalize_date(c.get("date"))
    for p in patches:
        p["date"] = normalize_date(p.get("date"))

    # write compatibility files expected by your site
    gitkernel_out = {"items": commits, "count": len(commits)}
    kernel_commits_out = {"items": commits, "count": len(commits)}
    linux_patches_out = {"items": patches, "count": len(patches)}
    kernel_patches_out = {"items": patches, "count": len(patches)}

    write_json(os.path.join(DATA_DIR, "gitkernel.json"), gitkernel_out)
    write_json(os.path.join(DATA_DIR, "kernel_commits.json"), kernel_commits_out)
    write_json(os.path.join(DATA_DIR, "linux_patches.json"), linux_patches_out)
    write_json(os.path.join(DATA_DIR, "kernel_patches.json"), kernel_patches_out)

    print("Wrote JSON files to", DATA_DIR)
    print("Done.")

if __name__ == "__main__":
    main()
