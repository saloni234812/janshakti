/**
 * JanaShakti (जनशक्ति) - Frontend Controller & Offline PWA Engine
 */

// State Management
const state = {
  rivers: [],
  selectedRiver: null,
  offlineQueue: [],
  activeTab: 'map',
  isOnline: navigator.onLine,
};

// Storage Key
const OFFLINE_STORAGE_KEY = 'janashakti_offline_queue_v1';

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
  initServiceWorker();
  initNetworkListeners();
  loadOfflineQueue();
  initTabs();
  initAudioGuide();
  initFormListeners();
  
  await loadRiversData();
  await loadMapSvg();
  await fetchDashboardMetrics();

  // Handle URL hash if any
  const hash = window.location.hash.replace('#', '');
  if (['map', 'survey', 'dashboard', 'plan'].includes(hash)) {
    switchTab(hash);
  }
});

/* ================= 1. SERVICE WORKER & NETWORKING ================= */
function initServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js')
      .then((reg) => console.log('[ServiceWorker] Registered with scope:', reg.scope))
      .catch((err) => console.warn('[ServiceWorker] Registration failed:', err));
  }
}

function initNetworkListeners() {
  window.addEventListener('online', () => {
    state.isOnline = true;
    updateNetworkUI();
    showToast('Internet connection restored. Ready to sync.');
    triggerSync();
  });

  window.addEventListener('offline', () => {
    state.isOnline = false;
    updateNetworkUI();
    showToast('Working offline. Submissions will be safely saved locally.');
  });

  updateNetworkUI();
}

function updateNetworkUI() {
  const dot = document.getElementById('networkPulseDot');
  const label = document.getElementById('networkStatusText');
  if (!dot || !label) return;

  if (state.isOnline) {
    dot.className = 'pulse-dot';
    label.textContent = 'Online';
  } else {
    dot.className = 'pulse-dot offline';
    label.textContent = 'Offline Mode';
  }
}

function loadOfflineQueue() {
  try {
    const raw = localStorage.getItem(OFFLINE_STORAGE_KEY);
    state.offlineQueue = raw ? JSON.parse(raw) : [];
  } catch (e) {
    state.offlineQueue = [];
  }
  updateSyncBadge();
}

function saveOfflineQueue() {
  try {
    localStorage.setItem(OFFLINE_STORAGE_KEY, JSON.stringify(state.offlineQueue));
  } catch (e) {
    console.error('Failed to save offline queue', e);
  }
  updateSyncBadge();
}

function updateSyncBadge() {
  const countEl = document.getElementById('pendingSyncCount');
  const btnSync = document.getElementById('btnSyncNow');
  if (countEl) countEl.textContent = state.offlineQueue.length;
  if (btnSync) {
    btnSync.style.display = state.offlineQueue.length > 0 && state.isOnline ? 'inline-flex' : 'none';
  }
}

async function triggerSync() {
  if (!state.isOnline || state.offlineQueue.length === 0) return;

  showToast(`Syncing ${state.offlineQueue.length} offline report(s)...`);
  try {
    const response = await fetch('/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: state.offlineQueue })
    });

    if (response.ok) {
      const result = await response.json();
      state.offlineQueue = [];
      saveOfflineQueue();
      showToast(`Sync complete! ${result.synced_count} reports processed.`);
      await fetchDashboardMetrics();
    } else {
      showToast('Sync server rejected payload. Retrying later.');
    }
  } catch (err) {
    console.warn('Sync failed:', err);
    showToast('Sync failed: Network error. Will retry.');
  }
}

/* ================= 2. TABS & NAVIGATION ================= */
function initTabs() {
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-tab');
      switchTab(target);
    });
  });
}

function switchTab(tabId) {
  state.activeTab = tabId;
  window.location.hash = tabId;

  document.querySelectorAll('.nav-tab').forEach((t) => {
    t.classList.toggle('active', t.getAttribute('data-tab') === tabId);
  });

  document.querySelectorAll('.tab-pane').forEach((pane) => {
    pane.classList.toggle('active', pane.id === `tab-${tabId}`);
  });

  if (tabId === 'dashboard') {
    fetchDashboardMetrics();
  }
}

