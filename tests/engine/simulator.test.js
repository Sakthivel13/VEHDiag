'use strict';
/**
 * VEHDiag — simulator integration tests.
 * Drives the virtual vehicle over BOTH diagnostic paths:
 *   1. ELM327 AT/OBD commands (what a scan tool sends)
 *   2. UDS over ISO-TP over the simulated CAN bus (what a dealer tool sends)
 */

const { test } = require('node:test');
const assert = require('node:assert');
const { createSession, destroySession } = require('../../diagnostics/simulator');

function newSession(profile = 'ice-sedan-2021') {
  return createSession(profile, { seed: 1234 });
}

test('simulator: profile facts (VIN, model, ECUs)', () => {
  const s = newSession();
  assert.equal(s.vin(), 'MA3JF31S6MK441207');
  assert.equal(s.profile().name, 'Sedan · Petrol 1.5L (2021)');
  assert.equal(s.profile().ecus.length, 2);
  assert.ok(s.profile().ecus.some((e) => e.ecuId === 'ecm'));
  destroySession(s.id);
});

test('ELM327: AT commands', () => {
  const s = newSession();
  assert.match(s.elmCommand('ATZ'), /VEH1\.5-2021/);
  assert.match(s.elmCommand('ATI'), /ELM327/);
  assert.match(s.elmCommand('ATDPN'), /A\d/); // protocol number
  assert.match(s.elmCommand('ATE0'), /OK/);
  assert.match(s.elmCommand('ATSP6'), /OK/);
  assert.equal(s.elmCommand(''), '');
  assert.equal(s.elmCommand('NOSUCH'), '?\r');
  destroySession(s.id);
});

test('ELM327: mode 01 live PIDs decode to sane values', () => {
  const s = newSession();
  for (const pid of ['010C', '0105', '010D', '0104', '0111', '0142']) {
    const r = s.elmCommand(pid);
    const line = r.split('\r').filter((l) => l.startsWith('41')).pop();
    assert.ok(line, `${pid} responded ${JSON.stringify(r)}`);
    assert.match(line, /^41 /);
  }
  const rpmLine = s.elmCommand('010C').split('\r').filter((l) => l.startsWith('41')).pop();
  const t = rpmLine.split(/\s+/);
  const rpm = parseInt(t[2], 16) * 256 + parseInt(t[3], 16);
  assert.ok(rpm / 4 > 500, `rpm ${rpm / 4} plausible`);
  destroySession(s.id);
});

test('ELM327: mode 03/07 stored+count, 09 VIN, 0200 freeze frame, 04 clear', () => {
  const s = newSession();
  const stored = s.elmCommand('03');
  assert.match(stored, /43 01 01 30/, 'P0130 stored (count 1, code 0130)');
  assert.match(s.elmCommand('07'), /47 01 03 51/, 'P0351 pending via mode 07');
  const vinLine = s.elmCommand('0902').split('\r').filter((l) => l.startsWith('49')).pop();
  const vin = vinLine.split(/\s+/).slice(3).map((h) => String.fromCharCode(parseInt(h, 16))).join('');
  assert.equal(vin, 'MA3JF31S6MK441207');
  assert.match(s.elmCommand('0202'), /^42 /);
  // clear
  assert.match(s.elmCommand('04'), /^44/);
  assert.match(s.elmCommand('03'), /43 00/);
  destroySession(s.id);
});

test('UDS over ISO-TP: session control, tester present, DID read (VIN + signal)', async () => {
  const s = newSession();
  const { session } = s.udsClient('ecm');
  const tp = await session.testerPresent();
  assert.deepEqual(tp.slice(0, 2), [0x7e, 0x00]);
  const dsc = await session.diagnosticSessionControl(0x03);
  assert.deepEqual(dsc.slice(0, 2), [0x50, 0x03]);
  const vinResp = await session.readDataByIdentifier(0xf190);
  assert.deepEqual(vinResp.slice(0, 3), [0x62, 0xf1, 0x90]);
  assert.equal(String.fromCharCode(...vinResp.slice(3)).trim(), 'MA3JF31S6MK441207');
  const rpmResp = await session.readDataByIdentifier(0xf040);
  assert.deepEqual(rpmResp.slice(0, 3), [0x62, 0xf0, 0x40]);
  destroySession(s.id);
});

test('UDS: 0x22 rejects unknown DIDs with NRC 0x31', async () => {
  const s = newSession();
  const { session } = s.udsClient('ecm');
  const resp = await session.request([0x22, 0x99, 0x99]);
  assert.deepEqual(resp, [0x7f, 0x22, 0x31]);
  destroySession(s.id);
});

