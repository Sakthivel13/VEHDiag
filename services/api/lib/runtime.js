'use strict';
/**
 * VEHDiag — diagnostic runtime.
 * Binds diagnostic sessions (DB records) to live SimulatorSession instances,
 * orchestrates scans (real ELM/UDS traffic against the virtual vehicle),
 * streams live data to WebSocket subscribers and enforces session isolation
 * (every session owns its state; failures cannot corrupt later sessions).
 */

const { createSession, destroySession, getSession, VEHICLE_PROFILES } = require('../../../diagnostics/simulator');
const { decodeMany } = require('../../../diagnostics/dtc');
const { parseDtcPayload, parsePidResponse, decodePid } = require('../../../diagnostics/obd');

class DiagnosticRuntime {
  constructor({ store, log, notify, broadcast }) {
    this.store = store;
    this.log = log;
    this.notify = notify;
    this.broadcast = broadcast; // fn(obj, { sessionId }) → WS fan-out
    this.live = new Map(); // dbSessionId -> { sim, subscribers:Set, interval }
    this.scans = new Map(); // dbSessionId -> scan state
  }

  /** Create + start the simulator backing for a DB session. */
  attach(dbSession) {
    let entry = this.live.get(dbSession.id);
    if (entry) return entry;
    const sim = createSession(dbSession.profileId, { seed: (dbSession.id.charCodeAt(0) || 1) * 7919 });
    entry = { sim, subscribers: new Set(), interval: null };
    this.live.set(dbSession.id, entry);
    this.log.diag('info', 'simulator_attached', { sessionId: dbSession.id, profile: dbSession.profileId });
    return entry;
  }

  detach(dbSessionId) {
    const entry = this.live.get(dbSessionId);
    if (entry) {
      if (entry.interval) clearInterval(entry.interval);
      destroySession(entry.sim.id);
      this.live.delete(dbSessionId);
      this.log.diag('info', 'simulator_detached', { sessionId: dbSessionId });
    }
  }

  getEntry(dbSessionId) {
    const dbSession = this.store.collection('sessions').find((s) => s.id === dbSessionId);
    if (!dbSession) return null;
    return this.attach(dbSession);
  }

  /* ---------------- live data ---------------- */
  subscribe(dbSessionId, wsId) {
    const entry = this.getEntry(dbSessionId);
    if (!entry) return false;
    entry.subscribers.add(wsId);
    if (!entry.interval) {
      entry.interval = setInterval(() => {
        const snapshot = entry.sim.liveSnapshot();
        for (const ws of entry.subscribers) this.broadcast({ type: 'live:data', sessionId: dbSessionId, values: snapshot }, { ws });
      }, 500);
      if (entry.interval.unref) entry.interval.unref();
    }
    return true;
  }

  unsubscribe(dbSessionId, wsId) {
    const entry = this.live.get(dbSessionId);
    if (!entry) return;
    entry.subscribers.delete(wsId);
    if (entry.subscribers.size === 0 && entry.interval) {
      clearInterval(entry.interval);
      entry.interval = null;
    }
  }

  /* ---------------- ELM terminal ---------------- */
  elm(dbSessionId, line) {
    const entry = this.getEntry(dbSessionId);
    if (!entry) throw Object.assign(new Error('session not found'), { status: 404 });
    const dbSession = this.store.collection('sessions').find((s) => s.id === dbSessionId);
    const resp = entry.sim.elmCommand(line);
    if (dbSession) this.recordEvent(dbSession, 'elm', { line, resp });
    return resp;
  }

  /* ---------------- UDS console ---------------- */
  async uds(dbSessionId, ecuId, service, sub, params = []) {
    const entry = this.getEntry(dbSessionId);
    if (!entry) throw Object.assign(new Error('session not found'), { status: 404 });
    const dbSession = this.store.collection('sessions').find((s) => s.id === dbSessionId);
    const { session } = entry.sim.udsClient(ecuId);
    const bytes = [service];
    if (sub !== undefined && sub !== null) bytes.push(sub);
    bytes.push(...(params || []).map((x) => typeof x === 'number' ? x : parseInt(x, 16)));

    const start = Date.now();
    const raw = await session.request(bytes);
    const elapsed = Date.now() - start;
    if (dbSession) this.recordEvent(dbSession, 'uds', { ecuId, request: bytes.map((b) => b.toString(16).padStart(2, '0')).join(' '), response: raw.map((b) => b.toString(16).padStart(2, '0')).join(' '), elapsed });
    return { ecuId, request: bytes, response: raw, elapsed };
  }