/* ================= 3. RIVERS & INTERACTIVE SVG MAP ================= */
async function loadRiversData() {
  try {
    const res = await fetch('/static/content/rivers.json');
    const data = await res.json();
    state.rivers = data.rivers || [];
    populateRiverDropdowns();
  } catch (err) {
    console.error('Failed to load rivers.json', err);
  }
}

function populateRiverDropdowns() {
  const selectSurvey = document.getElementById('surveyRiverSelect');
  const selectPlan = document.getElementById('planRiverSelect');

  const optionsHtml = state.rivers.map((r) => 
    `<option value="${r.id}">${r.name} — ${r.reach_name} (${r.state})</option>`
  ).join('');

  if (selectSurvey) selectSurvey.innerHTML = `<option value="">-- Choose River Reach --</option>` + optionsHtml;
  if (selectPlan) selectPlan.innerHTML = optionsHtml;
}

async function loadMapSvg() {
  const container = document.getElementById('mapSvgHolder');
  if (!container) return;

  try {
    const res = await fetch('/static/map.svg');
    const svgText = await res.text();
    container.innerHTML = svgText;

    // Attach click listeners to stations inside SVG
    const stations = container.querySelectorAll('.river-station');
    stations.forEach((st) => {
      st.addEventListener('click', () => {
        const riverId = st.getAttribute('data-river-id');
        selectRiverById(riverId);
      });
    });

    // Default select first river
    if (state.rivers.length > 0) {
      selectRiverById('ganga-varanasi');
    }
  } catch (err) {
    console.error('Failed to embed map.svg', err);
  }
}

function selectRiverById(riverId) {
  const river = state.rivers.find((r) => r.id === riverId);
  if (!river) return;
  state.selectedRiver = river;

  // Highlight node in SVG
  document.querySelectorAll('.river-station').forEach((el) => {
    el.style.opacity = el.getAttribute('data-river-id') === riverId ? '1.0' : '0.6';
  });

  // Render Telemetry Card
  const card = document.getElementById('stationDetailsCard');
  if (!card) return;

  const statusClass = `badge-${river.status.toLowerCase().replace(' ', '-')}`;

  card.innerHTML = `
    <div class="card-title-bar">
      <div>
        <h2>${river.name}</h2>
        <span style="font-size: 0.85rem; color: var(--text-muted);">${river.reach_name} (${river.state})</span>
      </div>
      <span class="badge ${statusClass}">${river.status}</span>
    </div>

    <div style="margin-bottom: 0.75rem;">
      <div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:0.25rem;">
        <span>Health Index: <strong>${river.health_index} / 100</strong></span>
        <span>Length: ${river.length_km} km</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill" style="width: ${river.health_index}%; background: ${getHealthColor(river.health_index)};"></div>
      </div>
    </div>

    <div class="telemetry-grid">
      <div class="telemetry-box">
        <div class="telemetry-label">Dissolved O₂</div>
        <div class="telemetry-val" style="color: ${river.parameters.dissolved_oxygen_mg_l < 5 ? '#f87171' : '#34d399'};">
          ${river.parameters.dissolved_oxygen_mg_l} <span style="font-size:0.75rem;">mg/L</span>
        </div>
      </div>
      <div class="telemetry-box">
        <div class="telemetry-label">Biochem. Oxygen Demand (BOD)</div>
        <div class="telemetry-val" style="color: ${river.parameters.bod_mg_l > 3 ? '#f87171' : '#34d399'};">
          ${river.parameters.bod_mg_l} <span style="font-size:0.75rem;">mg/L</span>
        </div>
      </div>
      <div class="telemetry-box">
        <div class="telemetry-label">pH Level</div>
        <div class="telemetry-val">${river.parameters.ph}</div>
      </div>
      <div class="telemetry-box">
        <div class="telemetry-label">Turbidity</div>
        <div class="telemetry-val">${river.parameters.turbidity_ntu} <span style="font-size:0.75rem;">NTU</span></div>
      </div>
    </div>

    <div style="margin-top: 1rem; font-size: 0.82rem;">
      <strong style="color: #38bdf8;">Primary Pressures:</strong>
      <ul style="margin: 0.4rem 0 0.8rem 1.2rem; color: var(--text-muted);">
        ${river.primary_threats.map((t) => `<li>${t}</li>`).join('')}
      </ul>
      <strong style="color: #2dd4bf;">Active Stewardship:</strong>
      <p style="color: var(--text-muted); margin-top: 0.2rem;">${river.active_interventions.join(', ')}</p>
    </div>

    <div style="margin-top: 1.25rem; display: flex; gap: 0.75rem;">
      <button class="btn-primary" onclick="quickReportForRiver('${river.id}')" style="font-size:0.85rem; padding: 0.6rem;">
        📝 Report Issue Here
      </button>
      <button class="btn-primary" onclick="quickPlanForRiver('${river.id}')" style="font-size:0.85rem; padding: 0.6rem; background: var(--bg-secondary); border: 1px solid var(--border-subtle);">
        📋 View Plan
      </button>
    </div>
  `;
}

