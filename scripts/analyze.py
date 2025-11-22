#!/usr/bin/env python3
"""
scripts/analyze.py

Aggregate contributions from:
 - data/github.json          (PRs)
 - data/github_issues.json   (optional Issues)
 - data/kafka_jira.json      (Apache JIRA)
 - data/linux_commits.json   (git.kernel.org / commits)
 - data/linux_patches.json   (lore.kernel.org / patches)
 - data/gitkernel.json       (compatibility)

Produces:
 - data/analytics.json

Notes:
 - All stored timestamps are normalized to UTC ISO (YYYY-MM-DDTHH:MM:SSZ)
 - Frontend should convert to local timezone for display (toLocaleString)
"""
from __future__ import annotations
import os
import json
import re
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

DATA_DIR = "data"
OUT_FILE = os.path.join(DATA_DIR, "analytics.json")

# ------------------ Helpers ------------------
def load_json(fn: str) -> Dict[str, Any]:
    path = os.path.join(DATA_DIR, fn)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _parse_iso_like(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = str(s).strip()
    # Convert trailing Z -> +00:00 for fromisoformat
    if s.endswith("Z"):
        s2 = s[:-1] + "+00:00"
        s = s2
    # Try fromisoformat
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    # Try common patterns
    fmts = [
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    # Try to extract an ISO timestamp inside text
    m = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+\-]\d{2}:?\d{2}))', s)
    if m:
        return _parse_iso_like(m.group(1))
    m2 = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?: [+\-]\d{4})?)', s)
    if m2:
        return _parse_iso_like(m2.group(1))
    return None

def parse_timestamp_to_iso(s: Any) -> Optional[str]:
    """Return UTC ISO string (Z) or None"""
    if not s:
        return None
    # If already a datetime object
    if isinstance(s, datetime):
        dt = s
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    s = str(s).strip()
    # Handle "3 weeks ago" / "yesterday" etc using approximate conversion:
    rel_iso = parse_relative_to_iso(s)
    if rel_iso:
        return rel_iso
    dt = _parse_iso_like(s)
    if dt:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None

