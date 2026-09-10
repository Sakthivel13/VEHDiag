'use strict';
/**
 * VEHDiag Simulator — Virtual Vehicle.
 * Simulates ECUs, live signals, DTCs, freeze frames and VIN so the full
 * diagnostic stack runs without physical hardware.
 *
 * Signal models evolve per tick with bounded noise; every value is
 * deterministic-seeded per session so tests are reproducible.
 */

const crypto = require('crypto');
const { encodeDtcs } = require('../obd');

/** Deterministic PRNG (mulberry32) — reproducible sessions in tests/demos. */
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const VEHICLE_PROFILES = {
  'ice-sedan-2021': {
    id: 'ice-sedan-2021',
    name: 'Sedan · Petrol 1.5L (2021)',
    type: 'car',
    vin: 'MA3JF31S6MK441207',
    model: 'VEH Atlas Sedan',
    year: 2021,
    fuel: 'petrol',
    transmission: 'CVT',
    odometerKm: 41250,
    protocol: 'obd-ii',
    ecus: [
      {
        ecuId: 'ecm',
        initialDtcs: [
          { code: 'P0130', status: 0x08, freeze: { pid: 0x05, values: { 0x0c: 2540, 0x05: 88, 0x0b: 45, 0x0d: 62, 0x11: 21, 0x04: 34 } } },
          { code: 'P0351', status: 0x04, freeze: null },
        ],
        signals: {
          rpm: { name: 'Engine RPM', pid: 0x0c, unit: 'rpm', value: 850, min: 800, max: 6400, noise: 24, drift: 3 },
          coolant: { name: 'Coolant Temperature', pid: 0x05, unit: '°C', value: 88, min: 70, max: 105, noise: 0.4, drift: 0.05 },
          speed: { name: 'Vehicle Speed', pid: 0x0d, unit: 'km/h', value: 0, min: 0, max: 140, noise: 0.2, drift: 0 },
          load: { name: 'Engine Load', pid: 0x04, unit: '%', value: 34, min: 12, max: 92, noise: 1.4, drift: 0.2 },
          throttle: { name: 'Throttle Position', pid: 0x11, unit: '%', value: 21, min: 10, max: 88, noise: 0.5, drift: 0.1 },
          map: { name: 'Manifold Pressure', pid: 0x0b, unit: 'kPa', value: 45, min: 28, max: 98, noise: 0.6, drift: 0.1 },
          voltage: { name: 'Control Module Voltage', pid: 0x42, unit: 'V', value: 14.1, min: 12.8, max: 14.6, noise: 0.03, drift: 0.01 },
          iat: { name: 'Intake Air Temperature', pid: 0x0f, unit: '°C', value: 36, min: 25, max: 60, noise: 0.2, drift: 0.05 },
          fuel: { name: 'Fuel Level', pid: 0x2f, unit: '%', value: 62, min: 10, max: 100, noise: 0.02, drift: -0.001 },
          stft: { name: 'Short Term Fuel Trim', pid: 0x06, unit: '%', value: 1.2, min: -8, max: 8, noise: 0.5, drift: 0.1 },
          o2: { name: 'O2 Sensor Voltage', pid: 0x14, unit: 'V', value: 0.62, min: 0.1, max: 0.9, noise: 0.05, drift: 0.02 },
        },
        pids: [0x00, 0x01, 0x04, 0x05, 0x06, 0x0b, 0x0c, 0x0d, 0x0f, 0x11, 0x14, 0x1f, 0x21, 0x2c, 0x2f, 0x33, 0x42, 0x45, 0x46, 0x49, 0x4c, 0x51, 0x5a, 0x5c, 0x5e],
        dids: { 0xf040: 'rpm', 0xf041: 'coolant', 0xf042: 'speed', 0xf043: 'load', 0xf044: 'throttle', 0xf046: 'voltage' },
        calid: 'VEH-ECM-CAL-7712A',
        cvn: '1A2B3C4D',
        ecuName: 'ECM VEH1.5-2021',
      },
      {
        ecuId: 'abs',
        initialDtcs: [],
        signals: {
          wheelSpeed: { name: 'Wheel Speed', pid: null, unit: 'km/h', value: 0, min: 0, max: 140, noise: 0.2, drift: 0 },
        },
        pids: [],
        calid: 'VEH-ABS-CAL-0031',
        cvn: 'AABBCCDD',
        ecuName: 'ABS VEH-2021',
      },
    ],
  },

  'ev-scooter': {
    id: 'ev-scooter',
    name: 'E-Scooter · 3.2 kWh (2023)',
    type: 'ev',
    vin: 'MD9EVS232PN104587',
    model: 'VEH Volt Scooter',
    year: 2023,
    fuel: 'electric',
    transmission: 'single-speed',
    odometerKm: 6320,
    protocol: 'uds',
    ecus: [
      {
        ecuId: 'bms',
        initialDtcs: [
          { code: 'P0A1F', status: 0x04, freeze: null },
        ],
        signals: {
          soc: { name: 'Battery SOC', unit: '%', value: 81, min: 10, max: 100, noise: 0.02, drift: -0.002 },
          soh: { name: 'Battery SOH', unit: '%', value: 96, min: 0, max: 100, noise: 0.001, drift: 0 },
          packVoltage: { name: 'Pack Voltage', unit: 'V', value: 62.4, min: 48, max: 67.2, noise: 0.05, drift: 0.01 },
          packCurrent: { name: 'Pack Current', unit: 'A', value: 4.2, min: -40, max: 60, noise: 0.6, drift: 0.05 },
          cellMax: { name: 'Cell Voltage Max', unit: 'V', value: 4.08, min: 3.5, max: 4.2, noise: 0.002, drift: 0 },
          cellMin: { name: 'Cell Voltage Min', unit: 'V', value: 4.04, min: 3.5, max: 4.2, noise: 0.002, drift: 0 },
          packTemp: { name: 'Pack Temperature', unit: '°C', value: 32, min: 20, max: 55, noise: 0.1, drift: 0.02 },
        },
        dids: { 0x1001: 'soc', 0x1002: 'soh', 0x1003: 'packVoltage', 0x1004: 'packCurrent', 0x1005: 'cellMax', 0x1006: 'cellMin', 0x1007: 'packTemp' },
        ecuName: 'BMS VOLT-2023',
      },
      {
        ecuId: 'vcu',
        initialDtcs: [],
        signals: {
          dcBusVoltage: { name: 'DC Bus Voltage', unit: 'V', value: 62.4, min: 48, max: 67.2, noise: 0.05, drift: 0.01 },
          dcBusCurrent: { name: 'DC Bus Current', unit: 'A', value: 4.2, min: -40, max: 60, noise: 0.6, drift: 0.05 },
        },
        dids: { 0x2001: 'dcBusVoltage', 0x2002: 'dcBusCurrent' },
        ecuName: 'VCU VOLT-2023',
      },
      {
        ecuId: 'mcu',
        initialDtcs: [],
        signals: {
          motorSpeed: { name: 'Motor Speed', unit: 'rpm', value: 1800, min: 0, max: 9000, noise: 60, drift: 8 },
          motorTorque: { name: 'Motor Torque', unit: 'Nm', value: 9.5, min: -80, max: 90, noise: 2, drift: 0.2 },
          motorTemp: { name: 'Motor Temperature', unit: '°C', value: 48, min: 25, max: 120, noise: 0.2, drift: 0.03 },
          inverterTemp: { name: 'Inverter Temperature', unit: '°C', value: 44, min: 25, max: 110, noise: 0.2, drift: 0.03 },
        },
        dids: { 0x3001: 'motorSpeed', 0x3002: 'motorTorque', 0x3003: 'motorTemp', 0x3004: 'inverterTemp' },
        ecuName: 'MCU VOLT-2023',
      },
      {
        ecuId: 'obc',
        initialDtcs: [],
        signals: {
          acVoltage: { name: 'AC Input Voltage', unit: 'V', value: 230, min: 210, max: 250, noise: 0.4, drift: 0 },
          chargePower: { name: 'Charge Power', unit: 'kW', value: 0.75, min: 0, max: 3.3, noise: 0.02, drift: 0 },
          chargerTemp: { name: 'Charger Temperature', unit: '°C', value: 39, min: 25, max: 80, noise: 0.1, drift: 0.02 },
        },
        dids: { 0x4001: 'acVoltage', 0x4002: 'chargePower', 0x4003: 'chargerTemp' },
        ecuName: 'OBC VOLT-2023',
      },
    ],
  },

  'motorcycle-bs6': {
    id: 'motorcycle-bs6',
    name: 'Motorcycle · 350cc BS6 (2022)',
    type: 'motorcycle',
    vin: 'ME3JDR358NK123456',
    model: 'VEH Cruiser 350',
    year: 2022,
    fuel: 'petrol',
    transmission: 'manual-5',
    odometerKm: 18640,
    protocol: 'obd-ii',
    ecus: [
      {
        ecuId: 'ecm',
        initialDtcs: [],
        signals: {
          rpm: { name: 'Engine RPM', pid: 0x0c, unit: 'rpm', value: 1150, min: 1000, max: 8500, noise: 30, drift: 4 },
          coolant: { name: 'Coolant Temperature', pid: 0x05, unit: '°C', value: 92, min: 75, max: 115, noise: 0.5, drift: 0.05 },
          speed: { name: 'Vehicle Speed', pid: 0x0d, unit: 'km/h', value: 0, min: 0, max: 160, noise: 0.3, drift: 0 },
          load: { name: 'Engine Load', pid: 0x04, unit: '%', value: 28, min: 10, max: 95, noise: 1.5, drift: 0.2 },
          throttle: { name: 'Throttle Position', pid: 0x11, unit: '%', value: 14, min: 5, max: 95, noise: 0.6, drift: 0.1 },
          voltage: { name: 'Control Module Voltage', pid: 0x42, unit: 'V', value: 13.9, min: 12.4, max: 14.5, noise: 0.04, drift: 0.01 },
          iat: { name: 'Intake Air Temperature', pid: 0x0f, unit: '°C', value: 34, min: 20, max: 65, noise: 0.2, drift: 0.05 },
        },
        pids: [0x00, 0x01, 0x04, 0x05, 0x0b, 0x0c, 0x0d, 0x0f, 0x11, 0x1f, 0x21, 0x2f, 0x33, 0x42, 0x45, 0x46, 0x49, 0x4c, 0x5c],
        calid: 'VEH-MC-CAL-9034B',
        cvn: '55667788',
        ecuName: 'ECM CRUISER-350',
      },
      { ecuId: 'abs', initialDtcs: [], signals: {}, pids: [], ecuName: 'ABS CRUISER-350' },
    ],
  },

  'truck-diesel': {
    id: 'truck-diesel',
    name: 'Truck · Diesel 3.0L (2020)',
    type: 'truck',
    vin: 'MEXTRK300LG700114',
    model: 'VEH Hauler 3.0',
    year: 2020,
    fuel: 'diesel',
    transmission: 'manual-6',
    odometerKm: 98200,
    protocol: 'obd-ii',
    ecus: [
      {
        ecuId: 'ecm',
        initialDtcs: [
          { code: 'P0401', status: 0x08, freeze: { pid: 0x05, values: { 0x0c: 1900, 0x05: 84, 0x0b: 96, 0x0d: 55, 0x04: 61 } } },
        ],
        signals: {
          rpm: { name: 'Engine RPM', pid: 0x0c, unit: 'rpm', value: 800, min: 700, max: 4200, noise: 16, drift: 2 },
          coolant: { name: 'Coolant Temperature', pid: 0x05, unit: '°C', value: 84, min: 65, max: 108, noise: 0.4, drift: 0.05 },
          speed: { name: 'Vehicle Speed', pid: 0x0d, unit: 'km/h', value: 0, min: 0, max: 120, noise: 0.2, drift: 0 },
          load: { name: 'Engine Load', pid: 0x04, unit: '%', value: 42, min: 15, max: 100, noise: 1.2, drift: 0.2 },
          map: { name: 'Manifold Pressure', pid: 0x0b, unit: 'kPa', value: 112, min: 95, max: 220, noise: 1.5, drift: 0.2 },
          voltage: { name: 'Control Module Voltage', pid: 0x42, unit: 'V', value: 28.2, min: 24, max: 29.4, noise: 0.05, drift: 0.01 },
          fuel: { name: 'Fuel Level', pid: 0x2f, unit: '%', value: 74, min: 5, max: 100, noise: 0.02, drift: -0.001 },
        },
        pids: [0x00, 0x01, 0x04, 0x05, 0x0b, 0x0c, 0x0d, 0x0f, 0x1f, 0x21, 0x2c, 0x2f, 0x33, 0x42, 0x45, 0x46, 0x49, 0x4c, 0x5a, 0x5c, 0x5e],
        calid: 'VEH-DSL-CAL-1188C',
        cvn: '99AABBCC',
        ecuName: 'ECM HAULER-3.0',
      },
      { ecuId: 'abs', initialDtcs: [], signals: {}, pids: [], ecuName: 'ABS HAULER-3.0' },
      { ecuId: 'tcm', initialDtcs: [], signals: {}, pids: [], ecuName: 'TCM HAULER-3.0' },
    ],
  },
};

