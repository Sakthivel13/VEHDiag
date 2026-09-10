'use strict';
/**
 * VEHDiag — end-to-end API smoke test (runs against a live server).
 * Start the server, then: node tests/e2e/api-smoke.test.js
 */

const { test } = require('node:test');
const assert = require('node:assert');

const BASE = process.env.VEHDIAG_TEST_URL || 'http://127.0.0.1:8080';

async function j(method, path, body, token) {
  const r = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  let d;
  try { d = JSON.parse(text); } catch (e) { d = text; }
  return { status: r.status, d };
}

test('healthz is public and healthy', async () => {
  const r = await j('GET', '/api/v1/healthz');
  assert.equal(r.status, 200);
  assert.equal(r.d.data.status, 'ok');
});

test('auth: register → login → me, and 401 without token', async () => {
  const unauth = await j('GET', '/api/v1/vehicles');
  assert.equal(unauth.status, 401);

  const email = `tech-${Date.now()}@example.com`;
  const reg = await j('POST', '/api/v1/auth/register', { name: 'Test Tech', email, password: 'password123' });
  assert.equal(reg.status, 201);
  assert.ok(reg.d.data.token);

  const bad = await j('POST', '/api/v1/auth/login', { email, password: 'nope' });
  assert.equal(bad.status, 401);

  const login = await j('POST', '/api/v1/auth/login', { email, password: 'password123' });
  assert.equal(login.status, 200);
  const token = login.d.data.token;

  const me = await j('GET', '/api/v1/auth/me', null, token);
  assert.equal(me.status, 200);
  assert.equal(me.d.data.user.email, email);
  return { token, email };
});

test('vehicle lifecycle + VIN identify/decode', async (t) => {
  const email = `veh-${Date.now()}@example.com`;
  const reg = await j('POST', '/api/v1/auth/register', { name: 'Vin Tester', email, password: 'password123' });
  const token = reg.d.data.token;

  const created = await j('POST', '/api/v1/vehicles', { vin: 'MA3JF31S6MK441207', manufacturer: 'VEH', model: 'Atlas', year: 2021, fuel_type: 'petrol' }, token);
  assert.equal(created.status, 201);
  const vid = created.d.data.vehicle.id;

  const identify = await j('POST', `/api/v1/vehicles/${vid}/identify`, {}, token);
  assert.equal(identify.status, 200);
  assert.equal(identify.d.data.decoded.checkDigitValid, true);

  const patched = await j('PATCH', `/api/v1/vehicles/${vid}`, { mileage_km: 42000 }, token);
  assert.equal(patched.d.data.vehicle.mileage_km, 42000);

  const del = await j('DELETE', `/api/v1/vehicles/${vid}`, null, token);
  assert.equal(del.status, 200);
});

