'use strict';
/**
 * VEHDiag — UDS (ISO 14229-1) protocol services.
 * Service handlers, negative response codes, security access flow,
 * and multi-frame response helpers. Used by both the UDS client in
 * the web app and the virtual-ECU UDS servers in the simulator.
 */

const NRC = {
  0x10: 'generalReject',
  0x11: 'serviceNotSupported',
  0x12: 'subFunctionNotSupported',
  0x13: 'incorrectMessageLengthOrInvalidFormat',
  0x14: 'responseTooLong',
  0x21: 'busyRepeatRequest',
  0x22: 'conditionsNotCorrect',
  0x24: 'requestSequenceError',
  0x25: 'noResponseFromSubnetComponent',
  0x26: 'failurePreventsExecution',
  0x31: 'requestOutOfRange',
  0x33: 'securityAccessDenied',
  0x35: 'invalidKey',
  0x36: 'exceedNumberOfAttempts',
  0x37: 'requiredTimeDelayNotExpired',
  0x70: 'uploadDownloadNotAccepted',
  0x71: 'transferDataSuspended',
  0x72: 'generalProgrammingFailure',
  0x73: 'wrongBlockSequenceCounter',
  0x78: 'requestCorrectlyReceivedResponsePending',
  0x7e: 'subFunctionNotSupportedInActiveSession',
  0x7f: 'serviceNotSupportedInActiveSession',
};
// PascalCase aliases (used by the simulator's ECU-side handlers)
for (const [code, name] of Object.entries(NRC)) {
  const alias = name.replace(/^[a-z]/, (c) => c.toUpperCase());
  if (!(alias in NRC)) NRC[alias] = parseInt(code, 10);
}

const SESSION = {
  DEFAULT: 0x01,
  PROGRAMMING: 0x02,
  EXTENDED: 0x03,
  SAFETY: 0x04,
};

const SERVICES = {
  DIAGNOSTIC_SESSION_CONTROL: 0x10,
  ECU_RESET: 0x11,
  CLEAR_DTC: 0x14,
  READ_DTC: 0x19,
  READ_DATA_BY_ID: 0x22,
  READ_MEMORY: 0x23,
  SECURITY_ACCESS: 0x27,
  WRITE_DATA_BY_ID: 0x2e,
  ROUTINE_CONTROL: 0x31,
  REQUEST_DOWNLOAD: 0x34,
  TRANSFER_DATA: 0x36,
  REQUEST_TRANSFER_EXIT: 0x37,
  TESTER_PRESENT: 0x3e,
  NEGATIVE_RESPONSE: 0x7f,
};
// PascalCase aliases (used by the simulator's ECU-side handlers)
Object.assign(SERVICES, {
  DiagnosticSessionControl: 0x10,
  EcuReset: 0x11,
  ClearDiagnosticInformation: 0x14,
  ReadDtcInformation: 0x19,
  ReadDataByIdentifier: 0x22,
  ReadMemoryByAddress: 0x23,
  SecurityAccess: 0x27,
  WriteDataByIdentifier: 0x2e,
  RoutineControl: 0x31,
  RequestDownload: 0x34,
  TransferData: 0x36,
  RequestTransferExit: 0x37,
  TesterPresent: 0x3e,
  NegativeResponse: 0x7f,
});

/** Build a negative response frame: [0x7F, service, nrc] */
function negativeResponse(service, nrc) { return [SERVICES.NEGATIVE_RESPONSE, service, nrc]; }
function positiveResponse(service, data = []) { return [service | 0x40, ...data]; }

/** Wrap a UDS conversation (request/response pairs) over a raw byte transport. */
class UdsSession {
  /**
   * @param {object} transport — anything with `request(bytes) => Promise<number[]>`
   * @param {object} opts — { timeoutMs, retries, onLog }
   */
  constructor(transport, { timeoutMs = 1000, retries = 2, onLog = () => {} } = {}) {
    this.transport = transport;
    this.timeoutMs = timeoutMs;
    this.retries = retries;
    this.onLog = onLog;
    this.activeSession = SESSION.DEFAULT;
    this.authenticated = false;
    this.downloadAuthorized = false;
    this.lastRequest = null;
  }

