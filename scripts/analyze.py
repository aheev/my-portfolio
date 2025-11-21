#!/usr/bin/env python3
"""
analyze.py
Reads data/*.json produced by fetch_contributions.py and writes data/analytics.json
"""
import os, json, re
from datetime import datetime
from collections import Counter, defaultdict

DATA_DIR = "data"
OUT_PATH = os.path.join(DATA_DIR, "analytics.json")

def load(fn):
    try:
        with open(os.path.join(DATA_DIR, fn), "r") as f:
            return json.load(f)
    except Exception:
        return None

gh = load("github.json") or {}
jira = load("kafka_jira.json") or {}
linux = load("linux_patches.json") or {}
gitk = load("gitkernel.json") or {}

# totals
totals = {
    "github_prs": len(gh.get("items", [])),
    "github_merged": gh.get("mergedCount", 0),
    "jira_total": jira.get("total", 0),
    "linux_patches": linux.get("count", 0),
    "gitkernel_commits": gitk.get("count", 0)
}

# timeline: months array (YYYY-MM) last 24 months
def month_key(dt):
    return dt.strftime("%Y-%m")

def parse_date(s):
    if not s: return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ","%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z","+00:00"))
    except:
        return None

# collect event dates
events = {"github": [], "jira": [], "kernel": [], "gitkernel": []}
for i in gh.get("items", []):
    d = parse_date(i.get("mergedAt") or i.get("updatedAt"))
    if d: events["github"].append(d)
for i in jira.get("items", []):
    d = parse_date(i.get("fields",{}).get("updated"))
    if d: events["jira"].append(d)
for i in linux.get("items", []):
    d = parse_date(i.get("date"))
    if d: events["kernel"].append(d)
for i in gitk.get("items", []):
    d = parse_date(i.get("date"))
    if d: events["gitkernel"].append(d)

# months range: derive from events or last 18 months
all_dates = [d for arr in events.values() for d in arr]
if all_dates:
    latest = max(all_dates)
else:
    latest = datetime.utcnow()
months = []
cur = datetime(latest.year, latest.month, 1)
import calendar
for i in range(0, 18):
    months.append(month_key(cur))
    # go back one month
    if cur.month == 1:
        cur = datetime(cur.year-1, 12, 1)
    else:
        cur = datetime(cur.year, cur.month-1, 1)
months = list(reversed(months))

def counts_for(arr):
    c = Counter(month_key(d) for d in arr)
    return [c.get(m,0) for m in months]

timeline = {
    "months": months,
    "github": counts_for(events["github"]),
    "jira": counts_for(events["jira"]),
    "kernel": counts_for(events["kernel"]),
    "gitkernel": counts_for(events["gitkernel"])
}

# subsystems: crude heuristic using keywords from titles
subsys_keywords = ["net","fs","mm","block","drivers","usb","crypto","bpf","sched","ipc","arch","sound","gpu","scsi"]
subsys = Counter()
for i in (linux.get("items",[]) + gitk.get("items",[])):
    title = (i.get("title") or i.get("subject") or "").lower()
    matched = False
    for kw in subsys_keywords:
        if " "+kw in " "+title:
            subsys[kw] += 1
            matched = True
    if not matched:
        subsys["other"] += 1

# repos: derive from GitHub PR URLs
repos = {}
import re
for pr in gh.get("items", []):
    url = pr.get("url","")
    m = re.match(r"https?://github.com/([^/]+/[^/]+)/pull/", url)
    if m:
        name = m.group(1)
        r = repos.get(name, {"name": name, "prs": 0, "stars": None})
        r["prs"] += 1
        repos[name] = r

# Optionally fetch repo stars when GITHUB_TOKEN available
import requests, os
token = os.environ.get("GITHUB_TOKEN")
if token and repos:
    headers = {"Authorization": f"token {token}"}
    for name in list(repos.keys())[:30]:
        try:
            r = requests.get(f"https://api.github.com/repos/{name}", headers=headers, timeout=10)
            if r.status_code==200:
                repos[name]["stars"] = r.json().get("stargazers_count",0)
        except Exception:
            continue

repos_list = sorted(repos.values(), key=lambda x: (x.get("prs",0)), reverse=True)[:12]

out = {
    "totals": totals,
    "timeline": timeline,
    "subsystems": dict(subsys),
    "repos": repos_list
}

with open(OUT_PATH, "w") as f:
    json.dump(out, f, indent=2)

print("analytics written to", OUT_PATH)
