'use strict';
/** VEHDiag — packages/config tests. */

const { test } = require('node:test');
const assert = require('node:assert');
const { loadConfig } = require('../../packages/config');

test('config: development defaults apply with empty env', () => {
  const c = loadConfig({}, { secret: 's' });
  assert.equal(c.host, '0.0.0.0');
  assert.equal(c.port, 8080);
  assert.equal(c.elm_tcp_port, 35000);
  assert.equal(c.rate_limit_per_minute, 1500);
  assert.equal(c.secret, 's');
  assert.equal(c.databaseUrl, null);
});

test('config: VEHDIAG_* env overrides win over defaults', () => {
  const c = loadConfig({ VEHDIAG_PORT: '9000', VEHDIAG_LOG_LEVEL: 'warn', DATABASE_URL: 'postgres://x' }, {});
  assert.equal(c.port, 9000);
  assert.equal(c.log_level, 'warn');
  assert.equal(c.databaseUrl, 'postgres://x');
});

test('config: invalid values fail fast', () => {
  assert.throws(() => loadConfig({ VEHDIAG_PORT: 'not-a-number' }, {}), /config: PORT/);
  assert.throws(() => loadConfig({ VEHDIAG_PORT: '70000' }, {}), /config: PORT/);
  assert.throws(() => loadConfig({ VEHDIAG_LOG_LEVEL: 'chatty' }, {}), /config: LOG_LEVEL/);
});

test('config: explicit overrides take precedence for tests', () => {
  const c = loadConfig({ VEHDIAG_PORT: '9999' }, { port: 1234 });
  assert.equal(c.port, 1234);
});
