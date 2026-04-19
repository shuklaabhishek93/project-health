/* Health Tracker Web UI - Main JavaScript */

// ========================================================================
// Globals
// ========================================================================
let currentDays = 7;
const charts = {};

// Chart.js default colours
const C = {
  primary:   'rgba(13,110,253,0.85)',
  primaryBg: 'rgba(13,110,253,0.15)',
  success:   'rgba(25,135,84,0.85)',
  successBg: 'rgba(25,135,84,0.15)',
  danger:    'rgba(220,53,69,0.85)',
  dangerBg:  'rgba(220,53,69,0.15)',
  warning:   'rgba(255,193,7,0.85)',
  warningBg: 'rgba(255,193,7,0.15)',
  info:      'rgba(13,202,240,0.85)',
  infoBg:    'rgba(13,202,240,0.15)',
  purple:    'rgba(111,66,193,0.85)',
  purpleBg:  'rgba(111,66,193,0.15)',
  grid:      'rgba(255,255,255,0.08)',
  text:      'rgba(255,255,255,0.7)',
};
const PIE_COLORS = [
  '#0d6efd','#198754','#dc3545','#ffc107','#0dcaf0',
  '#6f42c1','#d63384','#fd7e14','#20c997','#6610f2',
];

// ========================================================================
// Utilities
// ========================================================================
async function api(url, opts = {}) {
  if (opts.body && typeof opts.body === 'object') {
    opts.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(url, opts);
  return res.json();
}

function toast(msg) {
  const el = document.getElementById('toast');
  document.getElementById('toastMsg').textContent = msg;
  const t = bootstrap.Toast.getOrCreateInstance(el, { delay: 3000 });
  t.show();
}

function shortDate(iso) {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function fmt(n) {
  if (n >= 10000) return (n / 1000).toFixed(1) + 'k';
  if (n >= 1000) return n.toLocaleString();
  return String(n);
}

function chartOpts(title, yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: false },
      title: { display: false },
    },
    scales: {
      x: { grid: { color: C.grid }, ticks: { color: C.text, maxRotation: 45, font: { size: 10 } } },
      y: { grid: { color: C.grid }, ticks: { color: C.text, font: { size: 10 } },
           title: { display: !!yLabel, text: yLabel || '', color: C.text, font: { size: 10 } } },
    },
  };
}

// ========================================================================
// Profile
// ========================================================================
async function loadProfile() {
  const d = await api('/api/profile');
  const badge = document.getElementById('profileBadge');
  const status = document.getElementById('profileStatus');
  const info = document.getElementById('profileInfo');
  if (d.exists) {
    document.getElementById('pName').value = d.name;
    document.getElementById('pAge').value = d.age;
    document.getElementById('pWeight').value = d.weight_kg;
    document.getElementById('pHeight').value = d.height_cm;
    document.getElementById('pGender').value = d.gender;
    badge.textContent = `${d.name} | Age ${d.age} | BMI ${d.bmi}`;
    status.textContent = 'Configured';
    status.className = 'badge ms-auto badge-connected';
    info.textContent = `BMI: ${d.bmi} | Max Heart Rate: ${d.max_heart_rate} bpm`;
  } else {
    status.textContent = 'Not Set';
    status.className = 'badge ms-auto badge-disconnected';
    badge.textContent = '';
    info.textContent = 'Please fill in your profile to get started.';
  }
}

document.getElementById('profileForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = {
    name: document.getElementById('pName').value,
    age: document.getElementById('pAge').value,
    weight_kg: document.getElementById('pWeight').value,
    height_cm: document.getElementById('pHeight').value,
    gender: document.getElementById('pGender').value,
  };
  await api('/api/profile', { method: 'POST', body: data });
  toast('Profile saved!');
  loadProfile();
});

