'use strict';
/** VEHDiag — /api/v1/reports: diagnostic reports (JSON/CSV/printable PDF HTML). */

const { HttpError, ok, readJson, newId } = require('../lib/http');
const { decodeMany } = require('../../../diagnostics/dtc');

const PLANS = require('./subscriptions').PLANS;

function buildReport(session, user, vehicle) {
  const scan = session.scan || {};
  const dtcs = (scan.dtcs || []).map((d) => {
    const meta = decodeMany([d.code])[0];
    return { code: d.code, system: meta.system, description: meta.description, severity: meta.severity, status: d.status, ecu: d.ecuName || d.ecuId };
  });
  const stored = dtcs.filter((d) => d.status === 'stored');
  const recs = stored.map((d) => `${d.code} (${d.severity}): ${d.description}`);
  return {
    id: newId(),
    sessionId: session.id,
    userId: session.userId,
    createdAt: new Date().toISOString(),
    template: 'classic',
    vehicle: vehicle ? {
      vin: vehicle.vin, manufacturer: vehicle.manufacturer, model: vehicle.model,
      year: vehicle.year, engine: vehicle.engine, fuel_type: vehicle.fuel_type,
      transmission: vehicle.transmission, mileage_km: vehicle.mileage_km, plate: vehicle.plate,
    } : null,
    title: `VEHDiag Diagnostic Report — ${session.profileName || session.profileId}`,
    technician: user.name,
    diagnosticDevice: 'VEHDiag Simulator (virtual ELM327)',
    scanStartedAt: scan.startedAt || session.createdAt,
    scanCompletedAt: scan.completedAt || null,
    scanDurationMs: scan.durationMs || null,
    protocol: scan.protocol || null,
    vin: scan.vin || session.vehicleVin || (vehicle && vehicle.vin) || null,
    odometerKm: scan.ecuInfo ? scan.ecuInfo.odometerKm : null,
    ecusScanned: (scan.ecus || []).map((e) => ({ id: e.ecuId, name: e.name, status: e.status })),
    dtcs,
    dtcCount: dtcs.length,
    storedDtcCount: stored.length,
    freezeFrame: scan.freezeFrame || null,
    ecuInfo: scan.ecuInfo || null,
    liveDataSummary: scan.pidsSupported ? { pidsSupported: scan.pidsSupported } : null,
    diagnosticStatus: stored.length === 0 ? 'PASS' : 'FAULTS FOUND',
    recommendations: recs.length
      ? recs
      : ['No stored fault codes. Continue with scheduled maintenance.'],
  };
}

