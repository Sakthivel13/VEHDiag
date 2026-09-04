'use strict';
/**
 * VEHDiag — asynchronous structured logging.
 * Application, diagnostic, security, audit and error channels are separate.
 * Every diagnostic entry carries its session_id; logs are flushed by a
 * single background writer so the request path never blocks on I/O.
 */

const fs = require('fs');
const path = require('path');

const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 };

class Logger {
  constructor({ dir = path.join(process.cwd(), 'data', 'logs'), level = 'info', stdout = true } = {}) {
    this.dir = dir;
    this.level = LEVELS[level] || LEVELS.info;
    this.stdout = stdout;
    this.queue = [];
    this.writing = false;
    this.channels = new Map(); // channel -> write stream
    try { fs.mkdirSync(this.dir, { recursive: true }); } catch (e) { /* read-only fs */ }
  }

  _stream(channel) {
    let s = this.channels.get(channel);
    if (!s) {
      try {
        s = fs.createWriteStream(path.join(this.dir, `${channel}.log`), { flags: 'a' });
      } catch (e) { return null; }
      this.channels.set(channel, s);
    }
    return s;
  }

  /** Emit one structured record to a channel. */
  log(channel, level, msg, fields = {}) {
    if (LEVELS[level] < this.level) return;
    const rec = { ts: new Date().toISOString(), level, channel, msg, ...fields };
    if (this.stdout) {
      const line = `[${rec.ts}] ${channel.toUpperCase()} ${level.padEnd(5)} ${msg} ${JSON.stringify(fields)}`;
      if (level === 'error') console.error(line); else console.log(line);
    }
    const stream = this._stream(channel);
    if (!stream) return;
    this.queue.push({ stream, line: JSON.stringify(rec) });
    this._flush();
  }

  _flush() {
    if (this.writing || !this.queue.length) return;
    this.writing = true;
    setImmediate(() => {
      const batch = this.queue.splice(0, this.queue.length);
      for (const { stream, line } of batch) {
        try { stream.write(line + '\n'); } catch (e) { /* noop */ }
      }
      this.writing = false;
      if (this.queue.length) this._flush();
    });
  }

  app(level, msg, fields) { this.log('app', level, msg, fields); }
  diag(level, msg, fields) { this.log('diagnostics', level, msg, fields); }
  can(level, msg, fields) { this.log('can', level, msg, fields); }
  sec(level, msg, fields) { this.log('security', level, msg, fields); }
  audit(level, msg, fields) { this.log('audit', level, msg, fields); }
  err(level, msg, fields) { this.log('error', level, msg, fields); }

  close() {
    for (const s of this.channels.values()) { try { s.end(); } catch (e) { /* noop */ } }
    this.channels.clear();
  }
}

module.exports = { Logger };
