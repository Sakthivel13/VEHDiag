'use strict';
/**
 * VEHDiag — /api/v1/vehicles: vehicle management + VIN identification.
 */

const { HttpError, ok, readJson, isVin, newId, clampStr } = require('../lib/http');

/** Lightweight VIN decode (WMI/model-year/plant/check-digit), independent implementation. */
function decodeVin(vin) {
  const v = vin.toUpperCase();
  const yearChars = 'ABCDEFGHJKLMNPRSTVWXY123456789';
  const year = yearChars.indexOf(v[9]) >= 0 ? 1980 + yearChars.indexOf(v[9]) : null;
  // transliteration (no I,O,Q)
  const translit = { A: 1, B: 2, C: 3, D: 4, E: 5, F: 6, G: 7, H: 8, J: 1, K: 2, L: 3, M: 4, N: 5, P: 7, R: 9, S: 2, T: 3, U: 4, V: 5, W: 6, X: 7, Y: 8, Z: 9 };
  const weights = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2];
  let sum = 0;
  for (let i = 0; i < 17; i++) {
    const c = v[i];
    const num = /[0-9]/.test(c) ? parseInt(c, 10) : (translit[c] || 0);
    sum += num * weights[i];
  }
  const check = sum % 11 === 10 ? 'X' : String(sum % 11);
  return {
    vin: v,
    wmi: v.slice(0, 3),
    vds: v.slice(3, 8),
    vis: v.slice(8),
    modelYear: year,
    plant: v[10],
    checkDigit: v[8],
    checkDigitValid: check === v[8],
    valid: isVin(v),
  };
}

function mount(router, { store, log, notify }) {
  const mine = (req) => store.collection('vehicles').filter((v) => v.userId === req.user.id);

  router.get('/api/v1/vehicles', async (req, res) => {
    const q = String(req.query.q || '').toLowerCase();
    let list = mine(req);
    if (q) list = list.filter((v) => (v.vin + ' ' + v.model + ' ' + v.manufacturer).toLowerCase().includes(q));
    ok(res, { vehicles: list });
  });

  router.post('/api/v1/vehicles', async (req, res) => {
    const body = await readJson(req);
    const vin = clampStr(body.vin, 17).toUpperCase();
    if (vin && !isVin(vin)) throw new HttpError(400, 'Invalid VIN format (17 chars, no I/O/Q)', 'invalid_vin');
    const vehicle = {
      id: newId(),
      userId: req.user.id,
      vin: vin || null,
      manufacturer: clampStr(body.manufacturer, 60),
      model: clampStr(body.model, 80),
      variant: clampStr(body.variant, 60),
      year: Number.isInteger(body.year) ? body.year : null,
      engine: clampStr(body.engine, 60),
      fuel_type: clampStr(body.fuel_type, 30),
      transmission: clampStr(body.transmission, 40),
      mileage_km: Number.isFinite(body.mileage_km) ? body.mileage_km : null,
      plate: clampStr(body.plate, 20),
      notes: clampStr(body.notes, 500),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    store.collection('vehicles').push(vehicle);
    store.scheduleFlush();
    log.app('info', 'vehicle_created', { userId: req.user.id, vehicleId: vehicle.id });
    ok(res, { vehicle }, 201);
  });

  router.get('/api/v1/vehicles/:id', async (req, res) => {
    const v = mine(req).find((x) => x.id === req.params.id);
    if (!v) throw new HttpError(404, 'Vehicle not found', 'not_found');
    ok(res, { vehicle: v });
  });

  router.patch('/api/v1/vehicles/:id', async (req, res) => {
    const v = mine(req).find((x) => x.id === req.params.id);
    if (!v) throw new HttpError(404, 'Vehicle not found', 'not_found');
    const body = await readJson(req);
    const fields = ['manufacturer', 'model', 'variant', 'year', 'engine', 'fuel_type', 'transmission', 'mileage_km', 'plate', 'notes'];
    for (const f of fields) {
      if (body[f] !== undefined) v[f] = typeof body[f] === 'string' ? clampStr(body[f], f === 'notes' ? 500 : 80) : body[f];
    }
    if (body.vin !== undefined) {
      const vin = clampStr(body.vin, 17).toUpperCase();
      if (vin && !isVin(vin)) throw new HttpError(400, 'Invalid VIN format', 'invalid_vin');
      v.vin = vin || null;
    }
    v.updatedAt = new Date().toISOString();
    store.scheduleFlush();
    ok(res, { vehicle: v });
  });

  router.delete('/api/v1/vehicles/:id', async (req, res) => {
    const i = mine(req).findIndex((x) => x.id === req.params.id);
    if (i < 0) throw new HttpError(404, 'Vehicle not found', 'not_found');
    store.collection('vehicles').splice(i, 1);
    store.scheduleFlush();
    ok(res, { deleted: true });
  });

  /** Identify: decode a stored/queried VIN. */
  router.post('/api/v1/vehicles/:id/identify', async (req, res) => {
    const v = mine(req).find((x) => x.id === req.params.id);
    if (!v) throw new HttpError(404, 'Vehicle not found', 'not_found');
    const body = await readJson(req).catch(() => ({}));
    const vin = (body.vin || v.vin || '').toUpperCase();
    if (!isVin(vin)) throw new HttpError(400, 'A valid VIN is required to identify the vehicle', 'invalid_vin');
    const decoded = decodeVin(vin);
    if (!v.vin) v.vin = vin;
    v.identified = decoded;
    v.updatedAt = new Date().toISOString();
    store.scheduleFlush();
    ok(res, { vehicle: v, decoded });
  });

  router.get('/api/v1/vin/decode', async (req, res) => {
    const vin = String(req.query.vin || '').toUpperCase();
    if (!isVin(vin)) throw new HttpError(400, 'Invalid VIN', 'invalid_vin');
    ok(res, { decoded: decodeVin(vin) });
  });
}

module.exports = { mount, decodeVin };
