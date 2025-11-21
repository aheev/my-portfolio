// assets/charts.js
function renderCharts(analytics){
  try {
    const tl = analytics.timeline;
    const months = tl.months || [];
    const github = tl.github || [];
    const jira = tl.jira || [];
    const kernel = tl.kernel || [];
    const gitkernel = tl.gitkernel || [];

    // timeline line chart
    const tctx = document.getElementById('timelineChart').getContext('2d');
    if(window.timelineChart) window.timelineChart.destroy();
    window.timelineChart = new Chart(tctx, {
      type:'line',
      data:{
        labels: months,
        datasets:[
          {label:'GitHub PRs', data: github, borderColor:'#3b82f6', tension:0.2, fill:false},
          {label:'Kafka JIRA', data: jira, borderColor:'#10b981', tension:0.2, fill:false},
          {label:'Kernel (lore)', data: kernel, borderColor:'#f97316', tension:0.2, fill:false},
          {label:'git.kernel.org', data: gitkernel, borderColor:'#a78bfa', tension:0.2, fill:false},
        ]
      },
      options:{responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'top'}}}
    });

    // subsystems doughnut
    const subs = analytics.subsystems || {};
    const sctx = document.getElementById('subsystemChart').getContext('2d');
    if(window.subsystemChart) window.subsystemChart.destroy();
    window.subsystemChart = new Chart(sctx, {
      type:'doughnut',
      data:{ labels:Object.keys(subs), datasets:[{data:Object.values(subs)}] },
      options:{responsive:true, maintainAspectRatio:false}
    });

    // repos bar
    const repos = analytics.repos || [];
    const rctx = document.getElementById('reposChart').getContext('2d');
    if(window.reposChart) window.reposChart.destroy();
    window.reposChart = new Chart(rctx, {
      type:'bar',
      data:{ labels: repos.map(r=>r.name), datasets:[{label:'PRs', data: repos.map(r=>r.prs)}] },
      options:{responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}}
    });
  } catch(e){
    console.warn("charts error", e);
  }
}
