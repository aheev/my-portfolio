#!/usr/bin/env python3
import os
import json
from datetime import datetime, timedelta
from collections import Counter

DATA_DIR = "data"

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        try:
            return json.load(open(path, "r"))
        except:
            return []
    return []

def iso_day(d):
    if not d: return "1970-01-01"
    return d.split("T")[0]

def main():
    feed = []
    languages = Counter()
    dates = Counter()

    # 1. GitHub
    gh = load_json("github.json")
    for item in gh:
        feed.append({
            "source": "github",
            "icon": "git-merge",
            "title": item["title"],
            "url": item["url"],
            "date": item["date"],
            "subtitle": item.get("repo", "GitHub"),
            "meta": item.get("state", "").lower()
        })
        # Track Language
        if item.get("language"):
            languages[item["language"]] += 1
        # Track Date
        dates[iso_day(item["date"])] += 1

    # 2. Jira
    jira = load_json("kafka_jira.json")
    for item in jira:
        feed.append({
            "source": "jira",
            "icon": "ticket",
            "title": f"{item['key']}: {item['title']}",
            "url": item["url"],
            "date": item["date"],
            "subtitle": "Apache Kafka",
            "meta": item.get("status", "").lower()
        })
        dates[iso_day(item["date"])] += 1

    # 3. Blogs
    blogs = load_json("blogs.json")
    for item in blogs:
        feed.append({
            "source": "blog",
            "icon": "book-open",
            "title": item["title"],
            "url": item["url"],
            "date": item["date"],
            "subtitle": "Dev.to",
            "meta": "article"
        })
        dates[iso_day(item["date"])] += 1

    # 4. Kernel
    kcommits = load_json("linux_commits.json")
    if isinstance(kcommits, dict): kcommits = kcommits.get("commits", [])
    for item in kcommits:
        feed.append({
            "source": "kernel",
            "icon": "cpu",
            "title": item["title"],
            "url": item["url"],
            "date": item["date"],
            "subtitle": "Linux Kernel",
            "meta": "commit"
        })
        dates[iso_day(item["date"])] += 1
        languages["C"] += 1

    kpatches = load_json("linux_patches.json")
    if isinstance(kpatches, dict): kpatches = kpatches.get("patches", [])
    for item in kpatches:
        feed.append({
            "source": "kernel-patch",
            "icon": "mail",
            "title": item["title"],
            "url": item["url"],
            "date": item["date"],
            "subtitle": "LKML",
            "meta": item.get("state", "patch")
        })
        dates[iso_day(item["date"])] += 1

    # Sort Feed
    feed.sort(key=lambda x: x["date"] or "", reverse=True)

    # Throughput Chart Data (Last 30 days)
    chart_days = []
    chart_vals = []
    today = datetime.now()
    for i in range(29, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        chart_days.append(d)
        chart_vals.append(dates[d])

    # Output
    output = {
        "updated": datetime.now().isoformat(),
        "stats": {
            "github": len(gh),
            "jira": len(jira),
            "blogs": len(blogs),
            "kernel": len(kcommits) + len(kpatches)
        },
        "languages": dict(languages.most_common(5)),
        "chart": {
            "labels": chart_days,
            "data": chart_vals
        },
        "feed": feed
    }

    json.dump(output, open(os.path.join(DATA_DIR, "analytics.json"), "w"), indent=2)
    print(f"Generated analytics.json with {len(feed)} items.")

if __name__ == "__main__":
    main()
