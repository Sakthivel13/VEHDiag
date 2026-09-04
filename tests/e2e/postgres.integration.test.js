'use strict';
/**
 * VEHDiag — PostgreSQL integration test.
 *
 * Runs ONLY when VEHDIAG_TEST_PG_URL is set (skipped otherwise — this sandbox
 * has no PostgreSQL server; GitHub Actions CI supplies one):
 *
 *   VEHDIAG_TEST_PG_URL=postgres://user:pass@127.0.0.1:5432/vehdiag node --test tests/e2e/postgres.integration.test.js
 *
 * 1. applies database/migrations/*.sql via scripts/migrate.js
 * 2. exercises the real PostgresStore against the live server
 * 3. re-runs migrations to prove idempotence
 */

const { test } = require('node:test');
const assert = require('node:assert');
const { execFileSync } = require('child_process');
const path = require('path');
const { PostgresStore } = require('../../services/api/lib/db-postgres');

const URL = process.env.VEHDIAG_TEST_PG_URL;
const ROOT = path.join(__dirname, '..', '..');

test('PostgreSQL: migrations apply, store round-trips, re-run is idempotent', { skip: URL ? false : 'VEHDIAG_TEST_PG_URL not set' }, async () => {
  // apply migrations
  const out = execFileSync('node', [path.join(ROOT, 'scripts', 'migrate.js')], {
    env: { ...process.env, DATABASE_URL: URL },
    encoding: 'utf8',
  });
  assert.match(out, /apply 0001_init\.sql|up to date/);

  // write through the real store
  const store = new PostgresStore({ connectionString: URL });
  await store.open();
  store.collection('users').push({
    id: '11111111-1111-4111-8111-111111111111', email: 'pg-test@vehdiag.app',
    name: 'PG Tester', role: 'TECHNICIAN', passwordHash: 'scrypt$test$only',
    isDemo: false, settings: { theme: 'dark' }, createdAt: new Date().toISOString(),
  });
  store.collection('vehicles').push({
    id: '22222222-2222-4222-8222-222222222222', userId: '11111111-1111-4111-8111-111111111111',
    vin: 'MA3JF31S6MK441207', manufacturer: 'VEH', model: 'Atlas', year: 2021,
    engine: null, fuel_type: 'petrol', transmission: null, mileageKm: 5, plate: null,
    createdAt: new Date().toISOString(),
  });
  await store.flush();
  await store.close();

  // read it back through a fresh connection
  const store2 = new PostgresStore({ connectionString: URL });
  await store2.open();
  assert.equal(store2.collection('users').length, 1);
  assert.equal(store2.collection('users')[0].role, 'TECHNICIAN');
  assert.equal(store2.collection('users')[0].settings.theme, 'dark');
  assert.equal(store2.collection('vehicles')[0].mileageKm, 5);
  assert.equal(store2.collection('vehicles')[0].vin, 'MA3JF31S6MK441207');
  await store2.close();

  // migrations idempotent on re-run
  const out2 = execFileSync('node', [path.join(ROOT, 'scripts', 'migrate.js')], {
    env: { ...process.env, DATABASE_URL: URL },
    encoding: 'utf8',
  });
  assert.match(out2, /up to date/);
});
