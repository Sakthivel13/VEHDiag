'use strict';
/**
 * VEHDiag — CAN bus abstraction (CAN 2.0A/2.0B).
 * CanFrame model + transport-agnostic CanInterface (hardware adapters
 * implement this) + deterministic SimulationBus used by the simulator.
 *
 * SimulationBus contract (used by the simulator):
 *   new SimulationBus(name)
 *   bus.attachNode(name, [rxIds], handler) -> handle
 *   bus.detachNode(name)
 *   bus.send(frame) -> Promise<boolean>
 *   fault injection: injectError/setDropRate/setLatency/clearFaults
 */

const CAN_MAX_DLC = 8;

const CAN_ERRORS = {
  NONE: 0,
  BUS_OFF: 1,
  BIT_ERROR: 2,
  STUFF_ERROR: 3,
  CRC_ERROR: 4,
  ACK_ERROR: 5,
  FORM_ERROR: 6,
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class CanFrame {
  constructor({ id = 0, data = [], extended = false, remote = false, timestamp = Date.now() } = {}) {
    if (id < 0 || id > 0x1fffffff) throw new Error(`CAN id out of range: ${id}`);
    if (data.length > CAN_MAX_DLC) throw new Error(`CAN data longer than ${CAN_MAX_DLC} bytes`);
    this.id = id;
    this.data = Uint8Array.from(data);
    this.extended = !!extended;
    this.remote = !!remote;
    this.timestamp = timestamp;
  }
  get dlc() { return this.data.length; }
  toString() {
    return `${this.id.toString(16).toUpperCase().padStart(this.extended ? 8 : 3, '0')}#${Array.from(this.data, (b) => b.toString(16).toUpperCase().padStart(2, '0')).join('')}`;
  }
}

/** Adapter interface — real buses (SocketCAN, PCAN, Kvaser, Vector XL, ELM327) implement this. */
class CanInterface {
  constructor() { this.name = 'unconfigured'; this._open = false; }
  open() { throw new Error('not implemented'); }
  close() { throw new Error('not implemented'); }
  write(frame) { throw new Error('not implemented'); }
  onFrame(handler) { throw new Error('not implemented'); }
  get isOpen() { return this._open; }
}

/** In-memory CAN bus with node filters, latency/drop/error injection. */
class SimulationBus extends CanInterface {
  constructor(name = 'sim-bus', options = {}) {
    super();
    this.name = name;
    this.nodes = new Map(); // name -> { rxIds:Set, handler }
    this.errorState = CAN_ERRORS.NONE;
    this.latencyMs = options.latencyMs || 0;
    this.dropRate = 0;
    this.frames = []; // bounded trace for tests/observability
    this.onTrace = options.onTrace || (() => {});
    this._open = true;
  }

  open() { this._open = true; return this; }
  close() { this._open = false; this.nodes.clear(); }

  /** Attach a node listening on specific rx IDs; returns a handle. */
  attachNode(name, rxIds = [], handler = () => {}) {
    if (this.nodes.has(name)) throw new Error(`node ${name} already attached`);
    const ids = new Set(Array.isArray(rxIds) ? rxIds : [rxIds]);
    this.nodes.set(name, { rxIds: ids, handler });
    return { name, detach: () => this.detachNode(name) };
  }

  detachNode(name) { this.nodes.delete(name); }

  /** Transmit a frame (async to model bus latency); resolves delivery ok?. */
  async send(frame) {
    if (!this._open) return false;
    const f = frame instanceof CanFrame ? frame : new CanFrame({ id: frame.id, data: frame.data, extended: !!frame.extended });
    this.frames.push(f);
    if (this.frames.length > 2000) this.frames.shift();
    try { this.onTrace(f); } catch (e) { /* trace is best-effort */ }
    if (this.errorState === CAN_ERRORS.BUS_OFF) return false;
    if (this.dropRate > 0 && Math.random() < this.dropRate) return false;
    if (this.latencyMs > 0) await sleep(this.latencyMs);
    for (const node of this.nodes.values()) {
      if (node.rxIds.size > 0 && !node.rxIds.has(f.id)) continue;
      try {
        await node.handler({ id: f.id, extended: f.extended, dlc: f.data.length, data: Array.from(f.data) });
      } catch (e) {
        try { this.onTrace({ error: `handler ${node.name || '?'}: ${e.message}` }); } catch (x) { /* noop */ }
      }
    }
    return true;
  }

  /** Sync fire-and-forget transmit (for callers that don't need delivery). */
  write(frame) {
    this.send(frame).catch(() => {});
    return true;
  }

  injectError(state) { this.errorState = state; return this; }
  setDropRate(rate) { this.dropRate = Math.max(0, Math.min(1, rate)); return this; }
  setLatency(ms) { this.latencyMs = Math.max(0, ms); return this; }
  clearFaults() { this.errorState = CAN_ERRORS.NONE; this.dropRate = 0; this.latencyMs = 0; return this; }
}

module.exports = { CanFrame, CanInterface, SimulationBus, CAN_MAX_DLC, CAN_ERRORS };