// ========================================================================
// Daemon Control
// ========================================================================
async function loadDaemonStatus() {
  const d = await api('/api/daemon/status');
  const badge = document.getElementById('daemonBadge');
  const btnStart = document.getElementById('btnStartDaemon');
  const btnStop = document.getElementById('btnStopDaemon');

  if (d.running) {
    badge.textContent = `Running (PID ${d.pid})`;
    badge.className = 'badge ms-auto badge-running';
    btnStart.disabled = true;
    btnStop.disabled = false;
  } else {
    badge.textContent = 'Stopped';
    badge.className = 'badge ms-auto badge-stopped';
    btnStart.disabled = false;
    btnStop.disabled = true;
  }

  // Populate config fields
  document.getElementById('cfgAppleEnabled').checked = d.apple_health_server.enabled;
  document.getElementById('cfgApplePort').value = d.apple_health_server.port;
  document.getElementById('appleServerUrl').textContent = d.apple_health_server.url;

  document.getElementById('cfgFolderEnabled').checked = d.folder_watcher.enabled;
  document.getElementById('cfgFolderDir').value = d.folder_watcher.watch_dir || '';
  document.getElementById('cfgFolderInterval').value = d.folder_watcher.poll_interval;

  document.getElementById('cfgStravaEnabled').checked = d.strava.enabled;
  const [h, m] = d.strava.sync_time.split(':');
  document.getElementById('cfgStravaHour').value = parseInt(h);
  document.getElementById('cfgStravaMin').value = parseInt(m);
  document.getElementById('cfgStravaHR').checked = d.strava.fetch_heart_rates;
  document.getElementById('stravaLastSync').textContent = d.strava.last_sync
    ? `Last sync: ${d.strava.last_sync}` : 'Never synced';
}

document.getElementById('btnStartDaemon').addEventListener('click', async () => {
  const btn = document.getElementById('btnStartDaemon');
  btn.innerHTML = '<span class="spinner-inline"></span> Starting...';
  btn.disabled = true;
  await api('/api/daemon/start', { method: 'POST' });
  toast('Daemon started!');
  setTimeout(loadDaemonStatus, 500);
  setTimeout(loadLog, 1500);
});

document.getElementById('btnStopDaemon').addEventListener('click', async () => {
  await api('/api/daemon/stop', { method: 'POST' });
  toast('Daemon stopped.');
  setTimeout(loadDaemonStatus, 500);
});

document.getElementById('btnRefreshDaemon').addEventListener('click', loadDaemonStatus);

// Save config
document.getElementById('btnSaveConfig').addEventListener('click', async () => {
  const data = {
    apple_health_server: {
      enabled: document.getElementById('cfgAppleEnabled').checked,
      port: parseInt(document.getElementById('cfgApplePort').value),
    },
    folder_watcher: {
      enabled: document.getElementById('cfgFolderEnabled').checked,
      watch_dir: document.getElementById('cfgFolderDir').value,
      poll_interval_seconds: parseInt(document.getElementById('cfgFolderInterval').value),
    },
    strava: {
      enabled: document.getElementById('cfgStravaEnabled').checked,
      sync_hour: parseInt(document.getElementById('cfgStravaHour').value),
      sync_minute: parseInt(document.getElementById('cfgStravaMin').value),
      fetch_heart_rates: document.getElementById('cfgStravaHR').checked,
    },
  };
  await api('/api/daemon/config', { method: 'POST', body: data });
  const msg = document.getElementById('configSaveMsg');
  msg.style.display = 'inline';
  toast('Configuration saved! Restart daemon to apply.');
  setTimeout(() => { msg.style.display = 'none'; }, 3000);
});

// ========================================================================
// iOS Shortcut Guide
// ========================================================================
document.getElementById('btnShowGuide').addEventListener('click', async () => {
  const body = document.getElementById('shortcutGuideBody');
  if (body.style.display === 'none') {
    body.style.display = 'block';
    const d = await api('/api/shortcut/instructions');
    document.getElementById('shortcutUrl').textContent = d.server_url;
    document.getElementById('shortcutInstructions').textContent = d.instructions;
    document.getElementById('curlCommand').textContent = d.curl_command;
    document.getElementById('btnShowGuide').innerHTML = '<i class="bi bi-eye-slash"></i> Hide Guide';
  } else {
    body.style.display = 'none';
    document.getElementById('btnShowGuide').innerHTML = '<i class="bi bi-book"></i> Show Setup Guide';
  }
});

