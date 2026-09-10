'use strict';
/**
 * VEHDiag — PostgreSQL data store.
 *
 * Implements the same DataStore interface the API routes use as JsonStore:
 *   open() / collection(name) -> array / meta() / flush() / scheduleFlush()
 *
 * Strategy: read-through on open(), write-behind on flush(). Collections are
 * materialised as in-memory arrays (so every existing route keeps working
 * unchanged); any collection that was *touched* is rewritten to its table on
 * flush via DELETE + bulk INSERT in one transaction. Correct and simple for
 * workshop-scale data; a write-through DAO layer is the documented scale-up
 * path (see docs/PRODUCTION_AUDIT.md).
 *
 * Selected automatically when DATABASE_URL is set. Requires the migrations
 * from database/migrations/ to be applied (scripts/migrate.js).
 */

// `pg` is loaded lazily: the Postgres store is only used when DATABASE_URL is
// set, so a missing node_modules must not stop the whole platform from
// booting with the default JSON store.
let _pg = null;
function loadPg() {
  if (!_pg) {
    try {
      _pg = require('pg');
    } catch (err) {
      throw new Error(
        'PostgresStore needs the "pg" package (run `npm install`). ' +
        `Failed to load pg: ${err.message}`
      );
    }
  }
  return _pg;
}

/** collection name -> { table, columns: [jsonKey], sql: [columnSQL] } */
const TABLES = {
  users: {
    table: 'users',
    columns: ['id', 'email', 'name', 'role', 'passwordHash', 'isDemo', 'settings', 'createdAt'],
    sql: ['id', 'email', 'name', 'role', 'password_hash', 'is_demo', 'settings', 'created_at'],
  },
  vehicles: {
    table: 'vehicles',
    columns: ['id', 'userId', 'vin', 'manufacturer', 'model', 'year', 'engine', 'fuel_type', 'transmission', 'mileageKm', 'plate', 'createdAt'],
    sql: ['id', '"userId"', 'vin', 'manufacturer', 'model', 'year', 'engine', 'fuel_type', 'transmission', '"mileageKm"', 'plate', 'created_at'],
  },
  sessions: {
    table: 'sessions',
    columns: ['id', 'userId', 'vehicleId', 'profileId', 'profileName', 'status', 'progress', 'stage', 'error', 'scan', 'events', 'dtcCount', 'createdAt', 'updatedAt'],
    sql: ['id', '"userId"', '"vehicleId"', '"profileId"', '"profileName"', 'status', 'progress', 'stage', 'error', 'scan', 'events', '"dtcCount"', 'created_at', 'updated_at'],
  },
  reports: {
    table: 'reports',
    columns: ['id', 'sessionId', 'userId', 'title', 'template', 'technician', 'diagnosticStatus', 'storedDtcCount', 'pendingDtcCount', 'dtcs', 'vehicle', 'recommendations', 'createdAt'],
    sql: ['id', '"sessionId"', '"userId"', 'title', 'template', 'technician', '"diagnosticStatus"', '"storedDtcCount"', '"pendingDtcCount"', 'dtcs', 'vehicle', 'recommendations', 'created_at'],
  },
  devices: {
    table: 'devices',
    columns: ['id', 'userId', 'name', 'kind', 'address', 'status', 'pairedAt', 'createdAt'],
    sql: ['id', '"userId"', 'name', 'kind', 'address', 'status', '"pairedAt"', 'created_at'],
  },
  subscriptions: {
    table: 'subscriptions',
    columns: ['id', 'userId', 'plan', 'active', 'selectedAt'],
    sql: ['id', '"userId"', 'plan', 'active', '"selectedAt"'],
  },
  notifications: {
    table: 'notifications',
    columns: ['id', 'userId', 'type', 'title', 'body', 'sessionId', 'read', 'createdAt'],
    sql: ['id', '"userId"', 'type', 'title', 'body', '"sessionId"', 'read', 'created_at'],
  },
  audit: {
    table: 'audit_log',
    columns: ['id', 'ts', 'actorId', 'action', 'meta'],
    sql: ['id', 'ts', '"actorId"', 'action', 'meta'],
  },
};

/** child collections must be rewritten before their parents (FK order). */
const FLUSH_ORDER = ['notifications', 'subscriptions', 'reports', 'devices', 'sessions', 'vehicles', 'audit', 'users'];

class PostgresStore {
  constructor({ connectionString = process.env.DATABASE_URL, pool = null } = {}) {
    if (!connectionString && !pool) throw new Error('PostgresStore requires DATABASE_URL or a pool');
    this.connectionString = connectionString;
    this.pool = pool || new (loadPg().Pool)({ connectionString, max: 5 });
    this.data = null;
    this.dirty = new Set();
    this._flushTimer = null;
  }

  async open() {
    this.data = { meta: { schemaVersion: 1, backend: 'postgresql', createdAt: new Date().toISOString() } };
    for (const name of Object.keys(TABLES)) {
      const { table, columns, sql } = TABLES[name];
      const res = await this.pool.query(`SELECT ${sql.join(', ')} FROM ${table}`);
      this.data[name] = res.rows.map((r) => {
        const row = {};
        columns.forEach((jsonKey, i) => {
          row[jsonKey] = r[i] !== undefined && r[i] !== null ? r[i] : null;
        });
        return row;
      });
    }
    return this;
  }

  /** Returns the live array for a collection (mutations are flushed later). */
  collection(name) {
    if (!this.data) throw new Error('store not open');
    if (!this.data[name]) this.data[name] = [];
    this.dirty.add(name);
    return this.data[name];
  }

  meta() { return this.data.meta; }

  /** Queue a debounced flush (called after mutations). */
  scheduleFlush() {
    if (this._flushTimer) return;
    this._flushTimer = setTimeout(async () => { this._flushTimer = null; try { await this.flush(); } catch (e) { /* noop */ } }, 120);
    if (this._flushTimer.unref) this._flushTimer.unref();
  }

  /** Rewrite every touched collection into its table, in one transaction. */
  async flush() {
    if (this._flushTimer) { clearTimeout(this._flushTimer); this._flushTimer = null; }
    if (this.dirty.size === 0) return;
    const client = typeof this.pool.connect === 'function' ? await this.pool.connect() : this.pool;
    const isPoolClient = typeof client.release === 'function';
    try {
      await client.query('BEGIN');
      for (const name of FLUSH_ORDER) {
        if (!this.dirty.has(name)) continue;
        const { table, columns, sql } = TABLES[name];
        await client.query(`DELETE FROM ${table}`);
        const rows = this.data[name] || [];
        for (let i = 0; i < rows.length; i += 200) {
          const chunk = rows.slice(i, i + 200);
          const values = [];
          const placeholders = chunk.map((row, r) => {
            const group = columns.map((c, colIdx) => {
              values.push(row[c] !== undefined ? row[c] : null);
              return `$${r * columns.length + colIdx + 1}`;
            });
            return `(${group.join(', ')})`;
          });
          await client.query(
            `INSERT INTO ${table} (${sql.join(', ')}) VALUES ${placeholders.join(', ')}`,
            values
          );
        }
        this.dirty.delete(name);
      }
      await client.query('COMMIT');
    } catch (e) {
      try { await client.query('ROLLBACK'); } catch (x) { /* noop */ }
      throw e;
    } finally {
      if (isPoolClient) client.release();
    }
  }

  async close() {
    if (this._flushTimer) clearTimeout(this._flushTimer);
    if (typeof this.pool.end === 'function') await this.pool.end().catch(() => {});
  }
}

module.exports = { PostgresStore };