function getHealthColor(score) {
  if (score >= 75) return '#10b981';
  if (score >= 55) return '#38bdf8';
  if (score >= 35) return '#f59e0b';
  return '#ef4444';
}

window.quickReportForRiver = (riverId) => {
  switchTab('survey');
  const sel = document.getElementById('surveyRiverSelect');
  if (sel) sel.value = riverId;
};

window.quickPlanForRiver = (riverId) => {
  switchTab('plan');
  const sel = document.getElementById('planRiverSelect');
  if (sel) {
    sel.value = riverId;
    generateActionPlan();
  }
};

/* ================= 4. AUDIO GUIDE (M1.opus + TTS) ================= */
function initAudioGuide() {
  const btnAudio = document.getElementById('btnPlayAudioGuide');
  const audioEl = document.getElementById('moduleAudioPlayer');

  if (btnAudio) {
    btnAudio.addEventListener('click', () => {
      // First attempt to play static/audio/M1.opus
      if (audioEl) {
        audioEl.play().then(() => {
          showToast('Playing Module 1 audio prompt...');
        }).catch((err) => {
          console.log('Audio file playback fallback to Web Speech API', err);
          speakAudioPrompt();
        });
      } else {
        speakAudioPrompt();
      }
    });
  }
}

function speakAudioPrompt() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    const promptText = "नमस्ते। जनशक्ति नदी सर्वेक्षण मॉड्यूल 1 में आपका स्वागत है। कृपया नदी का जल रंग, गंध, झाग, और आस-पास के प्रदूषण स्रोतों का विवरण दर्ज करें। Welcome to JanaShakti river monitoring module 1. Please record water clarity, odor, and observed activities.";
    const utterance = new SpeechSynthesisUtterance(promptText);
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
    showToast('Spoken voice guidance started.');
  } else {
    showToast('Audio guidance not supported on this device.');
  }
}

/* ================= 5. FORM LISTENERS & REAL-TIME CLASSIFIER ================= */
let classifyDebounceTimer = null;

function initFormListeners() {
  const descInput = document.getElementById('surveyObservationText');
  const checkboxes = document.querySelectorAll('input[name="symptom"]');
  const form = document.getElementById('citizenSurveyForm');

  if (descInput) {
    descInput.addEventListener('input', scheduleClassificationPreview);
  }

  checkboxes.forEach((cb) => {
    cb.addEventListener('change', scheduleClassificationPreview);
  });

  if (form) {
    form.addEventListener('submit', handleSurveySubmit);
  }
}

function scheduleClassificationPreview() {
  clearTimeout(classifyDebounceTimer);
  classifyDebounceTimer = setTimeout(runAiClassificationPreview, 400);
}

async function runAiClassificationPreview() {
  const text = document.getElementById('surveyObservationText')?.value.trim() || '';
  const symptoms = Array.from(document.querySelectorAll('input[name="symptom"]:checked'))
    .map((c) => c.value);

  const clarity = document.getElementById('surveyClaritySelect')?.value || 'murky';
  const flow = document.getElementById('surveyFlowSelect')?.value || 'normal';
  const activity = document.getElementById('surveyActivitySelect')?.value || 'domestic_sewage';

  if (!text && symptoms.length === 0) return;

  const previewBox = document.getElementById('aiPredictionPreview');
  if (!previewBox) return;

  try {
    const res = await fetch('/api/classify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        symptoms: symptoms.join(';'),
        water_clarity: clarity,
        flow_rate: flow,
        surrounding_activity: activity,
      }),
    });

    if (res.ok) {
      const data = await res.json();
      renderAiPreview(data);
    }
  } catch (err) {
    // Offline heuristic preview if backend unreachable
    renderOfflineHeuristic(text, symptoms);
  }
}

