'use strict';
/**
 * VEHDiag — diagnostics engine tests (pure logic, no hardware).
 * Run: node --test tests/engine/
 */

const { test } = require('node:test');
const assert = require('node:assert');

const obd = require('../../diagnostics/obd');
const { CanFrame, SimulationBus, CAN_ERRORS } = require('../../diagnostics/can');
const { IsoTpReceiver, IsoTpSender, IsoTpError, ISO_TP_ERRORS } = require('../../diagnostics/isotp');
const { UdsSession, SERVICES } = require('../../diagnostics/uds');
const dtc = require('../../diagnostics/dtc');
const { registry } = require('../../diagnostics/ecu');

test('OBD: PID decode formulas are correct', () => {
  assert.deepEqual(obd.decodePid(0x0c, [0x1a, 0xf8]).value, 1726); // RPM (A*256+B)/4
  assert.equal(obd.decodePid(0x05, [0x80]).value, 88); // ECT A-40
  assert.equal(obd.decodePid(0x04, [0x80]).value, 50.2); // load %
  assert.equal(obd.decodePid(0x0d, [0x3e]).value, 62); // speed km/h
  assert.equal(obd.decodePid(0x42, [0x37, 0x04]).value, 14.08); // voltage /1000
  assert.equal(obd.decodePid(0x42, [0x37, 0x04]).value, 14.08);
});

test('OBD: encodePid inverts decodePid for key PIDs', () => {
  for (const pid of [0x04, 0x05, 0x0c, 0x0d, 0x0f, 0x11, 0x2f, 0x42, 0x1f]) {
    const def = obd.PIDS[pid];
    const sample = (def.min !== undefined ? def.min : 0) + ((def.max !== undefined ? def.max : 100) - (def.min !== undefined ? def.min : 0)) / 2;
    const encoded = obd.encodePid(pid, sample);
    const decoded = obd.decodePid(pid, encoded.slice(0, def.bytes || 2));
    assert.ok(Math.abs(decoded.value - sample) < Math.max(2, sample * 0.02), `roundtrip ${pid.toString(16)}: ${decoded.value} vs ${sample}`);
  }
});

test('OBD: DTC packing round-trips (J1979)', () => {
  const codes = ['P0130', 'P0351', 'C0561', 'B1000', 'U0100'];
  const packed = obd.encodeDtcs(codes);
  assert.equal(packed.length, codes.length * 2);
  assert.deepEqual(obd.decodeDtcs(packed), codes);
});

test('OBD: parsePidResponse parses mode 01 lines', () => {
  const r = obd.parsePidResponse('41 0C 1A F8');
  assert.equal(r.pid, 0x0c);
  assert.deepEqual([...r.data], [0x1a, 0xf8]);
  assert.equal(obd.parsePidResponse('43 01 33'), null); // not mode 41
});

test('CAN: frame encoding and bus routing', async () => {
  const bus = new SimulationBus();
  const got = [];
  bus.attachNode('tester', [0x7e8], (f) => got.push(f));
  const ok = await bus.send(new CanFrame({ id: 0x7e8, data: [0x06, 0x41, 0x0c, 0x1a, 0xf8] }));
  assert.equal(ok, true);
  assert.equal(got.length, 1);
  assert.equal(got[0].id, 0x7e8);
  assert.deepEqual(got[0].data, [0x06, 0x41, 0x0c, 0x1a, 0xf8]);
  // filter check: non-matching id not delivered
  await bus.send(new CanFrame({ id: 0x123, data: [0x01] }));
  assert.equal(got.length, 1);
});

