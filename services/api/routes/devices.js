'use strict';
/** VEHDiag — /api/v1/devices: diagnostic adapter registry (ELM327 BT/USB/TCP, CAN, Simulator). */

const { HttpError, ok, readJson, newId, clampStr } = require('../lib/http');

const DEVICE_KINDS = ['elm327-bluetooth', 'elm327-usb', 'elm327-wifi', 'can-socketcan', 'can-pcan', 'can-kvaser', 'can-vector', 'simulator'];

function mount(router, { store, log, tcp }) {
  const mine = (req) => store.collection('devices').filter((d) => d.userId === req.user.id);

  router.get('/api/v1/devices', async (req, res) => {
    const list = mine(req).map((d) => {
      if (d.kind === 'simulator') {
        return { ...d, online: true, simulatorTcp: tcp() ? { host: '127.0.0.1', port: tcp().port } : null };
      }
      return { ...d, online: false };
    });
    ok(res, { devices: list });
  });

  router.post('/api/v1/devices', async (req, res) => {
    const body = await readJson(req);
    if (!DEVICE_KINDS.includes(body.kind)) throw new HttpError(400, 'Unknown device kind', 'invalid_device');
    const device = {
      id: newId(),
      userId: req.user.id,
      name: clampStr(body.name, 60) || body.kind,
      kind: body.kind,
      address: clampStr(body.address, 80), // BT MAC / USB path / TCP host:port
      status: 'registered',
      pairedAt: null,
      lastSeenAt: null,
      firmware: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    store.collection('devices').push(device);
    store.scheduleFlush();
    log.app('info', 'device_registered', { userId: req.user.id, deviceId: device.id, kind: device.kind });
    ok(res, { device }, 201);
  });

  /** Pair: simulates the adapter handshake (AT ping over the TCP simulator for ELM327). */
  router.post('/api/v1/devices/:id/pair', async (req, res) => {
    const d = mine(req).find((x) => x.id === req.params.id);
    if (!d) throw new HttpError(404, 'Device not found', 'not_found');
    const net = require('net');
    const result = await new Promise((resolve) => {
      if (d.kind === 'simulator' && tcp()) {
        const sock = net.connect(tcp().port, '127.0.0.1');
        let buf = '';
        const timer = setTimeout(() => { sock.destroy(); resolve({ ok: false, error: 'pairing timeout' }); }, 3000);
        sock.on('connect', () => sock.write('ATZ\r'));
        sock.on('data', (c) => {
          buf += c.toString('latin1');
          if (buf.includes('ELM327')) {
            clearTimeout(timer);
            sock.destroy();
            resolve({ ok: true, response: buf.split('\r').slice(0, 2).join(' | ') });
          }
        });
        sock.on('error', () => { clearTimeout(timer); resolve({ ok: false, error: 'simulator unreachable' }); });
      } else if (d.kind.startsWith('elm327')) {
        resolve({ ok: true, response: 'AT handshake accepted (device offline in this environment — simulated pairing)' });
      } else {
        resolve({ ok: false, error: 'CAN interfaces require a hardware driver on the host' });
      }
    });
    if (result.ok) {
      d.status = 'paired';
      d.pairedAt = new Date().toISOString();
      d.lastSeenAt = d.pairedAt;
      store.scheduleFlush();
      log.diag('info', 'device_paired', { deviceId: d.id });
    }
    ok(res, { device: d, pairResult: result });
  });

  router.post('/api/v1/devices/:id/test', async (req, res) => {
    const d = mine(req).find((x) => x.id === req.params.id);
    if (!d) throw new HttpError(404, 'Device not found', 'not_found');
    const body = await readJson(req).catch(() => ({}));
    const line = clampStr(body.line, 64) || 'ATZ';
    const result = await new Promise((resolve) => {
      if (d.kind === 'simulator' && tcp()) {
        const net = require('net');
        const sock = net.connect(tcp().port, '127.0.0.1');
        let buf = '';
        const timer = setTimeout(() => { sock.destroy(); resolve({ ok: false, error: 'timeout' }); }, 2500);
        sock.on('connect', () => sock.write(line + '\r'));
        sock.on('data', (c) => {
          buf += c.toString('latin1');
          if (buf.includes('>') && buf.trim().length > 2) {
            clearTimeout(timer); sock.destroy();
            resolve({ ok: true, response: buf.split('\r').filter((l) => l && l !== '>').join(' | ') });
          }
        });
        sock.on('error', () => { clearTimeout(timer); resolve({ ok: false, error: 'simulator unreachable' }); });
      } else {
        resolve({ ok: false, error: 'device not reachable in this environment' });
      }
    });
    ok(res, { device: d, testResult: result });
  });

  router.delete('/api/v1/devices/:id', async (req, res) => {
    const i = mine(req).findIndex((x) => x.id === req.params.id);
    if (i < 0) throw new HttpError(404, 'Device not found', 'not_found');
    store.collection('devices').splice(i, 1);
    store.scheduleFlush();
    ok(res, { deleted: true });
  });
}

module.exports = { mount };
