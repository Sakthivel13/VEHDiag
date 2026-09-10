'use strict';
/**
 * VEHDiag Simulator — UDS server over ISO-TP (virtual CAN).
 *
 * Each virtual ECU answers UDS requests addressed to its diagnostic CAN ID.
 * Requests go through a real ISO-TP reassembly/segmentation path, so the
 * same client code that talks to a vehicle works against the simulator.
 */

const { CanFrame } = require('../can');
const { IsoTpReceiver, IsoTpSender, FC_CONTINUE } = require('../isotp');
const { UdsError, SERVICES, NRC, SESSION_TYPES, parseDtcReport, negativeResponse, positiveResponse } = require('../uds');
const { registry } = require('../ecu');

/**
 * Attach a UDS stack to one virtual ECU on a CAN bus.
 * @param bus SimulationBus
 * @param vehicle VirtualVehicle
 * @param ecuId e.g. 'ecm'
 */
function attachUdsEcu(bus, vehicle, ecuId, { onFrame = () => {} } = {}) {
  const ecu = vehicle.getEcu(ecuId);
  if (!ecu) throw new Error(`no ECU ${ecuId} in vehicle`);
  const def = registry.get(ecuId);
  const txId = def ? def.can.txId : 0x7e8; // ECU transmits on this id
  const rxId = def ? def.can.rxId : 0x7e0; // ECU receives requests on this id

  const sender = new IsoTpSender({
    txId, rxId,
    sendFrame: async (f) => { const ok = await bus.send(f); return !!ok; },
    onLog: (e) => onFrame({ ...e, ecu: ecuId }),
  });

  const receiver = new IsoTpReceiver({
    txId, rxId,
    onMessage: async (msg) => {
      try {
        const request = msg.data;
        const response = await handleUdsRequest(vehicle, ecuId, request, sender, onFrame);
        if (response) {
          await sender.send(response);
        }
      } catch (e) {
        onFrame({ dir: 'error', ecu: ecuId, error: e.code || e.message });
      }
    },
    onError: (err) => onFrame({ dir: 'error', ecu: ecuId, error: err.code || err.message }),
  });

  const rx = async (frame) => {
    onFrame({ dir: 'rx', ecu: ecuId, frame });
    try {
      // Route Flow Control frames to the sender's segmentation state machine.
      if (frame.data.length && (frame.data[0] & 0xf0) === 0x30) {
        sender.handleFlowControl(frame);
        return;
      }
      const fc = receiver.onFrame(frame);
      if (fc && fc.frame) {
        // FC is addressed back to the tester on the ECU's transmit id.
        await sender.sendFrame({ id: txId, extended: false, dlc: 8, data: fc.frame });
      }
    } catch (e) {
      onFrame({ dir: 'error', ecu: ecuId, error: e.code || e.message });
    }
  };

  bus.attachNode(`uds-${ecuId}`, [rxId], rx);
  return {
    detach: () => bus.detachNode(`uds-${ecuId}`),
    txId, rxId,
  };
}

/** Encode a scalar value into a 16-bit DID payload with scale/offset. */
function encodeDid(didDef, value) {
  if (didDef.raw) return [value & 0xff, (value >> 8) & 0xff];
  if (didDef.ascii) return [...String(value).padEnd(didDef.bytes, ' ').slice(0, didDef.bytes)].map((c) => c.charCodeAt(0));
  const scaled = Math.round((value - (didDef.offset || 0)) / (didDef.scale || 1));
  return [(scaled >> 8) & 0xff, scaled & 0xff];
}

/**
 * The simulated ECU's UDS application layer.
 * Implemented against the same public service definitions the client uses.
 */
