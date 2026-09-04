'use strict';
/**
 * VEHDiag Simulator — TCP ELM327 server.
 * Speaks ELM327 over raw TCP (default port 35000, like WiFi ELM327 clones),
 * so real terminal clients (or the web dashboard) can connect to the
 * virtual vehicle exactly as they would to hardware.
 */

const net = require('net');
const { createSession, destroySession, VEHICLE_PROFILES } = require('../../diagnostics/simulator');

class TcpElmServer {
  constructor({ port = 35000, host = '0.0.0.0', log = () => {} } = {}) {
    this.port = port;
    this.host = host;
    this.log = log;
    this.connections = new Map();
    this.server = null;
  }

  start() {
    this.server = net.createServer((socket) => {
      const id = `tcp-${Date.now()}-${Math.floor(Math.random() * 1e4)}`;
      const profileId = Object.keys(VEHICLE_PROFILES)[0];
      const sim = createSession(profileId, { seed: Math.floor(Math.random() * 2 ** 31) });
      const conn = { id, socket, sim, buffer: '' };
      this.connections.set(id, conn);
      this.log(`[tcp-elm] connection ${id} from ${socket.remoteAddress} (profile ${profileId})`);
      socket.write('ELM327 v1.5 (VEHDiag Simulator)\r\r>');

      socket.on('data', (chunk) => {
        conn.buffer += chunk.toString('latin1');
        let idx;
        while ((idx = conn.buffer.indexOf('\r')) !== -1) {
          const line = conn.buffer.slice(0, idx + 1);
          conn.buffer = conn.buffer.slice(idx + 1);
          const resp = String(sim.elmCommand(line));
          if (resp) {
            try { socket.write(resp); } catch (e) { this.log(`[tcp-elm] ${id} write error: ${e.message}`); }
            socket.write('>');
          }
        }
        if (conn.buffer.length > 512) conn.buffer = conn.buffer.slice(-512);
      });

      socket.on('error', (e) => this.log(`[tcp-elm] ${id} error: ${e.message}`));
      socket.on('close', () => {
        destroySession(sim.id);
        this.connections.delete(id);
        this.log(`[tcp-elm] ${id} closed`);
      });
    });
    return new Promise((resolve, reject) => {
      this.server.once('error', reject);
      this.server.listen(this.port, this.host, () => {
        this.log(`[tcp-elm] listening on ${this.host}:${this.port}`);
        resolve(this);
      });
    });
  }

  stop() {
    for (const [, c] of this.connections) { try { c.socket.destroy(); } catch (e) { /* noop */ } }
    this.connections.clear();
    if (this.server) this.server.close();
  }
}

module.exports = { TcpElmServer };
