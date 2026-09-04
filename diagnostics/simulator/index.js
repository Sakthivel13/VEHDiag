'use strict';
/**
 * VEHDiag Simulator — public facade.
 *
 * A SimulatorSession owns one virtual vehicle with:
 *   - an ELM327 AT/OBD interpreter (string in → string out)
 *   - UDS-over-ISO-TP ECUs on a virtual CAN bus
 *   - live signal ticking
 *   - fault injection for failure-path testing
 */

const { VirtualVehicle, VEHICLE_PROFILES } = require('./virtual-vehicle');
const { Elm327Interpreter, PROTOCOLS } = require('./elm327');
const { SimulationBus } = require('../can');
const { attachUdsEcu } = require('./uds-server');
const { IsotpTransport } = require('./isotp-transport');
const { UdsSession, UdsError, SERVICES, NRC } = require('../uds');
const { registry } = require('../ecu');

let nextSessionId = 1;

class SimulatorSession {
  constructor(profileId, { seed, tickMs = 100, onFrame = () => {}, onLog = () => {} } = {}) {
    this.id = `sim-${Date.now()}-${nextSessionId++}`;
    this.profileId = profileId;
    this.vehicle = new VirtualVehicle(profileId, { seed, tickMs });
    this.elm = new Elm327Interpreter(this.vehicle, { onLog: (e) => onLog({ ...e, simId: this.id }) });
    this.bus = new SimulationBus(`bus-${this.id}`);
    this.onFrame = onFrame;
    this._udscs = new Map(); // ecuId -> { transport, session }
    this._attached = new Map(); // ecuId -> handle
    this.startedAt = new Date().toISOString();
    this.terminated = false;
  }

  start() {
    this.vehicle.start();
    for (const ecu of this.vehicle.profile.ecus) {
      const def = registry.get(ecu.ecuId);
      if (def && def.protocol !== 'uds' && ecu.ecuId !== 'ecm') continue; // OBD path only via ECM for OBD profiles
      const handle = attachUdsEcu(this.bus, this.vehicle, ecu.ecuId, { onFrame: (e) => this.onFrame({ ...e, simId: this.id }) });
      this._attached.set(ecu.ecuId, handle);
    }
  }

  stop() {
    this.vehicle.stop();
    for (const [id, h] of this._attached) { try { h.detach(); } catch (e) { /* noop */ } }
    for (const [, c] of this._udscs) c.transport.detach();
    this._attached.clear();
    this._udscs.clear();
    this.terminated = true;
  }

  /** ELM327: feed a line, get response string. */
  elmCommand(line) { return this.elm.handleLine(line); }

  /** Live snapshot of every signal of every ECU. */
  liveSnapshot() {
    const out = [];
    for (const ecu of this.vehicle.profile.ecus) {
      for (const [key, sig] of Object.entries(ecu.signals || {})) {
        out.push({
          ecuId: ecu.ecuId,
          ecuName: ecu.ecuName || ecu.ecuId.toUpperCase(),
          key,
          name: sig.name,
          unit: sig.unit,
          value: Math.round(sig.value * 1000) / 1000,
          pid: sig.pid || null,
        });
      }
    }
    return out;
  }

  readDtcs(ecuId, kind = 'stored') { return this.vehicle.readDtcs(ecuId, kind); }
  clearDtcs(ecuId) { this.vehicle.clearDtcs(ecuId); }
  vin() { return this.vehicle.vin(); }
  profile() {
    const p = this.vehicle.profile;
    return {
      id: p.id, name: p.name, type: p.type, vin: p.vin, model: p.model,
      year: p.year, fuel: p.fuel, transmission: p.transmission,
      odometerKm: this.vehicle.odometer(), protocol: p.protocol,
      ecus: this.vehicle.listEcus(),
    };
  }

  /** Get (or create) a UDS client session for an ECU — full CAN/ISO-TP path. */
  udsClient(ecuId) {
    let c = this._udscs.get(ecuId);
    if (c) return c;
    const def = registry.get(ecuId);
    if (!def) throw new Error(`unknown ECU ${ecuId}`);
    const transport = new IsotpTransport(this.bus, def.can.rxId, def.can.txId, {
      onFrame: (e) => this.onFrame({ ...e, simId: this.id }),
      timeout: 2500,
    });
    const session = new UdsSession(transport, { onLog: (e) => this.onFrame({ ...e, simId: this.id }) });
    c = { transport, session };
    this._udscs.set(ecuId, c);
    return c;
  }

  injectFault(name) { this.vehicle.injectFault(name); }
  clearFault(name) { this.vehicle.clearFault(name); }
  listFaults() { return [...this.vehicle.faults]; }
}

/** Registry of live sessions (for the API layer). */
const sessions = new Map();

function createSession(profileId, opts) {
  const s = new SimulatorSession(profileId, opts);
  s.start();
  sessions.set(s.id, s);
  return s;
}

function getSession(id) { return sessions.get(id) || null; }

function destroySession(id) {
  const s = sessions.get(id);
  if (s) { s.stop(); sessions.delete(id); }
}

module.exports = {
  SimulatorSession, createSession, getSession, destroySession, sessions,
  VirtualVehicle, VEHICLE_PROFILES, Elm327Interpreter, PROTOCOLS,
  IsotpTransport, UdsSession, UdsError, SERVICES, NRC, registry,
};
