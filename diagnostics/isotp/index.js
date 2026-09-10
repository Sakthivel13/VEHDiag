'use strict';
/**
 * VEHDiag — ISO-TP (ISO 15765-2) transport over CAN.
 * Sender/receiver with flow control, sequence numbers and timeouts.
 * Frames are plain objects { id, extended, dlc, data:number[] } so any
 * bus (virtual or hardware adapter) can carry them.
 *
 * Contract used by the simulator (and any real CAN adapter):
 *   new IsoTpSender({ txId, rxId, sendFrame, onLog, options })
 *     .send(payload) -> Promise      .handleFlowControl(frame)
 *     .sendFrame(frame) -> Promise   (raw low-level transmit)
 *   new IsoTpReceiver({ txId, rxId, onMessage, onError, options })
 *     .onFrame(frame) -> { frame:[...] } | null   (returns FC to emit)
 *     onMessage({ data }) / onError(IsoTpError)
 */

const PCI = { SINGLE: 0x0, FIRST: 0x1, CONSECUTIVE: 0x2, FLOW_CONTROL: 0x3 };

const ISO_TP_ERRORS = {
  TIMEOUT: 'timeout',
  TIMEOUT_FC: 'flow_control_timeout',
  TIMEOUT_CF: 'consecutive_frame_timeout',
  WRONG_SN: 'wrong_sequence_number',
  OVERFLOW: 'buffer_overflow',
  UNEXPECTED: 'unexpected_frame',
  CANCELLED: 'cancelled',
  BUSY: 'busy',
  NO_RESPONSE: 'no_response',
};

const FLOW = { CONTINUE: 0, WAIT: 1, ABORT: 2 };
const FC_CONTINUE = FLOW.CONTINUE;

const DEFAULTS = { stmin: 10, blockSize: 8, timeoutMs: 1000, maxLength: 4096 };

