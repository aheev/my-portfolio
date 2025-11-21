#!/usr/bin/env python3
"""
Analyze contribution data and generate summary analytics.
Output: data/analytics.json
"""

import os
import json
import datetime
from collections import Counter, defaultdict

DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "analytics.json")


# -----------------------------
# Date parsing (robust, safe)
# -----------------------------
def parse_date(s):
    """
    Normalize any date string into a timezone-aware UTC datetime.
    Supports:
      - 2024-01-10T12:33:11Z
      - 2024-01-10T12:33:11+00:00
      - 2024-01-10 12:33:11
      - 2024-01-10
    Returns None on failure.
    """
    if not s:
        return None

    s = s.strip()

    # Convert "Z" to "+00:00"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    # Primary ISO attempt
    try:
        dt = datetime.datetime.fromisoformat(s)
    except Exception:
        dt = None

    # Fallback formats
    if dt is None:
        fallback_formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
        ]
        for fmt in fallback_formats:
            try:
                dt = datetime.datetime.strptime(s, fmt)
                break
            except Exception:
                dt = None

    if dt is None:
        return None

    # Make naive → UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    # Convert aware → UTC
    return dt.astimezone(datetime.timezone.utc)


# -----------------------------
# Load data helpers
# -----------------------------
def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


# -----------------------------
# Main analytics computation
# -----------------------------
def main():
    github = load_json(os.path.join(DATA_DIR, "github.json")) or {}
    kernel_commits = load_json(os.path.join(DATA_DIR, "linux_commits.json")) or {"commits": []}
    kernel_patches = load_json(os.path.join(DATA_DIR, "linux_patches.json")) or {"patches": []}

    # Extract lists
    github_items = github.get("items", [])
    kernel_commit_items = kernel_commits.get("commits", [])
    kernel_patch_items = kernel_patches.get("patches", [])

    # -----------------------------
    # Collect all dates (normalized)
    # -----------------------------
    all_dates = []

    # GitHub PRs
    for pr in github_items:
        dt = parse_date(pr.get("mergedAt") or pr.get("updatedAt"))
        if dt:
            all_dates.append(dt)

    # Kernel commits
    for c in kernel_commit_items:
        dt = parse_date(c.get("date"))
        if dt:
            all_dates.append(dt)

    # Kernel patches
    for p in kernel_patch_items:
        dt = parse_date(p.get("date"))
        if dt:
            all_dates.append(dt)

    # Earliest, latest
    earliest = min(all_dates).isoformat() if all_dates else None
    latest = max(all_dates).isoformat() if all_dates else None

    # -----------------------------
    # Yearly contribution counts
    # -----------------------------
    yearly = Counter()
    for dt in all_dates:
        yearly[dt.year] += 1

    # -----------------------------
    # Kernel subsystem frequencies
    # (from git.kernel.org paths)
    # -----------------------------
    subsystems = Counter()
    for c in kernel_commit_items:
        subsys = c.get("subsystem") or "unknown"
        subsystems[subsys] += 1

    # -----------------------------
    # Patch status distribution
    # -----------------------------
    patch_status = Counter()
    for p in kernel_patch_items:
        status = p.get("state") or "unknown"
        patch_status[status] += 1

    # -----------------------------
    # GitHub repo distribution
    # -----------------------------
    gh_repos = Counter()
    for pr in github_items:
        repo = pr.get("repository") or "unknown"
        gh_repos[repo] += 1

    # -----------------------------
    # Output structure
    # -----------------------------
    analytics = {
        "stats": {
            "total_events": len(all_dates),
            "github_prs": len(github_items),
            "kernel_commits": len(kernel_commit_items),
            "kernel_patches": len(kernel_patch_items),
        },
        "timeline": {
            "earliest": earliest,
            "latest": latest,
            "per_year": dict(sorted(yearly.items())),
        },
        "kernel": {
            "subsystems": dict(subsystems),
            "patch_status": dict(patch_status),
        },
        "github": {
            "repos": dict(gh_repos),
        },
    }

    # Save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(analytics, f, indent=2)

    print(f"analytics written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
