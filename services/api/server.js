#!/usr/bin/env node
'use strict';
/**
 * VEHDiag — application server.
 *
 * One process serves:
 *   - the marketing website (apps/web) and dashboard SPA (apps/dashboard)
 *   - the REST API (/api/v1)
 *   - the WebSocket realtime channel (/ws)
 *   - the TCP ELM327 simulator (:35000)
 *
 * Zero runtime dependencies (Node.js ≥ 18). Storage is JSON by default;
 * PostgreSQL is the documented production path (see docs + docker-compose).
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const { Logger } = require('./lib/log');
const { JsonStore, byId } = require('./lib/db');
const { Router, ok, securityHeaders, createRateLimiter, HttpError } = require('./lib/http');
const { verifyToken, publicUser, hasRole } = require('./lib/auth');
const { attachWs } = require('./lib/ws');
const { DiagnosticRuntime } = require('./lib/runtime');
const { TcpElmServer } = require('../simulator/tcp');

const ROOT = path.join(__dirname, '..', '..');
const WEB_DIR = path.join(ROOT, 'apps', 'web');
const APP_DIR = path.join(ROOT, 'apps', 'dashboard');
const BRAND_DIR = path.join(ROOT, 'branding');
const DOWNLOADS_DIR = path.join(ROOT, 'downloads');

const PORT = parseInt(process.env.PORT || '8080', 10);
const HOST = process.env.HOST || '0.0.0.0';
const SECRET = process.env.VEHDIAG_SECRET || crypto.randomBytes(32).toString('hex');
const DEMO_EMAIL = process.env.VEHDIAG_DEMO_EMAIL || 'demo@vehdiag.app';
const DEMO_PASSWORD = process.env.VEHDIAG_DEMO_PASSWORD || 'demo1234';

const log = new Logger({ dir: path.join(ROOT, 'data', 'logs') });
const store = new JsonStore(path.join(ROOT, 'data', 'db.json'));

/* ---------------- notifications ---------------- */
function notify(userId, n) {
  const item = {
    id: crypto.randomUUID(),
    userId,
    type: n.type,
    title: n.title,
    body: n.body,
    sessionId: n.sessionId || null,
    read: false,
    createdAt: new Date().toISOString(),
  };
  store.collection('notifications').push(item);
  store.scheduleFlush();
  broadcast({ type: 'notification', notification: item }, { userId });
  return item;
}

/* ---------------- WebSocket fan-out ---------------- */
const wsClients = new Map(); // wsId -> { conn, userId, sessions:Set }
function broadcast(obj, { sessionId, userId, ws } = {}) {
  const sendTo = (c) => { try { c.conn.send(obj); } catch (e) { log.app('debug', 'ws_send_failed', { error: e.message }); } };
  if (ws) {
    if (typeof ws === 'string') {
      const c = wsClients.get(ws);
      if (c && c.conn) sendTo(c);
    } else if (typeof ws.send === 'function') {
      try { ws.send(obj); } catch (e) { log.app('debug', 'ws_send_failed', { error: e.message }); }
    }
    return;
  }
  for (const c of wsClients.values()) {
    if (!c.conn || typeof c.conn.send !== 'function') continue;
    if (sessionId && !c.sessions.has(sessionId)) continue;
    if (userId && c.userId !== userId) continue;
    sendTo(c);
  }
}

/* ---------------- runtime ---------------- */
const runtime = new DiagnosticRuntime({ store, log, notify, broadcast });

/* ---------------- router + middleware ---------------- */
const router = new Router();
const limiter = createRateLimiter({ windowMs: 60_000, max: parseInt(process.env.VEHDIAG_RATE_LIMIT || '1500', 10) });
router.onError = (e, req) => {
  log.err('error', 'route_error', { path: (req.urlObj ? req.urlObj.pathname : req.url), error: e.message, stack: e.stack });
};

router.use((req, res, next) => {
  for (const [k, v] of Object.entries(securityHeaders())) res.setHeader(k, v);
  if (req.url.startsWith('/api/')) limiter(req, res, next); else next();
});

