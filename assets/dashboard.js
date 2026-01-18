const app = {
    data: null,

    async init() {
        this.updateUptime();
        setInterval(() => this.updateUptime(), 1000);
        
        try {
            const r = await fetch('data/analytics.json');
            if (!r.ok) throw new Error("Connection Refused");
            this.data = await r.json();
            this.render();
        } catch (e) {
            console.error(e);
            document.getElementById('log-feed').innerHTML = `<div style="padding:20px; color:#ff7b72;">ERROR: Failed to mount /data/analytics.json<br>System offline or initializing.</div>`;
        }

        // Search listener
        document.getElementById('log-filter').addEventListener('input', (e) => {
            this.renderFeed(e.target.value);
        });

        // Nav listener
        document.querySelectorAll('.nav-item').forEach(el => {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                el.classList.add('active');
                this.handleNav(el.dataset.tab);
            });
        });
    },

    updateUptime() {
        const start = new Date("2020-01-01").getTime(); // Career start roughly?
        const now = Date.now();
        const diff = now - start;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hrs = new Date().getHours();
        const mins = new Date().getMinutes();
        document.getElementById('uptime').innerText = `${days}d ${hrs}h ${mins}m`;
    },

    render() {
        if (!this.data) return;

        // Stats
        const s = this.data.stats;
        animateValue("stat-github", s.github);
        animateValue("stat-kernel", s.kernel);
        animateValue("stat-jira", s.jira);
        animateValue("stat-blojs", s.blogs);

        // Feed
        this.renderFeed("");
        
        // Charts
        this.renderCharts();
    },

    renderCharts() {
        if (!this.data.chart || !this.data.languages) return;

        // Common Chart Defaults
        Chart.defaults.color = '#8b949e';
        Chart.defaults.borderColor = '#30363d';

        // 1. Throughput Chart (Line)
        const ctx1 = document.getElementById('throughputChart');
        if (ctx1) {
            new Chart(ctx1, {
                type: 'line',
                data: {
                    labels: this.data.chart.labels,
                    datasets: [{
                        label: 'Operations',
                        data: this.data.chart.data,
                        borderWidth: 2,
                        borderColor: '#238636',
                        backgroundColor: 'rgba(35, 134, 54, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        hitRadius: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: { 
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `${context.parsed.y} contributions`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: { 
                            display: true,
                            grid: { display: false },
                            ticks: { 
                                maxTicksLimit: 6,
                                color: '#8b949e',
                                font: { size: 10 }
                            }
                        },
                        y: { 
                            beginAtZero: true, 
                            grid: { color: '#161b22' },
                            ticks: { stepSize: 1 } 
                        }
                    }
                }
            });
        }

        // 2. Language Chart (Doughnut)
        const ctx2 = document.getElementById('languageChart');
        if (ctx2) {
            const labels = Object.keys(this.data.languages);
            const data = Object.values(this.data.languages);
            
            new Chart(ctx2, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        backgroundColor: ['#58a6ff', '#d29922', '#ff7b72', '#238636', '#a371f7'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { 
                        legend: { position: 'right', labels: { boxWidth: 10 } }
                    },
                    layout: { padding: 0 }
                }
            });
        }
    },

    renderFeed(query) {
        const container = document.getElementById('log-feed');
        container.innerHTML = "";
        
        const q = query.toLowerCase();
        
        const items = this.data.feed.filter(item => {
            return item.title.toLowerCase().includes(q) || 
                   item.subtitle.toLowerCase().includes(q) || 
                   item.source.toLowerCase().includes(q);
        });

        if (items.length === 0) {
            container.innerHTML = `<div style="padding:20px; text-align:center; color:#8b949e;">-- No processes found --</div>`;
            return;
        }

        items.forEach(item => {
            const row = document.createElement('a');
            row.className = 'log-row';
            row.href = item.url || '#';
            row.target = "_blank";

            // Source Badge & Label
            let tagClass = "tag-github";
            let sourceLabel = item.subtitle; // Default to subtitle (repo name) for GitHub

            if(item.source.includes("kernel")) {
                tagClass = "tag-kernel";
                sourceLabel = "LINUX";
            } else if(item.source === "jira") {
                tagClass = "tag-jira";
                sourceLabel = "KAFKA";
            } else if(item.source === "blog") {
                tagClass = "tag-blog";
                sourceLabel = "DEV.TO";
            }

            row.innerHTML = `
                <div class="log-time">${item.date || "N/A"}</div>
                <div class="log-source-cell"><span class="log-source ${tagClass}">${sourceLabel}</span></div>
                <div class="log-msg">
                    <span style="color:#c9d1d9">${item.title}</span>
                </div>
                <div class="log-status">${item.meta ? item.meta.toUpperCase() : "OK"}</div>
            `;
            container.appendChild(row);
        });
    },

    handleNav(tab) {
        const dashboardView = document.getElementById('dashboard-view');
        const main = document.querySelector('.main-content');
        
        // Reset View
        const existingExtra = document.getElementById('extra-view');
        if(existingExtra) existingExtra.remove();
        
        if (tab === 'dashboard') {
            dashboardView.style.display = 'flex';
        } else {
            dashboardView.style.display = 'none';
        }

        // Scroll Top
        main.scrollTop = 0;

        if (tab === 'projects') {
             const view = document.createElement('div');
             view.id = 'extra-view';
             view.className = 'panel';
             
             const repos = this.getUniqueRepos();
             const groups = {};
             repos.forEach(r => {
                 const k = r.org || 'Other';
                 if (!groups[k]) groups[k] = [];
                 groups[k].push(r);
             });
             
             let content = '<div class="panel-header"><h3>INSTALLED_MODULES</h3></div><div class="panel-body" style="padding:20px;">';
             
             Object.keys(groups).sort().forEach(org => {
                 content += `<h4 style="color:#8b949e; border-bottom:1px solid #30363d; padding-bottom:5px; margin: 10px 0 10px 0; font-size:12px; letter-spacing:1px; text-transform:uppercase;">${org}</h4>`;
                 content += `<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(250px, 1fr)); gap:15px; margin-bottom:20px;">`;
                 groups[org].forEach(r => {
                    content += `
                        <a href="${r.url}" target="_blank" class="stat-card" style="text-decoration:none; display:block; transition: transform 0.1s;">
                            <h4 style="margin:0 0 10px 0; color:#58a6ff; font-size:14px;">${r.name}</h4>
                            <div style="font-size:12px; color:#8b949e">Repository</div>
                        </a>`;
                 });
                 content += `</div>`;
             });
             content += '</div>';

             view.innerHTML = content;
             main.appendChild(view);
        } else if (tab === 'about') {
            const view = document.createElement('div');
            view.id = 'extra-view';
            view.className = 'panel';
            view.innerHTML = `<div class="panel-header"><h3>/etc/motd</h3></div>
            <div class="panel-body" style="padding:20px; line-height:1.6; max-width:800px;">
                <p>Systems Engineer contributing to <strong>Apache Kafka</strong>, <strong>Apache Iceberg</strong>, <strong>LanceDB</strong>, <strong>LadybugDB</strong>, and the <strong>Linux Kernel</strong>.</p>
            </div>`;
            main.appendChild(view);
        }
    },

    getUniqueRepos() {
        if (!this.data) return [];
        const repos = new Map();
        
        this.data.feed.forEach(i => {
            if (i.source === 'github' && i.subtitle !== 'GitHub') {
                if (!repos.has(i.subtitle)) {
                    let url = `https://github.com/${i.subtitle}`;
                    let org = i.subtitle.split('/')[0];
                    repos.set(i.subtitle, { name: i.subtitle, url: url, org: org });
                }
            }
            if (i.source === 'kernel') {
                repos.set('linux.git', { name: 'linux.git', url: 'https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/', org: 'Linux Kernel' });
            }
            if (i.source === 'jira') {
                repos.set('Apache Kafka', { name: 'Apache Kafka', url: 'https://kafka.apache.org/', org: 'Apache Software Foundation' });
            }
        });
        
        return Array.from(repos.values());
    }
};

function animateValue(id, end) {
    if (end === undefined) return;
    const obj = document.getElementById(id);
    let start = 0;
    const duration = 1000;
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

// Boot
app.init();
