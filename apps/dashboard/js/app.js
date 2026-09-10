'use strict';
/* ============================================================
   VEHDiag — Web diagnostic application (SPA, zero dependencies)
   ============================================================ */
(function () {
  const API = '/api/v1';
  const state = { user: null, ws: null, wsConnected: false, liveSub: null, liveValues: [], notif: [] };

  /* ---------------- icons ---------------- */
  const I = {
    gauge: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 14l4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/></svg>',
    car: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 11l1.5-4.5A2 2 0 0 1 8.4 5h7.2a2 2 0 0 1 1.9 1.5L19 11"/><rect x="3" y="11" width="18" height="7" rx="1.5"/><path d="M6 18v2m12-2v2M7 14.5h.01M17 14.5h.01"/></svg>',
    scan: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>',
    activity: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
    alert: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4m0 4h.01"/></svg>',
    cpu: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v2m6-2v2M9 20v2m6-2v2M2 9h2m-2 6h2m16-6h2m-2 6h2"/></svg>',
    fingerprint: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 11a4 4 0 0 0-4 4c0 1.5-.5 3-1 4.5M12 11a4 4 0 0 1 4 4c0 2 .5 4 1.5 6M12 7a8 8 0 0 0-8 8c0 3 .8 5.5 2 7.5M12 7a8 8 0 0 1 8 8c0 1.6-.2 3-.6 4.4M12 3a12 12 0 0 0-12 12c0 1.3.1 2.6.4 3.8"/></svg>',
    snowflake: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M4.9 4.9l14.2 14.2M19.1 4.9 4.9 19.1M12 2l-2.5 2.5M12 2l2.5 2.5M12 22l-2.5-2.5M12 22l2.5-2.5"/></svg>',
    file: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M16 13H8m8 4H8m2-8H8"/></svg>',
    bt: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 7 10 10-5 5V2l5 5L7 17"/></svg>',
    term: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 9-5 5v-3l5-4v2Z"/><path d="m16 9 5 5v-3l-5-4v2Z"/><path d="M8 9h8"/><path d="m4 14 3 3 2-2m7 0 3 3 1-3"/></svg>',
    user: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    settings: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/></svg>',
    card: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></svg>',
    shield: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/></svg>',
    bolt: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z"/></svg>',
    help: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3m0 3h.01"/></svg>',
    bell: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>',
    menu: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>',
    download: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>',
    plus: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
    back: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5m7-7-7 7 7 7"/></svg>',
    check: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
    x: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>',
    battery: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2"/></svg>',
    zap: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z"/></svg>',
  };

  /* ---------------- api ---------------- */
  function token() { return localStorage.getItem('vehdiag_token'); }
  async function api(method, path, body) {
    const r = await fetch(API + path, {
      method,
      headers: { 'Content-Type': 'application/json', ...(token() ? { Authorization: 'Bearer ' + token() } : {}) },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const text = await r.text();
    let d;
    try { d = JSON.parse(text); } catch (e) { d = text; }
    if (!r.ok) {
      const err = new Error((d && d.error && d.error.message) || 'Request failed');
      err.status = r.status;
      throw err;
    }
    return d.data;
  }
  const get = (p) => api('GET', p);
  const post = (p, b) => api('POST', p, b);
  const patch = (p, b) => api('PATCH', p, b);
  const del = (p) => api('DELETE', p);

  function esc(s) { return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
  function fmtDate(s) { return s ? new Date(s).toLocaleString() : '—'; }
  function sevBadge(s) {
    const cls = { critical: 'badge-err', high: 'badge-err', medium: 'badge-warn', low: 'badge-info', info: 'badge-info' }[s] || 'badge';
    return `<span class="badge ${cls}">${esc(s)}</span>`;
  }
  function statusDot(s) {
    const c = { completed: 'dot-ok', created: 'dot-idle', scanning: 'dot-warn', failed: 'dot-err' }[s] || 'dot-idle';
    return `<span class="status-dot ${c}"></span>`;
  }

  /* ---------------- shell ---------------- */
  function shell(title, body, opts = {}) {
    const role = state.user ? state.user.role : 'USER';
    const admin = ['ADMIN', 'SUPER_ADMIN', 'WORKSHOP_ADMIN'].includes(role);
    const nav = [
      ['#/dashboard', 'dashboard', I.gauge, 'Dashboard'],
      ['#/vehicles', 'vehicles', I.car, 'Vehicles'],
      ['#/sessions', 'sessions', I.scan, 'Diagnostic Sessions'],
      ['#/live', 'live', I.activity, 'Live Data'],
      ['#/terminal', 'terminal', I.term, 'OBD / UDS Terminal'],
      ['#/dtc', 'dtc', I.alert, 'DTC Library'],
      ['#/reports', 'reports', I.file, 'Reports'],
      ['#/devices', 'devices', I.bt, 'Devices'],
      ['#/profile', 'profile', I.user, 'Profile'],
      ['#/subscription', 'subscription', I.card, 'Subscription'],
      ...(admin ? [['#/admin', 'admin', I.shield, 'Admin']] : []),
      ['#/support', 'support', I.help, 'Support'],
    ];
    return `
<div class="app-shell">
  <aside class="app-sidebar" id="sidebar">
    <div class="brand"><img src="/branding/logo.svg" alt="VEHDiag" width="150" height="38"></div>
    ${nav.map(([href, key, icon, label]) => `<a href="${href}" class="${opts.active === key ? 'active' : ''}">${icon}<span>${label}</span></a>`).join('')}
    <div class="spacer"></div>
    <a href="/" style="font-size:.8rem">← Back to website</a>
  </aside>
  <div class="app-backdrop" id="backdrop"></div>
  <div class="app-main">
    <div class="app-topbar">
      <button class="app-menu-btn" id="menu-btn" aria-label="Menu">${I.menu}</button>
      <h1>${title}</h1>
      <span class="badge ${state.wsConnected ? 'badge-ok' : 'badge-warn'}"><span class="status-dot ${state.wsConnected ? 'dot-ok' : 'dot-warn'}"></span>${state.wsConnected ? 'realtime' : 'offline'}</span>
      <button class="bell" id="bell-btn" aria-label="Notifications">${I.bell}${state.notif.some((n) => !n.read) ? '<span class="dot"></span>' : ''}</button>
      <div class="avatar" title="${esc(state.user ? state.user.email : '')}">${esc((state.user ? state.user.name : '?').slice(0, 1).toUpperCase())}</div>
    </div>
    <div id="view">${body}</div>
  </div>
</div>`;
  }

  /* ---------------- login view ---------------- */
  function viewLogin() {
    return `
<div class="section" style="min-height:100vh;display:flex;align-items:center">
  <div class="container" style="max-width:420px;width:100%">
    <div style="text-align:center;margin-bottom:1.5rem"><a href="/"><img src="/branding/logo.svg" alt="VEHDiag" width="170" height="44"></a></div>
    <div class="card">
      <h2 style="font-size:1.2rem;margin-bottom:.3rem">Log in</h2>
      <p class="muted small" style="margin-bottom:1.2rem">Your diagnostic workspace.</p>
      <a class="btn btn-secondary" href="#/demo" style="width:100%;margin-bottom:1rem">${I.zap} Try the demo — no signup</a>
      <form id="login-form">
        <div class="field"><label for="l-email">Email</label><input class="input" id="l-email" type="email" required autocomplete="email"><div class="field-error">Enter a valid email.</div></div>
        <div class="field"><label for="l-pass">Password</label><input class="input" id="l-pass" type="password" required minlength="8" autocomplete="current-password"><div class="field-error">Minimum 8 characters.</div></div>
        <button class="btn btn-primary" style="width:100%" type="submit"><span class="spinner"></span> Log in</button>
        <p class="hint" style="margin-top:1rem;text-align:center">New here? <a href="/register.html">Create an account</a> — then come back.</p>
      </form>
    </div>
    <p style="text-align:center;margin-top:1rem"><a href="/" class="small">← VEHDiag website</a></p>
  </div>
</div>`;
  }

  async function login(email, password) {
    const d = await post('/auth/login', { email, password });
    localStorage.setItem('vehdiag_token', d.token);
    localStorage.setItem('vehdiag_refresh', d.refreshToken);
    state.user = d.user;
    connectWs();
    location.hash = '#/dashboard';
  }

  /* ---------------- views ---------------- */
  async function viewDashboard() {
    const [vehicles, sessions, reports, devices, notif] = await Promise.all([
      get('/vehicles').catch(() => ({ vehicles: [] })),
      get('/diagnostics/sessions').catch(() => ({ sessions: [] })),
      get('/reports').catch(() => ({ reports: [] })),
      get('/devices').catch(() => ({ devices: [] })),
      get('/notifications').catch(() => ({ notifications: [] })),
    ]);
    state.notif = notif.notifications;
    const recent = sessions.sessions.slice(0, 5);
    const active = sessions.sessions.filter((s) => s.status === 'scanning' || s.status === 'created');
    const dtcTotal = sessions.sessions.reduce((a, s) => a + (s.dtcCount || 0), 0);
    const alerts = sessions.sessions.filter((s) => s.dtcCount > 0).length;
    return shell('Dashboard', `
      <div class="stat-grid mb">
        <div class="stat"><div class="v">${vehicles.vehicles.length}</div><div class="l">Vehicles</div></div>
        <div class="stat"><div class="v">${sessions.sessions.length}</div><div class="l">Diagnostic sessions</div><div class="d">${active.length} active now</div></div>
        <div class="stat"><div class="v">${dtcTotal}</div><div class="l">DTCs found</div><div class="d">${alerts} sessions with faults</div></div>
        <div class="stat"><div class="v">${reports.reports.length}</div><div class="l">Reports</div></div>
        <div class="stat"><div class="v">${devices.devices.length}</div><div class="l">Devices</div><div class="d">${devices.devices.filter((d) => d.kind === 'simulator').length} simulator</div></div>
      </div>
      <div class="grid grid-2">
        <div class="panel">
          <div class="panel-head">Recent scans<div class="actions"><a class="btn btn-secondary btn-sm" href="#/sessions">All sessions</a></div></div>
          ${recent.length ? recent.map((s) => `
            <a class="dtc-row" href="#/session/${s.id}" style="text-decoration:none;color:inherit">
              ${statusDot(s.status)}
              <div class="grow"><b>${esc(s.profileName)}</b><br><span class="small muted">${fmtDate(s.createdAt)} · ${esc(s.profileId)}</span></div>
              <span class="badge ${s.dtcCount > 0 ? 'badge-err' : 'badge-ok'}">${s.dtcCount > 0 ? s.dtcCount + ' DTC' : 'clear'}</span>
              <span class="muted" style="font-size:1.2rem">›</span>
            </a>`).join('') : `<div class="empty">${I.scan}<p>No sessions yet.<br><a href="#/sessions">Create your first diagnostic session</a> — no vehicle required, the simulator is built in.</p></div>`}
        </div>
        <div>
          <div class="panel mb">
            <div class="panel-head">Vehicle health<div class="actions"><a class="btn btn-secondary btn-sm" href="#/vehicles">Manage</a></div></div>
            <div class="panel-body">
              ${vehicles.vehicles.length ? vehicles.vehicles.slice(0, 4).map((v) => `
                <div class="flex" style="justify-content:space-between;padding:.4rem 0">
                  <span>${I.car} <b>${esc(v.manufacturer || '?')} ${esc(v.model || '')}</b> <span class="small muted">${esc(v.vin || 'no VIN')}</span></span>
                  <span class="badge badge-ok">ok</span>
                </div>`).join('') : `<div class="empty">${I.car}<p><a href="#/vehicles">Add your first vehicle</a></p></div>`}
            </div>
          </div>
          <div class="panel">
            <div class="panel-head">Quick actions</div>
            <div class="panel-body" style="display:grid;gap:.6rem">
              <a class="btn btn-primary" href="#/sessions">${I.scan} New diagnostic session (simulator)</a>
              <a class="btn btn-secondary" href="#/live">${I.activity} Open live data</a>
              <a class="btn btn-secondary" href="#/terminal">${I.term} OBD / UDS terminal</a>
            </div>
          </div>
        </div>
      </div>`);
  }

  /* ---------------- vehicles ---------------- */
  async function viewVehicles() {
    const d = await get('/vehicles');
    return shell('Vehicles', `
      <div class="flex mb"><a class="btn btn-primary" id="add-vehicle">${I.plus} Add vehicle</a>
      <input class="input grow" id="v-search" placeholder="Search VIN / model…" style="max-width:300px"></div>
      <div class="panel" id="v-list">
        ${d.vehicles.length ? d.vehicles.map((v) => `
          <div class="dtc-row" data-vin="${esc(v.vin || '')}">
            ${I.car}
            <div class="grow">
              <b>${esc(v.manufacturer || '—')} ${esc(v.model || '')}</b> <span class="small muted">${v.year ? v.year : ''} · ${esc(v.fuel_type || '')} · ${esc(v.transmission || '')}</span><br>
              <span class="small mono">${esc(v.vin || 'VIN not stored')}</span> ${v.mileage_km != null ? `<span class="small muted">· ${v.mileage_km.toLocaleString()} km</span>` : ''}
            </div>
            <div class="flex">
              <button class="btn btn-secondary btn-sm act" data-act="identify" data-id="${v.id}" ${v.vin ? '' : 'disabled title="Add a VIN first"'}>${I.fingerprint} Identify</button>
              <button class="btn btn-secondary btn-sm act" data-act="edit" data-id="${v.id}">Edit</button>
              <button class="btn btn-danger btn-sm act" data-act="del" data-id="${v.id}">${I.x}</button>
            </div>
          </div>`).join('') : `<div class="empty">${I.car}<p>No vehicles yet. Add one — or let a session identify it from its VIN.</p></div>`}
      </div>`, { active: 'vehicles' });
  }

  function vehicleForm(v = {}) {
    return modal(`
      <h2>${v.id ? 'Edit vehicle' : 'Add vehicle'}</h2>
      <form id="v-form">
        <div class="grid grid-2">
          <div class="field"><label>VIN (17 chars)</label><input class="input mono" name="vin" maxlength="17" value="${esc(v.vin || '')}" placeholder="MA3JF31S7MK441207"></div>
          <div class="field"><label>Manufacturer</label><input class="input" name="manufacturer" value="${esc(v.manufacturer || '')}" placeholder="VEH"></div>
          <div class="field"><label>Model</label><input class="input" name="model" value="${esc(v.model || '')}"></div>
          <div class="field"><label>Year</label><input class="input" name="year" type="number" value="${v.year || ''}"></div>
          <div class="field"><label>Engine</label><input class="input" name="engine" value="${esc(v.engine || '')}"></div>
          <div class="field"><label>Fuel type</label><select class="input" name="fuel_type">
            ${['', 'petrol', 'diesel', 'electric', 'hybrid', 'cng', 'lpg'].map((f) => `<option ${f === (v.fuel_type || '') ? 'selected' : ''}>${f || '—'}</option>`).join('')}
          </select></div>
          <div class="field"><label>Transmission</label><input class="input" name="transmission" value="${esc(v.transmission || '')}"></div>
          <div class="field"><label>Mileage (km)</label><input class="input" name="mileage_km" type="number" value="${v.mileage_km != null ? v.mileage_km : ''}"></div>
        </div>
        <div class="field"><label>Plate</label><input class="input" name="plate" value="${esc(v.plate || '')}"></div>
        <div class="flex" style="justify-content:flex-end">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button class="btn btn-primary" type="submit">${v.id ? 'Save changes' : 'Add vehicle'}</button>
        </div>
      </form>`);
  }

  async function afterVehicles() {
    document.getElementById('add-vehicle').onclick = () => {
      document.body.insertAdjacentHTML('beforeend', vehicleForm());
      wireModal();
      document.getElementById('v-form').onsubmit = async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const body = Object.fromEntries(fd.entries());
        body.year = body.year ? parseInt(body.year, 10) : null;
        body.mileage_km = body.mileage_km ? parseInt(body.mileage_km, 10) : null;
        body.vin = (body.vin || '').toUpperCase() || null;
        await post('/vehicles', body);
        closeModal();
        vehToast('Vehicle saved', 'ok');
        route();
      };
    };
    document.querySelectorAll('#v-list .act').forEach((b) => b.onclick = async () => {
      const id = b.dataset.id;
      if (b.dataset.act === 'del') {
        if (!confirm('Delete this vehicle?')) return;
        await del(`/vehicles/${id}`);
        vehToast('Vehicle deleted', 'ok');
        return route();
      }
      const d = await get(`/vehicles/${id}`);
      if (b.dataset.act === 'identify') {
        const r = await post(`/vehicles/${id}/identify`, {});
        const v = r.vehicle, dec = r.decoded;
        vehToast(`VIN decoded: year ${dec.modelYear ?? '?'} · WMI ${dec.wmi} · check digit ${dec.checkDigitValid ? 'valid' : 'invalid'}`, dec.checkDigitValid ? 'ok' : 'warn', 'Vehicle identified');
        return route();
      }
      document.body.insertAdjacentHTML('beforeend', vehicleForm(d.vehicle));
      wireModal();
      document.getElementById('v-form').onsubmit = async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const body = Object.fromEntries(fd.entries());
        body.year = body.year ? parseInt(body.year, 10) : null;
        body.mileage_km = body.mileage_km ? parseInt(body.mileage_km, 10) : null;
        await patch(`/vehicles/${id}`, body);
        closeModal();
        vehToast('Vehicle updated', 'ok');
        route();
      };
    });
    const s = document.getElementById('v-search');
    if (s) s.oninput = () => {
      const q = s.value.toLowerCase();
      document.querySelectorAll('#v-list .dtc-row').forEach((r) => {
        r.style.display = (r.dataset.vin || r.textContent).toLowerCase().includes(q) ? '' : 'none';
      });
    };
  }

  /* ---------------- sessions ---------------- */
  async function viewSessions() {
    const [sessions, profiles] = await Promise.all([get('/diagnostics/sessions'), get('/diagnostics/profiles')]);
    return shell('Diagnostic Sessions', `
      <div class="grid grid-2 mb">
        <div class="panel">
          <div class="panel-head">New session — pick a vehicle profile</div>
          <div class="panel-body" id="profiles" style="display:grid;gap:.6rem">
            ${profiles.profiles.map((p) => `
              <button class="btn btn-secondary" data-profile="${p.id}" style="justify-content:flex-start">
                ${p.type === 'ev' ? I.bolt : I.car}
                <span style="text-align:left"><b>${esc(p.name)}</b><br><span class="small muted">${p.vin} · ${p.ecuCount} ECUs · ${p.protocol.toUpperCase()}</span></span>
              </button>`).join('')}
          </div>
        </div>
        <div class="panel">
          <div class="panel-head">Session history</div>
          ${sessions.sessions.length ? sessions.sessions.map((s) => `
            <a class="dtc-row" href="#/session/${s.id}" style="text-decoration:none;color:inherit">
              ${statusDot(s.status)}
              <div class="grow"><b>${esc(s.profileName)}</b><br><span class="small muted">${fmtDate(s.createdAt)}</span></div>
              ${s.status === 'scanning' ? `<div class="progress" style="width:90px"><div style="width:${s.progress}%"></div></div>` : ''}
              <span class="badge ${s.dtcCount > 0 ? 'badge-err' : 'badge-ok'}">${s.dtcCount} DTC</span>
            </a>`).join('') : `<div class="empty">${I.scan}<p>No sessions yet — create one on the left.</p></div>`}
        </div>
      </div>`, { active: 'sessions' });
  }

  async function afterSessions() {
    document.querySelectorAll('#profiles [data-profile]').forEach((b) => b.onclick = async () => {
      b.disabled = true;
      try {
        const d = await post('/diagnostics/sessions', { profile_id: b.dataset.profile });
        location.hash = `#/session/${d.session.id}`;
      } catch (e) { vehToast(e.message, 'err'); b.disabled = false; }
    });
  }

  async function viewSession(id) {
    const d = await get(`/diagnostics/sessions/${id}`);
    const s = d.session;
    const sim = d.simulator;
    const dtcs = (s.scan && s.scan.dtcs) || [];
    const ff = s.scan && s.scan.freezeFrame;
    const ecus = sim ? sim.profile.ecus : [];
    const stored = dtcs.filter((x) => x.status === 'stored');
    const pending = dtcs.filter((x) => x.status === 'pending');
    return shell(`Session — ${s.profileName}`, `
      <p class="flex mb"><a class="btn btn-secondary btn-sm" href="#/sessions">${I.back} Sessions</a>
        <span class="badge ${s.status === 'completed' ? 'badge-ok' : s.status === 'failed' ? 'badge-err' : s.status === 'scanning' ? 'badge-warn' : 'badge'}">${s.status}</span>
        <span class="small muted">${fmtDate(s.createdAt)}</span>
        <span class="small muted mono">${s.id}</span></p>

      <div class="grid grid-2 mb">
        <div class="panel">
          <div class="panel-head">Scan<div class="actions">
            <button class="btn btn-primary btn-sm" id="btn-scan" ${s.status === 'scanning' ? 'disabled' : ''}>${I.scan} ${s.scan ? 'Re-scan' : 'Run full scan'}</button>
            <button class="btn btn-secondary btn-sm" id="btn-clear" ${stored.length ? '' : 'disabled'}>${I.check} Clear DTCs</button>
          </div></div>
          <div class="panel-body">
            <div class="flex mb"><div class="progress grow"><div id="scan-progress" style="width:${s.progress || 0}%"></div></div><span class="small mono" id="scan-pct">${s.progress || 0}%</span></div>
            <div id="scan-stage" class="small muted">${s.stage ? 'Stage: ' + esc(s.stage) : 'No scan run yet.'}</div>
            ${s.error ? `<div class="callout err" style="margin-top:.8rem"><div><strong>Scan failed</strong>${esc(s.error)}</div></div>` : ''}
            ${s.scan ? `
              <div class="dl-facts mt">
                <div><b>VIN</b><code>${esc(s.scan.vin || '—')}</code></div>
                <div><b>Protocol</b><code>${esc(s.scan.protocol || '—')}</code></div>
                <div><b>Duration</b><code>${s.scan.durationMs ? s.scan.durationMs + ' ms' : '—'}</code></div>
                <div><b>Odometer</b><code>${s.scan.ecuInfo ? s.scan.ecuInfo.odometerKm + ' km' : '—'}</code></div>
              </div>` : ''}
          </div>
        </div>
        <div class="panel">
          <div class="panel-head">ECUs (${ecus.length})</div>
          ${ecus.map((e) => `
            <div class="dtc-row">${e.ecuId === 'bms' || e.ecuId === 'mcu' || e.ecuId === 'vcu' || e.ecuId === 'obc' ? I.bolt : I.cpu}
              <div class="grow"><b>${esc(e.name)}</b><br><span class="small muted mono">${e.ecuId}</span></div>
              <span class="badge ${e.dtcCount > 0 ? 'badge-err' : 'badge-ok'}">${e.dtcCount} DTC</span>
            </div>`).join('')}
        </div>
      </div>

      <div class="grid grid-2">
        <div class="panel">
          <div class="panel-head">Fault codes — stored (${stored.length}) / pending (${pending.length})</div>
          ${dtcs.length ? dtcs.map((d) => `
            <div class="dtc-row"><span class="dtc-code">${esc(d.code)}</span>
              <div class="grow">${esc(d.description)}<br><span class="small muted">${esc(d.system)} · ${esc(d.ecuName || d.ecu)} · ${esc(d.status)}</span></div>
              ${sevBadge(d.severity)}
            </div>`).join('') : `<div class="empty">${I.check}<p>All clear — no fault codes stored.</p></div>`}
        </div>
        <div>
          <div class="panel mb">
            <div class="panel-head">Freeze frame ${ff ? `— ${ff.code}` : ''}</div>
            ${ff && ff.values ? `<div class="panel-body"><div class="ff-grid">
              ${Object.entries(ff.values).map(([k, v]) => `<div class="ff-cell"><b>${esc(k)}</b><span>${v.value} ${esc(v.unit)}</span></div>`).join('')}
            </div></div>` : `<div class="empty">${I.snowflake}<p>No freeze frame captured.</p></div>`}
          </div>
          <div class="panel">
            <div class="panel-head">Fault injection (test failure paths)</div>
            <div class="panel-body">
              <div class="flex">
                ${['no_response', 'nrc78', 'bus_busy', 'disconnect'].map((f) => `
                  <button class="btn btn-secondary btn-sm fault-btn" data-fault="${f}" data-active="${(sim ? sim.faults : []).includes(f)}">${(sim ? sim.faults : []).includes(f) ? '✓ ' : ''}${f}</button>`).join('')}
              </div>
              <p class="hint">Injecting a fault lets you verify how VEHDiag handles timeouts, NRC 0x78 and disconnects.</p>
            </div>
          </div>
        </div>
      </div>
      <div class="flex mt"><a class="btn btn-primary" href="#/live?session=${id}">${I.activity} Open live data</a>
      <a class="btn btn-secondary" href="#/terminal?session=${id}">${I.term} Open terminal</a>
      <button class="btn btn-secondary" id="btn-report" ${s.scan ? '' : 'disabled'}>${I.file} Generate report</button></div>`, { active: 'sessions' });
  }

  async function afterSession(id) {
    const btnScan = document.getElementById('btn-scan');
    if (btnScan) btnScan.onclick = async () => {
      await post(`/diagnostics/sessions/${id}/scan`);
      vehToast('Scan started — watch the progress', 'info');
      trackScan(id);
    };
    const btnClear = document.getElementById('btn-clear');
    if (btnClear) btnClear.onclick = async () => {
      if (!confirm('Clear all stored DTCs on this session?')) return;
      await post(`/diagnostics/sessions/${id}/clear-dtcs`);
      vehToast('DTCs cleared', 'ok');
      route();
    };
    const btnReport = document.getElementById('btn-report');
    if (btnReport) btnReport.onclick = async () => {
      const r = await post('/reports', { session_id: id });
      vehToast('Report generated', 'ok');
      window.open(`/api/v1/reports/${r.report.id}/download?format=html`, '_blank');
    };
    document.querySelectorAll('.fault-btn').forEach((b) => b.onclick = async () => {
      const active = b.dataset.active !== 'true';
      await post(`/diagnostics/sessions/${id}/faults`, { name: b.dataset.fault, active });
      b.dataset.active = String(active);
      b.textContent = active ? `✓ ${b.dataset.fault}` : b.dataset.fault;
      vehToast(`Fault ${b.dataset.fault} ${active ? 'injected' : 'cleared'}`, active ? 'warn' : 'ok');
    });
    trackScan(id);
  }

  async function trackScan(id) {
    let done = false;
    for (let i = 0; i < 60 && !done; i++) {
      await new Promise((r) => setTimeout(r, 500));
      try {
        const d = await get(`/diagnostics/sessions/${id}`);
        const s = d.session;
        const bar = document.getElementById('scan-progress');
        const pct = document.getElementById('scan-pct');
        const stage = document.getElementById('scan-stage');
        if (bar) bar.style.width = `${s.progress || 0}%`;
        if (pct) pct.textContent = `${s.progress || 0}%`;
        if (stage && s.stage) stage.textContent = `Stage: ${s.stage}`;
        if (s.status === 'completed' || s.status === 'failed') {
          done = true;
          vehToast(s.status === 'completed' ? `Scan complete — ${s.dtcCount} stored DTC(s)` : 'Scan failed', s.status === 'completed' ? 'ok' : 'err');
          route();
        }
      } catch (e) { /* session gone */ done = true; }
    }
  }

  /* ---------------- live data ---------------- */
  async function viewLive() {
    const q = new URLSearchParams(location.hash.split('?')[1] || '');
    const sid = q.get('session');
    const sessions = (await get('/diagnostics/sessions')).sessions.filter((s) => s.status !== 'failed');
    const sel = sid || (sessions[0] && sessions[0].id) || '';
    return shell('Live Data', `
      <div class="flex mb">
        <select class="input" id="live-session" style="max-width:380px">
          ${sessions.map((s) => `<option value="${s.id}" ${s.id === sel ? 'selected' : ''}>${esc(s.profileName)} — ${fmtDate(s.createdAt)}</option>`).join('')}
        </select>
        <button class="btn btn-primary" id="live-go">${I.activity} Stream</button>
        <span class="small muted" id="live-rate"></span>
      </div>
      <div class="gauge-grid" id="gauges"><div class="empty" style="grid-column:1/-1">${I.activity}<p>Pick a session and press Stream — values arrive over WebSocket from the virtual vehicle.</p></div></div>
      <div class="panel mt">
        <div class="panel-head">Signal list</div>
        <div class="panel-body" id="live-table"></div>
      </div>`, { active: 'live' });
  }

  function drawGauge(canvas, value, min, max, unit, color) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2 + 6, r = Math.min(w, h) / 2 - 10;
    const a0 = Math.PI * 0.75, a1 = Math.PI * 2.25;
    const pct = Math.max(0, Math.min(1, (value - min) / (max - min)));
    ctx.lineWidth = 7; ctx.lineCap = 'round';
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--veh-surface-2') || '#F1F5F9';
    ctx.beginPath(); ctx.arc(cx, cy, r, a0, a1); ctx.stroke();
    const grad = ctx.createLinearGradient(0, 0, w, h);
    grad.addColorStop(0, color || '#7C3AED'); grad.addColorStop(1, '#4F46E5');
    ctx.strokeStyle = grad;
    ctx.beginPath(); ctx.arc(cx, cy, r, a0, a0 + (a1 - a0) * pct); ctx.stroke();
    // needle
    const ang = a0 + (a1 - a0) * pct;
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--veh-text') || '#0F172A';
    ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(ang) * (r - 14), cy + Math.sin(ang) * (r - 14)); ctx.stroke();
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--veh-text') || '#0F172A';
    ctx.font = '700 13px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`${Number(value).toFixed(1)}`, cx, cy + r - 2);
    ctx.font = '10px Inter, sans-serif';
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--veh-text-muted') || '#64748B';
    ctx.fillText(unit || '', cx, cy + r + 12);
  }

  async function afterLive() {
    const gaugesEl = document.getElementById('gauges');
    const tableEl = document.getElementById('live-table');
    const rateEl = document.getElementById('live-rate');
    let charts = {}; // key -> {canvas, history}
    const keys = new Set();
    let count = 0, t0 = Date.now();

    function render(snapshot) {
      count++;
      if (count === 1) t0 = Date.now();
      const ids = [];
      for (const sig of snapshot) {
        const key = `${sig.ecuId}.${sig.key}`;
        ids.push(key);
        keys.add(key);
        if (!charts[key]) {
          const cell = document.createElement('div');
          cell.className = 'gauge';
          cell.innerHTML = `<canvas width="180" height="150"></canvas><div class="name"></div><div class="value"></div>`;
          cell.querySelector('.name').textContent = `${sig.ecuId.toUpperCase()} · ${sig.name}`;
          gaugesEl.appendChild(cell);
          const cv = cell.querySelector('canvas');
          charts[key] = { cell, cv, history: [] };
          // track gauge min/max from registry data
          charts[key].min = sig.value; charts[key].max = sig.value;
        }
        const c = charts[key];
        const scale = key.includes('rpm') ? 1000 : key.includes('cell') || key.includes('Voltage') ? 20 : key.includes('SOC') || key.includes('SOH') ? 100 : 200;
        c.min = Math.min(c.min, sig.value - scale * 0.3);
        c.max = Math.max(c.max, sig.value + scale * 0.3);
        c.history.push(sig.value);
        if (c.history.length > 120) c.history.shift();
        c.cell.querySelector('.value').textContent = `${sig.value} ${sig.unit || ''}`;
        drawGauge(c.cv, sig.value, c.min, c.max, sig.unit || '');
      }
      // remove vanished signals
      for (const k of Object.keys(charts)) {
        if (!ids.includes(k)) { charts[k].cell.remove(); delete charts[k]; }
      }
      // table
      tableEl.innerHTML = `<table><thead><tr><th>ECU</th><th>Signal</th><th>Value</th></tr></thead><tbody>
        ${snapshot.map((s) => `<tr><td class="mono">${esc(s.ecuId)}</td><td>${esc(s.name)}</td><td class="mono">${s.value} ${esc(s.unit)}</td></tr>`).join('')}
      </tbody></table>`;
      if (rateEl) rateEl.textContent = `${(count / ((Date.now() - t0) / 1000)).toFixed(1)} msg/s`;
    }

    _renderLive = render; // hook WebSocket messages to this view's renderer

    document.getElementById('live-go').onclick = () => {
      const sid = document.getElementById('live-session').value;
      if (!state.wsConnected) { vehToast('WebSocket offline — reconnecting…', 'warn'); }
      if (state.liveSub && state.liveSub !== sid) state.ws.send(JSON.stringify({ type: 'live:unsubscribe', sessionId: state.liveSub }));
      state.liveSub = sid;
      state.ws.send(JSON.stringify({ type: 'live:subscribe', sessionId: sid }));
    };
  }

  /* ---------------- terminal ---------------- */
  async function viewTerminal() {
    const q = new URLSearchParams(location.hash.split('?')[1] || '');
    const sid = q.get('session');
    const sessions = (await get('/diagnostics/sessions')).sessions;
    const sel = sid || (sessions[0] && sessions[0].id) || '';
    const ecus = [{ id: 'ecm' }, { id: 'abs' }, { id: 'bms' }, { id: 'vcu' }, { id: 'mcu' }, { id: 'obc' }];
    return shell('OBD / UDS Terminal', `
      <div class="flex mb">
        <select class="input" id="term-session" style="max-width:360px">
          ${sessions.map((s) => `<option value="${s.id}" ${s.id === sel ? 'selected' : ''}>${esc(s.profileName)} — ${fmtDate(s.createdAt)}</option>`).join('')}
        </select>
      </div>
      <div class="grid grid-2">
        <div>
          <div class="panel-head" style="background:var(--veh-surface);border:1px solid var(--veh-border);border-bottom:0;border-radius:12px 12px 0 0">ELM327 terminal <span class="small muted">(AT + OBD)</span></div>
          <div class="terminal" id="elm-log" style="border-radius:0 0 10px 10px"><span class="meta"># VEHDiag ELM327 simulator — try: ATZ · 0100 · 010C · 03 · 0902 · 0202</span>\n</div>
          <div class="terminal-input">
            <input class="input" id="elm-in" placeholder="010C" autocomplete="off" spellcheck="false">
            <button class="btn btn-primary" id="elm-send">Send</button>
          </div>
        </div>
        <div>
          <div class="panel-head" style="background:var(--veh-surface);border:1px solid var(--veh-border);border-bottom:0;border-radius:12px 12px 0 0">UDS console <span class="small muted">(ISO-TP → virtual ECU)</span></div>
          <div class="terminal" id="uds-log" style="border-radius:0 0 10px 10px"><span class="meta"># hex bytes: e.g. 3E 00 · 10 03 · 22 F1 90 · 19 02 FF</span>\n</div>
          <div class="terminal-input">
            <input class="input" id="uds-in" placeholder="22 F1 90" autocomplete="off" spellcheck="false">
            <select class="input" id="uds-ecu" style="max-width:90px">${ecus.map((e) => `<option>${e.id}</option>`).join('')}</select>
            <button class="btn btn-primary" id="uds-send">Send</button>
          </div>
        </div>
      </div>`, { active: 'terminal' });
  }

  function termLog(el, cls, text) {
    el.insertAdjacentHTML('beforeend', `<span class="${cls}">${esc(text)}</span>\n`);
    el.scrollTop = el.scrollHeight;
  }

  async function afterTerminal() {
    const elmLog = document.getElementById('elm-log');
    const udsLog = document.getElementById('uds-log');
    const sess = () => document.getElementById('term-session').value;
    const elmSend = () => {
      const line = document.getElementById('elm-in').value.trim();
      if (!line) return;
      termLog(elmLog, 'in', '> ' + line);
      post(`/diagnostics/sessions/${sess()}/elm`, { line }).then((d) => {
        d.response.split('\r').filter((l) => l.trim()).forEach((l) => termLog(elmLog, 'out', l));
      }).catch((e) => termLog(elmLog, 'meta', 'ERR ' + e.message));
      document.getElementById('elm-in').value = '';
    };
    const udsSend = () => {
      const raw = document.getElementById('uds-in').value.trim();
      if (!raw) return;
      const bytes = raw.split(/\s+/).map((t) => parseInt(t, 16));
      if (bytes.some(Number.isNaN)) return termLog(udsLog, 'meta', 'ERR invalid hex');
      termLog(udsLog, 'in', '> ' + bytes.map((b) => b.toString(16).toUpperCase().padStart(2, '0')).join(' '));
      const ecu = document.getElementById('uds-ecu').value;
      post(`/diagnostics/sessions/${sess()}/uds`, { ecu, service: bytes[0], sub: bytes[1], params: bytes.slice(2) }).then((d) => {
        termLog(udsLog, 'out', '< ' + d.response.map((b) => b.toString(16).toUpperCase().padStart(2, '0')).join(' '));
      }).catch((e) => termLog(udsLog, 'meta', 'ERR ' + e.message));
      document.getElementById('uds-in').value = '';
    };
    document.getElementById('elm-send').onclick = elmSend;
    document.getElementById('uds-send').onclick = udsSend;
    document.getElementById('elm-in').onkeydown = (e) => { if (e.key === 'Enter') elmSend(); };
    document.getElementById('uds-in').onkeydown = (e) => { if (e.key === 'Enter') udsSend(); };
  }

  /* ---------------- dtc library ---------------- */
  async function viewDtc() {
    const q = new URLSearchParams(location.hash.split('?')[1] || '').get('q') || '';
    const d = await get(`/dtc?q=${encodeURIComponent(q || 'P0')}&limit=60`);
    return shell('DTC Library', `
      <div class="flex mb">
        <input class="input grow" id="dtc-q" placeholder="Search codes — e.g. P03, U01, B1" value="${esc(q)}" style="max-width:320px">
        <button class="btn btn-primary" id="dtc-go">${I.scan} Search</button>
        <span class="small muted">${d.librarySize} codes in library</span>
      </div>
      <div class="panel">
        ${d.dtcs.map((x) => `
          <div class="dtc-row"><span class="dtc-code">${esc(x.code)}</span>
            <div class="grow">${esc(x.description)}<br><span class="small muted">${esc(x.system)}</span></div>
            ${sevBadge(x.severity)}
          </div>`).join('')}
      </div>`, { active: 'dtc' });
  }

  async function afterDtc() {
    const go = () => { location.hash = `#/dtc?q=${encodeURIComponent(document.getElementById('dtc-q').value.trim())}`; };
    document.getElementById('dtc-go').onclick = go;
    document.getElementById('dtc-q').onkeydown = (e) => { if (e.key === 'Enter') go(); };
  }

  /* ---------------- reports ---------------- */
  async function viewReports() {
    const d = await get('/reports');
    return shell('Reports', `
      <div class="panel">
        ${d.reports.length ? d.reports.map((r) => `
          <div class="dtc-row">
            ${I.file}
            <div class="grow">
              <b>${esc(r.title)}</b><br>
              <span class="small muted">${fmtDate(r.createdAt)} · ${esc(r.technician)} · ${r.storedDtcCount} stored DTC(s)</span><br>
              <span class="badge ${r.diagnosticStatus === 'PASS' ? 'badge-ok' : 'badge-err'}" style="margin-top:.3rem">${r.diagnosticStatus}</span>
            </div>
            <div class="flex">
              <a class="btn btn-secondary btn-sm" href="/api/v1/reports/${r.id}/download?format=html" target="_blank" rel="noopener">${I.file} PDF/Print</a>
              <a class="btn btn-secondary btn-sm" href="/api/v1/reports/${r.id}/download?format=csv">CSV</a>
              <a class="btn btn-secondary btn-sm" href="/api/v1/reports/${r.id}/download?format=json">JSON</a>
              <button class="btn btn-danger btn-sm act" data-act="del" data-id="${r.id}">${I.x}</button>
            </div>
          </div>`).join('') : `<div class="empty">${I.file}<p>No reports yet. Complete a scan and generate one from the session page.</p></div>`}
      </div>`, { active: 'reports' });
  }

  async function afterReports() {
    document.querySelectorAll('.act').forEach((b) => b.onclick = async () => {
      if (confirm('Delete report?')) { await del(`/reports/${b.dataset.id}`); route(); }
    });
  }

  /* ---------------- devices ---------------- */
  async function viewDevices() {
    const d = await get('/devices');
    return shell('Devices', `
      <div class="flex mb"><button class="btn btn-primary" id="add-device">${I.plus} Register device</button>
      <span class="small muted">ELM327 over Bluetooth/USB/WiFi, CAN interfaces — or the built-in simulator.</span></div>
      <div class="panel">
        ${d.devices.length ? d.devices.map((x) => `
          <div class="dtc-row">${x.kind === 'simulator' ? I.term : I.bt}
            <div class="grow"><b>${esc(x.name)}</b><br><span class="small muted mono">${esc(x.kind)}</span> ${x.address ? `<span class="small muted">· ${esc(x.address)}</span>` : ''}</div>
            <span class="badge ${x.status === 'paired' ? 'badge-ok' : 'badge'}">${x.status}</span>
            ${x.simulatorTcp ? `<span class="small muted mono">tcp:${x.simulatorTcp.port}</span>` : ''}
            <div class="flex">
              <button class="btn btn-secondary btn-sm act" data-act="pair" data-id="${x.id}" ${x.status === 'paired' ? 'disabled' : ''}>${I.bt} Pair</button>
              <button class="btn btn-secondary btn-sm act" data-act="test" data-id="${x.id}">${I.scan} Test ATZ</button>
              <button class="btn btn-danger btn-sm act" data-act="del" data-id="${x.id}">${I.x}</button>
            </div>
          </div>`).join('') : `<div class="empty">${I.bt}<p>No devices registered.</p></div>`}
      </div>`, { active: 'devices' });
  }

  async function afterDevices() {
    document.getElementById('add-device').onclick = () => {
      document.body.insertAdjacentHTML('beforeend', modal(`
        <h2>Register device</h2>
        <form id="dev-form">
          <div class="field"><label>Name</label><input class="input" name="name" required value="ELM327 Bluetooth"></div>
          <div class="field"><label>Kind</label><select class="input" name="kind">
            ${['simulator', 'elm327-bluetooth', 'elm327-usb', 'elm327-wifi', 'can-socketcan', 'can-pcan', 'can-kvaser', 'can-vector'].map((k) => `<option>${k}</option>`).join('')}
          </select></div>
          <div class="field"><label>Address (MAC / path / host:port)</label><input class="input" name="address" placeholder="00:1D:A5:68:98:8B"></div>
          <div class="flex" style="justify-content:flex-end">
            <button type="button" class="btn btn-ghost" data-close>Cancel</button>
            <button class="btn btn-primary" type="submit">Register</button>
          </div>
        </form>`));
      wireModal();
      document.getElementById('dev-form').onsubmit = async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        await post('/devices', Object.fromEntries(fd.entries()));
        closeModal(); vehToast('Device registered', 'ok'); route();
      };
    };
    document.querySelectorAll('.act').forEach((b) => b.onclick = async () => {
      const id = b.dataset.id;
      if (b.dataset.act === 'del') { if (confirm('Delete device?')) { await del(`/devices/${id}`); route(); } return; }
      if (b.dataset.act === 'pair') {
        const r = await post(`/devices/${id}/pair`);
        vehToast(r.pairResult.ok ? `Paired — ${r.pairResult.response}` : 'Pairing failed: ' + r.pairResult.error, r.pairResult.ok ? 'ok' : 'err');
        route();
        return;
      }
      const r = await post(`/devices/${id}/test`, { line: 'ATZ' });
      vehToast(r.testResult.ok ? r.testResult.response : 'Test failed: ' + r.testResult.error, r.testResult.ok ? 'ok' : 'err', 'ATZ test');
    });
  }

  /* ---------------- profile / subscription / admin / support ---------------- */
  async function viewProfile() {
    const d = await get('/users/me');
    return shell('Profile', `
      <div class="panel" style="max-width:520px">
        <div class="panel-head">Account</div>
        <div class="panel-body">
          <form id="profile-form">
            <div class="field"><label>Name</label><input class="input" name="name" value="${esc(d.user.name)}" required></div>
            <div class="field"><label>Email</label><input class="input" value="${esc(d.user.email)}" disabled></div>
            <div class="field"><label>Role</label><input class="input" value="${esc(d.user.role)}" disabled></div>
            <div class="field"><label>New password (optional)</label><input class="input" name="password" type="password" minlength="8" placeholder="••••••••"></div>
            <div class="field"><label>Theme</label><select class="input" name="settings[theme]">
              ${['system', 'light', 'dark'].map((t) => `<option ${d.user.settings && d.user.settings.theme === t ? 'selected' : ''}>${t}</option>`).join('')}
            </select></div>
            <button class="btn btn-primary" type="submit">Save</button>
          </form>
        </div>
      </div>`, { active: 'profile' });
  }

  async function afterProfile() {
    document.getElementById('profile-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = { name: fd.get('name') };
      const pw = fd.get('password');
      if (pw) body.password = pw;
      await patch('/users/me', body);
      state.user = (await get('/auth/me')).user;
      vehToast('Profile saved', 'ok');
      route();
    };
  }

  async function viewSubscription() {
    const d = await get('/subscriptions/me');
    return shell('Subscription', `
      <div class="grid grid-3">
        ${d.plans.map((p) => `
          <div class="card" style="${d.subscription.plan === p.id ? 'border:2px solid var(--veh-primary)' : ''}">
            <h3>${esc(p.name)}</h3>
            <p style="font-size:1.8rem;font-weight:800">₹${p.priceInr}<span style="font-size:.9rem;color:var(--veh-text-muted);font-weight:400"> /month</span></p>
            <p class="muted small" style="margin:.4rem 0 1rem">${p.limits.users} user(s) · ${p.limits.vehicles === -1 ? 'unlimited' : p.limits.vehicles} vehicles</p>
            ${d.subscription.plan === p.id ? `<span class="badge badge-ok" style="margin-bottom:.8rem">Current plan</span>` : `<button class="btn btn-secondary plan-btn" data-plan="${p.id}">Select</button>`}
          </div>`).join('')}
      </div>
      <p class="small muted mt">Payments are simulated in this build — plan state is stored with your account.</p>`, { active: 'subscription' });
  }

  async function afterSubscription() {
    document.querySelectorAll('.plan-btn').forEach((b) => b.onclick = async () => {
      await post('/subscriptions/select', { plan: b.dataset.plan });
      vehToast('Plan updated', 'ok');
      route();
    });
  }

  async function viewAdmin() {
    let stats = null, users = [], audit = [];
    try {
      stats = (await get('/admin/stats')).stats;
      users = (await get('/admin/users')).users;
      audit = (await get('/admin/audit')).audit;
    } catch (e) { /* gated */ }
    if (!stats) return shell('Admin', `<div class="panel"><div class="panel-body">Administrator role required.</div></div>`, { active: 'admin' });
    return shell('Admin', `
      <div class="stat-grid mb">
        ${Object.entries(stats).filter(([k]) => k !== 'byRole').map(([k, v]) => `<div class="stat"><div class="v">${v}</div><div class="l">${k.replace(/([A-Z])/g, ' $1')}</div></div>`).join('')}
      </div>
      <div class="grid grid-2">
        <div class="panel">
          <div class="panel-head">Users (${users.length})</div>
          ${users.map((u) => `
            <div class="dtc-row">${I.user}
              <div class="grow"><b>${esc(u.name)}</b> <span class="small muted">${esc(u.email)}</span><br><span class="small muted">joined ${fmtDate(u.createdAt)}</span></div>
              <span class="badge badge-purple">${esc(u.role)}</span>
            </div>`).join('')}
        </div>
        <div class="panel">
          <div class="panel-head">Recent activity</div>
          <div class="panel-body" style="font-size:.85rem">
            ${audit.length ? audit.map((a) => `<div style="padding:.3rem 0;border-bottom:1px solid var(--veh-border)"><span class="mono">${esc(a.id).slice(0, 8)}</span> · ${esc(a.msg || a.action || 'event')} · ${fmtDate(a.createdAt || a.ts)}</div>`).join('') : '<p class="muted">No audit entries.</p>'}
          </div>
        </div>
      </div>`, { active: 'admin' });
  }

  async function viewSupport() {
    return shell('Support', `
      <div class="prose" style="max-width:760px">
        <h2 style="font-size:1.3rem">Getting help</h2>
        <p class="muted">VEHDiag is an independent, open project. Support channels:</p>
        <ul>
          <li><a href="https://github.com/Sakthivel13/VEHDiag" rel="noopener">GitHub repository</a> — issues &amp; discussions.</li>
          <li><a href="/docs.html">Documentation</a> — architecture, API, simulator, protocols.</li>
          <li><a href="/contact.html">Contact page</a> — email the team.</li>
        </ul>
        <h2 style="font-size:1.3rem;margin-top:2rem">Diagnostics cheat-sheet</h2>
        <div class="table-wrap">
          <table>
            <caption>Useful ELM327 commands for the simulator</caption>
            <thead><tr><th>Command</th><th>Purpose</th></tr></thead>
            <tbody>
              <tr><td class="mono">ATZ / ATI / ATDP</td><td>Reset, identify, protocol</td></tr>
              <tr><td class="mono">0100 / 0120 / 0140</td><td>Supported PIDs</td></tr>
              <tr><td class="mono">010C · 0105 · 010D</td><td>RPM · coolant temp · speed</td></tr>
              <tr><td class="mono">03 / 07 / 0A</td><td>Stored / pending / permanent DTCs</td></tr>
              <tr><td class="mono">04</td><td>Clear stored DTCs</td></tr>
              <tr><td class="mono">0902 · 0904 · 090A</td><td>VIN · calibration ID · ECU name</td></tr>
            </tbody>
          </table>
        </div>
        <h2 style="font-size:1.3rem;margin-top:2rem">UDS console examples</h2>
        <div class="prose"><pre><code>3E 00        Tester Present
10 03        Diagnostic Session Control → Extended
22 F1 90     ReadDataByIdentifier → VIN
19 02 FF     ReadDtcInformation → all statuses
14 FF FF FF  ClearDiagnosticInformation</code></pre></div>
      </div>`, { active: 'support' });
  }

  /* ---------------- modal helpers ---------------- */
  function modal(inner) {
    return `<div class="modal-backdrop" data-modal-backdrop><div class="modal" role="dialog" aria-modal="true">${inner}</div></div>`;
  }
  function wireModal() {
    document.querySelectorAll('[data-modal-backdrop]').forEach((bd) => {
      bd.addEventListener('click', (e) => { if (e.target === bd) closeModal(); });
    });
    document.querySelectorAll('[data-close]').forEach((b) => b.onclick = closeModal);
  }
  function closeModal() {
    const m = document.querySelector('[data-modal-backdrop]');
    if (m) m.remove();
  }

  function vehToast(msg, kind, title) {
    if (window.vehToast) return window.vehToast(msg, kind, title);
    alert((title ? title + ': ' : '') + msg);
  }

  /* ---------------- demo mode ---------------- */
  async function viewDemo() {
    // Demo mode = real account, real API. One click, no signup.
    const app = document.getElementById('app');
    app.innerHTML = `<div class="section" style="display:flex;align-items:center;justify-content:center;min-height:100vh">
      <div class="card" style="max-width:460px;text-align:center">
        ${I.zap}
        <h2 style="font-size:1.2rem;margin:.8rem 0 .3rem">Starting demo…</h2>
        <p class="muted small" style="margin-bottom:1.2rem">Signing you into the shared demo workspace (real sessions, real simulator traffic).</p>
      </div>
    </div>`;
    try {
      await login('demo@vehdiag.app', 'demo1234');
      vehToast('Demo signed in — everything is real: sessions, DTCs, live data', 'ok', 'Demo mode');
    } catch (e) {
      app.innerHTML = viewLogin();
      vehToast('Demo sign-in failed: ' + e.message, 'err');
      location.hash = '#/login';
    }
    return '';
  }

  function connectWs() {
    if (state.ws && state.ws.readyState <= 1) return;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws`);
    state.ws = ws;
    ws.onopen = () => {
      state.wsConnected = true;
      if (token()) ws.send(JSON.stringify({ type: 'auth', token: token() }));
      document.querySelectorAll('#view .badge').forEach(() => {});
      updateBadge();
    };
    ws.onclose = () => {
      state.wsConnected = false;
      updateBadge();
      setTimeout(connectWs, 2500);
    };
    ws.onerror = () => { /* onclose follows */ };
    ws.onmessage = (e) => {
      let m;
      try { m = JSON.parse(e.data); } catch (x) { return; }
      if (m.type === 'live:data' && state.liveSub === m.sessionId) {
        const f = document.getElementById('gauges');
        if (f) renderLive(m.values);
      } else if (m.type === 'notification') {
        state.notif.unshift(m.notification);
        vehToast(m.notification.body, 'info', m.notification.title);
      }
    };
  }

  let _renderLive = null;
  function renderLive(v) { if (_renderLive) _renderLive(v); }

  function updateBadge() {
    document.querySelectorAll('#view .badge').forEach((b) => {
      if (b.textContent.includes('realtime') || b.textContent.includes('offline')) {
        b.innerHTML = `<span class="status-dot ${state.wsConnected ? 'dot-ok' : 'dot-warn'}"></span>${state.wsConnected ? 'realtime' : 'offline'}`;
      }
    });
  }

  /* ---------------- router ---------------- */
  const views = {
    '': viewDashboard,
    dashboard: viewDashboard,
    demo: viewDemo,
    vehicles: viewVehicles,
    sessions: viewSessions,
    live: viewLive,
    terminal: viewTerminal,
    dtc: viewDtc,
    reports: viewReports,
    devices: viewDevices,
    profile: viewProfile,
    subscription: viewSubscription,
    admin: viewAdmin,
    support: viewSupport,
    login: () => viewLogin(),
  };
  const afters = {
    vehicles: afterVehicles,
    sessions: afterSessions,
    live: afterLive,
    terminal: afterTerminal,
    dtc: afterDtc,
    reports: afterReports,
    devices: afterDevices,
    profile: afterProfile,
    subscription: afterSubscription,
  };

  async function route() {
    const app = document.getElementById('app');
    const hash = location.hash.replace(/^#\/?/, '');
    const [pathPart, query] = hash.split('?');
    const parts = pathPart.split('/').filter(Boolean);
    const name = parts[0] || 'dashboard';

    try {
      if (!state.user) {
        // try stored session
        try { state.user = (await get('/auth/me')).user; } catch (e) { state.user = null; }
      }
      if (!state.user && name !== 'login' && name !== 'demo') {
        app.innerHTML = viewLogin();
        const form = document.getElementById('login-form');
        form.onsubmit = async (e) => {
          e.preventDefault();
          if (!form.checkValidity()) return;
          const btn = form.querySelector('button[type=submit]');
          btn.classList.add('loading'); btn.disabled = true;
          try {
            await login(document.getElementById('l-email').value, document.getElementById('l-pass').value);
          } catch (err) {
            vehToast(err.message, 'err', 'Login failed');
            btn.classList.remove('loading'); btn.disabled = false;
          }
        };
        return;
      }

      if (name === 'session' && parts[1]) {
        app.innerHTML = await viewSession(parts[1]);
        await afterSession(parts[1]);
        return;
      }
      const view = views[name];
      if (!view) { app.innerHTML = shell('Not found', `<div class="empty"><p>Page not found. <a href="#/dashboard">Dashboard</a></p></div>`); return; }
      app.innerHTML = await view();
      if (name === 'live') _renderLive = null; // set by afterLive via closure
      if (afters[name]) await afters[name]();
      wireSidebar();
    } catch (e) {
      if (e.status === 401) {
        localStorage.removeItem('vehdiag_token');
        state.user = null;
        location.hash = '#/login';
        return route();
      }
      app.innerHTML = shell('Error', `<div class="panel"><div class="panel-body"><div class="callout err"><div><strong>${esc(e.message)}</strong>Something went wrong loading this view.</div></div><p class="mt"><a class="btn btn-secondary" href="#/dashboard">Back to dashboard</a></p></div></div>`);
    }
  }

  function wireSidebar() {
    const btn = document.getElementById('menu-btn');
    const backdrop = document.getElementById('backdrop');
    const sidebar = document.getElementById('sidebar');
    if (btn) btn.onclick = () => { sidebar.classList.toggle('open'); backdrop.classList.toggle('show'); };
    if (backdrop) backdrop.onclick = () => { sidebar.classList.remove('open'); backdrop.classList.remove('show'); };
    const bell = document.getElementById('bell-btn');
    if (bell) bell.onclick = async () => {
      if (!state.notif.length) { try { state.notif = (await get('/notifications')).notifications; } catch (e) { /* noop */ } }
      const list = state.notif.slice(0, 8).map((n) => `<div class="dtc-row"><div class="grow"><b>${esc(n.title)}</b><br><span class="small muted">${esc(n.body)}</span></div><span class="small muted">${fmtDate(n.createdAt)}</span></div>`).join('') || '<div class="empty">No notifications</div>';
      document.body.insertAdjacentHTML('beforeend', modal(`<h2>Notifications</h2><div style="display:grid">${list}</div><div class="flex" style="justify-content:flex-end"><button class="btn btn-ghost" data-close>Close</button></div>`));
      wireModal();
    };
  }

  /* ---------------- boot ---------------- */
  window.addEventListener('hashchange', route);
  window.addEventListener('DOMContentLoaded', () => {
    connectWs();
    route();
  });
})();