function renderAiPreview(data) {
  const container = document.getElementById('aiPredictionPreview');
  if (!container) return;

  const sevBadge = `badge-${data.severity.toLowerCase()}`;
  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
      <span class="ai-badge">⚡ AI Classification Result</span>
      <span class="badge ${sevBadge}">${data.severity} Risk</span>
    </div>
    <div style="font-size: 1.1rem; font-weight: 700; color: #38bdf8; margin-bottom: 0.35rem;">
      ${data.predicted_category}
    </div>
    <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.75rem;">
      Model Confidence: <strong>${Math.round(data.confidence * 100)}%</strong>
    </div>
    <div style="font-size: 0.82rem; background: var(--bg-secondary); padding: 0.6rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
      <strong style="color: #2dd4bf;">Recommended Action:</strong>
      <div style="color: var(--text-main); margin-top: 0.2rem;">${data.recommended_action}</div>
    </div>
  `;
}

function renderOfflineHeuristic(text, symptoms) {
  const container = document.getElementById('aiPredictionPreview');
  if (!container) return;
  const symStr = (text + ' ' + symptoms.join(' ')).toLowerCase();

  let category = 'Domestic Sewage & Outfalls';
  let severity = 'Medium';

  if (symStr.includes('foam') || symStr.includes('chemical') || symStr.includes('dye') || symStr.includes('black')) {
    category = 'Industrial Effluents';
    severity = 'Critical';
  } else if (symStr.includes('plastic') || symStr.includes('garbage') || symStr.includes('bottle')) {
    category = 'Solid Waste & Plastic Dumping';
    severity = 'Medium';
  } else if (symStr.includes('sand') || symStr.includes('dredging') || symStr.includes('rubble')) {
    category = 'Illegal Sand Mining & Encroachment';
    severity = 'High';
  }

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
      <span class="ai-badge">Offline Local Rule</span>
      <span class="badge badge-polluted">${severity}</span>
    </div>
    <div style="font-size: 1.05rem; font-weight: 700; color: #38bdf8; margin-bottom: 0.25rem;">
      ${category}
    </div>
    <div style="font-size: 0.75rem; color: var(--text-dim);">Offline classification heuristic active.</div>
  `;
}

async function handleSurveySubmit(e) {
  e.preventDefault();

  const riverId = document.getElementById('surveyRiverSelect').value;
  const location = document.getElementById('surveyLocationName').value.trim();
  const text = document.getElementById('surveyObservationText').value.trim();
  const clarity = document.getElementById('surveyClaritySelect').value;
  const flow = document.getElementById('surveyFlowSelect').value;
  const activity = document.getElementById('surveyActivitySelect').value;
  const symptoms = Array.from(document.querySelectorAll('input[name="symptom"]:checked'))
    .map((c) => c.value);

  if (!riverId || !text) {
    showToast('Please select a river and enter observation details.');
    return;
  }

  const newReport = {
    id: 'REP-' + Date.now().toString(36).toUpperCase(),
    river_id: riverId,
    location: location || 'Field Observation Point',
    text,
    symptoms: symptoms.join(';'),
    water_clarity: clarity,
    flow_rate: flow,
    surrounding_activity: activity,
    created_at: new Date().toISOString(),
  };

  if (!state.isOnline) {
    // Save to offline queue
    state.offlineQueue.push(newReport);
    saveOfflineQueue();
    showToast('Report saved offline! Will auto-sync when online.');
    resetForm();
    return;
  }

  // Attempt direct online sync
  try {
    const res = await fetch('/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: [newReport] }),
    });

    if (res.ok) {
      showToast('Report submitted and classified successfully!');
      resetForm();
      fetchDashboardMetrics();
    } else {
      throw new Error('Server returned non-200');
    }
  } catch (err) {
    state.offlineQueue.push(newReport);
    saveOfflineQueue();
    showToast('Network issue: Report queued locally for sync.');
    resetForm();
  }
}