def parse_relative_to_iso(text: str) -> Optional[str]:
    """
    Convert relative expressions like '3 weeks ago' to UTC ISO timestamp.
    Uses M3 month = 30.44 days for months.
    """
    if not text:
        return None
    t = str(text).strip().lower()
    now = datetime.now(timezone.utc)

    # direct keywords
    if t in ("just now", "moments ago", "a few seconds ago"):
        return now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if t in ("yesterday", "a day ago"):
        return (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if t in ("an hour ago", "an hr ago"):
        return (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    m = re.match(r'(\d+)\s+(second|seconds|minute|minutes|min|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago', t)
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
            dt = now - timedelta(days=n * 30.44)
        elif unit.startswith("year"):
            dt = now - timedelta(days=n * 365.25)
        else:
            return None
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # e.g. "about 3 months ago"
    m2 = re.match(r'(about|over|around)?\s*(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago', t)
    if m2:
        n = int(m2.group(2))
        unit = m2.group(3)
        return parse_relative_to_iso(f"{n} {unit} ago")
    return None

def month_key_from_iso(iso: str) -> Optional[str]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"{dt.year:04d}-{dt.month:02d}"
    except Exception:
        return None

def ensure_list(x):
    if x is None:
        return []
    return x

# ------------------ Load sources ------------------
gh = load_json("github.json")                 # expected: { items: [...], mergedCount: N }
gh_issues = load_json("github_issues.json")   # optional
jira = load_json("kafka_jira.json")           # expected: { items: [...], total: N }
# commits = load_json("linux_commits.json")     # expected: { commits: [...] } or { items: [...] }
# patches = load_json("linux_patches.json")     # expected: { patches: [...] } or { items: [...] }
# gitk = load_json("gitkernel.json")            # expected compatibility { items: [...], count: N }

# Normalize shapes
gh_items = gh.get("items") or gh.get("prs") or []
gh_items = ensure_list(gh_items)
gh_issue_items = gh_issues.get("items") if isinstance(gh_issues.get("items"), list) else gh_issues.get("issues") or []
gh_issue_items = ensure_list(gh_issue_items)
jira_items = ensure_list(jira.get("items") or jira.get("issues") or [])
commit_items = ensure_list(commits.get("commits") or commits.get("items") or [])
patch_items = ensure_list(patches.get("patches") or patches.get("items") or [])
gitk_items = ensure_list(gitk.get("items") or [])

# ------------------ Aggregate events ------------------
# We will build month counters for the past N months based on the available data (last 24 months by default)
per_source_month = {
    "github_prs": Counter(),
    "github_issues": Counter(),
    "jira": Counter(),
#     "kernel_commits": Counter(),
#     "kernel_patches": Counter(),
#     "gitkernel": Counter()
}

# repo counters and kernel subsystems
repo_counter = Counter()
# subsystem_counter = Counter()

# recent contributions aggregated across sources (collect ISO date + metadata)
recent = []

def add_recent(source: str, title: str, url: str, iso_date: Optional[str], extra: dict = None):
    extra = extra or {}
    recent.append({"source": source, "title": title, "url": url, "date": iso_date, **extra})

# -- GitHub PRs --
for pr in gh_items:
    # GraphQL field names: mergedAt, createdAt; REST: merged_at, created_at
    iso = None
    iso = iso or parse_timestamp_to_iso(pr.get("mergedAt") or pr.get("merged_at"))
    iso = iso or parse_timestamp_to_iso(pr.get("closedAt") or pr.get("closed_at"))
    iso = iso or parse_timestamp_to_iso(pr.get("createdAt") or pr.get("created_at"))
    # repo extraction
    repo = None
    repo = repo or pr.get("repository") or pr.get("repositoryName")
    if isinstance(repo, dict):
        # GraphQL may return repository { nameWithOwner }
        repo = repo.get("nameWithOwner") or repo.get("full_name") or repo.get("name")
    if not repo:
        # parse from URL
        url = pr.get("url") or pr.get("html_url") or ""
        m = re.match(r"https?://github\.com/([^/]+/[^/]+)/", str(url))
        if m:
            repo = m.group(1)
    if repo:
        repo_counter[repo] += 1
    # month bucketing
    month = month_key_from_iso(iso) if iso else None
    if month:
        per_source_month["github_prs"][month] += 1
    # recent
    add_recent("GitHub PR", pr.get("title") or pr.get("body") or "", pr.get("url") or pr.get("html_url") or pr.get("htmlUrl") or "", iso, {"repo": repo})

# -- GitHub Issues (optional) --
for issue in gh_issue_items:
    iso = None
    iso = iso or parse_timestamp_to_iso(issue.get("closedAt") or issue.get("closed_at"))
    iso = iso or parse_timestamp_to_iso(issue.get("updatedAt") or issue.get("updated_at"))
    iso = iso or parse_timestamp_to_iso(issue.get("createdAt") or issue.get("created_at"))
    month = month_key_from_iso(iso) if iso else None
    if month:
        per_source_month["github_issues"][month] += 1
    add_recent("GitHub Issue", issue.get("title") or "", issue.get("html_url") or issue.get("url") or "", iso, {"issue_key": issue.get("number")})

# -- Apache JIRA (Kafka) --
for it in jira_items:
    # Jira items often have fields.created, fields.updated, fields.resolutiondate
    f = it.get("fields", {}) if isinstance(it, dict) else {}
    iso = None
    iso = iso or parse_timestamp_to_iso(f.get("resolutiondate"))
    iso = iso or parse_timestamp_to_iso(f.get("updated"))
    iso = iso or parse_timestamp_to_iso(f.get("created"))
    month = month_key_from_iso(iso) if iso else None
    if month:
        per_source_month["jira"][month] += 1
    key = (it.get("key") or it.get("id") or "")
    title = (f.get("summary") if isinstance(f, dict) else "") or it.get("fields", {}).get("summary", "") or ""
    url = it.get("self") or (f"https://issues.apache.org/jira/browse/{key}" if key else "")
    add_recent("JIRA", f"{key}: {title}".strip(), url, iso, {"jira_key": key})

# -- Kernel commits (linux_commits.json & gitkernel compatibility) --
# commit entries may have 'date' or 'commit_date' or other forms
# for c in commit_items + gitk_items:
#     iso = None
#     iso = iso or parse_timestamp_to_iso(c.get("date") or c.get("commit_date") or c.get("author_date") or c.get("committer_date"))
#     # many kernel entries used relative strings; parse_timestamp_to_iso handles that
#     month = month_key_from_iso(iso) if iso else None
#     if month:
#         per_source_month["kernel_commits"][month] += 1
#     sub = c.get("subsystem") or c.get("subsys") or "unknown"
#     subsystem_counter[sub] += 1
#     title = c.get("title") or c.get("subject") or ""
#     url = c.get("url") or c.get("link") or ""
#     add_recent("Kernel commit", title, url, iso, {"subsystem": sub})

# -- Kernel patches (lore) --
# for p in patch_items:
#     iso = None
#     iso = iso or parse_timestamp_to_iso(p.get("date") or p.get("posted") or p.get("created"))
#     month = month_key_from_iso(iso) if iso else None
#     if month:
#         per_source_month["kernel_patches"][month] += 1
#     title = p.get("title") or p.get("subject") or ""
#     url = p.get("url") or p.get("link") or ""
#     state = p.get("state") or p.get("status") or ""
#     add_recent("Kernel patch", title, url, iso, {"state": state})

# ------------------ Build month axis (last 24 months ending at latest event) ------------------
# collect all months seen
all_months = set()
for cnt in per_source_month.values():
    all_months.update(cnt.keys())
# If none, build last 24 months anchored to now
if not all_months:
    now = datetime.now(timezone.utc)
    mon_list = []
    for i in range(24):
        y = now.year - ((now.month - i - 1) // 12)
        m = ((now.month - i - 1) % 12) + 1
        mon_list.append(f"{y:04d}-{m:02d}")
    mon_list = list(reversed(mon_list))
else:
    latest_mon = max(all_months)
    ly, lm = map(int, latest_mon.split("-"))
    # generate 24 months ending at latest_mon
    mon_list = []
    dt = datetime(ly, lm, 1)
    for _ in range(24):
        mon_list.append(f"{dt.year:04d}-{dt.month:02d}")
        if dt.month == 12:
            dt = datetime(dt.year + 1, 1, 1)
        else:
            dt = datetime(dt.year, dt.month + 1, 1)
    # ensure we cover latest_mon at end
    if mon_list[-1] != latest_mon:
        # shift window so latest_mon is last
        # recompute ending at latest_mon
        ly, lm = map(int, latest_mon.split("-"))
        mon_list = []
        dt = datetime(ly, lm, 1)
        for i in range(24):
            # prepending months backwards then reverse
            pass
        # simpler fallback: sort all months and pick last 24
        sorted_months = sorted(all_months)
        if len(sorted_months) <= 24:
            mon_list = sorted_months
        else:
            mon_list = sorted_months[-24:]

# align arrays for each source
timeline = {
    "months": mon_list,
    "github_prs": [per_source_month["github_prs"].get(m, 0) for m in mon_list],
    "github_issues": [per_source_month["github_issues"].get(m, 0) for m in mon_list],
    "jira": [per_source_month["jira"].get(m, 0) for m in mon_list],
#     "kernel_commits": [per_source_month["kernel_commits"].get(m, 0) for m in mon_list],
#     "kernel_patches": [per_source_month["kernel_patches"].get(m, 0) for m in mon_list],
#     "gitkernel": [per_source_month["gitkernel"].get(m, 0) for m in mon_list]
}

# ------------------ Top repos (from GitHub PRs) ------------------
top_repos = [{"name": k, "prs": v} for k, v in repo_counter.most_common(12)]

# ------------------ Recent contributions (sorted) ------------------
# filter only those with a date if possible, then sort by date desc
def iso_to_ts(iso: Optional[str]) -> int:
    if not iso:
        return 0
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return 0

recent_sorted = sorted(recent, key=lambda x: iso_to_ts(x.get("date")), reverse=True)
recent_trimmed = recent_sorted[:60]

# ------------------ Totals ------------------
totals = {
    "github_prs": len(gh_items),
    "github_issues": len(gh_issue_items),
    "jira_total": jira.get("total") or len(jira_items),
#     "kernel_commits": len(commit_items) + len(gitk_items),
#     "kernel_patches": len(patch_items)
}

# ------------------ Output ------------------
out = {
    "timeline": timeline,
    "totals": totals,
    "top_repos": top_repos,
#     "kernel_subsystems": dict(subsystem_counter),
    "recent": recent_trimmed
}

# Ensure output directory exists
os.makedirs(DATA_DIR, exist_ok=True)
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print("[analyze] wrote", OUT_FILE)