class VirtualVehicle {
  /**
   * @param profileId one of VEHICLE_PROFILES
   * @param options { seed, tickMs, injectFaults }
   */
  constructor(profileId, options = {}) {
    const profile = VEHICLE_PROFILES[profileId];
    if (!profile) throw new Error(`unknown vehicle profile: ${profileId}`);
    this.profile = JSON.parse(JSON.stringify(profile));
    this.options = options;
    this.tickMs = options.tickMs || 100;
    this.rand = mulberry32(options.seed !== undefined ? options.seed : crypto.randomInt(0, 2 ** 31));
    this.tickCount = 0;
    this.ignition = true;
    this.mil = this.profile.ecus.some((e) => e.initialDtcs.some((d) => d.status & 0x08));
    this._timer = null;
    this.faults = new Set();

    // per-ECU runtime state
    for (const ecu of this.profile.ecus) {
      ecu.dtcs = (ecu.initialDtcs || []).map((d) => ({
        code: d.code,
        status: d.status,
        freeze: d.freeze ? JSON.parse(JSON.stringify(d.freeze)) : null,
        occurredAt: new Date().toISOString(),
      }));
      ecu.session = 0x01; // default session
      ecu.securityLevel = 0;
      ecu.authenticated = false;
    }

    // flatten signal registry: ecuId -> signalKey -> signal
    this._signals = new Map();
    for (const ecu of this.profile.ecus) {
      const map = new Map();
      for (const [key, sig] of Object.entries(ecu.signals || {})) map.set(key, sig);
      this._signals.set(ecu.ecuId, map);
    }
  }