function resetForm() {
  const form = document.getElementById('citizenSurveyForm');
  if (form) form.reset();
  const previewBox = document.getElementById('aiPredictionPreview');
  if (previewBox) {
    previewBox.innerHTML = '<span style="font-size: 0.85rem; color: var(--text-dim);">Fill the form or mark symptoms above to see live AI classification.</span>';
  }
}

/* ================= 6. DASHBOARD ANALYTICS ================= */
async function fetchDashboardMetrics() {
  try {
    const res = await fetch('/api/dashboard');
    if (!res.ok) return;
    const data = await res.json();
    renderDashboard(data);
  } catch (err) {
    console.warn('Dashboard fetch offline', err);
  }
}

function renderDashboard(data) {
  // KPI counts
  const totalReportsEl = document.getElementById('kpiTotalReports');
  const criticalStretchesEl = document.getElementById('kpiCriticalStretches');
  const activeVolunteersEl = document.getElementById('kpiActiveVolunteers');
  const syncHealthEl = document.getElementById('kpiSyncHealth');

  if (totalReportsEl) totalReportsEl.textContent = data.total_reports || 0;
  if (criticalStretchesEl) criticalStretchesEl.textContent = data.critical_stretches || 0;
  if (activeVolunteersEl) activeVolunteersEl.textContent = data.community_champions || 3200;
  if (syncHealthEl) syncHealthEl.textContent = `${data.sync_rate_pct || 100}%`;

  // Categories Bars
  const catHolder = document.getElementById('dashboardCategoryBars');
  if (catHolder && data.categories_breakdown) {
    const total = Object.values(data.categories_breakdown).reduce((a, b) => a + b, 0) || 1;
    catHolder.innerHTML = Object.entries(data.categories_breakdown).map(([cat, count]) => {
      const pct = Math.round((count / total) * 100);
      return `
        <div class="bar-row">
          <div class="bar-header">
            <span>${cat}</span>
            <span style="font-weight: 700;">${count} (${pct}%)</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width: ${pct}%; background: #38bdf8;"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  // Severities Bars
  const sevHolder = document.getElementById('dashboardSeverityBars');
  if (sevHolder && data.severity_breakdown) {
    const sevColors = {
      Critical: '#ef4444',
      High: '#f97316',
      Medium: '#f59e0b',
      Low: '#10b981',
    };
    const total = Object.values(data.severity_breakdown).reduce((a, b) => a + b, 0) || 1;
    sevHolder.innerHTML = Object.entries(data.severity_breakdown).map(([sev, count]) => {
      const pct = Math.round((count / total) * 100);
      return `
        <div class="bar-row">
          <div class="bar-header">
            <span>${sev}</span>
            <span style="font-weight: 700;">${count}</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width: ${pct}%; background: ${sevColors[sev] || '#38bdf8'};"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  // Recent Stream
  const streamHolder = document.getElementById('dashboardRecentStream');
  if (streamHolder && data.recent_reports) {
    streamHolder.innerHTML = data.recent_reports.map((rep) => `
      <div style="background: var(--bg-secondary); border: 1px solid var(--border-subtle); padding: 0.75rem; border-radius: var(--radius-sm); margin-bottom: 0.6rem;">
        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.2rem;">
          <strong style="color: #38bdf8;">${rep.river_name || rep.river_id}</strong>
          <span style="color: var(--text-dim);">${rep.location}</span>
        </div>
        <p style="font-size: 0.82rem; color: var(--text-muted);">${rep.text}</p>
        <div style="margin-top: 0.4rem; display: flex; gap: 0.5rem; align-items: center;">
          <span class="badge badge-${(rep.severity || 'medium').toLowerCase()}">${rep.severity}</span>
          <span style="font-size: 0.72rem; color: var(--text-dim);">${rep.category}</span>
        </div>
      </div>
    `).join('');
  }
}

/* ================= 7. ACTION PLAN GENERATOR ================= */
window.generateActionPlan = async () => {
  const riverId = document.getElementById('planRiverSelect')?.value;
  const categoryOverride = document.getElementById('planCategorySelect')?.value;
  const resultBox = document.getElementById('planOutputResult');

  if (!riverId || !resultBox) return;

  resultBox.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">Generating multi-stakeholder river action plan...</div>';

  try {
    const res = await fetch('/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        river_id: riverId,
        category: categoryOverride || undefined,
      }),
    });

    if (res.ok) {
      const plan = await res.json();
      renderActionPlanResult(plan);
    } else {
      resultBox.innerHTML = '<div style="color: #f87171;">Failed to generate plan from server.</div>';
    }
  } catch (err) {
    resultBox.innerHTML = '<div style="color: #f87171;">Error contacting planner service.</div>';
  }
};