class IsoTpError extends Error {
  constructor(code, message) {
    super(message || code);
    this.name = 'IsoTpError';
    this.code = code;
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function pciType(raw) { return (raw & 0xf0) >> 4; }

/** Reassemble incoming frames; emits FC for multi-frame reception. */
class IsoTpReceiver {
  constructor({ txId, rxId, onMessage = () => {}, onError = () => {}, options = {} } = {}) {
    this.txId = txId;
    this.rxId = rxId;
    this.onMessage = onMessage;
    this.onError = onError;
    this.options = { ...DEFAULTS, ...options };
    this.reset();
  }

  reset() {
    this.buffer = [];
    this.expectedLength = 0;
    this.expectedSn = 1;
    this.receiving = false;
    this._clearTimer();
  }

  _clearTimer() { if (this.timer) { clearTimeout(this.timer); this.timer = null; } }

  onFrame(frame) {
    const data = frame.data;
    if (!data || data.length === 0) return null;
    switch (pciType(data[0])) {
      case PCI.SINGLE: {
        const len = data[0] & 0x0f;
        this._deliver(data.slice(1, 1 + len));
        return null;
      }
      case PCI.FIRST: {
        this.reset();
        this.expectedLength = ((data[0] & 0x0f) << 8) | data[1];
        if (this.expectedLength > this.options.maxLength) {
          this._fail(new IsoTpError(ISO_TP_ERRORS.OVERFLOW, `payload ${this.expectedLength} exceeds max ${this.options.maxLength}`));
          return { frame: [0x30 | FLOW.ABORT, 0, 0] };
        }
        this.buffer = Array.from(data.slice(2));
        this.expectedSn = 1;
        this.receiving = true;
        this._armTimer();
        return { frame: [0x30 | FLOW.CONTINUE, this.options.blockSize & 0xff, Math.min(0x7f, this.options.stmin) & 0xff] };
      }
      case PCI.CONSECUTIVE: {
        if (!this.receiving) { this._fail(new IsoTpError(ISO_TP_ERRORS.UNEXPECTED, 'CF without FF')); return null; }
        const sn = data[0] & 0x0f;
        if (sn !== this.expectedSn) { this._fail(new IsoTpError(ISO_TP_ERRORS.WRONG_SN, `expected ${this.expectedSn} got ${sn}`)); return null; }
        this.expectedSn = (this.expectedSn + 1) & 0x0f;
        this.buffer.push(...Array.from(data.slice(1)));
        if (this.buffer.length >= this.expectedLength) { this._deliver(this.buffer.slice(0, this.expectedLength)); return null; }
        this._armTimer();
        return null;
      }
      case PCI.FLOW_CONTROL:
        return null; // receivers never act on FC
      default:
        this._fail(new IsoTpError(ISO_TP_ERRORS.UNEXPECTED, `unknown PCI type ${pciType(data[0])}`));
        return null;
    }
  }

  _armTimer() {
    this._clearTimer();
    this.timer = setTimeout(() => this._fail(new IsoTpError(ISO_TP_ERRORS.TIMEOUT_CF, 'consecutive frame timeout')), this.options.timeoutMs);
    if (this.timer.unref) this.timer.unref();
  }

  _deliver(payload) {
    this._clearTimer();
    this.receiving = false;
    this.buffer = [];
    this.onMessage({ data: Array.from(payload) });
  }

  _fail(err) {
    this._clearTimer();
    this.receiving = false;
    this.buffer = [];
    this.onError(err);
  }
}

/** Segments outgoing payloads; waits for flow control on multi-frame sends. */
class IsoTpSender {
  constructor({ txId, rxId, sendFrame = async () => false, onLog = () => {}, options = {} } = {}) {
    this.txId = txId;
    this.rxId = rxId;
    this.onLog = onLog;
    this.options = { ...DEFAULTS, ...options };
    this._tx = sendFrame;
    this._active = null;
  }

  /** Raw low-level transmit (also used by owners to emit FC frames). */
  sendFrame(frame) { return this._tx(frame); }

  /** Segment + transmit a payload; resolves when transmission completes. */
  send(payload) {
    const data = Array.from(payload);
    const st = {
      data, offset: 0, sn: 1, blockLeft: 0, stminMs: this.options.stmin,
      done: false, resolve: null, reject: null, timeout: null,
    };
    const promise = new Promise((resolve, reject) => { st.resolve = resolve; st.reject = reject; });
    if (data.length <= 7) {
      // single frame — no flow control involved
      this._tx(this._frame([(PCI.SINGLE << 4) | data.length, ...data]))
        .then(() => this._finish(st))
        .catch((e) => this._fail(st, e instanceof IsoTpError ? e : new IsoTpError(ISO_TP_ERRORS.NO_RESPONSE, e.message)));
      return promise;
    }
    // multi-frame: fully arm state BEFORE transmitting the FF so an inline
    // FC (synchronous simulated bus) can never race past us.
    this._active = st;
    st.offset = 6;
    this._tx(this._frame([(PCI.FIRST << 4) | ((data.length >> 8) & 0x0f), data.length & 0xff, ...data.slice(0, 6)]))
      .catch((e) => this._fail(st, e instanceof IsoTpError ? e : new IsoTpError(ISO_TP_ERRORS.NO_RESPONSE, e.message)));
    this._armFcTimer(st);
    return promise;
  }

  /** Route an incoming FC frame into the active segmentation. */
  handleFlowControl(frame) {
    const st = this._active;
    if (!st || st.done) return;
    const fs = frame.data[0] & 0x0f;
    if (fs === FLOW.ABORT) { this._fail(st, new IsoTpError(ISO_TP_ERRORS.TIMEOUT_FC, 'receiver aborted (overflow)')); return; }
    if (fs === FLOW.WAIT) { this._armFcTimer(st); return; }
    st.blockLeft = (frame.data[1] || this.options.blockSize) & 0xff;
    const stmin = frame.data[2];
    st.stminMs = stmin >= 0x80 ? (stmin & 0x7f) * 1000 : stmin;
    this._sendConsecutive(st);
  }

  _frame(data) { return { id: this.txId, extended: false, dlc: 8, data }; }

  _armFcTimer(st) {
    if (st.timeout) clearTimeout(st.timeout);
    st.timeout = setTimeout(() => this._fail(st, new IsoTpError(ISO_TP_ERRORS.TIMEOUT_FC, 'flow control timeout')), this.options.timeoutMs);
    if (st.timeout.unref) st.timeout.unref();
  }

  async _sendConsecutive(st) {
    if (st.done) return;
    let count = 0;
    while (st.offset < st.data.length && count < st.blockLeft) {
      const chunk = st.data.slice(st.offset, st.offset + 7);
      st.offset += chunk.length;
      count++;
      const frame = this._frame([(PCI.CONSECUTIVE << 4) | (st.sn & 0x0f), ...chunk]);
      st.sn = (st.sn + 1) & 0x0f;
      try { await this._tx(frame); } catch (e) { return this._fail(st, new IsoTpError(ISO_TP_ERRORS.NO_RESPONSE, e.message)); }
      if (st.offset < st.data.length && count < st.blockLeft && st.stminMs > 0) await sleep(st.stminMs);
      if (st.done) return;
    }
    if (st.offset >= st.data.length) return this._finish(st);
    // block exhausted — wait for the next FC
    this._armFcTimer(st);
  }

  _finish(st) {
    if (st.done) return;
    st.done = true;
    this._active = null;
    if (st.timeout) clearTimeout(st.timeout);
    st.resolve();
  }

  _fail(st, err) {
    if (st.done) return;
    st.done = true;
    this._active = null;
    if (st.timeout) clearTimeout(st.timeout);
    st.reject(err);
  }
}

module.exports = { IsoTpReceiver, IsoTpSender, IsoTpError, ISO_TP_ERRORS, FLOW, FC_CONTINUE, PCI, DEFAULTS };
