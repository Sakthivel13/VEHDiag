'use strict';
/**
 * VEHDiag — PostgreSQL migration runner.
 *
 *   DATABASE_URL=postgres://user:pass@host:5432/vehdiag node scripts/migrate.js
 *
 * Applies database/migrations/*.sql in filename order, one migration per
 * transaction, recording each in schema_migrations. Idempotent: applied
 * migrations are skipped on re-runs.
 */

const fs = require('fs');
const path = require('path');
const { Client } = require('pg');

const ROOT = path.join(__dirname, '..');
const MIGRATIONS_DIR = path.join(ROOT, 'database', 'migrations');

async function main() {
  const url = process.env.DATABASE_URL;
  if (!url) {
    console.error('DATABASE_URL not set (postgres://user:pass@host:5432/vehdiag)');
    process.exit(1);
  }
  const client = new Client({ connectionString: url });
  await client.connect();

  await client.query(`CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
  )`);

  const files = fs.readdirSync(MIGRATIONS_DIR).filter((f) => f.endsWith('.sql')).sort();
  const done = new Set((await client.query('SELECT name FROM schema_migrations')).rows.map((r) => r.name));

  let applied = 0;
  for (const file of files) {
    if (done.has(file)) {
      console.log(`skip  ${file} (already applied)`);
      continue;
    }
    const sql = fs.readFileSync(path.join(MIGRATIONS_DIR, file), 'utf8');
    try {
      await client.query('BEGIN');
      await client.query(sql);
      await client.query('INSERT INTO schema_migrations (name) VALUES ($1)', [file]);
      await client.query('COMMIT');
      console.log(`apply ${file}`);
      applied++;
    } catch (e) {
      await client.query('ROLLBACK');
      console.error(`FAIL  ${file}: ${e.message}`);
      await client.end();
      process.exit(1);
    }
  }
  await client.end();
  console.log(applied ? `migrations applied: ${applied}` : 'up to date');
}

main().catch((e) => { console.error(e.message); process.exit(1); });
