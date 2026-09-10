'use strict';
/**
 * VEHDiag — WebSocket realtime flow test (runs against a live server).
 *   ws → {auth} → auth:ok → live:subscribe → live:data (500ms cadence)
 *   → scan:progress (during async scan) → notification push (on report create)
 */

const { test } = require('node:test');
const assert = require('node:assert');

const HTTP = process.env.VEHDIAG_TEST_URL || 'http://127.0.0.1:8080';
const WS = HTTP.replace(/^http/, 'ws') + '/ws';

async function api(method, path, body, token) {
  const r = await fetch(HTTP + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  let d; try { d = JSON.parse(text); } catch (e) { d = text; }
  if (!r.ok) throw new Error(`${method} ${path} -> ${r.status}: ${JSON.stringify(d)}`);
  return d.data;
}

/** Minimal WS client with message queue. */
class WsClient {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.queue = [];
    this.waiters = [];
    this.ws.onmessage = (e) => {
      let m; try { m = JSON.parse(e.data); } catch (x) { m = e.data; }
      const w = this.waiters.shift();
      if (w) w(m); else this.queue.push(m);
    };
    this.ready = new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = () => reject(new Error('ws connect failed'));
    });
  }
  send(obj) { this.ws.send(JSON.stringify(obj)); }
  next(timeoutMs = 8000) {
    if (this.queue.length) return Promise.resolve(this.queue.shift());
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('ws message timeout')), timeoutMs);
      this.waiters.push((m) => { clearTimeout(t); resolve(m); });
    });
  }
  async expectType(type, timeoutMs) {
    const deadline = Date.now() + (timeoutMs || 8000);
    for (;;) {
      const m = await this.next(Math.max(200, deadline - Date.now()));
      if (m && m.type === type) return m;
      if (Date.now() > deadline) throw new Error(`expected ${type}, never received`);
    }
  }
  close() { try { this.ws.close(); } catch (e) { /* noop */ } }
}

test('WS: auth + live:data + scan:progress + notification flow', async (t) => {
  const sockets = [];
  const closeAll = () => sockets.forEach((s) => s.close());
  try {
    const email = `ws-${Date.now()}@example.com`;
    const reg = await api('POST', '/api/v1/auth/register', { name: 'WS Tester', email, password: 'password123' });
    const token = reg.token;

    // unauthenticated WS must be rejected for live subscribe
    const anon = new WsClient(WS);
    sockets.push(anon);
    await anon.ready;
    anon.send({ type: 'auth', token: 'garbage-token' });
    const anonResp = await anon.expectType('auth:fail');
    assert.ok(anonResp.message);
    anon.close();

    // real client
    const ws = new WsClient(WS);
    sockets.push(ws);
    await ws.ready;
    ws.send({ type: 'auth', token });
    const authOk = await ws.expectType('auth:ok');
    assert.ok(authOk.user && authOk.user.id);

    // create a session + subscribe to live data
    const session = await api('POST', '/api/v1/diagnostics/sessions', { profile_id: 'ice-sedan-2021' }, token);
    const sid = session.session.id;
    ws.send({ type: 'live:subscribe', sessionId: sid });

    // kick off a scan (async) — progress messages should arrive
    await api('POST', `/api/v1/diagnostics/sessions/${sid}/scan`, {}, token);

    const gotLive = [];
    const gotProgress = [];
    const deadline = Date.now() + 9000;
    while (Date.now() < deadline) {
      const m = await ws.next(1000);
      if (!m) continue;
      if (m.type === 'live:data' && m.sessionId === sid) gotLive.push(m);
      if (m.type === 'scan:progress' && m.sessionId === sid) gotProgress.push(m);
    }
    assert.ok(gotLive.length >= 3, `live:data frames received (${gotLive.length})`);
    const frame = gotLive[0];
    assert.ok(Array.isArray(frame.values));
    assert.ok(frame.values.some((v) => v.key === 'rpm' || v.key === 'soc'));
    assert.ok(gotProgress.length >= 3, `scan:progress events received (${gotProgress.length})`);
    const pcts = gotProgress.map((p) => p.pct);
    assert.ok(pcts.includes(100) && pcts.includes(5), 'progress covers 5..100');

    // generate a report → notification pushed to this user's sockets
    const rep = await api('POST', '/api/v1/reports', { session_id: sid }, token);
    assert.ok(rep.report.id);
    const notif = await ws.expectType('notification', 8000);
    assert.equal(notif.notification.type, 'report');

    // unsubscribe stops live:data
    ws.send({ type: 'live:unsubscribe', sessionId: sid });
    const before = gotLive.length;
    await new Promise((r) => setTimeout(r, 1500));
    assert.equal(gotLive.length, before, 'no more live:data after unsubscribe');
  } finally {
    closeAll();
  }
});