  /* ---------------- scan orchestrator ---------------- */
  async scan(dbSession, { onProgress = () => {} } = {}) {
    const entry = this.getEntry(dbSession.id);
    if (!entry) throw Object.assign(new Error('session not found'), { status: 404 });
    const sim = entry.sim;
    const stages = ['connect', 'protocol', 'discover', 'vin', 'dtc', 'freeze', 'ecu_info', 'done'];
    const stagePct = { connect: 5, protocol: 12, discover: 25, vin: 45, dtc: 70, freeze: 82, ecu_info: 92, done: 100 };

    const report = { startedAt: new Date().toISOString(), stages: [], dtcs: [], vin: null, freezeFrame: null, ecus: [] };
    // Expand possibly-space-compacted hex tokens into byte pairs (defensive).
    const hexBytes = (tokens) => tokens
      .flatMap((t) => (t.length > 2 && /^[0-9a-f]+$/i.test(t) ? t.match(/../g) : [t]))
      .map((t) => parseInt(t, 16));
    for (const stage of stages) {
      onProgress({ pct: stagePct[stage], stage });
      report.stages.push(stage);
      switch (stage) {
        case 'connect': {
          sim.elmCommand('ATZ');
          sim.elmCommand('ATE0'); sim.elmCommand('ATL0'); sim.elmCommand('ATSP6');
          break;
        }
        case 'protocol': {
          const resp = sim.elmCommand('ATDPN');
          report.protocol = resp.replace(/\r/g, '').trim();
          break;
        }
        case 'discover': {
          const supported = sim.elmCommand('0100').replace(/\r/g, '').trim();
          report.pidsSupported = supported;
          for (const ecu of sim.profile().ecus) {
            report.ecus.push({
              ecuId: ecu.ecuId,
              name: ecu.name,
              protocol: sim.profile().protocol,
              dtcCount: sim.readDtcs(ecu.ecuId, 'stored').length,
              status: 'discovered',
            });
          }
          break;
        }
        case 'vin': {
          const line = sim.elmCommand('0902').split('\r').filter((l) => l.startsWith('49')).pop() || '';
          const bytes = hexBytes(line.split(/\s+/).slice(2));
          const payload = bytes.slice(1); // skip the info-type count byte
          report.vin = payload.map((b) => String.fromCharCode(b)).join('').trim() || sim.vin();
          break;
        }
        case 'dtc': {
          const elm03 = sim.elmCommand('03').split('\r').filter((l) => l.startsWith('43')).pop() || '';
          const tokens = elm03.split(/\s+/).slice(1);
          const obdCount = parseInt(tokens[0], 16) || 0;
          const obdCodes = parseDtcPayload(hexBytes(tokens.slice(1))).slice(0, obdCount);
          const seen = new Set();
          const add = (d, status, statusBits) => {
            const key = `${d.ecuId}:${d.code}:${status}`;
            if (seen.has(key)) return;
            seen.add(key);
            report.dtcs.push({ ...d, ...decodeMany([d.code])[0], status, statusBits });
          };
          for (const ecu of sim.profile().ecus) {
            for (const d of sim.readDtcs(ecu.ecuId, 'stored')) {
              // OBD evidence: the code appeared on the shared mode 03 bus response
              const onBus = obdCodes.includes(d.code);
              add({ ecuId: ecu.ecuId, ecuName: ecu.name, code: d.code }, 'stored', { confirmedDtc: true, onBus });
            }
            for (const d of sim.readDtcs(ecu.ecuId, 'pending')) {
              add({ ecuId: ecu.ecuId, ecuName: ecu.name, code: d.code }, 'pending', { pendingDtc: true });
            }
          }
          break;
        }
        case 'freeze': {
          const ff = sim.elmCommand('0200').replace(/\r/g, '').trim();
          const stored = sim.vehicle.getEcu('ecm').dtcs.find((d) => d.status & 0x08 && d.freeze);
          if (stored && stored.freeze) {
            const values = {};
            for (const [pid, v] of Object.entries(stored.freeze.values)) {
              const def = decodePid(parseInt(pid, 10), [v >> 8, v & 0xff]);
              if (def) values[def.name] = { value: def.value, unit: def.unit };
            }
            report.freezeFrame = { code: stored.code, values };
          }
          break;
        }
        case 'ecu_info': {
          report.ecuInfo = { vin: sim.vin(), calid: sim.vehicle.calid('ecm'), cvn: sim.vehicle.cvn('ecm'), ecuName: sim.vehicle.ecuName('ecm'), odometerKm: sim.vehicle.odometer() };
          break;
        }
        case 'done': break;
      }
      // respect real-ish scan pacing
      await new Promise((r) => setTimeout(r, 220));
    }

    report.completedAt = new Date().toISOString();
    report.durationMs = new Date(report.completedAt) - new Date(report.startedAt);
    dbSession.scan = report;
    dbSession.status = 'completed';
    dbSession.dtcCount = report.dtcs.filter((d) => d.status === 'stored').length;
    dbSession.updatedAt = new Date().toISOString();
    this.store.scheduleFlush();
    this.recordEvent(dbSession, 'scan', { dtcCount: report.dtcCount, durationMs: report.durationMs });
    this.notify(dbSession.userId, {
      type: 'scan_complete',
      title: 'Scan complete',
      body: `${report.dtcs.filter((d) => d.status === 'stored').length} stored DTC(s) on ${dbSession.profileName || dbSession.profileId}`,
      sessionId: dbSession.id,
    });
    onProgress({ pct: 100, stage: 'done' });
    return report;
  }

  recordEvent(dbSession, kind, detail) {
    const events = this.store.collection('sessions');
    const s = events.find((x) => x.id === dbSession.id);
    if (s) {
      s.events = s.events || [];
      s.events.push({ ts: new Date().toISOString(), kind, detail });
      if (s.events.length > 500) s.events = s.events.slice(-500);
    }
    this.store.scheduleFlush();
  }

  shutdown() {
    for (const id of [...this.live.keys()]) this.detach(id);
  }
}

module.exports = { DiagnosticRuntime, VEHICLE_PROFILES };
