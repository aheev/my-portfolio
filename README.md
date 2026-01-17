# System Monitor Portfolio

A live, auto-updating "System Monitor" dashboard visualizing my open-source engineering work across the Linux Kernel, Apache Kafka, LadybugDB, and more.

[**Live Dashboard**](https://aheev.github.io/my-portfolio/)

## 🖥️ Interface
The UI is designed to look like a low-level system monitor tool, featuring:
- **Real-time Ops Frequency**: Line chart tracking daily contribution throughput.
- **Language Distro**: Doughnut chart showing programming language distribution.
- **System Logs**: A unified, grep-able feed of all activities (Commits, PRs, JIRA tickets, Blogs).
- **Installed Modules**: A grouped view of active repositories and projects.

## 📡 Telemetry Sources
Data is aggregated weekly (or on push) via Python scripts from multiple remote endpoints:
1.  **GitHub**: Pull Requests & repository metadata (GraphQL & REST).
2.  **Linux Kernel**:
    - Commits upstreamed to `torvalds/linux` (fetched via GitHub API).
    - Patches submitted to LKML (fetched via `lore.kernel.org`).
3.  **Apache JIRA**: Tracks tickets and issues for Apache Kafka.
4.  **Dev.to**: Technical blog posts.

## 🛠️ Architecture
- **Frontend**: Vanilla HTML5, CSS3 (Grid/Flexbox), and JavaScript (ES6+).
    - No frameworks, just raw DOM manipulation.
    - **Chart.js** for data visualization.
- **Backend / ETL**: Python 3.11 scripts (`fetch_contributions.py`, `analyze.py`).
- **CI/CD**: GitHub Actions workflow.

## 🚀 Setup & Usage

### Prerequisites
- Python 3.11+
- GitHub Token (PAT) with `read:user` and `repo` scopes.

### Local Development
1.  **Clone the repo**:
    ```bash
    git clone https://github.com/aheev/my-portfolio.git
    cd my-portfolio
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    # Or manually: pip install requests PyGithub beautifulsoup4 lxml
    ```

3.  **Fetch Data**:
    ```bash
    export GITHUB_TOKEN="your_token_here"
    export KERNEL_EMAIL="your_email@example.com"
    
    python3 scripts/fetch_contributions.py
    python3 scripts/analyze.py
    ```

4.  **Run Dev Server**:
    ```bash
    python3 -m http.server
    ```
    Open `http://localhost:8000` to view the dashboard.

## 🔄 Automation
The project uses **GitHub Actions** to keep the dashboard alive:
- **Trigger**: Runs on every `push` to `main` and weekly via `cron`.
- **Process**: Fetches fresh data, generates `analytics.json`, and deploys the static site.
- **Deployment**: Content is pushed directly to the `gh-pages` branch. The `main` branch remains clean of data artifacts.

## 📄 License
MIT