// ========================================================================
// Strava
// ========================================================================
async function loadStravaStatus() {
  const d = await api('/api/strava/status');
  const badge = document.getElementById('stravaBadge');
  const info = document.getElementById('stravaInfo');
  const connectForm = document.getElementById('stravaConnectForm');
  if (d.connected) {
    badge.textContent = 'Connected';
    badge.className = 'badge ms-auto badge-connected';
    info.textContent = 'Strava is connected via OAuth2. The scheduler will automatically fetch your activities daily.';
    if (connectForm) connectForm.style.display = 'none';
  } else {
    badge.textContent = 'Not Connected';
    badge.className = 'badge ms-auto badge-disconnected';
    info.innerHTML = 'Enter your Strava API credentials below to connect.';
    if (connectForm) connectForm.style.display = 'block';
  }
}

async function connectStrava() {
  const clientId = document.getElementById('stravaClientId')?.value?.trim();
  const clientSecret = document.getElementById('stravaClientSecret')?.value?.trim();
  const result = document.getElementById('stravaConnectResult');
  if (!clientId || !clientSecret) {
    result.textContent = 'Please enter both Client ID and Client Secret.';
    result.className = 'small mt-2 text-danger';
    result.style.display = 'block';
    return;
  }
  const btn = document.getElementById('btnConnectStrava');
  btn.disabled = true;
  btn.textContent = 'Redirecting to Strava...';
  try {
    const d = await api('/api/strava/connect', { method: 'POST', body: { client_id: clientId, client_secret: clientSecret } });
    if (d.error) {
      result.textContent = 'Error: ' + d.error;
      result.className = 'small mt-2 text-danger';
      result.style.display = 'block';
      btn.disabled = false;
      btn.textContent = 'Connect Strava';
    } else {
      result.textContent = 'Opening Strava authorization page...';
      result.className = 'small mt-2 text-info';
      result.style.display = 'block';
      window.location.href = d.auth_url;
    }
  } catch (e) {
    result.textContent = 'Error: ' + e.message;
    result.className = 'small mt-2 text-danger';
    result.style.display = 'block';
    btn.disabled = false;
    btn.textContent = 'Connect Strava';
  }
}

// Populate the callback domain hint in the connect form
const domainEl = document.getElementById('stravaCallbackDomain');
if (domainEl) domainEl.textContent = window.location.hostname;

// Show success message if redirected back from Strava
if (new URLSearchParams(window.location.search).get('strava') === 'connected') {
  loadStravaStatus();
  showToast('Strava connected successfully!');
  window.history.replaceState({}, '', '/');
}

document.getElementById('btnSyncStrava').addEventListener('click', async () => {
  const btn = document.getElementById('btnSyncStrava');
  btn.innerHTML = '<span class="spinner-inline"></span> Syncing...';
  btn.disabled = true;
  const result = document.getElementById('stravaSyncResult');
  try {
    const d = await api('/api/strava/sync', { method: 'POST', body: { days: 7 } });
    if (d.error) {
      result.textContent = 'Error: ' + d.error;
      result.className = 'small mt-2 text-danger';
    } else {
      result.textContent = `Sync complete! ${d.days_updated} days updated, ${d.days_created} days created.`;
      result.className = 'small mt-2 text-success';
    }
  } catch (e) {
    result.textContent = 'Network error: ' + e.message;
    result.className = 'small mt-2 text-danger';
  }
  result.style.display = 'block';
  btn.innerHTML = '<i class="bi bi-cloud-download"></i> Sync Now (Last 7 Days)';
  btn.disabled = false;
  setTimeout(loadLog, 1000);
});

// ========================================================================
// Sync Log
// ========================================================================
async function loadLog() {
  const d = await api('/api/daemon/log?lines=50');
  const el = document.getElementById('syncLog');
  if (d.lines.length === 0) {
    el.textContent = 'No log entries yet. Start the daemon to begin logging.';
  } else {
    el.textContent = d.lines.join('\n');
    el.scrollTop = el.scrollHeight;
  }
}
document.getElementById('btnRefreshLog').addEventListener('click', loadLog);

// ========================================================================
// Analytics - Charts
// ========================================================================
function destroyChart(name) {
  if (charts[name]) { charts[name].destroy(); delete charts[name]; }
}

