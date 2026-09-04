'use strict';
/**
 * VEHDiag Simulator — ISO-TP client transport over the virtual CAN bus.
 * Used by the API/dashboard UDS console so requests traverse the same
 * segmentation/reassembly path a real vehicle uses.
 */

const { IsoTpSender, IsoTpReceiver, IsoTpError, ISO_TP_ERRORS, FLOW } = require('../isotp');

class IsotpTransport {
  /**
   * @param bus SimulationBus
   * @param txId diagnostic request CAN ID (e.g. 0x7E0)
   * @param rxId diagnostic response CAN ID (e.g. 0x7E8)
   */
  constructor(bus, txId, rxId, { onFrame = () => {}, timeout = 2000 } = {}) {
    this.bus = bus;
    this.txId = txId;
    this.rxId = rxId;
    this.timeout = timeout;
    this.onFrame = onFrame;
    this._pending = null;

    this.sender = new IsoTpSender({
      txId, rxId,
      sendFrame: async (f) => { const ok = await bus.send(f); if (!ok) throw new IsoTpError(ISO_TP_ERRORS.TIMEOUT, 'bus rejected frame'); return ok; },
      onLog: (e) => onFrame({ ...e, transport: 'isotp' }),
      options: { stmin: 10, blockSize: 8 },
    });

    this.receiver = new IsoTpReceiver({
      txId: rxId, rxId: txId,
      onMessage: (msg) => {
        if (this._pending) {
          const { resolve } = this._pending;
          this._pending = null;
          resolve(msg.data);
        }
      },
      onError: (e) => {
        if (this._pending) {
          const { reject } = this._pending;
          this._pending = null;
          reject(e);
        }
      },
    });

    this._node = async (frame) => {
      onFrame({ dir: 'rx', frame });
      try {
        // Route Flow Control frames to the sender (0x3 << 4 = 0x30 PCI type).
        if (frame.data.length && (frame.data[0] & 0xf0) === 0x30) {
          this.sender.handleFlowControl(frame);
          return;
        }
        const fc = this.receiver.onFrame(frame);
        if (fc && fc.frame) {
          // FC is addressed back to the ECU under test: use txId here.
          await this.sender.sendFrame({ id: txId, extended: false, dlc: 8, data: fc.frame });
        }
      } catch (e) {
        if (this._pending) {
          const { reject } = this._pending;
          this._pending = null;
          reject(e);
        }
      }
    };
    bus.attachNode(`isotp-client-${txId}`, [rxId], this._node);
  }

  detach() { this.bus.detachNode(`isotp-client-${this.txId}`); }

  /** Abandon any in-flight request (caller timed out). */
  cancel() {
    if (this._finishTimer) { clearTimeout(this._finishTimer); this._finishTimer = null; }
    this._pending = null;
  }

  /** UDS client contract: request(payload) -> Promise<response bytes>. */
  request(payload) { return this.send(payload); }

  /** Send a raw payload; resolves with the reassembled response payload. */
  send(payload, { awaitCompletion = true } = {}) {
    if (this._pending) throw new IsoTpError(ISO_TP_ERRORS.CANCELLED, 'transport busy');
    return new Promise((resolve, reject) => {
      this._pending = { resolve, reject };
      const t = setTimeout(() => {
        if (this._pending) {
          const { reject: rj } = this._pending;
          this._pending = null;
          rj(new IsoTpError(ISO_TP_ERRORS.TIMEOUT, 'ISO-TP response timeout'));
        }
      }, this.timeout);
      this.sender.send(payload, { awaitCompletion })
        .then(() => { /* response comes via receiver */ })
        .catch((e) => {
          clearTimeout(t);
          if (this._pending) { this._pending.reject(e); this._pending = null; }
        });
      this._finishTimer = t;
    });
  }
}

module.exports = { IsotpTransport };
