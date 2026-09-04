'use strict';
/**
 * VEHDiag — /api/v1/diagnostics: diagnostic sessions (create, scan, DTCs,
 * freeze frame, ECU info, ELM terminal, UDS console, fault injection).
 */

const { HttpError, ok, readJson, newId } = require('../lib/http');
const { VEHICLE_PROFILES } = require('../lib/runtime');
const { decodeMany } = require('../../../diagnostics/dtc');

function mount(router, { store, runtime, log, broadcast }) {
  const mine = (req) => store.collection('sessions').filter((s) => s.userId === req.user.id);

  router.get('/api/v1/diagnostics/profiles', async (req, res) => {
    ok(res, { profiles: Object.values(VEHICLE_PROFILES).map((p) => ({
      id: p.id, name: p.name, type: p.type, vin: p.vin, model: p.model,
      year: p.year, fuel: p.fuel, transmission: p.transmission, protocol: p.protocol,
      ecuCount: p.ecus.length,
    })) });
  });

  router.post('/api/v1/diagnostics/sessions', async (req, res) => {
    const body = await readJson(req);
    const profileId = body.profile_id || 'ice-sedan-2021';
    if (!VEHICLE_PROFILES[profileId]) throw new HttpError(400, 'Unknown vehicle profile', 'invalid_profile');
    const vehicle = body.vehicle_id
      ? store.collection('vehicles').find((v) => v.id === body.vehicle_id && v.userId === req.user.id)
      : null;

    const s = {
      id: newId(),
      userId: req.user.id,
      vehicleId: vehicle ? vehicle.id : null,
      vehicleVin: vehicle ? vehicle.vin : null,
      profileId,
      profileName: VEHICLE_PROFILES[profileId].name,
      deviceId: body.device_id || null,
      status: 'created', // created | scanning | completed | failed
      progress: 0,
      dtcCount: 0,
      events: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    store.collection('sessions').push(s);
    store.scheduleFlush();
    const entry = runtime.attach(s);
    log.diag('info', 'session_created', { sessionId: s.id, userId: req.user.id, profile: profileId });
    ok(res, {
      session: s,
      simulator: {
        id: entry.sim.id,
        profile: entry.sim.profile(),
        faults: entry.sim.listFaults(),
      },
    }, 201);
  });

  router.get('/api/v1/diagnostics/sessions', async (req, res) => {
    const list = mine(req).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    ok(res, { sessions: list.map((s) => ({ ...s, events: (s.events || []).slice(-20) })) });
  });

  router.get('/api/v1/diagnostics/sessions/:id', async (req, res) => {
    const s = mine(req).find((x) => x.id === req.params.id);
    if (!s) throw new HttpError(404, 'Session not found', 'not_found');
    const entry = runtime.getEntry(s.id);
    ok(res, {
      session: { ...s, events: (s.events || []).slice(-30) },
      simulator: entry ? { id: entry.sim.id, profile: entry.sim.profile(), faults: entry.sim.listFaults() } : null,
    });
  });

  router.delete('/api/v1/diagnostics/sessions/:id', async (req, res) => {
    const i = mine(req).findIndex((x) => x.id === req.params.id);
    if (i < 0) throw new HttpError(404, 'Session not found', 'not_found');
    runtime.detach(req.params.id);
    store.collection('sessions').splice(i, 1);
    store.scheduleFlush();
    ok(res, { deleted: true });
  });

  /** Full scan — drives the real simulator through ELM + UDS traffic. */
  router.post('/api/v1/diagnostics/sessions/:id/scan', async (req, res) => {
    const s = mine(req).find((x) => x.id === req.params.id);
    if (!s) throw new HttpError(404, 'Session not found', 'not_found');
    if (s.status === 'scanning') throw new HttpError(409, 'Scan already running', 'busy');
    s.status = 'scanning';
    s.progress = 0;
    store.scheduleFlush();

    // run asynchronously; progress streams over WebSocket
    const onProgress = (p) => {
      s.progress = p.pct;
      if (p.stage) s.stage = p.stage;
      store.scheduleFlush();
      broadcast({ type: 'scan:progress', sessionId: s.id, ...p }, { sessionId: s.id });
    };
    ok(res, { started: true, sessionId: s.id });

    runtime.scan(s, { onProgress }).catch((e) => {
      s.status = 'failed';
      s.error = e.code || e.message;
      s.updatedAt = new Date().toISOString();
      store.scheduleFlush();
      log.err('error', 'scan_failed', { sessionId: s.id, error: e.message });
      broadcast({ type: 'scan:progress', sessionId: s.id, pct: 0, stage: 'failed', error: e.message }, { sessionId: s.id });
    });
  });

  router.get('/api/v1/diagnostics/sessions/:id/dtc', async (req, res) => {
    const s = mine(req).find((x) => x.id === req.params.id);
    if (!s) throw new HttpError(404, 'Session not found', 'not_found');
    const entry = runtime.getEntry(s.id);
    const kind = req.query.kind || 'all';
    const out = [];
    if (entry) {
      for (const ecu of entry.sim.profile().ecus) {
        for (const d of entry.sim.readDtcs(ecu.ecuId, kind === 'pending' ? 'pending' : kind === 'permanent' ? 'permanent' : 'stored')) {
          out.push({ ecuId: ecu.ecuId, ecuName: ecu.name, code: d.code, status: d.status, ...decodeMany([d.code])[0], occurredAt: d.occurredAt, freezeFrame: d.freeze ? entry.sim.vehicle.freezeFrame(ecu.ecuId, d.code) : null });
        }
        if (kind === 'all') {
          for (const d of entry.sim.readDtcs(ecu.ecuId, 'pending')) {
            if (!out.some((x) => x.code === d.code && x.status === d.status)) {
              out.push({ ecuId: ecu.ecuId, ecuName: ecu.name, code: d.code, status: d.status, ...decodeMany([d.code])[0], occurredAt: d.occurredAt, freezeFrame: null });
            }
          }
        }
      }
    }
    ok(res, { dtcs: out });
  });

  router.post('/api/v1/diagnostics/sessions/:id/clear-dtcs', async (req, res) => {
    const s = mine(req).find((x) => x.id === req.params.id);
    if (!s) throw new HttpError(404, 'Session not found', 'not_found');
    const entry = runtime.getEntry(s.id);
    const cleared = [];
    let elm = null;
    if (entry) {
      elm = entry.sim.elmCommand('04');
      for (const ecu of entry.sim.profile().ecus) { entry.sim.clearDtcs(ecu.ecuId); cleared.push(ecu.ecuId); }
      runtime.recordEvent(s, 'clear_dtcs', { ecus: cleared });
      log.diag('info', 'dtcs_cleared', { sessionId: s.id, userId: req.user.id });
    }
    ok(res, { cleared, elmResponse: elm || '' });
  });

  /** ELM327 raw terminal. */
  router.post('/api/v1/diagnostics/sessions/:id/elm', async (req, res) => {
    const s = mine(req).find((x) => x.id === req.params.id);
    if (!s) throw new HttpError(404, 'Session not found', 'not_found');
    const body = await readJson(req);
    const line = typeof body.line === 'string' ? body.line.slice(0, 128) : '';
    if (!line) throw new HttpError(400, 'Provide an ELM327 command line', 'invalid_command');
    const resp = runtime.elm(s.id, line);
    ok(res, { line, response: resp });
  });

  /** UDS console (hex bytes, full ISO-TP path to the virtual ECU). */
  router.post('/api/v1/diagnostics/sessions/:id/uds', async (req, res) => {
    const s = mine(req).find((x) => x.id === req.params.id);
    if (!s) throw new HttpError(404, 'Session not found', 'not_found');
    const body = await readJson(req);
    const out = await runtime.uds(s.id, body.ecu || 'ecm', body.service, body.sub, body.params);
    ok(res, out);
  });

  /** Fault injection for testing failure paths. */
  router.post('/api/v1/diagnostics/sessions/:id/faults', async (req, res) => {
    const s = mine(req).find((x) => x.id === req.params.id);
    if (!s) throw new HttpError(404, 'Session not found', 'not_found');
    const entry = runtime.getEntry(s.id);
    const body = await readJson(req);
    const allowed = ['no_response', 'nrc78', 'bus_busy', 'disconnect', 'uds_reject'];
    if (body.name && allowed.includes(body.name)) {
      if (body.active) entry.sim.injectFault(body.name);
      else entry.sim.clearFault(body.name);
      runtime.recordEvent(s, 'fault', { name: body.name, active: !!body.active });
    }
    ok(res, { faults: entry.sim.listFaults() });
  });
}

module.exports = { mount };
