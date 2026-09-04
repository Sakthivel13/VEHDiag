'use strict';
/**
 * VEHDiag — OBD-II (SAE J1979) codec.
 * Mode 01 PID definitions with decoding formulas, DTC packing,
 * and mode 09 vehicle-information types. Pure functions, fully tested.
 */

/* PIDS: id -> { name, unit, bytes, fn(A,B,C,D), min, max } */
const PIDS = {
  0x00: { name: 'PIDs supported [01-20]', unit: '', bytes: 4, fn: (A) => A },
  0x01: { name: 'Monitor status', unit: '', bytes: 4, fn: (A) => A },
  0x03: { name: 'Fuel system status', unit: '', bytes: 2, fn: (A, B) => [A, B].join(',') },
  0x04: { name: 'Calculated engine load', unit: '%', bytes: 1, fn: (A) => (A * 100) / 255 },
  0x05: { name: 'Engine coolant temperature', unit: '°C', bytes: 1, fn: (A) => A - 40 },
  0x06: { name: 'Short term fuel trim — Bank 1', unit: '%', bytes: 1, fn: (A) => ((A - 128) * 100) / 128 },
  0x07: { name: 'Long term fuel trim — Bank 1', unit: '%', bytes: 1, fn: (A) => ((A - 128) * 100) / 128 },
  0x0A: { name: 'Fuel pressure', unit: 'kPa', bytes: 1, fn: (A) => A * 3 },
  0x0B: { name: 'Intake manifold absolute pressure', unit: 'kPa', bytes: 1, fn: (A) => A },
  0x0C: { name: 'Engine RPM', unit: 'rpm', bytes: 2, fn: (A, B) => ((A * 256) + B) / 4 },
  0x0D: { name: 'Vehicle speed', unit: 'km/h', bytes: 1, fn: (A) => A },
  0x0E: { name: 'Timing advance', unit: '°', bytes: 1, fn: (A) => A / 2 - 64 },
  0x0F: { name: 'Intake air temperature', unit: '°C', bytes: 1, fn: (A) => A - 40 },
  0x10: { name: 'MAF air flow rate', unit: 'g/s', bytes: 2, fn: (A, B) => ((A * 256) + B) / 100 },
  0x11: { name: 'Throttle position', unit: '%', bytes: 1, fn: (A) => (A * 100) / 255 },
  0x12: { name: 'Commanded secondary air status', unit: '', bytes: 1, fn: (A) => A },
  0x13: { name: 'Oxygen sensors present (Bank 1)', unit: '', bytes: 1, fn: (A) => A },
  0x14: { name: 'O2 Sensor 1 — voltage', unit: 'V', bytes: 2, fn: (A, B) => A / 200, },
  0x15: { name: 'O2 Sensor 1 — short term fuel trim', unit: '%', bytes: 2, fn: (A) => ((A - 128) * 100) / 128 },
  0x1C: { name: 'OBD standard', unit: '', bytes: 1, fn: (A) => A },
  0x1F: { name: 'Run time since engine start', unit: 's', bytes: 2, fn: (A, B) => A * 256 + B },
  0x21: { name: 'Distance travelled with MIL on', unit: 'km', bytes: 2, fn: (A, B) => A * 256 + B },
  0x2F: { name: 'Fuel level input', unit: '%', bytes: 1, fn: (A) => (A * 100) / 255 },
  0x33: { name: 'Absolute barometric pressure', unit: 'kPa', bytes: 1, fn: (A) => A },
  0x42: { name: 'Control module voltage', unit: 'V', bytes: 2, fn: (A, B) => ((A * 256) + B) / 1000 },
  0x45: { name: 'Relative throttle position', unit: '%', bytes: 1, fn: (A) => (A * 100) / 255 },
  0x46: { name: 'Ambient air temperature', unit: '°C', bytes: 1, fn: (A) => A - 40 },
  0x4C: { name: 'Commanded throttle actuator', unit: '%', bytes: 1, fn: (A) => (A * 100) / 255 },
  0x51: { name: 'Fuel type', unit: '', bytes: 1, fn: (A) => A },
  0x5C: { name: 'Engine oil temperature', unit: '°C', bytes: 1, fn: (A) => A - 40 },
};

/** Mode 09 (vehicle info) types. */
const INFO_TYPES = {
  0x02: { name: 'VIN', decode: (bytes) => bytes.map((b) => String.fromCharCode(b)).join('').trim() },
  0x04: { name: 'Calibration ID', decode: (bytes) => bytes.map((b) => String.fromCharCode(b)).join('').trim() },
  0x06: { name: 'Calibration Verification Number', decode: (bytes) => bytes.map((b) => String.fromCharCode(b)).join('').trim() },
  0x0A: { name: 'ECU name', decode: (bytes) => bytes.map((b) => String.fromCharCode(b)).join('').trim() },
};

