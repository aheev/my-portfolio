// assets/charts.js
// Expects data/analytics.json with the following shape:
// { totals:{...}, timeline: { months: [...], github: [...], jira: [...], kernel: [...], gitkernel: [...] }, subsystems: {name:count, ...}, repos: [{name, prs, stars}, ...] }

function initCharts(analytics) {
  try {
    drawTimeline(analytics.timeline);
    drawSubsystems(analytics.subsystems);
    drawRepos(analytics.repos);
  } catch (e) {
    console.warn("chart error", e);
  }
}

function drawTimeline(tl){
  const ctx = document.getElementById('timelineChart').getContext('2d');
  const labels = tl.months;
  const datasets = [
    { label: 'GitHub PRs', data: tl.github, fill:false },
    { label: 'Kafka JIRA', data: tl.jira, fill:false },
    { label: 'Kernel (lore)', data: tl.kernel, fill:false },
    { label: 'git.kernel.org', data: tl.gitkernel, fill:false }
  ];
  new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'top'}} }
  });
}

function drawSubsystems(subsys){
  const ctx = document.getElementById('subsystemChart').getContext('2d');
  const labels = Object.keys(subsys);
  const data = Object.values(subsys);
  new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets:[{ data }] },
    options: { responsive:true, maintainAspectRatio:false }
  });
}

function drawRepos(repos){
  const ctx = document.getElementById('reposChart').getContext('2d');
  const labels = repos.map(r=>r.name);
  const data = repos.map(r=>r.prs);
  new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets:[{ label:'PRs', data }] },
    options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{x:{ticks:{maxRotation:45,minRotation:0}}} }
  });
}
