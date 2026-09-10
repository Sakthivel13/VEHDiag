'use strict';
/**
 * VEHDiag — authentication & authorization.
 * scrypt password hashing, HMAC-signed session tokens, refresh tokens,
 * role-based access control, email verification & password reset flows.
 * Plaintext passwords are never stored.
 */

const crypto = require('crypto');

const ROLES = ['USER', 'TECHNICIAN', 'WORKSHOP_ADMIN', 'ADMIN', 'SUPER_ADMIN'];
const ROLE_RANK = Object.fromEntries(ROLES.map((r, i) => [r, i]));

/** scrypt hash with per-user random salt, format: scrypt$N$r$p$salt$hash */
function hashPassword(password) {
  const salt = crypto.randomBytes(16);
  const N = 16384, r = 8, p = 1;
  const hash = crypto.scryptSync(password, salt, 64, { N, r, p });
  return `scrypt$${N}$${r}$${p}$${salt.toString('hex')}$${hash.toString('hex')}`;
}

function verifyPassword(password, stored) {
  try {
    const parts = stored.split('$');
    if (parts[0] !== 'scrypt' || parts.length !== 6) return false;
    const [, N, r, p, saltHex, hashHex] = parts;
    const salt = Buffer.from(saltHex, 'hex');
    const expected = Buffer.from(hashHex, 'hex');
    const actual = crypto.scryptSync(password, salt, expected.length, { N: +N, r: +r, p: +p });
    return crypto.timingSafeEqual(actual, expected);
  } catch (e) {
    return false;
  }
}

/** HMAC-SHA256 signed token: base64url(payload).base64url(sig). */
function signToken(payload, secret) {
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const sig = crypto.createHmac('sha256', secret).update(body).digest('base64url');
  return `${body}.${sig}`;
}

function verifyToken(token, secret) {
  try {
    const [body, sig] = String(token).split('.');
    if (!body || !sig) return null;
    const expected = crypto.createHmac('sha256', secret).update(body).digest('base64url');
    const a = Buffer.from(sig); const b = Buffer.from(expected);
    if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
    const payload = JSON.parse(Buffer.from(body, 'base64url').toString('utf8'));
    if (payload.exp && Date.now() > payload.exp) return null;
    return payload;
  } catch (e) {
    return null;
  }
}

function issueTokens(user, secret, { accessTtl = 15 * 60 * 1000, refreshTtl = 30 * 24 * 3600 * 1000 } = {}) {
  const now = Date.now();
  const access = signToken({ sub: user.id, role: user.role, typ: 'access', iat: now, exp: now + accessTtl }, secret);
  const refresh = signToken({ sub: user.id, role: user.role, typ: 'refresh', iat: now, exp: now + refreshTtl }, secret);
  return { access, refresh };
}

function hasRole(user, minRole) {
  if (!user || !user.role) return false;
  return ROLE_RANK[user.role] >= ROLE_RANK[minRole];
}

/** Public user view — never leak the password hash. */
function publicUser(u) {
  const { passwordHash, passwordResetToken, passwordResetExpires, emailVerifyToken, ...rest } = u;
  return rest;
}

function randomToken(bytes = 32) { return crypto.randomBytes(bytes).toString('hex'); }

module.exports = {
  ROLES, ROLE_RANK, hashPassword, verifyPassword, signToken, verifyToken,
  issueTokens, hasRole, publicUser, randomToken,
};
