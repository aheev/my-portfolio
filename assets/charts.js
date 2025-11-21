// assets/charts.js
// Reads data/analytics.json and draws three charts: timeline, subsystems, repos

window.initCharts = function(analytics){
  if (!analytics) return;
  try {
    drawTimeline(analytics.timeline);
    drawSubsystems(analytics.subsystems);
    drawRepos(analytics.repos);
  } catch(e){ console.warn("initCharts error", e); }
};

function drawTimeline(tl){
  const ctx = document.getElementById('timelineChart').getContext('2d');
  const labels = tl.months || [];
  const datasets = [
    { label: 'GitHub PRs', data: tl.github || [], tension:0.2, borderWidth:2 },
    { label: 'Kafka JIRA', data: tl.jira || [], tension:0.2, borderWidth:2 },
    { label: 'Kernel (lore)', data: tl.kernel || [], tension:0.2, borderWidth:2 },
    { label: 'git.kernel.org', data: tl.gitkernel || [], tension:0.2, borderWidth:2 }
  ];
  if (window.timelineChart) window.timelineChart.destroy();
  window.timelineChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'top'}} }
  });
}

function drawSubsystems(subsys){
  const ctx = document.getElementById('subsystemChart').getContext('2d');
  const labels = Object.keys(subsys || {});
  const data = Object.values(subsys || {});
  if (window.subsystemChart) window.subsystemChart.destroy();
  window.subsystemChart = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets:[{ data, backgroundColor: generatePalette(labels.length) }] },
    options: { responsive:true, maintainAspectRatio:false }
  });
}

function drawRepos(repos){
  const ctx = document.getElementById('reposChart').getContext('2d');
  const labels = (repos || []).map(r=>r.name);
  const data = (repos || []).map(r=>r.prs || 0);// assets/charts.js
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

  if (window.reposChart) window.reposChart.destroy();
  window.reposChart = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets:[{ label:'PRs', data, backgroundColor: generatePalette(labels.length) }] },
    options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{x:{ticks:{maxRotation:45,minRotation:0}}} }
  });
}

// simple palette
function generatePalette(n){
  const base = ['#4dc9f6','#f67019','#f53794','#537bc4','#acc236','#166a8f','#00a950','#58595b','#8549ba'];
  const out = [];
  for(let i=0;i<n;i++) out.push(base[i % base.length]);
  return out;
}
