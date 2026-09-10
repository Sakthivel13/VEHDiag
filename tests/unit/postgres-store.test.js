'use strict';
/**
 * VEHDiag — PostgresStore unit tests (no live PostgreSQL required).
 * Uses a fake pool client that records SQL and returns canned rows, so the
 * adapter's SQL generation and row mapping are verified in the sandbox.
 * A real integration test (CI, postgres service) is tests/e2e/postgres.integration.test.js.
 */

const { test } = require('node:test');
const assert = require('node:assert');
const { PostgresStore } = require('../../services/api/lib/db-postgres');

function fakePool(initial = {}) {
  const queries = [];
  const client = {
    query: async (sql, params) => {
      queries.push({ sql, params });
      if (/^SELECT/.test(sql)) {
        const table = sql.match(/FROM (\w+)/)[1];
        const rows = initial[table] || [];
        // canned rows are returned as objects keyed by column position: row[i]
        return { rows: rows.map((r) => Object.assign({}, r, { _sql: sql })) };
      }
      return { rowCount: 1 };
    },
    release: () => {},
  };
  return {
    queries,
    pool: { connect: async () => client, query: client.query, end: async () => {} },
  };
}

function cannedRow(table, values) {
  // values in sql-column order; PostgresStore reads by position
  const row = {};
  const cols = {
    users: ['id', 'email', 'name', 'role', 'password_hash', 'is_demo', 'settings', 'created_at'],
    vehicles: ['id', 'userId', 'vin', 'manufacturer', 'model', 'year', 'engine', 'fuel_type', 'transmission', 'mileageKm', 'plate', 'created_at'],
    notifications: ['id', 'userId', 'type', 'title', 'body', 'sessionId', 'read', 'created_at'],
  }[table];
  cols.forEach((c, i) => { row[i] = values[i]; });
  return row;
}

test('PostgresStore: open() loads every table into collections', async () => {
  const f = fakePool({
    users: [cannedRow('users', ['u1', 'a@x.com', 'Alice', 'USER', 'scrypt$..', false, {}, '2026-01-01T00:00:00Z'])],
    vehicles: [cannedRow('vehicles', ['v1', 'u1', 'MA3JF31S6MK441207', 'VEH', 'Atlas', 2021, null, 'petrol', null, 42000, null, '2026-01-01T00:00:00Z'])],
  });
  const store = new PostgresStore({ pool: f.pool });
  await store.open();
  assert.equal(store.collection('users').length, 1);
  assert.equal(store.collection('users')[0].passwordHash, 'scrypt$..');
  assert.equal(store.collection('users')[0].isDemo, false);
  assert.equal(store.collection('vehicles')[0].mileageKm, 42000);
  assert.equal(store.collection('vehicles')[0].fuel_type, 'petrol');
  assert.equal(store.meta().backend, 'postgresql');
});

test('PostgresStore: flush rewrites dirty collections in FK-safe order', async () => {
  const f = fakePool({});
  const store = new PostgresStore({ pool: f.pool });
  await store.open();

  store.collection('users').push({
    id: 'u1', email: 'a@x.com', name: 'Alice', role: 'USER',
    passwordHash: 'scrypt$..', isDemo: false, settings: {}, createdAt: '2026-01-01T00:00:00Z',
  });
  store.collection('vehicles').push({
    id: 'v1', userId: 'u1', vin: 'MA3JF31S6MK441207', manufacturer: 'VEH',
    model: 'Atlas', year: 2021, engine: null, fuel_type: 'petrol',
    transmission: null, mileageKm: 1, plate: null, createdAt: '2026-01-01T00:00:00Z',
  });
  await store.flush();

  const writes = f.queries.filter((q) => /^(DELETE|INSERT)/.test(q.sql));
  const order = writes.map((q) => (q.sql.startsWith('DELETE') ? 'D:' : 'I:') + q.sql.match(/(?:FROM|INTO) (\w+)/)[1]);
  // children (vehicles) must be written before parents (users) — here only
  // user data is inserted, but the flush order itself must be children-first
  assert.ok(order.includes('D:vehicles') && order.includes('I:vehicles'), 'vehicles rewritten');
  assert.ok(order.includes('D:users') && order.includes('I:users'), 'users rewritten');
  assert.ok(order.indexOf('D:vehicles') < order.indexOf('D:users'), 'vehicles flushed before users (FK order)');

  const insertUsers = f.queries.find((q) => /INSERT INTO users/.test(q.sql));
  assert.ok(insertUsers.params.includes('a@x.com'), 'row values parameterised');
  assert.equal(store.collection('users')[0].passwordHash, 'scrypt$..');
});

test('PostgresStore: scheduleFlush debounces and flushes once', async () => {
  const f = fakePool({});
  const store = new PostgresStore({ pool: f.pool });
  await store.open();
  store.collection('devices').push({ id: 'd1', userId: 'u1', name: 'ELM', kind: 'simulator', status: 'registered' });
  store.scheduleFlush();
  store.scheduleFlush();
  store.scheduleFlush();
  await new Promise((r) => setTimeout(r, 250));
  const inserts = f.queries.filter((q) => /INSERT INTO devices/.test(q.sql));
  assert.equal(inserts.length, 1, 'single flush despite triple schedule');
});

test('PostgresStore: unknown collection defaults to an empty in-memory array', async () => {
  const f = fakePool({});
  const store = new PostgresStore({ pool: f.pool });
  await store.open();
  const arr = store.collection('other');
  assert.ok(Array.isArray(arr) && arr.length === 0);
});