function csv(report) {
  const esc = (v) => {
    const s = v === null || v === undefined ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const head = ['code', 'system', 'severity', 'status', 'ecu', 'description'];
  const rows = [head.map(esc).join(',')];
  for (const d of report.dtcs) rows.push([d.code, d.system, d.severity, d.status, d.ecu, d.description].map(esc).join(','));
  if (!report.dtcs.length) rows.push('NO_DTCS,,,,,No stored fault codes');
  return rows.join('\n');
}

function mount(router, { store, log, notify }) {
  const mine = (req) => store.collection('reports').filter((r) => r.userId === req.user.id);

  router.get('/api/v1/reports', async (req, res) => {
    ok(res, { reports: mine(req).sort((a, b) => b.createdAt.localeCompare(a.createdAt)) });
  });

  router.post('/api/v1/reports', async (req, res) => {
    const body = await readJson(req);
    const session = store.collection('sessions').find((s) => s.id === body.session_id && s.userId === req.user.id);
    if (!session) throw new HttpError(404, 'Session not found', 'not_found');
    const vehicle = session.vehicleId ? store.collection('vehicles').find((v) => v.id === session.vehicleId) : null;
    const report = buildReport(session, req.user, vehicle);
    store.collection('reports').push(report);
    store.scheduleFlush();
    log.app('info', 'report_generated', { userId: req.user.id, reportId: report.id, sessionId: session.id });
    if (notify) {
      notify(req.user.id, {
        type: 'report',
        title: 'Report ready',
        body: `${report.title} (${report.diagnosticStatus})`,
        sessionId: session.id,
      });
    }
    ok(res, { report }, 201);
  });

  router.get('/api/v1/reports/:id', async (req, res) => {
    const r = mine(req).find((x) => x.id === req.params.id);
    if (!r) throw new HttpError(404, 'Report not found', 'not_found');
    ok(res, { report: r });
  });

  router.get('/api/v1/reports/:id/download', async (req, res) => {
    const r = mine(req).find((x) => x.id === req.params.id);
    if (!r) throw new HttpError(404, 'Report not found', 'not_found');
    const format = req.query.format || 'json';
    if (format === 'csv') {
      res.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': `attachment; filename="vehdiag-report-${r.id.slice(0, 8)}.csv"` });
      return res.end(csv(r));
    }
    if (format === 'txt') {
      const lines = [
        r.title, '='.repeat(r.title.length),
        `Technician: ${r.technician}`, `Device: ${r.diagnosticDevice}`,
        `VIN: ${r.vin || 'n/a'}`, `Scanned: ${r.scanStartedAt}`,
        `Status: ${r.diagnosticStatus}`,
        '',
        ...(r.dtcs.length ? r.dtcs.map((d) => `[${d.status.toUpperCase()}] ${d.code} (${d.severity}) — ${d.description}`) : ['No fault codes.']),
        '',
        'Recommendations:',
        ...r.recommendations.map((x) => ` - ${x}`),
      ];
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Content-Disposition': `attachment; filename="vehdiag-report-${r.id.slice(0, 8)}.txt"` });
      return res.end(lines.join('\n'));
    }
    if (format === 'html') {
      // printable HTML (print → PDF in the browser)
      const html = `<!doctype html><html><head><meta charset="utf-8"><title>${r.title}</title>
<style>body{font-family:'Segoe UI',Arial,sans-serif;max-width:820px;margin:32px auto;color:#0F172A}
h1{font-size:22px;border-bottom:3px solid #7C3AED;padding-bottom:8px}
table{width:100%;border-collapse:collapse;margin:14px 0}
th,td{border:1px solid #E2E8F0;padding:8px 10px;font-size:13px;text-align:left}
th{background:#F1F5F9;text-transform:uppercase;font-size:11px;letter-spacing:.05em}
.sev-critical,.sev-high{color:#DC2626;font-weight:700}.sev-medium{color:#D97706;font-weight:600}.sev-low{color:#2563EB}
.pass{color:#16A34A;font-weight:800}.fail{color:#DC2626;font-weight:800}
.mono{font-family:Consolas,monospace}</style></head><body>
<h1>${r.title}</h1>
<table><tr><th>Technician</th><td>${r.technician}</td><th>Device</th><td>${r.diagnosticDevice}</td></tr>
<tr><th>VIN</th><td class="mono">${r.vin || '—'}</td><th>Odometer</th><td>${r.odometerKm !== null && r.odometerKm !== undefined ? r.odometerKm + ' km' : '—'}</td></tr>
<tr><th>Scanned</th><td>${r.scanStartedAt}</td><th>Duration</th><td>${r.scanDurationMs ? r.scanDurationMs + ' ms' : '—'}</td></tr>
<tr><th>Status</th><td colspan="3" class="${r.diagnosticStatus === 'PASS' ? 'pass' : 'fail'}">${r.diagnosticStatus}</td></tr></table>
<h2>Fault codes (${r.dtcCount})</h2>
${r.dtcs.length ? `<table><tr><th>Code</th><th>System</th><th>Severity</th><th>Status</th><th>Description</th></tr>
${r.dtcs.map((d) => `<tr><td class="mono">${d.code}</td><td>${d.system}</td><td class="sev-${d.severity}">${d.severity}</td><td>${d.status}</td><td>${d.description}</td></tr>`).join('')}</table>`
    : '<p class="pass">No fault codes stored.</p>'}
<h2>ECUs scanned</h2><table><tr><th>ECU</th><th>Status</th></tr>${r.ecusScanned.map((e) => `<tr><td>${e.name}</td><td>${e.status}</td></tr>`).join('')}</table>
<h2>Recommendations</h2><ul>${r.recommendations.map((x) => `<li>${x}</li>`).join('')}</ul>
<p style="color:#94A3B8;font-size:11px;margin-top:28px">Generated by VEHDiag — independent diagnostics platform · ${r.createdAt}</p>
</body></html>`;
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      return res.end(html);
    }
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Disposition': `attachment; filename="vehdiag-report-${r.id.slice(0, 8)}.json"` });
    res.end(JSON.stringify(r, null, 2));
  });

  router.delete('/api/v1/reports/:id', async (req, res) => {
    const i = mine(req).findIndex((x) => x.id === req.params.id);
    if (i < 0) throw new HttpError(404, 'Report not found', 'not_found');
    store.collection('reports').splice(i, 1);
    store.scheduleFlush();
    ok(res, { deleted: true });
  });
}

module.exports = { mount, buildReport, csv };