function renderActionPlanResult(plan) {
  const resultBox = document.getElementById('planOutputResult');
  if (!resultBox) return;

  resultBox.innerHTML = `
    <div style="border-bottom: 1px solid var(--border-subtle); padding-bottom: 1rem; margin-bottom: 1.25rem;">
      <div style="display: flex; justify-content: space-between; align-items: start;">
        <div>
          <h2 style="color: #38bdf8; font-size: 1.35rem;">${plan.plan_title}</h2>
          <span style="font-size: 0.85rem; color: var(--text-muted);">Reach: <strong>${plan.river_reach}</strong> (${plan.state})</span>
        </div>
        <span class="badge badge-${plan.urgency.toLowerCase()}">${plan.urgency} Urgency</span>
      </div>
      <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.5rem;">${plan.problem_summary}</p>
    </div>

    <!-- Co-occurrence Insight Banner -->
    <div style="background: rgba(6, 182, 212, 0.1); border-left: 3px solid var(--brand-cyan); padding: 0.75rem 1rem; border-radius: var(--radius-sm); margin-bottom: 1.5rem; font-size: 0.85rem;">
      <strong style="color: #38bdf8;">🧠 Co-occurrence Risk Signal:</strong>
      <div style="color: var(--text-main); margin-top: 0.2rem;">${plan.cooccurrence_insight}</div>
    </div>

    <!-- Timeline Steps -->
    <div style="margin-bottom: 1.5rem;">
      <h3 style="font-size: 1rem; margin-bottom: 1rem; color: #2dd4bf;">Phased Intervention Roadmap:</h3>
      
      <div class="timeline-step">
        <div class="timeline-title">Phase 1: Immediate Containment (0–48 Hours)</div>
        <div class="timeline-desc">${plan.phases.immediate.action}</div>
        <div style="font-size:0.75rem; color: var(--text-dim); margin-top:0.2rem;">Lead Stakeholder: <strong>${plan.phases.immediate.lead}</strong></div>
      </div>

      <div class="timeline-step">
        <div class="timeline-title">Phase 2: Community Remediation (30 Days)</div>
        <div class="timeline-desc">${plan.phases.mid_term.action}</div>
        <div style="font-size:0.75rem; color: var(--text-dim); margin-top:0.2rem;">Lead Stakeholder: <strong>${plan.phases.mid_term.lead}</strong></div>
      </div>

      <div class="timeline-step">
        <div class="timeline-title">Phase 3: Systemic &amp; Ecological Policy (1 Year)</div>
        <div class="timeline-desc">${plan.phases.long_term.action}</div>
        <div style="font-size:0.75rem; color: var(--text-dim); margin-top:0.2rem;">Lead Stakeholder: <strong>${plan.phases.long_term.lead}</strong></div>
      </div>
    </div>

    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; background: var(--bg-secondary); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
      <div>
        <span style="font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase;">Estimated Budget</span>
        <div style="font-size: 1.15rem; font-weight: 700; color: #34d399;">${plan.estimated_budget_inr}</div>
      </div>
      <div>
        <span style="font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase;">Expected Ecological Impact</span>
        <div style="font-size: 0.9rem; font-weight: 600; color: var(--text-main); margin-top: 0.2rem;">${plan.expected_impact}</div>
      </div>
    </div>
  `;
}

/* ================= TOAST UTILITY ================= */
function showToast(message) {
  let toast = document.getElementById('toastNotification');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toastNotification';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.display = 'block';

  setTimeout(() => {
    toast.style.display = 'none';
  }, 4000);
}
