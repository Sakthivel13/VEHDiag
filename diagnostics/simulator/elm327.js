'use strict';
/**
 * VEHDiag Simulator — ELM327 interpreter.
 * A faithful ELM327 v1.5-style AT/OBD command interpreter backed by a
 * VirtualVehicle, including protocol detection, echo/header/space/linefeed
 * controls and fault-injection hooks (timeouts, no-response, bus busy).
 */

const { PIDS, encodePid, encodeDtcs, INFO_PIDS } = require('../obd');

const PROTOCOLS = {
  '0': 'AUTO',
  '1': 'SAE J1850 PWM',
  '2': 'SAE J1850 VPW',
  '3': 'ISO 9141-2',
  '4': 'ISO 14230-4 KWP (5BAUD INIT)',
  '5': 'ISO 14230-4 KWP (FAST INIT)',
  '6': 'ISO 15765-4 CAN (11 BIT ID, 500 KBAUD)',
  '7': 'ISO 15765-4 CAN (29 BIT ID, 500 KBAUD)',
  '8': 'ISO 15765-4 CAN (11 BIT ID, 250 KBAUD)',
  '9': 'ISO 15765-4 CAN (29 BIT ID, 250 KBAUD)',
  A: 'ISO 15765-4 CAN (29 BIT ID, 250 KBAUD)',
  B: 'USER1 CAN',
  C: 'USER2 CAN',
};

class Elm327Interpreter {
  constructor(vehicle, { onLog = () => {} } = {}) {
    this.vehicle = vehicle;
    this.onLog = onLog;
    this.reset();
  }

  reset() {
    this.echo = true;
    this.headers = false;
    this.spaces = true;
    this.linefeeds = false;
    this.protocol = '0';
    this.protocolName = 'AUTO';
    this.adaptiveTiming = 2;
    this.timeoutMs = 300;
    this.longMessages = false;
    this.headerBytes = null; // forced header (ATSH)
    this.filter = null;      // CAN filter (ATCRA)
    this.remember = false;   // ATWM
    this.memory = false;     // ATM1
    this.currentEcu = 'ecm'; // OBD routing target
    this.searched = false;
    this.buffer = '';
  }

  /** Feed a raw command line; returns array of response lines (without CR). */
  handleLine(line) {
    const raw = line.replace(/\r?\n$/, '');
    if (this.echo && raw) this.onLog({ dir: 'echo', line: raw });
    const cmd = raw.trim();
    let responses = [];
    if (!cmd) return ''; // empty line → no response (never return the bare array)

    if (/^(AT|at)/.test(cmd)) responses = this._handleAt(cmd);
    else responses = this._handleObd(cmd);

    const out = [];
    for (const r of responses) {
      this.onLog({ dir: 'out', line: r });
      out.push(r + '\r');
    }
    return out.join('');
  }

  /* ---------------- AT commands ---------------- */
  _handleAt(cmd) {
    const c = cmd.toUpperCase();
    const ok = () => ['OK'];
    let [head, ...rest] = c.split(/\s+/);
    let arg = rest.join('');
    // ELM327 accepts inline args (e.g. ATSP6 == ATSP 6, ATSH7E0 == ATSH 7E0)
    const inline = /^(ATSP|ATTP|ATSH|ATCRA|ATAT|ATST|ATBRD)(.+)$/.exec(head);
    if (inline && !arg) { head = inline[1]; arg = inline[2]; }
    switch (head) {
      case 'ATZ': case 'ATWS': this.reset(); return [this.vehicle.ecuName('ecm')];
      case 'ATD': this.reset(); return ok();
      case 'ATI': return [`ELM327 v1.5 (VEHDiag Simulator)`];
      case 'AT@1': return ['VEHDiag Virtual ELM327'];
      case 'AT@2': return ['VEHDiAG-ELM-2026'];
      case 'ATE0': this.echo = false; return ok();
      case 'ATE1': this.echo = true; return ok();
      case 'ATL0': this.linefeeds = false; return ok();
      case 'ATL1': this.linefeeds = true; return ok();
      case 'ATH0': this.headers = false; return ok();
      case 'ATH1': this.headers = true; return ok();
      case 'ATS0': this.spaces = false; return ok();
      case 'ATS1': this.spaces = true; return ok();
      case 'ATAL': this.longMessages = true; return ok();
      case 'ATNL': this.longMessages = false; return ok();
      case 'ATM0': this.memory = false; return ok();
      case 'ATM1': this.memory = true; return ok();
      case 'ATWM': this.remember = true; return ok();
      case 'ATSP': {
        const p = arg || '0';
        if (!(p in PROTOCOLS)) return ['?'];
        this.protocol = p;
        this.protocolName = PROTOCOLS[p];
        return ok();
      }
      case 'ATTP': {
        const p = arg || '0';
        if (!(p in PROTOCOLS)) return ['?'];
        this.protocol = p;
        this.protocolName = PROTOCOLS[p];
        return ok();
      }
      case 'ATDP': return [`AUTO, ${this.protocolName}`];
      case 'ATDPN': return [`A${this.protocol === '0' ? '6' : this.protocol}`];
      case 'ATAT': {
        const t = parseInt(arg, 10);
        if ([0, 1, 2].includes(t)) { this.adaptiveTiming = t; return ok(); }
        return ['?'];
      }
      case 'ATST': {
        const t = parseInt(arg, 16);
        if (!Number.isNaN(t) && t >= 0 && t <= 0xff) { this.timeoutMs = t * 4; return ok(); }
        return ['?'];
      }
      case 'ATRV': return [this._fmt([(14.2 * 1000) >> 8, (14.2 * 1000) & 0xff])]; // 14.2V
      case 'ATIGN': return this.vehicle.ignition ? ['ON'] : ['OFF'];
      case 'ATSH': {
        const h = arg.replace(/\s+/g, '');
        if (/^[0-9A-Fa-f]{3,8}$/.test(h)) { this.headerBytes = h; return ok(); }
        return ['?'];
      }
      case 'ATCRA': {
        const h = arg.replace(/\s+/g, '');
        if (/^[0-9A-Fa-f]{3,8}$/.test(h)) { this.filter = h; return ok(); }
        return ['?'];
      }
      case 'ATCF': this.filter = null; return ok();
      case 'ATCAF0': case 'ATCFC0': return ok(); // formatting controls accepted
      case 'ATCAF1': case 'ATCFC1': return ok();
      case 'ATBRD': {
        const d = parseInt(arg, 16);
        return Number.isNaN(d) ? ['?'] : ok(); // baud divisor accepted, ignored
      }
      case 'ATBD': return ['1F'];
      case 'ATIIA': return [this._fmt([0xf1])];
      case 'ATFI': this.filter = null; return ok();
      case 'ATKW': return ['7E0 7E8'];
      case 'ATKW0': case 'ATKW1': return ok();
      case 'ATAR': return ok();
      case 'ATPC': return ['?'];
      default: return ['?'];
    }
  }

