// assets/charts.js
// expects analytics.json shape { totals, timeline:{months, github, jira, kernel, gitkernel}, subsystems, repos }

window.renderCharts = async function(analytics){
  try {
    const tl = analytics.timeline;
    const months = tl.months || [];
    const github_prs = tl.github_prs || [];
    const jira = tl.jira || [];
//     const kernel = tl.kernel || [];
//     const gitkernel = tl.gitkernel || [];

    // timeline line chart
    const tctx = document.getElementById('timelineChart').getContext('2d');
    if(window.timelineChart && typeof window.timelineChart.destroy === 'function') window.timelineChart.destroy();
    window.timelineChart = new Chart(tctx, {
      type:'line',
      data:{
        labels: months,
        datasets:[
          {label:'GitHub PRs', data: github_prs, borderColor:'#2563eb', backgroundColor:'rgba(37,99,235,0.06)', tension:0.3, pointRadius:2},
          {label:'Kafka JIRA', data: jira, borderColor:'#059669', backgroundColor:'rgba(5,150,105,0.04)', tension:0.3, pointRadius:2},
        //   {label:'Kernel (lore)', data: kernel, borderColor:'#f97316', backgroundColor:'rgba(249,115,22,0.04)', tension:0.3, pointRadius:2},
        //   {label:'git.kernel.org', data: gitkernel, borderColor:'#a855f7', backgroundColor:'rgba(168,85,247,0.04)', tension:0.3, pointRadius:2},
        ]
      },
      options:{
        responsive:true,
        maintainAspectRatio:false,
        animation:{duration:700,easing:'easeOutQuad'},
        plugins:{legend:{position:'top',labels:{usePointStyle:true,padding:12}}},
        scales:{x:{grid:{display:false}}, y:{beginAtZero:true,grid:{color:'rgba(255,255,255,0.03)'}}}
      }
    });

    // subsystems doughnut
//     const subs = analytics.subsystems || {};
//     const sctx = document.getElementById('subsystemChart').getContext('2d');
//     if(window.subsystemChart) window.subsystemChart.destroy();
//     window.subsystemChart = new Chart(sctx, {
//       type:'doughnut',
//       data:{ labels:Object.keys(subs), datasets:[{data:Object.values(subs), backgroundColor:generatePalette(Object.keys(subs).length)}] },
//       options:{responsive:true, maintainAspectRatio:false, animation:{duration:700}}
//     });

    // repos bar
    const top_repos = analytics.top_repos || [];
    const rctx = document.getElementById('reposChart').getContext('2d');
    if(window.reposChart && typeof window.reposChart.destroy === 'function') window.reposChart.destroy();
    window.reposChart = new Chart(rctx, {
      type:'bar',
      data:{ labels: top_repos.map(r=>r.name), datasets:[{label:'PRs', data: top_repos.map(r=>r.prs), backgroundColor:generatePalette(top_repos.length)}] },
      options:{responsive:true, maintainAspectRatio:false, animation:{duration:700}, plugins:{legend:{display:false}}, scales:{x:{ticks:{maxRotation:30,minRotation:0}}} }
    });

    // small accessibility: return a resolved promise after a small delay so UI can animate in
    return new Promise(resolve => setTimeout(resolve, 240));
  } catch(e){
    console.warn("charts error", e);
    return Promise.resolve();
  }
};

function generatePalette(n){
  const base = ['#2563eb','#fb7185','#f97316','#10b981','#a78bfa','#f59e0b','#06b6d4','#ef4444','#7c3aed'];
  const out = [];
  for(let i=0;i<n;i++) out.push(base[i % base.length]);
  return out;
}
