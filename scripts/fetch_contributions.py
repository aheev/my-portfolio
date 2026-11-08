#!/usr/bin/env python3
import os
import json
import requests
import re
import time
from urllib.parse import quote_plus
from datetime import datetime, timedelta, timezone

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# User IDs / Config
GITHUB_USER = "aheev"
DEVTO_USER = "ally_heev_a2677bbdadf870a" 
JIRA_JQL = f"project=KAFKA AND reporter={GITHUB_USER}"
KERNEL_EMAIL = os.environ.get("KERNEL_EMAIL", "allyheev@gmail.com") 
MAX_PAGES = 5
SLEEP_BETWEEN_REQUESTS = 1.0

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; fetch_contributions/1.0)"}

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def safe_get(url: str, params: dict | None = None, tries: int = 3):
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

def extract_iso_from_text(text: str):
    if not text: return None
    # ISO-like: 2024-01-02T12:34:56Z
    m = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+\-]\d{2}:?\d{2}))', text)
    if m:
        v = m.group(1).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(v).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except: pass
    
    # YYYY-MM-DD
    m2 = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if m2:
        return m2.group(1) + "T00:00:00Z"
    return None

def relative_to_utc_iso(text: str):
    if not text: return None
    s = text.strip().lower()
    now = datetime.now(timezone.utc)
    if "just now" in s or "seconds ago" in s: return now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if "day ago" in s: return (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    m = re.search(r'(\d+)\s+(day|week|month|year)', s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if "day" in unit: dt = now - timedelta(days=n)
        elif "week" in unit: dt = now - timedelta(days=n*7)
        elif "month" in unit: dt = now - timedelta(days=n*30)
        elif "year" in unit: dt = now - timedelta(days=n*365)
        else: return None
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None

# -----------------------------------------------------------------------------
# GitHub (GraphQL)
# -----------------------------------------------------------------------------
def fetch_github():
    print("[GitHub] Fetching...")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[GitHub] No token found. Skipping.")
        return []
    
    query = """
    query($login:String!) {
      user(login:$login) {
        pullRequests(first:50, orderBy:{field:CREATED_AT, direction:DESC}) {
          nodes {
            title
            url
            merged
            createdAt
            mergedAt
            state
            repository {
              nameWithOwner
              url
              primaryLanguage {
                name
              }
            }
          }
        }
      }
    }
    """
    
    try:
        r = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": {"login": GITHUB_USER}},
            headers={"Authorization": f"bearer {token}"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if "errors" in data: return []
            return data["data"]["user"]["pullRequests"]["nodes"]
    except Exception as e:
        print(f"[GitHub] Exception: {e}")
    return []

# -----------------------------------------------------------------------------
# Apache Jira (Kafka)
# -----------------------------------------------------------------------------
def fetch_jira():
    print("[JIRA] Fetching...")
    url = "https://issues.apache.org/jira/rest/api/2/search"
    try:
        r = requests.get(url, params={"jql": JIRA_JQL, "maxResults": 20}, timeout=10)
        if r.status_code == 200:
            return r.json().get("issues", [])
    except Exception as e:
        print(f"[JIRA] Exception: {e}")
    return []

# -----------------------------------------------------------------------------
# Dev.to (Blogs)
# -----------------------------------------------------------------------------
def fetch_blogs():
    print("[Dev.to] Fetching...")
    url = f"https://dev.to/api/articles?username={DEVTO_USER}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200: return r.json()
    except Exception as e:
        print(f"[Dev.to] Exception: {e}")
    return []

# -----------------------------------------------------------------------------
# Linux Kernel (GitHub API for torvalds/linux)
# -----------------------------------------------------------------------------
def fetch_kernel_commits():
    print("[Kernel] Fetching Commits via GitHub (torvalds/linux)...")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[Kernel] No GITHUB_TOKEN found. Skipping.")
        return []

    commits = []
    query = f"repo:torvalds/linux author-email:{KERNEL_EMAIL}"
    url = "https://api.github.com/search/commits"
    
    try:
        r = requests.get(
            url,
            params={"q": query, "sort": "author-date", "order": "desc", "per_page": 100},
            headers={
                "Authorization": f"bearer {token}",
                "Accept": "application/vnd.github.cloak-preview" 
            },
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            for item in items:
                c = item.get("commit", {})
                author = c.get("author", {})
                message = c.get("message", "").split("\n")[0] # First line as title
                
                commits.append({
                    "title": message,
                    "url": item.get("html_url"),
                    "date": author.get("date"),
                    "subsystem": "linux"
                })
        else:
            print(f"[Kernel] Error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"[Kernel] Exception: {e}")
        
    return commits

def fetch_kernel_patches():
    print("[Kernel] Fetching Patches (Lore)...")
    patches = []
    base = "https://lore.kernel.org/all/"
    q = quote_plus(f"a:{KERNEL_EMAIL}")
    
    # Simple scrape for patches on lore
    for page in range(MAX_PAGES):
        url = f"{base}?q={q}&page={page}"
        html = safe_get(url)
        if not html: break
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        entries = soup.select("a.snippet-subject") or soup.select("a[href^='/r/']")
        if not entries: break
        
        for a in entries:
            href = a.get("href")
            if not href: continue
            title = a.get_text(strip=True)
            url2 = "https://lore.kernel.org" + href if href.startswith("/") else href
            
            patches.append({"title": title, "url": url2, "date": datetime.now().isoformat(), "state": "patch"})
        
        time.sleep(SLEEP_BETWEEN_REQUESTS)
    return patches

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    # 1. GitHub
    gh_data = fetch_github()
    gh_clean = []
    for item in gh_data:
        gh_clean.append({
            "type": "github",
            "title": item["title"],
            "url": item["url"],
            "repo": item["repository"]["nameWithOwner"],
            "state": item["state"],
            "date": item["mergedAt"] or item["createdAt"],
            "language": item["repository"]["primaryLanguage"]["name"] if item["repository"].get("primaryLanguage") else "Text"
        })
    json.dump(gh_clean, open(f"{DATA_DIR}/github.json", "w"), indent=2)

    # 2. Jira
    jira_data = fetch_jira()
    jira_clean = []
    for item in jira_data:
        fields = item.get("fields", {})
        jira_clean.append({
            "type": "jira",
            "key": item["key"],
            "title": fields.get("summary", "No Summary"),
            "url": f"https://issues.apache.org/jira/browse/{item['key']}",
            "status": fields.get("status", {}).get("name", "Unknown"),
            "date": fields.get("created")
        })
    json.dump(jira_clean, open(f"{DATA_DIR}/kafka_jira.json", "w"), indent=2)

    # 3. Blogs
    blog_data = fetch_blogs()
    blog_clean = []
    for item in blog_data:
        blog_clean.append({
            "type": "blog",
            "title": item["title"],
            "url": item["url"],
            "tags": item.get("tag_list", []),
            "date": item["published_at"],
            "desc": item.get("description")
        })
    json.dump(blog_clean, open(f"{DATA_DIR}/blogs.json", "w"), indent=2)

    # 4. Kernel (Commits & Patches)
    try:
        kcommits = fetch_kernel_commits()
        json.dump({"commits": kcommits}, open(f"{DATA_DIR}/linux_commits.json", "w"), indent=2)
        
        kpatches = fetch_kernel_patches()
        json.dump({"patches": kpatches}, open(f"{DATA_DIR}/linux_patches.json", "w"), indent=2)
    except Exception as e:
        print(f"[Kernel] Failed to fetch: {e}")
    
    print("Done fetching all contributions.")

if __name__ == "__main__":
    main()
