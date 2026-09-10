'use strict';
/**
 * VEHDiag — WebSocket server (RFC 6455), zero dependencies.
 * Handshake, frame decode/encode, ping/pong heartbeats, close handshake.
 */

const crypto = require('crypto');

const OPCODES = { CONTINUATION: 0x0, TEXT: 0x1, BINARY: 0x2, CLOSE: 0x8, PING: 0x9, PONG: 0xa };
const GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';

class WsConnection {
  constructor(socket, { heartbeat = 30000, onClose = () => {} } = {}) {
    this.socket = socket;
    this.id = `ws-${crypto.randomBytes(6).toString('hex')}`;
    this.closed = false;
    this.onClose = onClose;
    this._hb = setInterval(() => {
      if (this.closed) return;
      try { this.ping(); } catch (e) { this.close(1011, 'heartbeat failed'); }
    }, heartbeat);
    if (this._hb.unref) this._hb.unref();
  }

  static accept(key) {
    return crypto.createHash('sha1').update(key + GUID).digest('base64');
  }

  send(obj) {
    if (this.closed) return false;
    try {
      const payload = Buffer.from(JSON.stringify(obj), 'utf8');
      this._writeFrame(OPCODES.TEXT, payload);
      return true;
    } catch (e) { return false; }
  }

  sendRaw(data) {
    if (this.closed) return false;
    try { this._writeFrame(OPCODES.BINARY, Buffer.isBuffer(data) ? data : Buffer.from(data)); return true; } catch (e) { return false; }
  }

  ping() { if (!this.closed) this._writeFrame(OPCODES.PING, Buffer.alloc(0)); }
  pong() { if (!this.closed) this._writeFrame(OPCODES.PONG, Buffer.alloc(0)); }

  close(code = 1000, reason = '') {
    if (this.closed) return;
    this.closed = true;
    try {
      const body = Buffer.alloc(2 + Buffer.byteLength(reason));
      body.writeUInt16BE(code, 0);
      body.write(reason, 2);
      this._writeFrame(OPCODES.CLOSE, body);
    } catch (e) { /* noop */ }
    if (this._hb) clearInterval(this._hb);
    this.onClose(this);
    try { this.socket.destroy(); } catch (e) { /* noop */ }
  }

  _writeFrame(opcode, payload) {
    if (this.closed) return;
    const len = payload.length;
    let header;
    if (len < 126) {
      header = Buffer.from([0x80 | opcode, len]);
    } else if (len < 65536) {
      header = Buffer.alloc(4);
      header[0] = 0x80 | opcode; header[1] = 126; header.writeUInt16BE(len, 2);
    } else {
      header = Buffer.alloc(10);
      header[0] = 0x80 | opcode; header[1] = 127;
      header.writeBigUInt64BE(BigInt(len), 2);
    }
    this.socket.write(Buffer.concat([header, payload]));
  }

  /** Feed socket data in; returns array of decoded text/binary messages. */
  handleData(chunk) {
    this._buffer = this._buffer ? Buffer.concat([this._buffer, chunk]) : chunk;
    const messages = [];
    for (;;) {
      if (this._buffer.length < 2) break;
      const b0 = this._buffer[0], b1 = this._buffer[1];
      const fin = (b0 & 0x80) !== 0;
      const opcode = b0 & 0x0f;
      const masked = (b1 & 0x80) !== 0;
      let len = b1 & 0x7f;
      let offset = 2;
      if (len === 126) {
        if (this._buffer.length < 4) break;
        len = this._buffer.readUInt16BE(2); offset = 4;
      } else if (len === 127) {
        if (this._buffer.length < 10) break;
        len = Number(this._buffer.readBigUInt64BE(2)); offset = 10;
      }
      let mask = null;
      if (masked) {
        if (this._buffer.length < offset + 4) break;
        mask = this._buffer.slice(offset, offset + 4); offset += 4;
      }
      if (this._buffer.length < offset + len) break;
      const payload = this._buffer.slice(offset, offset + len);
      this._buffer = this._buffer.slice(offset + len);
      if (mask) for (let i = 0; i < payload.length; i++) payload[i] ^= mask[i & 3];

      switch (opcode) {
        case OPCODES.CLOSE: this.close(1000, 'client close'); break;
        case OPCODES.PING: this.pong(); break;
        case OPCODES.PONG: break;
        case OPCODES.TEXT: if (fin) messages.push({ type: 'text', data: payload.toString('utf8') }); break;
        case OPCODES.BINARY: if (fin) messages.push({ type: 'binary', data: payload }); break;
        default: break; // continuation frames unsupported (clients don't fragment here)
      }
    }
    if (this._buffer && this._buffer.length > 4 * 1024 * 1024) this.close(1009, 'message too big');
    return messages;
  }
}

/**
 * Upgrade handling for a Node http server 'upgrade' event.
 * onConnection(conn, message) — message is null for the connection-open event.
 * onClose(conn) — fired when the connection closes.
 */
function attachWs(httpServer, { path = '/ws', onConnection = () => {}, onClose = () => {}, log = () => {} } = {}) {
  httpServer.on('upgrade', (req, socket) => {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname !== path) { socket.destroy(); return; }
    const key = req.headers['sec-websocket-key'];
    if (!key) { socket.write('HTTP/1.1 400 Bad Request\r\n\r\n'); socket.destroy(); return; }
    socket.write(
      'HTTP/1.1 101 Switching Protocols\r\n' +
      'Upgrade: websocket\r\n' +
      'Connection: Upgrade\r\n' +
      `Sec-WebSocket-Accept: ${WsConnection.accept(key)}\r\n\r\n`
    );
    const conn = new WsConnection(socket, { onClose: (c) => { try { onClose(c); } catch (e) { /* noop */ } } });
    log({ level: 'info', msg: `ws connected ${conn.id}` });
    onConnection(conn, null);
    socket.on('data', (chunk) => {
      try {
        const msgs = conn.handleData(chunk);
        for (const m of msgs) onConnection(conn, m);
      } catch (e) { try { conn.close(1011, 'frame error'); } catch (x) { /* noop */ } }
    });
    socket.on('error', () => { try { conn.close(1011, 'socket error'); } catch (x) { /* noop */ } });
    socket.on('close', () => conn.close(1000, 'socket close'));
  });
}

module.exports = { WsConnection, attachWs, OPCODES };