  /* ---------------- OBD requests ---------------- */
  _handleObd(cmd) {
    const tokens = cmd.trim().split(/\s+/).filter(Boolean);
    if (!tokens.length) return [];
    // ELM327 accepts "0100" or "01 00" — expand tokens > 2 hex chars into bytes
    const hexBytes = tokens.flatMap((t) => {
      const clean = t.replace(/^0x/i, '');
      if (!/^[0-9A-Fa-f]+$/.test(clean) || clean.length % 2 !== 0) return [NaN];
      const out = [];
      for (let i = 0; i < clean.length; i += 2) out.push(parseInt(clean.slice(i, i + 2), 16));
      return out;
    });
    const bytes = hexBytes;
    if (bytes.some(Number.isNaN)) return ['?'];

    if (this.vehicle.faults.has('disconnect')) return ['UNABLE TO CONNECT'];
    if (this.vehicle.faults.has('bus_busy')) return ['BUS BUSY'];
    if (this.vehicle.faults.has('no_response') && bytes[0] !== 0x04) return ['NO DATA'];

    const mode = bytes[0];
    const pid = bytes.length > 1 ? bytes[1] : null;

    // protocol search preamble (once)
    const preamble = !this.searched ? (this.searched = true, ['SEARCHING...', this.protocol === '0' ? 'ISO 15765-4 CAN (11 BIT ID, 500 KBAUD)' : this.protocolName]) : [];

    switch (mode) {
      case 0x01: return [...preamble, ...this._mode01(pid)];
      case 0x02: return [...preamble, ...this._mode02(pid)];
      case 0x03: return [...preamble, this._mode03()];
      case 0x04: return [...preamble, this._mode04()];
      case 0x05: return [...preamble, 'NO DATA'];
      case 0x06: return [...preamble, 'NO DATA'];
      case 0x07: return [...preamble, this._mode07()];
      case 0x08: return [...preamble, 'NO DATA'];
      case 0x09: return [...preamble, ...this._mode09(pid)];
      case 0x0a: return [...preamble, this._mode0A()];
      default: return ['?'];
    }
  }

  _fmt(bytes) {
    const h = bytes.map((b) => b.toString(16).toUpperCase().padStart(2, '0'));
    return h.join(this.spaces ? ' ' : '');
  }

  _hdr(prefix, payload) {
    const hex = this._fmt(payload);
    if (this.headers) {
      const id = this.headerBytes || (this.currentEcu === 'ecm' ? '7E8' : '7EA');
      return `${id} ${prefix} ${hex}`;
    }
    return `${prefix} ${hex}`;
  }

