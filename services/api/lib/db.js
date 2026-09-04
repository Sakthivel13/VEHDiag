'use strict';
/**
 * VEHDiag — data layer.
 *
 * DataStore interface with two adapters:
 *   - JsonStore (default, zero-dependency, atomic writes, development/test)
 *   - PostgresStore (production; selected via DATABASE_URL, see db/postgres.js)
 *
 * Migrations are versioned; production schemas are never edited by hand.
 */

const fs = require('fs');
const path = require('path');

class JsonStore {
  constructor(file = path.join(process.cwd(), 'data', 'db.json')) {
    this.file = file;
    this.dirty = false;
    this._flushTimer = null;
    this.data = null;
  }

  async open() {
    fs.mkdirSync(path.dirname(this.file), { recursive: true });
    if (fs.existsSync(this.file)) {
      this.data = JSON.parse(fs.readFileSync(this.file, 'utf8'));
    } else {
      this.data = {};
    }
    // structural baseline (kept in sync by migrations)
    for (const coll of ['users', 'vehicles', 'sessions', 'reports', 'devices', 'subscriptions', 'notifications', 'audit']) {
      if (!Array.isArray(this.data[coll])) this.data[coll] = [];
    }
    this.data.meta = this.data.meta || { schemaVersion: 1, createdAt: new Date().toISOString() };
    await this.flush();
    return this;
  }

  collection(name) {
    if (!this.data[name]) this.data[name] = [];
    return this.data[name];
  }

  meta() { return this.data.meta; }

  async flush() {
    if (this._flushTimer) clearTimeout(this._flushTimer);
    this._flushTimer = null;
    const tmp = this.file + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(this.data, null, 2));
    fs.renameSync(tmp, this.file); // atomic on POSIX
  }

  /** Queue a debounced flush (called after mutations). */
  scheduleFlush() {
    if (this._flushTimer) return;
    this._flushTimer = setTimeout(async () => { this._flushTimer = null; try { await this.flush(); } catch (e) { /* noop */ } }, 120);
    if (this._flushTimer.unref) this._flushTimer.unref();
  }

  async close() { if (this._flushTimer) clearTimeout(this._flushTimer); await this.flush(); }
}

/** Collection helpers shared by adapters. */
function byId(coll, id) { return coll.find((x) => x.id === id); }
function upsert(coll, item) { const i = coll.findIndex((x) => x.id === item.id); if (i >= 0) coll[i] = item; else coll.push(item); }
function remove(coll, id) { const i = coll.findIndex((x) => x.id === id); if (i >= 0) coll.splice(i, 1); return i >= 0; }

module.exports = { JsonStore, byId, upsert, remove };