test('CAN: extended IDs and DLC limits', () => {
  const f = new CanFrame({ id: 0x18db33f1, extended: true, data: [1, 2, 3] });
  assert.match(f.toString(), /^18DB33F1#010203$/);
  assert.throws(() => new CanFrame({ id: 0x7e8, data: [0, 1, 2, 3, 4, 5, 6, 7, 8] }));
  assert.throws(() => new CanFrame({ id: -1 }));
});

test('CAN: fault injection drops frames and clears', async () => {
  const bus = new SimulationBus();
  const got = [];
  bus.attachNode('a', [1], (f) => got.push(f));
  bus.setDropRate(1);
  await bus.send(new CanFrame({ id: 1, data: [1] }));
  assert.equal(got.length, 0);
  bus.clearFaults();
  await bus.send(new CanFrame({ id: 1, data: [1] }));
  assert.equal(got.length, 1);
  bus.injectError(CAN_ERRORS.BUS_OFF);
  assert.equal(await bus.send(new CanFrame({ id: 1, data: [1] })), false);
  assert.equal(got.length, 1); // bus-off: write refused
});

test('ISO-TP: single frame round trip through a wire pair', async () => {
  const wire = [];
  let received = null;
  const rx = new IsoTpReceiver({ txId: 2, rxId: 1, onMessage: (msg) => { received = msg.data; } });
  const tx = new IsoTpSender({ txId: 1, rxId: 2, sendFrame: async (f) => { wire.push(f); return true; } });
  await tx.send([0x3e, 0x00]);
  assert.equal(wire.length, 1);
  rx.onFrame(wire[0]);
  assert.deepEqual(received, [0x3e, 0x00]);
});

test('ISO-TP: multi-frame message with flow control', async () => {
  const payload = Array.from({ length: 40 }, (_, i) => i); // 40 bytes → FF + 5 CF
  let received = null;
  let receiverError = null;
  const rx = new IsoTpReceiver({
    txId: 2, rxId: 1,
    onMessage: (msg) => { received = msg.data; },
    onError: (e) => { receiverError = e; },
  });
  const wire = [];
  const tx = new IsoTpSender({
    txId: 1, rxId: 2,
    // inline delivery mirrors the simulated bus: frames route as they are emitted
    sendFrame: async (f) => {
      wire.push(f);
      if ((f.data[0] & 0xf0) === 0x30) { tx.handleFlowControl(f); return true; }
      const fc = rx.onFrame(f);
      if (fc && fc.frame) tx.handleFlowControl({ id: 1, data: fc.frame });
      return true;
    },
  });
  await tx.send(payload);
  assert.equal(receiverError, null);
  assert.deepEqual(received, payload);
  assert.ok(wire.some((f) => (f.data[0] & 0xf0) === 0x10), 'FF present');
  assert.ok(wire.filter((f) => (f.data[0] & 0xf0) === 0x20).length >= 4, 'CFs present');
});

test('ISO-TP: sequence number violations are detected', () => {
  let err = null;
  const rx = new IsoTpReceiver({ txId: 2, rxId: 1, onError: (e) => { err = e; } });
  const fc = rx.onFrame({ data: [0x10, 0x10, 1, 2, 3, 4, 5, 6] }); // FF: length 16
  assert.ok(fc && fc.frame, 'FF must produce an FC');
  rx.onFrame({ data: [0x21, 9] }); // SN 1 ✓
  rx.onFrame({ data: [0x23, 11] }); // expected SN 2, got 3 → error
  assert.equal(err.code, ISO_TP_ERRORS.WRONG_SN);
});

test('ISO-TP: sender times out without flow control', async () => {
  const keepAlive = setInterval(() => {}, 20); // unref'd timers don't hold the loop in tests
  try {
    const sender = new IsoTpSender({ txId: 1, rxId: 2, sendFrame: async () => true, options: { timeoutMs: 30 } });
    await assert.rejects(
      sender.send(Array.from({ length: 30 }, (_, i) => i)),
      (e) => e instanceof IsoTpError && e.code === ISO_TP_ERRORS.TIMEOUT_FC
    );
  } finally {
    clearInterval(keepAlive);
  }
});

test('UDS: negative response parsing and NRC names', async () => {
  const fake = { request: async () => [0x7f, 0x22, 0x31] };
  const s = new UdsSession(fake, { retries: 0 });
  const r = await s._once([0x22, 0xf1, 0x90]);
  assert.equal(r.negative, true);
  assert.equal(r.nrc, 0x31);
  assert.equal(r.name, 'requestOutOfRange');
});

test('UDS: response-pending (0x78) polling loops until done', async () => {
  let calls = 0;
  const fake = {
    request: async (bytes) => {
      calls++;
      if (bytes[0] === SERVICES.TESTER_PRESENT && calls < 4) return [0x7f, 0x3e, 0x78];
      if (calls < 4) return [0x7f, 0x22, 0x78];
      return [0x62, 0xf1, 0x90, 0x41];
    },
  };
  const s = new UdsSession(fake, { retries: 0 });
  const r = await s.request([0x22, 0xf1, 0x90]);
  assert.deepEqual(r, [0x62, 0xf1, 0x90, 0x41]);
  assert.ok(calls >= 4);
});

test('UDS: timeout surfaces as error object, not a hang', async () => {
  const keepAlive = setInterval(() => {}, 20);
  try {
    const fake = { request: async () => new Promise(() => {}) };
    const s = new UdsSession(fake, { timeoutMs: 30, retries: 0 });
    const r = await s._once([0x3e, 0x00]);
    assert.equal(r.negative, true);
    assert.equal(r.error, 'uds_timeout');
  } finally {
    clearInterval(keepAlive);
  }
});

test('DTC: validity, decode, severity and library', () => {
  assert.equal(dtc.isValid('P0130'), true);
  assert.equal(dtc.isValid('P01300'), false);
  assert.equal(dtc.isValid('X0130'), false);
  const d = dtc.decode('P0130');
  assert.equal(d.system, 'Powertrain');
  assert.equal(d.generic, false); // third char '1' → manufacturer range
  assert.equal(dtc.decode('P0030').generic, true); // third char '0' → generic
  assert.equal(dtc.decode('B1000').system, 'Body');
  assert.equal(dtc.decode('U0100').system, 'Network');
  const l = dtc.lookup('P0130');
  assert.equal(l.severity, 3);
  assert.match(l.description, /O2/i);
  assert.equal(dtc.lookup('P9999').description, 'DTC P9999 — see manufacturer documentation');
});

test('ECU registry: addressing and capabilities', () => {
  const ecm = registry.get('ecm');
  assert.equal(ecm.can.txId, 0x7e8);
  assert.equal(ecm.can.rxId, 0x7e0);
  assert.ok(ecm.supportedServices.includes(0x27));
  const bms = registry.get('bms');
  assert.equal(bms.can.txId, 0x628);
  assert.equal(bms.dids[0x1001].unit, '%');
  assert.equal(registry.forKind('ev').length, 4);
  assert.equal(registry.list().length, 7);
});