  _mode01(pid) {
    if (pid === null || pid === undefined) return ['?'];
    if (pid === 0x00) return [this._hdr('41 00', this._pidMask(0x00))];
    if (pid === 0x20) return [this._hdr('41 20', this._pidMask(0x20))];
    if (pid === 0x40) return [this._hdr('41 40', this._pidMask(0x40))];
    if (pid === 0x60) return [this._hdr('41 60', this._pidMask(0x60))];
    if (pid === 0x80) return [this._hdr('41 80', this._pidMask(0x80))];
    if (pid === 0xa0) return [this._hdr('41 A0', this._pidMask(0xa0))];
    if (pid === 0xc0) return [this._hdr('41 C0', this._pidMask(0xc0))];

    const ecu = this.vehicle.getEcu(this.currentEcu);
    if (!ecu || !ecu.pids.includes(pid)) return ['NO DATA'];

    if (pid === 0x01) {
      // monitor status since DTCs cleared
      const mil = this.vehicle.mil ? 0x80 : 0;
      const count = ecu.dtcs.filter((d) => d.status & 0x08).length;
      const tests = 0x07; // spark/comp/misfire/fuel monitored
      return [this._hdr('41 01', [mil | count, tests, 0x00, 0x00])];
    }
    const def = PIDS[pid];
    const sig = this.vehicle.signalByPid(this.currentEcu, pid);
    if (!sig) return ['NO DATA'];
    const data = encodePid(pid, sig.value);
    if (!data) return ['NO DATA'];
    return [this._hdr(`41 ${pid.toString(16).toUpperCase().padStart(2, '0')}`, data)];
  }

  _pidMask(base) {
    const mask = new Array(4).fill(0);
    for (const p of this.vehicle.supportedPids(this.currentEcu)) {
      if (p > base && p <= base + 0x20) {
        const bit = p - base - 1;
        mask[3 - (bit >> 3)] |= 1 << (bit & 7);
      }
    }
    return mask;
  }

  _mode02(pid) {
    if (pid === null || pid === undefined) return ['?'];
    const ecu = this.vehicle.getEcu(this.currentEcu);
    const stored = ecu.dtcs.find((d) => d.status & 0x08 && d.freeze);
    if (!stored || !stored.freeze) return ['NO DATA'];
    if (pid === 0x00) return [this._hdr('42 00', this._pidMask(0x00))];
    if (pid === 0x02) return [this._hdr('42 02', encodeDtcs([stored.code]).slice(0, 2))];
    const v = stored.freeze.values[pid];
    if (v === undefined) return ['NO DATA'];
    const data = encodePid(pid, v);
    return [this._hdr(`42 ${pid.toString(16).toUpperCase().padStart(2, '0')}`, data)];
  }

  _mode03() {
    const ecu = this.vehicle.getEcu(this.currentEcu);
    const codes = ecu.dtcs.filter((d) => d.status & 0x08).map((d) => d.code);
    if (!codes.length) return this._hdr('43 00', encodeDtcs([]));
    const packed = encodeDtcs(codes.slice(0, 3));
    return this._hdr(`43 ${codes.length.toString(16).toUpperCase().padStart(2, '0')}`, packed);
  }

  _mode04() { this.vehicle.clearDtcs(this.currentEcu); return this._hdr('44 00', []); }
  _mode07() {
    const ecu = this.vehicle.getEcu(this.currentEcu);
    const codes = ecu.dtcs.filter((d) => d.status & 0x04).map((d) => d.code);
    if (!codes.length) return this._hdr('47 00', encodeDtcs([]));
    return this._hdr(`47 ${codes.length.toString(16).toUpperCase().padStart(2, '0')}`, encodeDtcs(codes.slice(0, 3)));
  }
  _mode0A() {
    const ecu = this.vehicle.getEcu(this.currentEcu);
    const codes = ecu.dtcs.filter((d) => d.status & 0x50).map((d) => d.code);
    if (!codes.length) return this._hdr('4A 00', encodeDtcs([]));
    return this._hdr(`4A ${codes.length.toString(16).toUpperCase().padStart(2, '0')}`, encodeDtcs(codes.slice(0, 3)));
  }

  _mode09(pid) {
    const ecu = this.vehicle.getEcu(this.currentEcu);
    const prefix = '49';
    if (pid === 0x00) {
      const mask = new Array(4).fill(0);
      for (const p of [0x02, 0x04, 0x06, 0x08, 0x09, 0x0a]) {
        if (p <= 0x20) { const bit = p - 1; mask[3 - (bit >> 3)] |= 1 << (bit & 7); }
      }
      return [this._hdr(`${prefix} 00`, mask)];
    }
    const ascii = (s, n) => [...s.padEnd(n, ' ').slice(0, n)].map((ch) => ch.charCodeAt(0));
    switch (pid) {
      case 0x02: return [this._hdr(`${prefix} 02 01`, ascii(this.vehicle.vin(), 17))];
      case 0x04: return [this._hdr(`${prefix} 04 01`, ascii(this.vehicle.calid(this.currentEcu), 16))];
      case 0x06: return [this._hdr(`${prefix} 06 01`, [...Buffer.from(this.vehicle.cvn(this.currentEcu), 'hex')].slice(0, 4))];
      case 0x09: return [this._hdr(`${prefix} 09 01`, ascii(this.vehicle.ecuName(this.currentEcu), 20))];
      case 0x0a: return [this._hdr(`${prefix} 0A 01`, ascii(this.vehicle.ecuName(this.currentEcu), 20))];
      default: return ['NO DATA'];
    }
  }
}

module.exports = { Elm327Interpreter, PROTOCOLS };