async function loadAnalytics() {
  const status = document.getElementById('analyticsStatus');
  status.innerHTML = '<span class="spinner-inline"></span> Loading...';

  const d = await api(`/api/analytics/range?days=${currentDays}`);
  if (d.error) { status.textContent = d.error; return; }

  const labels = d.days.map(r => shortDate(r.date));
  const dataDays = d.days.filter(r => r.has_data);

  status.textContent = `${d.totals.total_days} days with data out of ${currentDays}`;

  // KPIs
  document.getElementById('kpiScore').textContent = d.totals.avg_score || '--';
  document.getElementById('kpiSteps').textContent = d.totals.avg_steps ? fmt(d.totals.avg_steps) : '--';
  document.getElementById('kpiSleep').textContent = d.totals.avg_sleep || '--';
  document.getElementById('kpiCalories').textContent = d.totals.total_calories_burned ? fmt(Math.round(d.totals.total_calories_burned)) : '--';
  document.getElementById('kpiWorkouts').textContent = d.totals.total_workouts || '--';
  document.getElementById('kpiWorkoutMin').textContent = d.totals.total_workout_minutes || '--';

  // --- Health Score Chart ---
  destroyChart('score');
  charts.score = new Chart(document.getElementById('chartScore'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Health Score',
        data: d.days.map(r => r.has_data ? r.score : null),
        borderColor: C.primary,
        backgroundColor: C.primaryBg,
        fill: true, tension: 0.3, pointRadius: 3, spanGaps: true,
      }],
    },
    options: { ...chartOpts('Score', 'Score /100'),
      scales: { ...chartOpts('','Score').scales,
        y: { ...chartOpts('','').scales.y, min: 0, max: 100 }
      }
    },
  });

  // --- Calories Chart ---
  destroyChart('calories');
  charts.calories = new Chart(document.getElementById('chartCalories'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'BMR', data: d.days.map(r => r.has_data ? r.bmr : 0), backgroundColor: 'rgba(108,117,125,0.5)' },
        { label: 'Steps', data: d.days.map(r => r.has_data ? r.step_calories : 0), backgroundColor: C.infoBg.replace('0.15','0.6') },
        { label: 'Workout', data: d.days.map(r => r.has_data ? r.workout_calories : 0), backgroundColor: C.success },
      ],
    },
    options: { ...chartOpts('Calories', 'kcal'),
      plugins: { legend: { display: true, labels: { boxWidth: 12, font: { size: 10 }, color: C.text } } },
      scales: { ...chartOpts('','kcal').scales,
        x: { ...chartOpts('','').scales.x, stacked: true },
        y: { ...chartOpts('','kcal').scales.y, stacked: true },
      },
    },
  });

  // --- Heart Rate Chart ---
  destroyChart('hr');
  charts.hr = new Chart(document.getElementById('chartHR'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Avg HR', data: d.days.map(r => r.has_data && r.avg_heart_rate ? r.avg_heart_rate : null),
          borderColor: C.danger, backgroundColor: C.dangerBg, fill: true, tension: 0.3, pointRadius: 3, spanGaps: true },
        { label: 'Min HR', data: d.days.map(r => r.has_data && r.min_heart_rate ? r.min_heart_rate : null),
          borderColor: C.info, borderDash: [4,4], fill: false, tension: 0.3, pointRadius: 2, spanGaps: true },
        { label: 'Max HR', data: d.days.map(r => r.has_data && r.max_heart_rate ? r.max_heart_rate : null),
          borderColor: C.warning, borderDash: [4,4], fill: false, tension: 0.3, pointRadius: 2, spanGaps: true },
      ],
    },
    options: { ...chartOpts('Heart Rate', 'bpm'),
      plugins: { legend: { display: true, labels: { boxWidth: 12, font: { size: 10 }, color: C.text } } },
    },
  });

  // --- Steps & Workout Minutes Chart ---
  destroyChart('activity');
  charts.activity = new Chart(document.getElementById('chartActivity'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Steps', data: d.days.map(r => r.has_data ? r.steps : 0),
          backgroundColor: C.primary, yAxisID: 'y' },
        { label: 'Workout Min', data: d.days.map(r => r.has_data ? r.workout_minutes : 0),
          backgroundColor: C.success, yAxisID: 'y1' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { display: true, labels: { boxWidth: 12, font: { size: 10 }, color: C.text } } },
      scales: {
        x: { grid: { color: C.grid }, ticks: { color: C.text, maxRotation: 45, font: { size: 10 } } },
        y:  { position: 'left',  grid: { color: C.grid }, ticks: { color: C.text, font: { size: 10 } },
              title: { display: true, text: 'Steps', color: C.text, font: { size: 10 } } },
        y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: C.text, font: { size: 10 } },
              title: { display: true, text: 'Minutes', color: C.text, font: { size: 10 } } },
      },
    },
  });

  // --- Sleep Chart ---
  destroyChart('sleep');
  charts.sleep = new Chart(document.getElementById('chartSleep'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Sleep',
        data: d.days.map(r => r.has_data ? r.sleep_hours : 0),
        backgroundColor: d.days.map(r => {
          if (!r.has_data || r.sleep_hours === 0) return 'rgba(108,117,125,0.3)';
          if (r.sleep_hours >= 7 && r.sleep_hours <= 9) return C.success;
          if (r.sleep_hours >= 6) return C.warning;
          return C.danger;
        }),
      }],
    },
    options: { ...chartOpts('Sleep', 'Hours'),
      scales: { ...chartOpts('','Hours').scales, y: { ...chartOpts('','Hours').scales.y, min: 0, max: 12 } },
    },
  });

  // --- Workout Types Pie ---
  const typeCounts = {};
  dataDays.forEach(r => {
    (r.workout_types || []).forEach(t => {
      const label = t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      typeCounts[label] = (typeCounts[label] || 0) + 1;
    });
  });
  const typeLabels = Object.keys(typeCounts);
  const typeValues = Object.values(typeCounts);

  destroyChart('workoutTypes');
  charts.workoutTypes = new Chart(document.getElementById('chartWorkoutTypes'), {
    type: 'doughnut',
    data: {
      labels: typeLabels.length ? typeLabels : ['No workouts'],
      datasets: [{
        data: typeValues.length ? typeValues : [1],
        backgroundColor: typeLabels.length ? PIE_COLORS.slice(0, typeLabels.length) : ['rgba(108,117,125,0.3)'],
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: { position: 'right', labels: { boxWidth: 10, font: { size: 10 }, color: C.text } },
      },
    },
  });

  // --- Recommendations ---
  if (d.recommendations) {
    const rc = document.getElementById('recsCard');
    rc.style.display = 'block';
    const rb = document.getElementById('recsBody');
    const rec = d.recommendations;
    rb.innerHTML = `
      <div class="row g-3">
        <div class="col-md-3">
          <strong class="small">Weekly Exercise</strong>
          <div>${rec.exercise_minutes_per_week} min/week</div>
        </div>
        <div class="col-md-3">
          <strong class="small">Sleep Target</strong>
          <div>${rec.sleep_hours} hours</div>
        </div>
        <div class="col-md-3">
          <strong class="small">Recommended Workouts</strong>
          <div class="small">${rec.recommended_workouts.join(', ')}</div>
        </div>
      </div>
      <div class="mt-2">
        <strong class="small">Focus Areas</strong>
        <ul>${rec.focus_areas.map(a => `<li>${a}</li>`).join('')}</ul>
      </div>
      <div class="alert alert-warning small mt-2 mb-0 py-1">${rec.caution}</div>
    `;
  }
}

// Range buttons
document.querySelectorAll('#rangeBtns button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#rangeBtns button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentDays = parseInt(btn.dataset.days);
    loadAnalytics();
  });
});

document.getElementById('btnRefreshAnalytics').addEventListener('click', loadAnalytics);

// ========================================================================
// Daily Detail
// ========================================================================
document.getElementById('btnLoadDetail').addEventListener('click', async () => {
  const d = document.getElementById('detailDate').value;
  if (!d) return;
  const el = document.getElementById('dailySummaryText');
  el.textContent = 'Loading...';
  const res = await api(`/api/records/${d}/summary`);
  if (res.error) {
    el.textContent = `No data for ${d}. ${res.error}`;
  } else {
    el.textContent = res.summary_text;
  }
});

// ========================================================================
// Tab switch: auto-load analytics when Results tab is shown
// ========================================================================
document.getElementById('results-tab').addEventListener('shown.bs.tab', () => {
  loadAnalytics();
});

// ========================================================================
// Init
// ========================================================================
document.addEventListener('DOMContentLoaded', () => {
  loadProfile();
  loadDaemonStatus();
  loadStravaStatus();
  loadLog();
});
