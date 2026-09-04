'use strict';
/**
 * VEHDiag — DTC engine: decode, severity, and lookup against the
 * bundled library. The library itself is a curated set of common
 * OBD-II codes (seed data; extensible via JSON).
 */

const LIBRARY = require('./dtc-library.json');

const SYSTEMS = { P: 'Powertrain', C: 'Chassis', B: 'Body', U: 'Network' };

const DTC_RE = /^([PBCU])([0-9A-F])([0-9A-F])([0-9A-F])([0-9A-F])$/;

function isValid(code) { return DTC_RE.test(String(code).toUpperCase()); }

function decode(code) {
  const m = String(code).toUpperCase().match(DTC_RE);
  if (!m) return { code: String(code).toUpperCase(), valid: false };
  const [, letter, d1, d2, d3, d4] = m;
  const group = parseInt(d1, 16);
  let subsystem = null;
  if (letter === 'P') {
    subsystem = { 0: 'Fuel and air metering', 1: 'Fuel and air metering', 2: 'Fuel and air metering (injector circuit)', 3: 'Ignition system or misfire', 4: 'Auxiliary emission controls', 5: 'Vehicle speed, idle control, and auxiliary inputs', 6: 'Computer and auxiliary outputs', 7: 'Transmission', 8: 'Transmission', 9: 'Transmission' }[group] || 'Reserved';
  } else if (letter === 'C') {
    subsystem = group <= 3 ? 'Chassis systems' : 'Reserved';
  } else if (letter === 'B') {
    subsystem = group <= 3 ? 'Body systems' : 'Reserved';
  } else {
    subsystem = group <= 3 ? 'Network communication' : 'Reserved';
  }
  const generic = d2 === '0';
  const engineSpecific = !generic && d2 !== '3';
  return { code: String(code).toUpperCase(), valid: true, system: SYSTEMS[letter], subsystem, generic, engineSpecific };
}

const SEVERITY = {
  0: { level: 'info', rank: 0 },
  1: { level: 'low', rank: 1 },
  2: { level: 'medium', rank: 2 },
  3: { level: 'high', rank: 3 },
  4: { level: 'critical', rank: 4 },
};

const SEV_BY_NAME = { info: 0, low: 1, medium: 2, high: 3, critical: 4 };

function severityRank(sev) {
  if (typeof sev === 'number') return SEVERITY[sev] ? sev : 2;
  return SEV_BY_NAME[sev] !== undefined ? SEV_BY_NAME[sev] : 2;
}

const SEV_DEFAULT = { severity: 2, description: null };

function lookup(code) {
  const c = String(code).toUpperCase();
  const lib = LIBRARY[c] || null;
  const decoded = decode(c);
  return {
    ...decoded,
    severity: severityRank(lib ? lib.severity : SEV_DEFAULT.severity),
    severityLevel: SEVERITY[severityRank(lib ? lib.severity : SEV_DEFAULT.severity)].level,
    description: lib ? lib.description : `DTC ${c} — see manufacturer documentation`,
  };
}

function severityInfo(sev) { return SEVERITY[severityRank(sev)] || SEVERITY[2]; }

function decodeMany(codes) { return codes.map((c) => lookup(c)); }

module.exports = { isValid, decode, lookup, decodeMany, severityInfo, SYSTEMS, LIBRARY };