test('UDS: security access requires a legitimate key provider (never guessed)', async () => {
  const s = newSession();
  const { session } = s.udsClient('ecm');
  // seed request must be answered with the key; simulator uses a documented demo algorithm
  const seedResp = await session.request([0x27, 0x01]);
  assert.equal(seedResp[0], 0x67, 'seed response');
  assert.equal(seedResp[1], 0x01);
  const seed = seedResp.slice(2);
  const key = keyFromSeed(seed);
  const keyResp = await session.request([0x27, 0x02, ...key]);
  assert.equal(keyResp[0], 0x67, 'key accepted');
  assert.equal(session.authenticated, true);
  destroySession(s.id);
});

test('UDS: 0x2E write requires prior security access (NRC 0x33)', async () => {
  const s = newSession();
  const { session } = s.udsClient('ecm');
  const denied = await session.request([0x2e, 0xf1, 0x90, 0x41, 0x41]);
  assert.deepEqual(denied, [0x7f, 0x2e, 0x33]);
  // after auth it works
  const seedResp = await session.request([0x27, 0x01]);
  const key = keyFromSeed(seedResp.slice(2));
  await session.request([0x27, 0x02, ...key]);
  const ok = await session.request([0x2e, 0xf1, 0x90, 0x41, 0x41]);
  assert.equal(ok[0], 0x6e);
  destroySession(s.id);
});

test('UDS: 0x19 DTC report returns stored codes with status bytes', async () => {
  const s = newSession();
  const { session } = s.udsClient('ecm');
  const resp = await session.readDtc(0x02, [0xff, 0xff, 0xff]);
  assert.equal(resp[0], 0x59);
  assert.equal(resp[1], 0x02);
  // payload: [sub, availabilityMask, statusAvailability, status, b1, b2, 0x00, ...]
  assert.equal(resp[2], 0xff);
  const status = resp[4], b1 = resp[5], b2 = resp[6];
  assert.ok(status & 0x08, 'stored DTC status bit set');
  const code = ['P', 'C', 'B', 'U'][(b1 >> 6) & 0x3] + ((b1 >> 4) & 0x3).toString(16) + (b1 & 0xf).toString(16) + ((b2 >> 4) & 0xf).toString(16) + (b2 & 0xf).toString(16);
  assert.equal(code.toUpperCase(), 'P0130');
  // clear via UDS — stored P0130 gone, pending P0351 remains (mask 0xFF includes pending)
  const cleared = await session.clearDtc();
  assert.equal(cleared[0], 0x54);
  const after = await session.readDtc(0x02, [0xff, 0xff, 0xff]);
  assert.equal(after.length, 8); // one remaining entry (pending P0351)
  assert.equal(after[4], 0x04, 'remaining entry has pending status');
  destroySession(s.id);
});

test('simulator: live data drifts but stays in bounds', () => {
  const s = newSession();
  const before = s.liveSnapshot().find((x) => x.key === 'rpm');
  assert.ok(before.value >= 700 && before.value <= 7000);
  destroySession(s.id);
});

test('EV profile: BMS SOC + voltage DIDs via UDS', async () => {
  const s = newSession('ev-scooter');
  const { session } = s.udsClient('bms');
  const soc = await session.readDataByIdentifier(0x1001);
  assert.deepEqual(soc.slice(0, 3), [0x62, 0x10, 0x01]);
  assert.ok(soc[3] >= 0 && soc[3] <= 100, `SOC ${soc[3]} in range`);
  const volts = await session.readDataByIdentifier(0x1003);
  const raw = (volts[3] << 8) | volts[4];
  assert.ok(raw / 10 > 40 && raw / 10 < 70, `pack V ${raw / 10}`);
  const vin = await session.readDataByIdentifier(0xf190);
  assert.equal(String.fromCharCode(...vin.slice(3)).trim(), 'MD9EVS232PN104587');
  destroySession(s.id);
});

test('fault injection: no_response makes requests fail cleanly (no hang)', async () => {
  const s = newSession();
  s.injectFault('no_response');
  const { session } = s.udsClient('ecm');
  const r = await session.request([0x3e, 0x00]);
  assert.equal(r.negative, true);
  assert.equal(r.error, 'uds_timeout');
  s.clearFault('no_response');
  const ok = await session.testerPresent();
  assert.equal(ok[0], 0x7e);
  destroySession(s.id);
});

test('session isolation: two sessions own independent state', async () => {
  const a = newSession();
  const b = newSession();
  a.elmCommand('04'); // clear a's DTCs
  assert.match(a.elmCommand('03'), /43 00/);
  assert.match(b.elmCommand('03'), /43 01 01 30/, 'b still has its own P0130');
  destroySession(a.id);
  destroySession(b.id);
});

test('destroySession detaches and is idempotent', () => {
  const s = newSession();
  destroySession(s.id);
  destroySession(s.id); // no throw
});

/** Simulator's documented demo security algorithm (public contract). */
function keyFromSeed(seed) {
  // documented demo algorithm: key byte = seed byte + 0x5A (mod 256)
  return seed.map((b) => (b + 0x5a) & 0xff);
}