async function handleUdsRequest(vehicle, ecuId, req, sender, onFrame) {
  const ecu = vehicle.getEcu(ecuId);
  const def = registry.get(ecuId) || {};
  const sid = req[0];
  const sub = req.length > 1 ? req[1] : null;
  const supported = def.supportedServices || [];

  onFrame({ dir: 'uds', ecu: ecuId, request: req.map((b) => b.toString(16).padStart(2, '0')).join(' ') });

  const nrc = (code) => negativeResponse(sid, code);

  // Fault injection: the ECU simply never answers (client must time out cleanly).
  if (vehicle.hasFault('no_response')) return null;

  if (vehicle.hasFault('nrc78') && sid !== SERVICES.TesterPresent) {
    await sleep(400);
  }

  // unsupported service?
  if (!supported.includes(sid)) return nrc(NRC.ServiceNotSupported);
  if (vehicle.hasFault('uds_reject')) return nrc(NRC.ConditionsNotCorrect);

  switch (sid) {
    case SERVICES.DiagnosticSessionControl: {
      if (![0x01, 0x02, 0x03, 0x04].includes(sub)) return nrc(NRC.SubFunctionNotSupported);
      ecu.session = sub;
      return positiveResponse(sid, [sub, 0x00, 0x13, 0x88, 0x00, 0x32]); // P2=5000ms, P2*=50ms
    }
    case SERVICES.EcuReset: {
      if (![0x01, 0x02, 0x03].includes(sub)) return nrc(NRC.SubFunctionNotSupported);
      ecu.session = 0x01;
      ecu.authenticated = false;
      return positiveResponse(sid, [sub]);
    }
    case SERVICES.TesterPresent: {
      if (sub !== 0x00 && sub !== 0x80) return nrc(NRC.SubFunctionNotSupported);
      if (sub === 0x80) return []; // suppress positive response
      return positiveResponse(sid, [sub]);
    }
    case SERVICES.ReadDataByIdentifier: {
      const did = (req[1] << 8) | req[2];
      const didDef = def.dids && def.dids[did];
      if (!didDef) return nrc(NRC.RequestOutOfRange);
      let value;
      if (did === 0xf190 || did === 0x0090) value = vehicle.vin();
      else {
        const signalKey = ecu.dids && ecu.dids[did];
        value = signalKey ? vehicle.signalValue(ecuId, signalKey) : null;
        if (value === null || value === undefined) return nrc(NRC.RequestOutOfRange);
      }
      return positiveResponse(sid, [(did >> 8) & 0xff, did & 0xff, ...encodeDid(didDef, value)]);
    }
    case SERVICES.ReadDtcInformation: {
      if (sub !== 0x02) return nrc(NRC.SubFunctionNotSupported);
      const statusMask = req[2] || 0x09;
      const dtcs = ecu.dtcs.filter((d) => d.status & statusMask);
      const payload = [];
      payload.push(0x02, 0xff, 0xff); // sub-function, availability mask, DTC status availability
      for (const d of dtcs) {
        const b1 = { P: 0, C: 1, B: 2, U: 3 }[d.code[0]] << 6 | parseInt(d.code[1], 16) << 4 | parseInt(d.code[2], 10);
        const b2 = parseInt(d.code[3], 10) << 4 | parseInt(d.code[4], 10);
        payload.push(d.status, b1, b2, 0x00);
      }
      return positiveResponse(sid, payload);
    }
    case SERVICES.ClearDiagnosticInformation: {
      vehicle.clearDtcs(ecuId);
      return positiveResponse(sid);
    }
    case SERVICES.SecurityAccess: {
      // odd sub-functions request a seed; the following even sub-function sends the key
      if (![0x01, 0x02, 0x03, 0x04, 0x05, 0x06].includes(sub)) return nrc(NRC.SubFunctionNotSupported);
      if (sub % 2 === 1) {
        // seed request — simulator uses a documented demo algorithm only
        const seed = [0x31, 0xD4, 0x42];
        ecu._pendingSeed = seed;
        return positiveResponse(sid, [sub, ...seed]);
      } else {
        const key = req.slice(2);
        const expected = ecu._pendingSeed ? ecu._pendingSeed.map((b) => (b + 0x5a) & 0xff) : [];
        const match = key.length === expected.length && key.every((b, i) => b === expected[i]);
        if (!match) return nrc(NRC.InvalidKey);
        ecu.authenticated = true;
        ecu.securityLevel = sub;
        return positiveResponse(sid, [sub]);
      }
    }
    case SERVICES.WriteDataByIdentifier: {
      if (!ecu.authenticated) return nrc(NRC.SecurityAccessDenied);
      return positiveResponse(sid, [req[1], req[2]]);
    }
    case SERVICES.RoutineControl: {
      if (!ecu.authenticated && ecuId !== 'ecm') return nrc(NRC.SecurityAccessDenied);
      return positiveResponse(sid, [sub, req[2], req[3]]);
    }
    case SERVICES.RequestDownload: {
      return nrc(NRC.UploadDownloadNotAccepted); // flashing not authorized in simulator
    }
    case SERVICES.TransferData: return nrc(NRC.RequestSequenceError);
    case SERVICES.RequestTransferExit: return nrc(NRC.RequestSequenceError);
    default: return nrc(NRC.ServiceNotSupported);
  }
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

module.exports = { attachUdsEcu, handleUdsRequest };