test('diagnostic session: scan finds real DTCs, VIN, freeze frame; UDS + ELM paths work', async (t) => {
  const email = `diag-${Date.now()}@example.com`;
  const reg = await j('POST', '/api/v1/auth/register', { name: 'Diag Tester', email, password: 'password123' });
  const token = reg.d.data.token;

  const profiles = await j('GET', '/api/v1/diagnostics/profiles', null, token);
  assert.ok(profiles.d.data.profiles.length >= 4);

  const created = await j('POST', '/api/v1/diagnostics/sessions', { profile_id: 'ice-sedan-2021' }, token);
  assert.equal(created.status, 201);
  assert.ok(created.d.data.simulator.id);
  const sid = created.d.data.session.id;

  const scanStart = await j('POST', `/api/v1/diagnostics/sessions/${sid}/scan`, {}, token);
  assert.equal(scanStart.status, 200);

  // poll until completed (max ~15s)
  let session = null;
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 500));
    const r = await j('GET', `/api/v1/diagnostics/sessions/${sid}`, null, token);
    session = r.d.data.session;
    if (session.status === 'completed' || session.status === 'failed') break;
  }
  assert.equal(session.status, 'completed');
  assert.equal(session.progress, 100);
  assert.equal(session.scan.vin, 'MA3JF31S6MK441207');
  assert.ok(session.scan.dtcs.filter((d) => d.status === 'stored').length >= 1);
  assert.ok(session.scan.freezeFrame && session.scan.freezeFrame.code === 'P0130');

  const dtcs = await j('GET', `/api/v1/diagnostics/sessions/${sid}/dtc?kind=all`, null, token);
  assert.ok(dtcs.d.data.dtcs.some((d) => d.code === 'P0130'));

  const elm = await j('POST', `/api/v1/diagnostics/sessions/${sid}/elm`, { line: '010C' }, token);
  assert.match(elm.d.data.response, /41 0C/i);

  const uds = await j('POST', `/api/v1/diagnostics/sessions/${sid}/uds`, { ecu: 'ecm', service: 0x22, sub: 0xf1, params: [0x90] }, token);
  assert.equal(uds.status, 200);
  assert.equal(Buffer.from(uds.d.data.response.slice(3)).toString().trim(), 'MA3JF31S6MK441207');

  // fault injection path
  const inject = await j('POST', `/api/v1/diagnostics/sessions/${sid}/faults`, { name: 'nrc78', active: true }, token);
  assert.ok(inject.d.data.faults.includes('nrc78'));
  await j('POST', `/api/v1/diagnostics/sessions/${sid}/faults`, { name: 'nrc78', active: false }, token);

  // clear DTCs
  const clear = await j('POST', `/api/v1/diagnostics/sessions/${sid}/clear-dtcs`, {}, token);
  assert.equal(clear.status, 200);
  const after = await j('GET', `/api/v1/diagnostics/sessions/${sid}/dtc?kind=stored`, null, token);
  assert.equal(after.d.data.dtcs.length, 0);

  // reports in all formats
  const rep = await j('POST', '/api/v1/reports', { session_id: sid }, token);
  assert.equal(rep.status, 201);
  const rid = rep.d.data.report.id;
  for (const f of ['json', 'csv', 'txt', 'html']) {
    const r = await j('GET', `/api/v1/reports/${rid}/download?format=${f}`, null, token);
    assert.equal(r.status, 200);
  }

  // session isolation: second session unaffected by first session's clear
  const s2 = await j('POST', '/api/v1/diagnostics/sessions', { profile_id: 'ice-sedan-2021' }, token);
  const sid2 = s2.d.data.session.id;
  const dtcs2 = await j('GET', `/api/v1/diagnostics/sessions/${sid2}/dtc?kind=stored`, null, token);
  assert.ok(dtcs2.d.data.dtcs.length >= 1, 'second session must have its own fresh DTC state');
  await j('DELETE', `/api/v1/diagnostics/sessions/${sid2}`, null, token);
});

test('devices: register + pair + raw AT test over TCP simulator', async (t) => {
  const email = `dev-${Date.now()}@example.com`;
  const reg = await j('POST', '/api/v1/auth/register', { name: 'Dev', email, password: 'password123' });
  const token = reg.d.data.token;

  const created = await j('POST', '/api/v1/devices', { kind: 'simulator', name: 'Virtual ELM327' }, token);
  assert.equal(created.status, 201);
  const did = created.d.data.device.id;

  const pair = await j('POST', `/api/v1/devices/${did}/pair`, {}, token);
  assert.equal(pair.status, 200);
  assert.equal(pair.d.data.pairResult.ok, true);

  const testr = await j('POST', `/api/v1/devices/${did}/test`, { line: 'ATI' }, token);
  assert.equal(testr.d.data.testResult.ok, true);
  assert.match(testr.d.data.testResult.response, /ELM327/);
});

test('subscriptions, notifications, admin gating, DTC library, ECUs', async (t) => {
  const email = `sub-${Date.now()}@example.com`;
  const reg = await j('POST', '/api/v1/auth/register', { name: 'Sub Tester', email, password: 'password123' });
  const token = reg.d.data.token;

  const plan = await j('POST', '/api/v1/subscriptions/select', { plan: 'pro' }, token);
  assert.equal(plan.d.data.subscription.plan, 'pro');

  const notif = await j('GET', '/api/v1/notifications', null, token);
  assert.ok(notif.d.data.notifications.length >= 2);

  const adminDenied = await j('GET', '/api/v1/admin/stats', null, token);
  assert.equal(adminDenied.status, 403);

  const dtcs = await j('GET', '/api/v1/dtc?q=P03', null, token);
  assert.ok(dtcs.d.data.dtcs.length >= 3);
  const one = await j('GET', '/api/v1/dtc/P0130', null, token);
  assert.equal(one.d.data.dtc.system, 'Powertrain');

  const ecus = await j('GET', '/api/v1/ecus', null, token);
  assert.ok(ecus.d.data.ecus.some((e) => e.id === 'bms'));
});

test('marketing site + dashboard SPA + 404 served', async () => {
  const home = await fetch(BASE + '/');
  assert.equal(home.status, 200);
  assert.match(await home.text(), /VEHDiag/);
  const dl = await fetch(BASE + '/downloads.html');
  assert.equal(dl.status, 200);
  const spa = await fetch(BASE + '/app/');
  assert.equal(spa.status, 200);
  const missing = await fetch(BASE + '/does-not-exist');
  assert.equal(missing.status, 404);
  const css = await fetch(BASE + '/css/style.css');
  assert.equal(css.status, 200);
  assert.match(css.headers.get('content-type'), /text\/css/);
});
