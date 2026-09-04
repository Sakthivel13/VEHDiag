'use strict';
/**
 * VEHDiag — HTTP helpers: router, envelopes, validation, rate limiting,
 * security headers. Business logic never lives here — only transport concerns.
 */

const crypto = require('crypto');

/* ---------- security headers ---------- */
function securityHeaders(req) {
  return {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'SAMEORIGIN',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Content-Security-Policy':
      "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:; frame-ancestors 'self'",
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cache-Control': 'no-store',
  };
}

/* ---------- error envelope ---------- */
class HttpError extends Error {
  constructor(status, message, code) {
    super(message);
    this.status = status;
    this.code = code || 'error';
  }
}

function errorEnvelope(err) {
  const status = err instanceof HttpError ? err.status : 500;
  const message = err instanceof HttpError ? err.message : 'Internal server error';
  return { status, body: { error: { code: err.code || 'error', message } } };
}

/* ---------- response envelope ---------- */
function ok(res, data, status = 200, extra = {}) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', ...extra });
  res.end(JSON.stringify({ data, meta: { ts: new Date().toISOString(), ...extra.meta } }));
}

/* ---------- in-memory rate limiter (token bucket) ---------- */
function createRateLimiter({ windowMs = 60 * 1000, max = 120 } = {}) {
  const buckets = new Map();
  setInterval(() => {
    const now = Date.now();
    for (const [k, v] of buckets) if (now - v.t0 > windowMs) buckets.delete(k);
  }, windowMs).unref();
  return function rateLimit(req, res, next) {
    const key = req.socket.remoteAddress || 'local';
    const now = Date.now();
    let b = buckets.get(key);
    if (!b || now - b.t0 > windowMs) { b = { t0: now, n: 0 }; buckets.set(key, b); }
    b.n++;
    if (b.n > max) {
      res.writeHead(429, { 'Content-Type': 'application/json', 'Retry-After': '60', ...securityHeaders() });
      res.end(JSON.stringify({ error: { code: 'rate_limited', message: 'Too many requests' } }));
      return;
    }
    next();
  };
}

/* ---------- router ---------- */
class Router {
  constructor() { this.routes = []; this.middleware = []; this.onError = null; }

  use(fn) { this.middleware.push(fn); return this; }

  add(method, pattern, handler) {
    const keys = [];
    const regex = new RegExp('^' + pattern.replace(/:[a-zA-Z_]+/g, (m) => { keys.push(m.slice(1)); return '([^/]+)'; }) + '$');
    this.routes.push({ method, regex, keys, handler });
    return this;
  }
  get(p, h) { return this.add('GET', p, h); }
  post(p, h) { return this.add('POST', p, h); }
  patch(p, h) { return this.add('PATCH', p, h); }
  put(p, h) { return this.add('PUT', p, h); }
  delete(p, h) { return this.add('DELETE', p, h); }

  async handle(req, res, ctx) {
    const url = new URL(req.url, 'http://localhost');
    const method = req.method.toUpperCase();
    let idx = 0;
    const runMw = (i, done) => {
      if (i >= this.middleware.length) return done();
      this.middleware[i](req, res, () => runMw(i + 1, done));
    };
    runMw(0, () => {
      for (const r of this.routes) {
        if (r.method !== method) continue;
        const m = url.pathname.match(r.regex);
        if (!m) continue;
        const params = {};
        r.keys.forEach((k, i) => { params[k] = decodeURIComponent(m[i + 1]); });
        req.params = params;
        req.query = Object.fromEntries(url.searchParams.entries());
        req.urlObj = url;
        return r.handler(req, res, ctx).catch((e) => {
          if (this.onError) { try { this.onError(e, req); } catch (x) { /* noop */ } }
          const env = errorEnvelope(e);
          res.writeHead(env.status, { 'Content-Type': 'application/json; charset=utf-8', ...securityHeaders() });
          res.end(JSON.stringify(env.body));
        });
      }
      res.writeHead(404, { 'Content-Type': 'application/json; charset=utf-8', ...securityHeaders() });
      res.end(JSON.stringify({ error: { code: 'not_found', message: 'Not found' } }));
    });
  }
}

/* ---------- body parsing ---------- */
function readJson(req, { limit = 1 * 1024 * 1024 } = {}) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', (c) => {
      size += c.length;
      if (size > limit) { reject(new HttpError(413, 'Payload too large')); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => {
      if (!chunks.length) return resolve({});
      try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
      catch (e) { reject(new HttpError(400, 'Invalid JSON body')); }
    });
    req.on('error', () => reject(new HttpError(400, 'Request aborted')));
  });
}

/* ---------- small validators ---------- */
const isEmail = (s) => typeof s === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s);
const isVin = (s) => typeof s === 'string' && /^[A-HJ-NPR-Z0-9]{17}$/.test(s.toUpperCase());
const isUuid = (s) => typeof s === 'string' && /^[0-9a-f-]{8,64}$/i.test(s);
const newId = () => crypto.randomUUID();
const clampStr = (s, max) => (typeof s === 'string' ? s.slice(0, max) : '');

module.exports = {
  HttpError, Router, ok, readJson, errorEnvelope, securityHeaders,
  createRateLimiter, isEmail, isVin, isUuid, newId, clampStr,
};
