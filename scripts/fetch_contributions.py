#!/usr/bin/env python3
import os, json, re, requests
from datetime import datetime

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

GITHUB_USER = "aheev"
KERNEL_NAME = "Ally Heev"   # No email displayed in public output

# ---------------------------
# GitHub PRs
# ---------------------------

def github_graphql(query, variables=None):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    headers = {"Authorization": f"bearer {token}"}
    r = requests.post("https://api.github.com/graphql",
        json={"query": query, "variables": variables}, headers=headers)
    if r.status_code != 200:
        return None
    return r.json()

GQ = """
query($login:String!){
  user(login:$login){
    pullRequests(first:50, orderBy:{field:CREATED_AT, direction:DESC}){
      nodes{
        title url merged mergedAt updatedAt
      }
    }
  }
}
"""

def fetch_github():
    res = github_graphql(GQ, {"login": GITHUB_USER})
    out = {"items": [], "mergedCount": 0, "openCount": 0}

    if not res:
        return out

    nodes = res["data"]["user"]["pullRequests"]["nodes"]
    for n in nodes:
        out["items"].append(n)
        if n["merged"]:
            out["mergedCount"] += 1
        else:
            out["openCount"] += 1
    return out

# ---------------------------
# Kafka JIRA
# ---------------------------

def fetch_kafka_jira():
    url = "https://issues.apache.org/jira/rest/api/2/search"
    jql = f"project=KAFKA AND reporter={GITHUB_USER}"
    r = requests.get(url, params={"jql": jql, "maxResults": 50})
    if r.status_code != 200:
        return {"items": [], "total": 0}

    data = r.json()
    return {"items": data.get("issues", []), "total": data.get("total", 0)}

# ---------------------------
# Linux Kernel (lore.kernel.org)
# ---------------------------

def fetch_linux_patches():
    url = f"https://lore.kernel.org/search/?q={KERNEL_NAME}&x=0&y=0"
    r = requests.get(url)
    out = {"items": [], "count": 0}
    if r.status_code != 200:
        return out

    matches = re.findall(r'<a class="snippet-subject" href="([^"]+)">([^<]+)</a>', r.text)
    for href, subj in matches[:25]:
        out["items"].append({
            "type": "Kernel patch",
            "title": subj.strip(),
            "link": "https://lore.kernel.org" + href,
            "date": datetime.utcnow().isoformat()
        })
    out["count"] = len(out["items"])
    return out

# ---------------------------
# git.kernel.org (search by name)
# ---------------------------

def fetch_gitkernel():
    # Atom search feed
    url = f"https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/atom/?q={KERNEL_NAME}"
    r = requests.get(url)
    out = {"items": [], "count": 0}

    if r.status_code != 200:
        return out

    entries = re.findall(r"<title>(.*?)</title>\s*<id>(.*?)</id>", r.text)
    for title, link in entries[1:25]:  # skip first repo title
        out["items"].append({
            "type": "git.kernel.org",
            "title": title,
            "link": link,
            "date": datetime.utcnow().isoformat()
        })

    out["count"] = len(out["items"])
    return out

# ---------------------------
# Write all JSON files
# ---------------------------

json.dump(fetch_github(), open(f"{DATA_DIR}/github.json", "w"), indent=2)
json.dump(fetch_kafka_jira(), open(f"{DATA_DIR}/kafka_jira.json", "w"), indent=2)
json.dump(fetch_linux_patches(), open(f"{DATA_DIR}/linux_patches.json", "w"), indent=2)
json.dump(fetch_gitkernel(), open(f"{DATA_DIR}/gitkernel.json", "w"), indent=2)