/* --- auth middleware: resolve Bearer token --- */
router.use((req, res, next) => {
  req.user = null;
  if (!req.url.startsWith('/api/')) return next();
  const auth = req.headers.authorization || '';
  const m = auth.match(/^Bearer\s+(.+)$/i);
  if (m) {
    const payload = verifyToken(m[1], SECRET);
    if (payload && payload.typ === 'access') {
      const user = store.collection('users').find((u) => u.id === payload.sub);
      if (user && !user.suspended) {
        req.user = publicUser(user);
        req.userRaw = user;
      }
    }
  }
  next();
});

/* --- public API paths --- */
const publicPaths = new Set(['/api/v1/auth/login', '/api/v1/auth/register', '/api/v1/auth/refresh', '/api/v1/auth/forgot', '/api/v1/auth/reset', '/api/v1/auth/verify', '/api/v1/healthz', '/api/v1/openapi.json', '/api/v1/dtc', '/api/v1/ecus', '/api/v1/subscriptions/plans']);
router.use((req, res, next) => {
  if (!req.url.startsWith('/api/')) return next();
  const pathname = new URL(req.url, 'http://localhost').pathname;
  const isPublicDtc = pathname === '/api/v1/dtc' || (pathname.startsWith('/api/v1/dtc/') && pathname.split('/').length === 5);
  const isPublicEcu = pathname === '/api/v1/ecus' || (pathname.startsWith('/api/v1/ecus/') && pathname.split('/').length === 5);
  if (!publicPaths.has(pathname) && !isPublicDtc && !isPublicEcu && !req.user) {
    res.writeHead(401, { 'Content-Type': 'application/json; charset=utf-8' });
    return res.end(JSON.stringify({ error: { code: 'unauthorized', message: 'Authentication required' } }));
  }
  next();
});

/* --- health + meta --- */
router.get('/api/v1/healthz', async (req, res) => {
  ok(res, { status: 'ok', uptimeS: Math.round(process.uptime()), activeSimulators: runtime.live.size, wsClients: wsClients.size });
});

router.get('/api/v1/openapi.json', async (req, res) => {
  const spec = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'docs', 'openapi.json'), 'utf8'));
  res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(spec));
});

/* --- notifications --- */
router.get('/api/v1/notifications', async (req, res) => {
  const list = store.collection('notifications').filter((n) => n.userId === req.user.id).slice(-50).reverse();
  ok(res, { notifications: list, unread: list.filter((n) => !n.read).length });
});
router.post('/api/v1/notifications/read', async (req, res) => {
  const body = await require('./lib/http').readJson(req).catch(() => ({}));
  const ids = Array.isArray(body.ids) ? body.ids : null;
  for (const n of store.collection('notifications')) {
    if (n.userId === req.user.id && (!ids || ids.includes(n.id))) n.read = true;
  }
  store.scheduleFlush();
  ok(res, { ok: true });
});

/* --- users/me --- */
router.get('/api/v1/users/me', async (req, res) => ok(res, { user: req.user }));
router.patch('/api/v1/users/me', async (req, res) => {
  const body = await require('./lib/http').readJson(req);
  const u = byId(store.collection('users'), req.user.id);
  if (typeof body.name === 'string' && body.name.trim().length >= 2) u.name = body.name.trim().slice(0, 120);
  if (body.settings && typeof body.settings === 'object') u.settings = { ...u.settings, ...body.settings };
  if (typeof body.password === 'string' && body.password.length >= 8) {
    u.passwordHash = require('./lib/auth').hashPassword(body.password);
    log.sec('info', 'password_changed', { userId: u.id });
  }
  u.updatedAt = new Date().toISOString();
  store.scheduleFlush();
  ok(res, { user: publicUser(u) });
});

/* --- feature routes --- */
let tcpServer = null;
const tcpRef = () => tcpServer;