  start() {
    if (this._timer) return;
    this._timer = setInterval(() => this.tick(), this.tickMs);
    if (this._timer.unref) this._timer.unref();
  }

  stop() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
  }

  get isRunning() { return !!this._timer; }

  /** Advance all signals one step (noise + drift + clamping + profile curve). */
  tick() {
    this.tickCount++;
    if (this.faults.has('disconnect')) return;
    for (const ecu of this.profile.ecus) {
      for (const sig of Object.values(ecu.signals || {})) {
        const n = (this.rand() * 2 - 1) * (sig.noise || 0);
        let next = sig.value + n + (sig.drift || 0);
        if (sig.profile === 'rpm') {
          next = sig.min + (Math.sin(this.tickCount / 18) * 0.5 + 0.5) * (sig.max - sig.min) * 0.35;
        }
        sig.value = Math.min(sig.max, Math.max(sig.min, next));
      }
    }
  }

  listEcus() {
    return this.profile.ecus.map((e) => ({
      ecuId: e.ecuId,
      name: e.ecuName || e.ecuId.toUpperCase(),
      dtcCount: e.dtcs.length,
      signals: Object.keys(e.signals || {}).length,
    }));
  }

  getEcu(ecuId) { return this.profile.ecus.find((e) => e.ecuId === ecuId) || null; }

  /** DTCs by status filter: stored=0x08, pending=0x04, permanent=0x50. */
  readDtcs(ecuId, kind = 'stored') {
    const ecu = this.getEcu(ecuId);
    if (!ecu) return [];
    const mask = kind === 'stored' ? 0x08 : kind === 'pending' ? 0x04 : 0x50;
    return ecu.dtcs.filter((d) => d.status & mask);
  }

  clearDtcs(ecuId) {
    const ecu = this.getEcu(ecuId);
    if (!ecu) return;
    ecu.dtcs = ecu.dtcs.filter((d) => !(d.status & 0x08));
    this.mil = this.profile.ecus.some((e) => e.dtcs.some((d) => d.status & 0x08));
  }

  /** Freeze frame for a stored DTC. */
  freezeFrame(ecuId, code) {
    const ecu = this.getEcu(ecuId);
    if (!ecu) return null;
    const dtc = ecu.dtcs.find((d) => d.code === code);
    return dtc ? dtc.freeze : null;
  }

  /** Live value for a signal (PIDs map to signals via pid field). */
  signalValue(ecuId, key) {
    const m = this._signals.get(ecuId);
    const sig = m && m.get(key);
    return sig ? sig.value : null;
  }

  signalByPid(ecuId, pid) {
    const m = this._signals.get(ecuId);
    if (!m) return null;
    for (const sig of m.values()) if (sig.pid === pid) return sig;
    return null;
  }

  injectFault(name) { this.faults.add(name); }
  clearFault(name) { this.faults.delete(name); }
  hasFault(name) { return this.faults.has(name); }

  /** Supported OBD PIDs for an ECU (mode 01). */
  supportedPids(ecuId) { const e = this.getEcu(ecuId); return e ? e.pids || [] : []; }

  vin() { return this.profile.vin; }
  calid(ecuId) { const e = this.getEcu(ecuId); return e ? e.calid || '' : ''; }
  cvn(ecuId) { const e = this.getEcu(ecuId); return e ? e.cvn || '' : ''; }
  ecuName(ecuId) { const e = this.getEcu(ecuId); return e ? e.ecuName || e.ecuId.toUpperCase() : ''; }
  odometer() { return Math.round(this.profile.odometerKm + this.tickCount * 0.001); }
}

/** Encode the stored-DTC payload for mode 03-style responses. */
function dtcPayloadFor(ecu) {
  const codes = ecu.dtcs.filter((d) => d.status & 0x08).map((d) => d.code);
  return encodeDtcs(codes.slice(0, 3));
}

module.exports = { VirtualVehicle, VEHICLE_PROFILES, mulberry32, dtcPayloadFor };
