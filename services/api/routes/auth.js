'use strict';
/**
 * VEHDiag — /api/v1/auth: registration, login, logout, refresh, email
 * verification, password reset, session management.
 */

const { hashPassword, verifyPassword, issueTokens, verifyToken, publicUser, randomToken, hasRole } = require('../lib/auth');
const { HttpError, ok, readJson, isEmail, newId, clampStr } = require('../lib/http');

function mount(router, { store, secret, log, notify }) {
  /** Shared login implementation. */
  async function doLogin(email, password) {
    const users = store.collection('users');
    const user = users.find((u) => u.email === String(email).toLowerCase());
    if (!user || !verifyPassword(password, user.passwordHash)) {
      throw new HttpError(401, 'Invalid email or password', 'invalid_credentials');
    }
    const tokens = issueTokens(user, secret);
    store.collection('tokens').push({ id: newId(), userId: user.id, typ: 'refresh', token: tokens.refresh, createdAt: new Date().toISOString() });
    user.lastLoginAt = new Date().toISOString();
    store.scheduleFlush();
    log.sec('info', 'login', { userId: user.id, email: user.email });
    return { token: tokens.access, refreshToken: tokens.refresh, user: publicUser(user) };
  }

  router.post('/api/v1/auth/register', async (req, res) => {
    const body = await readJson(req);
    const email = clampStr(body.email, 254).toLowerCase();
    const name = clampStr(body.name, 120);
    const password = typeof body.password === 'string' ? body.password : '';
    if (!isEmail(email)) throw new HttpError(400, 'A valid email is required', 'invalid_email');
    if (name.length < 2) throw new HttpError(400, 'Name must be at least 2 characters', 'invalid_name');
    if (password.length < 8) throw new HttpError(400, 'Password must be at least 8 characters', 'weak_password');

    const users = store.collection('users');
    if (users.some((u) => u.email === email)) throw new HttpError(409, 'An account with this email already exists', 'email_taken');

    const user = {
      id: newId(),
      name,
      email,
      passwordHash: hashPassword(password),
      role: users.length === 0 ? 'SUPER_ADMIN' : 'USER', // first user bootstraps the instance
      emailVerified: false,
      emailVerifyToken: randomToken(24),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      settings: { theme: 'system', units: 'metric' },
      subscription: { plan: 'free' },
    };
    users.push(user);
    const tokens = issueTokens(user, secret);
    store.collection('tokens').push({ id: newId(), userId: user.id, typ: 'refresh', token: tokens.refresh, createdAt: new Date().toISOString() });
    notify(user.id, { type: 'welcome', title: 'Welcome to VEHDiag', body: 'Your account is ready. Try a session with the built-in simulator.' });
    store.scheduleFlush();
    log.sec('info', 'register', { userId: user.id });
    ok(res, { token: tokens.access, refreshToken: tokens.refresh, user: publicUser(user) }, 201);
  });

  router.post('/api/v1/auth/login', async (req, res) => {
    const body = await readJson(req);
    const data = await doLogin(body.email || '', body.password || '');
    ok(res, data);
  });

  router.post('/api/v1/auth/refresh', async (req, res) => {
    const body = await readJson(req);
    const payload = verifyToken(body.refreshToken, secret);
    if (!payload || payload.typ !== 'refresh') throw new HttpError(401, 'Invalid refresh token', 'invalid_token');
    const users = store.collection('users');
    const user = users.find((u) => u.id === payload.sub);
    if (!user) throw new HttpError(401, 'Unknown user', 'invalid_token');
    const tokens = issueTokens(user, secret);
    ok(res, { token: tokens.access, refreshToken: tokens.refresh, user: publicUser(user) });
  });

  router.post('/api/v1/auth/logout', async (req, res) => {
    const body = await readJson(req).catch(() => ({}));
    const tokens = store.collection('tokens');
    const i = tokens.findIndex((t) => t.token === body.refreshToken);
    if (i >= 0) tokens.splice(i, 1);
    store.scheduleFlush();
    ok(res, { loggedOut: true });
  });

  router.post('/api/v1/auth/forgot', async (req, res) => {
    const body = await readJson(req);
    const users = store.collection('users');
    const user = users.find((u) => u.email === String(body.email || '').toLowerCase());
    // Always respond the same way (no user enumeration).
    if (user) {
      user.passwordResetToken = randomToken(24);
      user.passwordResetExpires = Date.now() + 30 * 60 * 1000;
      store.scheduleFlush();
      log.sec('info', 'password_reset_requested', { userId: user.id });
    }
    ok(res, { message: 'If the account exists, a reset token has been issued.' });
  });

  router.post('/api/v1/auth/reset', async (req, res) => {
    const body = await readJson(req);
    const password = typeof body.password === 'string' ? body.password : '';
    if (password.length < 8) throw new HttpError(400, 'Password must be at least 8 characters', 'weak_password');
    const users = store.collection('users');
    const user = users.find((u) => u.passwordResetToken && u.passwordResetToken === body.token);
    if (!user || Date.now() > (user.passwordResetExpires || 0)) {
      throw new HttpError(400, 'Reset token is invalid or expired', 'invalid_token');
    }
    user.passwordHash = hashPassword(password);
    user.passwordResetToken = null;
    user.passwordResetExpires = null;
    // revoke existing refresh tokens
    store.collection('tokens').forEach((t, i, arr) => { if (t.userId === user.id) arr.splice(i, 1); });
    store.scheduleFlush();
    log.sec('info', 'password_reset', { userId: user.id });
    ok(res, { message: 'Password updated. Please log in.' });
  });

  router.get('/api/v1/auth/me', async (req, res) => {
    ok(res, { user: req.user });
  });

  router.post('/api/v1/auth/verify', async (req, res) => {
    const body = await readJson(req);
    const users = store.collection('users');
    const user = users.find((u) => u.emailVerifyToken === body.token);
    if (!user) throw new HttpError(400, 'Invalid verification token', 'invalid_token');
    user.emailVerified = true;
    user.emailVerifyToken = null;
    store.scheduleFlush();
    ok(res, { verified: true });
  });
}

module.exports = { mount };
