#!/usr/bin/env python3
"""
scripts/analyze.py

Produce data/analytics.json for charts and UI.
"""

import os, json, re
from datetime import datetime, timezone
from collections import Counter, defaultdict

DATA_DIR = "data"
OUT = os.path.join(DATA_DIR, "analytics.json")

def load(fn):
    try:
        with open(os.path.join(DATA_DIR, fn), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def parse_date_to_month(s):
    if not s: return None
    s = str(s).strip()
    # unify Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # try iso
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        # try common formats
        fmts = ["%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
        dt = None
        for fmt in fmts:
            try:
                dt = datetime.strptime(s, fmt)
                break
            except Exception:
                dt = None
        if dt is None:
            return None
    # ensure tz-aware in UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m")

# load sources
gh = load("github.json")
jira = load("kafka_jira.json")
commits = load("linux_commits.json")
patches = load("linux_patches.json")

# collect events by month
months_counter = Counter()
source_months = {"github": Counter(), "jira": Counter(), "kernel": Counter(), "gitkernel": Counter()}

# github PRs
gh_items = gh.get("items", [])
for pr in gh_items:
    m = parse_date_to_month(pr.get("mergedAt") or pr.get("updatedAt"))
    if m:
        source_months["github"][m] += 1
        months_counter[m] += 1

# kafka jira
for it in jira.get("items", []):
    m = parse_date_to_month(it.get("fields", {}).get("updated"))
    if m:
        source_months["jira"][m] += 1
        months_counter[m] += 1

# kernel commits
for c in commits.get("commits", []):
    m = parse_date_to_month(c.get("date"))
    if m:
        source_months["kernel"][m] += 1
        months_counter[m] += 1

# lore/gitkernel patches (treat as gitkernel)
for p in patches.get("patches", []):
    m = parse_date_to_month(p.get("date"))
    if m:
        source_months["gitkernel"][m] += 1
        months_counter[m] += 1

# build months list (last 24 months anchored to latest)
all_months = sorted(months_counter.keys())
if not all_months:
    # fallback to last 24 months
    now = datetime.utcnow()
    mon_list = []
    for i in range(24):
        y = now.year - ( (now.month - i -1) // 12 )
        m = ((now.month - i -1) % 12) +1
        mon_list.append(f"{y:04d}-{m:02d}")
    mon_list = list(reversed(mon_list))
else:
    # take last 24 months ending at latest month
    latest = max(all_months)
    year, month = map(int, latest.split("-"))
    mon_list = []
    dt = datetime(year, month, 1)
    for i in range(24):
        mon = (dt.year, dt.month)
        mon_list.append(f"{mon[0]:04d}-{mon[1]:02d}")
        # advance month forward:
        if dt.month == 12:
            dt = datetime(dt.year+1, 1, 1)
        else:
            dt = datetime(dt.year, dt.month+1, 1)
    # ensure we end at latest; if not, fallback to months from counters
    mon_list = mon_list[-24:]

# produce arrays aligned to mon_list
timeline = {
    "months": mon_list,
    "github": [source_months["github"].get(m,0) for m in mon_list],
    "jira": [source_months["jira"].get(m,0) for m in mon_list],
    "kernel": [source_months["kernel"].get(m,0) for m in mon_list],
    "gitkernel": [source_months["gitkernel"].get(m,0) for m in mon_list],
}

# kernel subsystems
subsys_counter = Counter()
for c in commits.get("commits", []):
    ss = c.get("subsystem") or "other"
    subsys_counter[ss] += 1

# top repos from GitHub items
repo_counter = Counter()
for pr in gh_items:
    # repository field may be nested earlier; try common keys
    repo = pr.get("repository") or pr.get("repositoryName") or None
    if not repo:
        # try url parse
        url = pr.get("url","")
        m = re.match(r"https?://github.com/([^/]+/[^/]+)/", url)
        if m:
            repo = m.group(1)
    if repo:
        repo_counter[repo] += 1

top_repos = [{"name": k, "prs": v} for k,v in repo_counter.most_common(12)]

# totals
totals = {
    "github_prs": len(gh_items),
    "github_merged": gh.get("mergedCount", 0),
    "jira_total": jira.get("total", 0),
    "kernel_commits": len(commits.get("commits", [])),
    "kernel_patches": len(patches.get("patches", [])),
}

out = {
    "totals": totals,
    "timeline": timeline,
    "subsystems": dict(subsys_counter),
    "repos": top_repos
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print("[analyze] analytics written to", OUT)