require('./routes/auth').mount(router, { store, secret: SECRET, log, notify });
require('./routes/vehicles').mount(router, { store, log, notify });
require('./routes/diagnostics').mount(router, { store, runtime, log, broadcast });
require('./routes/dtc').mount(router);
require('./routes/ecus').mount(router);
require('./routes/reports').mount(router, { store, log, notify });
require('./routes/devices').mount(router, { store, log, tcp: tcpRef });
require('./routes/subscriptions').mount(router, { store, log, notify });
require('./routes/admin').mount(router, { store, log });

/* ---------------- static files ---------------- */
const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp',
  '.json': 'application/json; charset=utf-8', '.txt': 'text/plain; charset=utf-8', '.ico': 'image/x-icon',
  '.apk': 'application/vnd.android.package-archive', '.zip': 'application/zip', '.md': 'text/markdown; charset=utf-8',
};

function serveStatic(req, res, filePath) {
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) return false;
  const stat = fs.statSync(filePath);
  const ext = path.extname(filePath).toLowerCase();
  const headers = { 'Content-Type': MIME[ext] || 'application/octet-stream', 'Content-Length': stat.size };
  if (ext === '.apk' || ext === '.zip') {
    headers['Content-Disposition'] = `attachment; filename="${path.basename(filePath)}"`;
  }
  if (ext !== '.html') headers['Cache-Control'] = 'no-cache';
  res.writeHead(200, headers);
  fs.createReadStream(filePath).pipe(res);
  return true;
}

function resolveStatic(req) {
  const url = new URL(req.url, 'http://localhost');
  let p = url.pathname;
  if (p === '/' || p === '') return path.join(WEB_DIR, 'index.html');
  if (p === '/favicon.svg') return path.join(BRAND_DIR, 'favicon.svg');
  if (p.startsWith('/branding/')) {
    const candidate = path.normalize(path.join(BRAND_DIR, p.slice('/branding/'.length)));
    if (candidate.startsWith(BRAND_DIR)) return candidate;
    return path.join(WEB_DIR, '404.html');
  }
  if (p.startsWith('/downloads/')) {
    const candidate = path.normalize(path.join(DOWNLOADS_DIR, p.slice('/downloads/'.length)));
    if (candidate.startsWith(DOWNLOADS_DIR)) return candidate;
    return path.join(WEB_DIR, '404.html');
  }
  if (p === '/app' || p.startsWith('/app/')) {
    // dashboard SPA — everything serves its index.html
    const rel = p.slice(4) || '/';
    const candidate = path.normalize(path.join(APP_DIR, rel));
    if (rel.startsWith('/') && fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
    return path.join(APP_DIR, 'index.html');
  }
  const candidate = path.normalize(path.join(WEB_DIR, p));
  if (candidate.startsWith(WEB_DIR)) return candidate;
  return path.join(WEB_DIR, '404.html');
}

/* ---------------- HTTP server ---------------- */
const server = http.createServer(async (req, res) => {
  const start = Date.now();
  res.on('finish', () => {
    if (req.url.startsWith('/api/')) {
      log.app('debug', 'http', { method: req.method, path: req.urlObj ? req.urlObj.pathname : req.url, status: res.statusCode, ms: Date.now() - start });
    }
  });
  try {
    if (req.url.startsWith('/api/')) {
      await router.handle(req, res, { store, log });
    } else {
      const file = resolveStatic(req);
      if (!serveStatic(req, res, file)) {
        res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end('<h1>404</h1>');
      }
    }
  } catch (e) {
    log.err('error', 'unhandled', { error: e.message, stack: e.stack });
    if (!res.headersSent) {
      const status = e instanceof HttpError ? e.status : 500;
      res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ error: { code: 'error', message: e.message } }));
    }
  }
});

