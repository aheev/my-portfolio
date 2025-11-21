# aheev/my-portfolio

Automatically updated open-source contribution portfolio.

Live site: https://aheev.github.io/my-portfolio/

## Features
- GitHub Pull Requests
- Apache Kafka JIRA
- Linux kernel patches (lore.kernel.org)
- git.kernel.org commit search
- Nightly automatic deployment to GitHub Pages

## GitHub Pages
This repository publishes to the `gh-pages` branch using GitHub Actions.

## Updating data
The workflow runs:
- nightly (02:00 UTC)
- on push to main
- manually on demand

All JSON output goes into `data/`.