  _parse(raw) {
    const bytes = Array.from(raw);
    if (bytes.length < 2) return { raw: bytes };
    const sid = bytes[0];
    if (sid === SERVICES.NEGATIVE_RESPONSE) {
      const nrc = bytes[2];
      return { raw: bytes, negative: true, service: bytes[1], nrc, name: NRC[nrc] || `nrc0x${nrc.toString(16)}` };
    }
    return { raw: bytes, positive: true, service: sid & 0xbf, data: bytes.slice(1) };
  }

  /** Low-level request with 0x21 retry and 0x78 response-pending polling. */
  async request(bytes, { raw = false } = {}) {
    this.lastRequest = bytes;
    let resp;
    for (let attempt = 0; attempt <= this.retries; attempt++) {
      resp = await this._once(bytes);
      if (resp.timeout) break; // no response — never retry/poll
      if (!resp.negative || resp.nrc !== 0x21 || attempt === this.retries) break;
    }
    if (resp.negative && resp.nrc === 0x78 && !resp.timeout) {
      // response pending — poll with Tester Present (or suppress), with timeout
      const deadline = Date.now() + this.timeoutMs * 10;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 50));
        resp = await this._once([SERVICES.TESTER_PRESENT, 0x00]);
        if (!(resp.negative && resp.nrc === 0x78)) break;
      }
    }
    if (raw) return resp;
    if (resp.positive && resp.service === SERVICES.SECURITY_ACCESS) this.authenticated = true;
    return resp.raw !== undefined ? resp.raw : resp;
  }

  async _once(bytes) {
    let raw;
    try {
      raw = await Promise.race([
        this.transport.request(bytes),
        new Promise((_, reject) => {
          const t = setTimeout(() => reject(new Error('uds_timeout')), this.timeoutMs);
          if (t.unref) t.unref();
        }),
      ]);
    } catch (e) {
      try { if (this.transport && this.transport.cancel) this.transport.cancel(); } catch (x) { /* noop */ }
      return { negative: true, service: bytes[0], nrc: 0x78, name: 'timeout', error: e.message, timeout: true };
    }
    return this._parse(raw);
  }

  /* ---- services ---- */
  async testerPresent() { return this.request([SERVICES.TESTER_PRESENT, 0x00]); }
  async diagnosticSessionControl(session) {
    const r = await this.request([SERVICES.DIAGNOSTIC_SESSION_CONTROL, session]);
    this.activeSession = session;
    return r;
  }
  async ecuReset(type = 0x01) { return this.request([SERVICES.ECU_RESET, type]); }
  async readDataByIdentifier(did) { return this.request([SERVICES.READ_DATA_BY_ID, (did >> 8) & 0xff, did & 0xff]); }
  async securityAccess(sub, key = null) {
    const req = [SERVICES.SECURITY_ACCESS, sub];
    if (key !== null) req.push(...key);
    const r = await this.request(req);
    if (!r.negative) this.authenticated = true;
    return r;
  }
  async writeDataByIdentifier(did, data) {
    return this.request([SERVICES.WRITE_DATA_BY_ID, (did >> 8) & 0xff, did & 0xff, ...data]);
  }
  async readDtc(sub = 0x02, mask = [0xff, 0xff, 0xff]) {
    return this.request([SERVICES.READ_DTC, sub, ...mask]);
  }
  async clearDtc() { return this.request([SERVICES.CLEAR_DTC, 0xff, 0xff, 0xff]); }
  async requestDownload({ format = 0x00, address = 0, size = 0, compressed = false, encrypting = false } = {}) {
    const r = this.request([
      SERVICES.REQUEST_DOWNLOAD,
      (compressed ? 0x10 : 0) | (encrypting ? 0x20 : 0) | format,
      ((address >> 24) & 0xff), ((address >> 16) & 0xff), ((address >> 8) & 0xff), address & 0xff,
      ((size >> 24) & 0xff), ((size >> 16) & 0xff), ((size >> 8) & 0xff), size & 0xff,
    ]);
    return r;
  }
}

module.exports = { UdsSession, NRC, SESSION, SERVICES, negativeResponse, positiveResponse };
