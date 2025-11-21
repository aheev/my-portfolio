#!/usr/bin/env python3
"""
Analyze contribution data and generate summary analytics.
Output: data/analytics.json

This version converts all dates into UNIX timestamps to avoid
offset-naive vs offset-aware datetime comparison errors.
"""

import os
import json
import datetime
from collections import Counter


DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "analytics.json")


# ---------------------------------------------------------
# Robust universal date parser → UTC UNIX timestamp
# ---------------------------------------------------------
def parse_timestamp(s):
    """
    Parse any incoming date format into a UNIX timestamp (UTC).
    Returns None if parsing fails.
    """
    if not s:
        return None

    s = s.strip()

    # Convert trailing Z → +00:00
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    # Try ISO8601 first
    try:
        dt = datetime.datetime.fromisoformat(s)
    except Exception:
        dt = None

    # Try common fallback formats
    if dt is None:
        fmts = [
            "%Y-%m-%d %H:%M:%S %z",   # 2024-01-12 10:15:41 -0400
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in fmts:
            try:
                dt = datetime.datetime.strptime(s, fmt)
                break
            except Exception:
                dt = None

    if dt is None:
        return None

    # Make timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    dt = dt.astimezone(datetime.timezone.utc)
    return int(dt.timestamp())  # UNIX timestamp


# ---------------------------------------------------------
# JSON loader
# ---------------------------------------------------------
def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


# ---------------------------------------------------------
# Main analytics
# ---------------------------------------------------------
def main():
    github = load_json(os.path.join(DATA_DIR, "github.json")) or {}
    kernel_commits = load_json(os.path.join(DATA_DIR, "linux_commits.json")) or {"commits": []}
    kernel_patches = load_json(os.path.join(DATA_DIR, "linux_patches.json")) or {"patches": []}

    github_items = github.get("items", [])
    commit_items = kernel_commits.get("commits", [])
    patch_items = kernel_patches.get("patches", [])

    timestamps = []

    # GitHub PRs
    for pr in github_items:
        ts = parse_timestamp(pr.get("mergedAt") or pr.get("updatedAt"))
        if ts:
            timestamps.append(ts)

    # Kernel commits
    for c in commit_items:
        ts = parse_timestamp(c.get("date"))
        if ts:
            timestamps.append(ts)

    # Kernel patches
    for p in patch_items:
        ts = parse_timestamp(p.get("date"))
        if ts:
            timestamps.append(ts)

    timestamps.sort()

    earliest = timestamps[0] if timestamps else None
    latest = timestamps[-1] if timestamps else None

    # Year buckets
    per_year = Counter()
    for ts in timestamps:
        year = datetime.datetime.utcfromtimestamp(ts).year
        per_year[year] += 1

    # Kernel subsystem usage
    subsystems = Counter()
    for c in commit_items:
        subsystems[c.get("subsystem", "unknown")] += 1

    # Patch status summary
    patch_status = Counter()
    for p in patch_items:
        patch_status[p.get("state", "unknown")] += 1

    # GitHub repo distribution
    gh_repos = Counter()
    for pr in github_items:
        gh_repos[pr.get("repository", "unknown")] += 1

    analytics = {
        "stats": {
            "total_events": len(timestamps),
            "github_prs": len(github_items),
            "kernel_commits": len(commit_items),
            "kernel_patches": len(patch_items),
        },
        "timeline": {
            "earliest_timestamp": earliest,
            "latest_timestamp": latest,
            "per_year": dict(sorted(per_year.items())),
        },
        "kernel": {
            "subsystems": dict(subsystems),
            "patch_status": dict(patch_status),
        },
        "github": {
            "repos": dict(gh_repos),
        },
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(analytics, f, indent=2)

    print(f"[OK] analytics written → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
