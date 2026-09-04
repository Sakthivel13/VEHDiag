'use strict';
/**
 * VEHDiag — shared runtime configuration.
 *
 * Single source of truth for environment-driven settings across services
 * (api, simulator, worker). Every value has a development-safe default and
 * is validated at boot — a misconfigured production variable fails fast
 * instead of degrading silently.
 */

const DEFAULTS = {
  HOST: '0.0.0.0',
  PORT: 8080,
  ELM_TCP_PORT: 35000,
  RATE_LIMIT_PER_MINUTE: 1500,
  LOG_LEVEL: 'info',
  DATA_DIR: 'data',
  DEMO_EMAIL: 'demo@vehdiag.app',
  DEMO_PASSWORD: 'demo1234',
};

const RULES = {
  PORT: { type: 'int', min: 1, max: 65535 },
  ELM_TCP_PORT: { type: 'int', min: 1, max: 65535 },
  RATE_LIMIT_PER_MINUTE: { type: 'int', min: 1 },
  LOG_LEVEL: { oneOf: ['debug', 'info', 'warn', 'error'] },
};

function fail(name, why) {
  throw new Error(`config: ${name} ${why}`);
}

function validate(name, value) {
  const rule = RULES[name];
  if (!rule) return value;
  if (rule.type === 'int') {
    const n = parseInt(value, 10);
    if (Number.isNaN(n)) fail(name, `must be an integer (got ${JSON.stringify(value)})`);
    if (rule.min !== undefined && n < rule.min) fail(name, `must be >= ${rule.min}`);
    if (rule.max !== undefined && n > rule.max) fail(name, `must be <= ${rule.max}`);
    return n;
  }
  if (rule.oneOf && !rule.oneOf.includes(value)) fail(name, `must be one of ${rule.oneOf.join(', ')}`);
  return value;
}

/**
 * Build the runtime config from process.env (or an explicit overrides map
 * for tests). Unknown keys are ignored; invalid values throw.
 */
function loadConfig(env = process.env, overrides = {}) {
  const over = {};
  for (const [k, v] of Object.entries(overrides)) over[k.toUpperCase()] = v;
  const config = {};
  for (const [key, fallback] of Object.entries(DEFAULTS)) {
    const raw = over[key] !== undefined ? over[key] : env[`VEHDIAG_${key}`] !== undefined ? env[`VEHDIAG_${key}`] : fallback;
    config[key.toLowerCase()] = validate(key, raw);
  }
  config.secret = over.SECRET !== undefined
    ? over.SECRET
    : env.VEHDIAG_SECRET || require('crypto').randomBytes(32).toString('hex');
  config.databaseUrl = over.DATABASEURL !== undefined ? over.DATABASEURL : env.DATABASE_URL || null;
  return config;
}

module.exports = { loadConfig, DEFAULTS, RULES };