/* ---------------- WebSocket ---------------- */
attachWs(server, {
  path: '/ws',
  log: (e) => log.app('debug', 'ws', e),
  onConnection: (conn, msg) => {
    if (!msg) {
      // connection opened — register
      conn._meta = { conn, userId: null, sessions: new Set() };
      wsClients.set(conn.id, conn._meta);
      return;
    }
    if (msg.type !== 'text') return;
    let payload;
    try { payload = JSON.parse(msg.data); } catch (e) { return; }

    switch (payload.type) {
      case 'auth': {
        const token = verifyToken(payload.token, SECRET);
        if (token && token.typ === 'access') {
          const user = store.collection('users').find((u) => u.id === token.sub);
          if (user) {
            conn._meta.userId = user.id;
            conn.send({ type: 'auth:ok', user: publicUser(user) });
            log.app('debug', 'ws_auth', { ws: conn.id, userId: user.id });
            return;
          }
        }
        conn.send({ type: 'auth:fail', message: 'Invalid token' });
        break;
      }
      case 'live:subscribe': {
        if (!conn._meta.userId) return conn.send({ type: 'error', message: 'authenticate first' });
        if (runtime.subscribe(payload.sessionId, conn.id)) {
          conn._meta.sessions.add(payload.sessionId);
          conn.send({ type: 'live:subscribed', sessionId: payload.sessionId });
        } else {
          conn.send({ type: 'error', message: 'session not found' });
        }
        break;
      }
      case 'live:unsubscribe': {
        runtime.unsubscribe(payload.sessionId, conn.id);
        conn._meta.sessions.delete(payload.sessionId);
        break;
      }
      case 'ping': conn.send({ type: 'pong', ts: Date.now() }); break;
      default: conn.send({ type: 'error', message: 'unknown message type' });
    }
  },
  onClose: (conn) => {
    if (conn._meta) {
      for (const sid of conn._meta.sessions) runtime.unsubscribe(sid, conn.id);
      wsClients.delete(conn.id);
    }
  },
});

/* ---------------- TCP ELM327 simulator ---------------- */
tcpServer = new TcpElmServer({ port: parseInt(process.env.ELM_TCP_PORT || '35000', 10), host: HOST, log: (m) => log.diag('info', m) });

/* ---------------- startup ---------------- */
async function ensureDemoUser() {
  // A real, flagged demo account so the /app/#/demo flow works without
  // asking visitors for their email. Sessions are real API calls.
  const users = store.collection('users');
  const existing = users.find((u) => u.email === DEMO_EMAIL);
  if (!existing) {
    const { hashPassword } = require('./lib/auth');
    users.push({
      id: crypto.randomUUID(),
      email: DEMO_EMAIL,
      name: 'Demo Driver',
      role: 'USER',
      isDemo: true,
      passwordHash: hashPassword(DEMO_PASSWORD),
      settings: { theme: 'system' },
      createdAt: new Date().toISOString(),
    });
    // keep the demo workspace tidy: purge stale demo sessions/reports
    const cutoff = Date.now() - 24 * 3600 * 1000;
    const demoUsers = new Set(users.filter((u) => u.isDemo).map((u) => u.id));
    store.collection('sessions').filter((s) => demoUsers.has(s.userId) && new Date(s.createdAt).getTime() < cutoff)
      .forEach((s) => { const i = store.collection('sessions').indexOf(s); if (i >= 0) store.collection('sessions').splice(i, 1); });
    store.scheduleFlush();
    log.app('info', 'demo_account_provisioned', { email: DEMO_EMAIL });
  }
}

(async () => {
  await store.open();
  ensureDemoUser();
  await tcpServer.start().catch((e) => log.err('warn', 'tcp_simulator', { error: e.message }));
  server.listen(PORT, HOST, () => {
    log.app('info', `VEHDiag listening on http://${HOST}:${PORT}`);
    log.app('info', `ELM327 TCP simulator on ${HOST}:${tcpServer.port} (if enabled)`);
  });
})();

/* ---------------- shutdown ---------------- */
function shutdown(sig) {
  log.app('info', `${sig} received — shutting down`);
  runtime.shutdown();
  tcpServer.stop();
  for (const c of wsClients.keys()) { try { wsClients.get(c).conn.close(1001, 'server shutdown'); } catch (e) { /* noop */ } }
  store.close().then(() => {
    log.close();
    process.exit(0);
  });
  setTimeout(() => process.exit(0), 2000).unref();
}
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

module.exports = { server, runtime, store, log };