const MODE_NAMES = {
  0x01: 'Current data',
  0x02: 'Freeze frame data',
  0x03: 'Stored DTCs',
  0x04: 'Clear DTCs',
  0x07: 'Pending DTCs',
  0x09: 'Vehicle information',
  0x0A: 'Permanent DTCs',
};

/** Decode a single PID response (A..D data bytes). */
function decodePid(pid, data) {
  const def = PIDS[pid];
  if (!def) return { pid, name: `PID ${pid.toString(16).toUpperCase().padStart(2, '0')}`, value: null, unit: '', raw: data };
  const [A, B, C, D] = [data[0], data[1], data[2], data[3]];
  const value = def.fn(A, B, C, D);
  const round = (v) => (typeof v === 'number' ? Math.round(v * 100) / 100 : v);
  return { pid, name: def.name, value: round(value), unit: def.unit, bytes: def.bytes };
}

/** Encode a human value back into data bytes for the given PID (inverse of fn). */
function encodePid(pid, value) {
  const def = PIDS[pid];
  if (!def) return null;
  switch (pid) {
    case 0x04: case 0x11: case 0x2F: case 0x45: case 0x4C:
      return [Math.round((value * 255) / 100) & 0xff];
    case 0x05: case 0x0F: case 0x46: case 0x5C:
      return [Math.round(value + 40) & 0xff];
    case 0x06: case 0x07: case 0x15:
      return [Math.round((value * 128) / 100 + 128) & 0xff];
    case 0x0C: {
      const raw = Math.round(value * 4);
      return [(raw >> 8) & 0xff, raw & 0xff];
    }
    case 0x42: {
      const raw = Math.round(value * 1000);
      return [(raw >> 8) & 0xff, raw & 0xff];
    }
    case 0x1F: case 0x21: {
      const raw = Math.round(value);
      return [(raw >> 8) & 0xff, raw & 0xff];
    }
    default:
      // generic single-byte passthrough
      return [Math.round(value) & 0xff];
  }
}

/** Pack one or more DTC codes into the 2-byte J1979 representation. */
function encodeDtcs(codes) {
  const bytes = [];
  for (const code of codes) {
    const m = String(code).toUpperCase().match(/^([PBCU])([0-9A-F])([0-9A-F])([0-9A-F])([0-9A-F])$/);
    if (!m) throw new Error(`Invalid DTC: ${code}`);
    const first = { P: 0, C: 1, B: 2, U: 3 }[m[1]] << 6;
    bytes.push(first | (parseInt(m[2], 16) << 4) | parseInt(m[3], 16));
    bytes.push((parseInt(m[4], 16) << 4) | parseInt(m[5], 16));
  }
  return bytes;
}

/** Decode J1979 packed DTC bytes back into codes. */
function decodeDtcs(bytes) {
  const codes = [];
  for (let i = 0; i + 1 < bytes.length; i += 2) {
    const b0 = bytes[i], b1 = bytes[i + 1];
    if (b0 === 0 && b1 === 0) continue; // padding
    const letter = ['P', 'C', 'B', 'U'][(b0 >> 6) & 0x3];
    codes.push(
      letter
      + ((b0 >> 4) & 0x3).toString(16).toUpperCase()
      + (b0 & 0xf).toString(16).toUpperCase()
      + ((b1 >> 4) & 0xf).toString(16).toUpperCase()
      + (b1 & 0xf).toString(16).toUpperCase()
    );
  }
  return codes;
}

/** Parse a mode 01/02 response line like "41 0C 1A F8" -> { pid, data } */
function parsePidResponse(line) {
  const tokens = String(line).trim().split(/\s+/).map((t) => parseInt(t, 16));
  if (tokens.length < 2 || tokens[0] !== 0x41) return null;
  const pid = tokens[1];
  return { pid, data: tokens.slice(2, 2 + 4) };
}

/** Parse a mode 03/07/0A response line like "43 01 01 33 00 00..." -> { count, codes } */
function parseDtcPayload(payloadBytes) {
  return decodeDtcs(Array.isArray(payloadBytes) ? payloadBytes : []);
}

module.exports = {
  PIDS,
  INFO_TYPES,
  MODE_NAMES,
  decodePid,
  encodePid,
  encodeDtcs,
  decodeDtcs,
  parsePidResponse,
  parseDtcPayload,
};
