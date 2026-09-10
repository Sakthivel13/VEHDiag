'use strict';
/**
 * VEHDiag — ECU registry: definitions for virtual vehicles.
 * Each ECU: CAN addressing, supported UDS services, DIDs (data
 * identifiers) with encoding metadata, and (for reference) the live
 * signals it publishes. The vehicle profiles own signal values;
 * this registry owns addressing, capabilities and DID encoding.
 */

const A = (len) => ({ ascii: true, bytes: len });

const ECU_DEFS = {
  /* ---------- ICE (petrol) ---------- */
  ecm: {
    ecuId: 'ecm', name: 'Engine Control Module', kind: 'ice', protocol: 'obd',
    can: { rxId: 0x7e0, txId: 0x7e8 },
    supportedServices: [0x10, 0x11, 0x14, 0x19, 0x22, 0x23, 0x27, 0x2e, 0x3e],
    dids: {
      0x0090: { name: 'VIN', ...A(17) },
      0x00a2: { name: 'ECU serial number', ...A(10) },
      0xf100: { name: 'Software version', ...A(10) },
      0xf101: { name: 'Calibration ID', ...A(16) },
      0xf102: { name: 'Hardware part number', ...A(12) },
      0xf110: { name: 'ECU programming date', ...A(8) },
      0xf190: { name: 'VIN (repeat)', ...A(17) },
      0xf1b0: { name: 'Mileage (odometer)', type: 'u32', unit: 'km', scale: 1 },
      0xf1b1: { name: 'Engine runtime total', type: 'u32', unit: 's', scale: 1 },
      0xf040: { name: 'Engine RPM', type: 'u16', unit: 'rpm', scale: 1 },
      0xf041: { name: 'Coolant temperature', type: 'u8', unit: '°C', scale: 1, offset: 40 },
      0xf042: { name: 'Vehicle speed', type: 'u8', unit: 'km/h', scale: 1 },
      0xf043: { name: 'Engine load', type: 'u8', unit: '%', scale: 0.3921568627 },
      0xf044: { name: 'Throttle position', type: 'u8', unit: '%', scale: 0.3921568627 },
      0xf046: { name: 'Battery voltage', type: 'u16', unit: 'V', scale: 0.001 },
    },
  },
  tcm: {
    ecuId: 'tcm', name: 'Transmission Control Module', kind: 'ice', protocol: 'uds',
    can: { rxId: 0x7e1, txId: 0x7e9 },
    supportedServices: [0x10, 0x11, 0x14, 0x19, 0x22, 0x3e],
    dids: {
      0x0090: { name: 'VIN', ...A(17) },
      0xf190: { name: 'VIN (repeat)', ...A(17) },
      0xf1a0: { name: 'Gear position', type: 'u8', scale: 1 },
      0xf1a1: { name: 'Transmission fluid temperature', type: 'u16', unit: '°C', scale: 1 },
      0xf1a2: { name: 'Output shaft speed', type: 'u16', unit: 'rpm', scale: 1 },
    },
  },
  abs: {
    ecuId: 'abs', name: 'ABS Control Module', kind: 'ice', protocol: 'uds',
    can: { rxId: 0x7e2, txId: 0x7ea },
    supportedServices: [0x10, 0x11, 0x14, 0x19, 0x22, 0x3e],
    dids: {
      0x0090: { name: 'VIN', ...A(17) },
      0xf190: { name: 'VIN (repeat)', ...A(17) },
      0xf2a0: { name: 'Wheel speed FL', type: 'u16', unit: 'km/h', scale: 1 },
      0xf2a1: { name: 'Wheel speed FR', type: 'u16', unit: 'km/h', scale: 1 },
      0xf2a4: { name: 'Brake pedal travel', type: 'u8', unit: '%', scale: 1 },
    },
  },

  /* ---------- EV ---------- */
  bms: {
    ecuId: 'bms', name: 'Battery Management System', kind: 'ev', protocol: 'uds',
    can: { rxId: 0x620, txId: 0x628 },
    supportedServices: [0x10, 0x11, 0x14, 0x19, 0x22, 0x27, 0x2e, 0x3e],
    dids: {
      0x0090: { name: 'VIN', ...A(17) },
      0x1001: { name: 'State of Charge', type: 'u8', unit: '%', scale: 1 },
      0x1002: { name: 'State of Health', type: 'u8', unit: '%', scale: 1 },
      0x1003: { name: 'Pack voltage', type: 'u16', unit: 'V', scale: 0.1 },
      0x1004: { name: 'Pack current', type: 's16', unit: 'A', scale: 0.1 },
      0x1005: { name: 'Cell voltage (max)', type: 'u16', unit: 'V', scale: 0.001 },
      0x1006: { name: 'Cell voltage (min)', type: 'u16', unit: 'V', scale: 0.001 },
      0x1007: { name: 'Pack temperature', type: 'u8', unit: '°C', scale: 1 },
      0x1008: { name: 'Charging cycles', type: 'u16', scale: 1 },
      0xf190: { name: 'VIN (repeat)', ...A(17) },
    },
  },
  vcu: {
    ecuId: 'vcu', name: 'Vehicle Control Unit', kind: 'ev', protocol: 'uds',
    can: { rxId: 0x605, txId: 0x60d },
    supportedServices: [0x10, 0x11, 0x14, 0x19, 0x22, 0x2e, 0x3e],
    dids: {
      0x0090: { name: 'VIN', ...A(17) },
      0x2001: { name: 'DC bus voltage', type: 'u16', unit: 'V', scale: 0.1 },
      0x2002: { name: 'DC bus current', type: 's16', unit: 'A', scale: 0.1 },
      0x2003: { name: 'Drive mode', type: 'u8', scale: 1 },
      0xf190: { name: 'VIN (repeat)', ...A(17) },
    },
  },
  mcu: {
    ecuId: 'mcu', name: 'Motor Control Unit', kind: 'ev', protocol: 'uds',
    can: { rxId: 0x610, txId: 0x618 },
    supportedServices: [0x10, 0x11, 0x14, 0x19, 0x22, 0x2e, 0x3e],
    dids: {
      0x0090: { name: 'VIN', ...A(17) },
      0x3001: { name: 'Motor speed', type: 'u16', unit: 'rpm', scale: 1 },
      0x3002: { name: 'Motor torque', type: 's16', unit: 'Nm', scale: 1 },
      0x3003: { name: 'Motor temperature', type: 'u8', unit: '°C', scale: 1, offset: 40 },
      0x3004: { name: 'Inverter temperature', type: 'u8', unit: '°C', scale: 1, offset: 40 },
      0x3005: { name: 'Motor power', type: 's16', unit: 'kW', scale: 0.1 },
    },
  },
  obc: {
    ecuId: 'obc', name: 'On-Board Charger', kind: 'ev', protocol: 'uds',
    can: { rxId: 0x640, txId: 0x648 },
    supportedServices: [0x10, 0x11, 0x14, 0x19, 0x22, 0x2e, 0x3e],
    dids: {
      0x0090: { name: 'VIN', ...A(17) },
      0x4001: { name: 'AC input voltage', type: 'u16', unit: 'V', scale: 1 },
      0x4002: { name: 'Charging power', type: 'u16', unit: 'kW', scale: 0.1 },
      0x4003: { name: 'Charging status', type: 'u8', scale: 1 },
      0x4004: { name: 'Total energy charged', type: 'u32', unit: 'kWh', scale: 0.1 },
    },
  },
};

class EcuRegistry {
  get(ecuId) { return ECU_DEFS[ecuId] || null; }
  list() { return Object.values(ECU_DEFS); }
  forKind(kind) { return Object.values(ECU_DEFS).filter((e) => e.kind === kind); }
  all() { return ECU_DEFS; }
}

const registry = new EcuRegistry();

module.exports = { registry, EcuRegistry, ECU_DEFS };
