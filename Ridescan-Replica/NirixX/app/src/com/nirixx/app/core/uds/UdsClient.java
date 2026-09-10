package com.nirixx.app.core.uds;

/** UDS (ISO 14229) service layer on top of IsoTp — real requests, real parsing.
 *  Pure Java; a scripted Link makes every method unit-testable off-device.
 *
 *  Rules honoured here:
 *   - 0x7F responses are surfaced as UdsError carrying the NRC (see Nrc.java)
 *   - NRC 0x78 (Response Pending) is waited out (P2*) instead of failing
 *   - no request is executed unless the session/security preconditions the
 *     caller set up are met — this class verifies responses, not magic. */
public final class UdsClient {

    public static final class UdsError extends Exception {
        public final int serviceId;
        public final Nrc nrc;
        public UdsError(int sid, int nrcCode) {
            super("ECU refused 0x" + hex(sid) + " — " + Nrc.of(nrcCode).name
                    + " (0x" + hex(nrcCode) + ")");
            this.serviceId = sid; this.nrc = Nrc.of(nrcCode);
        }
    }

    private final IsoTp tp;
    public UdsClient(IsoTp tp) { this.tp = tp; }

    // ------------------------------------------------------------ primitives
    /** Raw request; transparently waits through Response-Pending. */
    public byte[] uds(byte[] req, int timeoutMs) throws Exception {
        byte[] resp = tp.request(req, timeoutMs);
        int guard = 0;
        while (isNegative(resp) && (resp[2] & 0xFF) == 0x78 && guard++ < 40) {
            resp = tp.awaitResponse(5000);
        }
        if (isNegative(resp)) throw new UdsError(resp[1] & 0xFF, resp[2] & 0xFF);
        return resp;
    }

    private static boolean isNegative(byte[] r) {
        return r != null && r.length >= 3 && (r[0] & 0xFF) == 0x7F;
    }

    /** Verify the positive SID echoes request SID + 0x40. */
    private static byte[] positive(byte[] resp, int reqSid) throws UdsError {
        if (resp.length < 1 || (resp[0] & 0xFF) != (reqSid + 0x40))
            throw new UdsError(reqSid, 0x10);
        byte[] out = new byte[resp.length - 1];
        System.arraycopy(resp, 1, out, 0, out.length);
        return out;
    }

    // ------------------------------------------------------------ services
    /** 0x10 — Diagnostic Session Control. Returns the raw session-parameter record. */
    public byte[] sessionControl(int level) throws Exception {
        return positive(uds(new byte[]{0x10, (byte) level}, 2500), 0x10);
    }

    /** 0x11 — ECU Reset. */
    public byte[] ecuReset(int resetType) throws Exception {
        return positive(uds(new byte[]{0x11, (byte) resetType}, 2500), 0x11);
    }

    /** 0x22 — Read Data By Identifier. */
    public byte[] readDid(int did) throws Exception {
        byte[] req = new byte[]{0x22, (byte) (did >> 8), (byte) did};
        byte[] d = positive(uds(req, 3000), 0x22);
        if (d.length < 2 || ((d[0] & 0xFF) << 8 | (d[1] & 0xFF)) != did)
            throw new UdsError(0x22, 0x10);
        byte[] out = new byte[d.length - 2];
        System.arraycopy(d, 2, out, 0, out.length);
        return out;
    }

    /** 0x2E — Write Data By Identifier. */
    public void writeDid(int did, byte[] data) throws Exception {
        byte[] req = new byte[3 + data.length];
        req[0] = 0x2E; req[1] = (byte) (did >> 8); req[2] = (byte) did;
        System.arraycopy(data, 0, req, 3, data.length);
        positive(uds(req, 3000), 0x2E);
    }

    /** VIN convenience — DID F190 as ASCII. */
    public String readVin() throws Exception {
        return ascii(readDid(0xF190)).trim();
    }

    /** 0x19 02 — Read DTC by status mask. Returns parsed records. */
    public DtcRecord[] readDtc(int statusMask) throws Exception {
        return parseDtcResponse(positive(uds(new byte[]{0x19, 0x02, (byte) statusMask}, 4000), 0x19));
    }

    /** Static parse of a positive 59 02 payload (kept reusable for traced paths).
     *  Accepts either the full response [59 02 …] or a SID-stripped body [02 …]. */
    public static DtcRecord[] parseDtcResponse(byte[] resp) {
        if (resp == null) return new DtcRecord[0];
        byte[] d = resp;
        if (d.length >= 2 && (d[0] & 0xFF) == 0x59) {          // strip 59 02 header
            if (d.length >= 2 && (d[1] & 0xFF) != 0x02) return new DtcRecord[0];
            byte[] body = new byte[d.length - 1];
            System.arraycopy(d, 1, body, 0, body.length);
            d = body;
        }
        // d = [subfn, availabilityMask, DTC hi mid lo status]*
        if (d.length < 2) return new DtcRecord[0];
        int n = (d.length - 2) / 4;
        DtcRecord[] out = new DtcRecord[n];
        for (int i = 0; i < n; i++) {
            int o = 2 + i * 4;
            out[i] = new DtcRecord(d[o], d[o + 1], d[o + 2], d[o + 3]);
        }
        return out;
    }

    /** 0x14 — Clear Diagnostic Information (all groups). */
    public void clearDtc() throws Exception {
        positive(uds(new byte[]{0x14, (byte) 0xFF, (byte) 0xFF, (byte) 0xFF}, 4000), 0x14);
    }

    /** 0x27 odd sub — request seed. */
    public byte[] securitySeed(int level) throws Exception {
        return positive(uds(new byte[]{0x27, (byte) level}, 3000), 0x27);
    }

    /** 0x27 even sub — send key (sub = level + 1). */
    public void securityKey(int levelPlusOne, byte[] key) throws Exception {
        byte[] req = new byte[2 + key.length];
        req[0] = 0x27; req[1] = (byte) levelPlusOne;
        System.arraycopy(key, 0, req, 2, key.length);
        positive(uds(req, 3000), 0x27);
    }

    /** 0x31 — Routine Control. Returns the routine status record. */
    public byte[] routineControl(int controlType, int routineId, byte[] option) throws Exception {
        int n = option == null ? 0 : option.length;
        byte[] req = new byte[4 + n];
        req[0] = 0x31; req[1] = (byte) controlType;
        req[2] = (byte) (routineId >> 8); req[3] = (byte) routineId;
        if (n > 0) System.arraycopy(option, 0, req, 4, n);
        return positive(uds(req, 5000), 0x31);
    }

    /** 0x34 — Request Download. Returns [lenFormatId, maxBlocks…]. */
    public byte[] requestDownload(long address, long size, int dataFormatId) throws Exception {
        byte[] req = new byte[11];
        req[0] = 0x34; req[1] = (byte) dataFormatId;
        req[2] = 0x44;                                     // addr/len = 4 bytes each
        req[3] = (byte) (address >> 24); req[4] = (byte) (address >> 16);
        req[5] = (byte) (address >> 8);  req[6] = (byte) address;
        req[7] = (byte) (size >> 24);    req[8] = (byte) (size >> 16);
        req[9] = (byte) (size >> 8);     req[10] = (byte) size;
        return positive(uds(req, 4000), 0x34);
    }

    /** 0x36 — Transfer Data (one block). */
    public void transferData(int blockSequenceCounter, byte[] block) throws Exception {
        byte[] req = new byte[2 + block.length];
        req[0] = 0x36; req[1] = (byte) blockSequenceCounter;
        System.arraycopy(block, 0, req, 2, block.length);
        positive(uds(req, 4000), 0x36);
    }

    /** 0x37 — Request Transfer Exit. */
    public byte[] transferExit() throws Exception {
        return positive(uds(new byte[]{0x37}, 8000), 0x37);
    }

    /** 0x3E — Tester Present. suppress=true uses sub 0x80 (no response expected). */
    public void testerPresent(boolean suppress) throws Exception {
        if (suppress) tp.sendNoReply(new byte[]{0x3E, (byte) 0x80});
        else positive(uds(new byte[]{0x3E, 0x00}, 1500), 0x3E);
    }

    /** 0x85 — Control DTC Setting (on=0x02 / off=0x01). */
    public void controlDtcSetting(boolean on) throws Exception {
        positive(uds(new byte[]{(byte) 0x85, (byte) (on ? 0x02 : 0x01)}, 2000), 0x85);
    }

    /** 0x28 — Communication Control. */
    public void communicationControl(int controlType, int commType) throws Exception {
        positive(uds(new byte[]{0x28, (byte) controlType, (byte) commType}, 2500), 0x28);
    }

    /** 0x2F — Input Output Control By Identifier.
     *  controlParam: 0x00 returnControlToECU, 0x03 shortTermAdjustment.
     *  state is the actuator control-state bytestring (may be null/short). */
    public byte[] ioControl(int did, int controlParam, byte[] state) throws Exception {
        int n = state == null ? 0 : state.length;
        byte[] req = new byte[4 + n];
        req[0] = 0x2F; req[1] = (byte) (did >> 8); req[2] = (byte) did;
        req[3] = (byte) controlParam;
        if (n > 0) System.arraycopy(state, 0, req, 4, n);
        return positive(uds(req, 4000), 0x2F);
    }

    /** 0x23 — Read Memory By Address (4-byte address, 2-byte size). */
    public byte[] readMemory(long address, int size) throws Exception {
        byte[] req = new byte[8];
        req[0] = 0x23; req[1] = 0x42;   // addrAndLengthFormatId: 4-byte addr, 2-byte size
        req[2] = (byte) (address >> 24); req[3] = (byte) (address >> 16);
        req[4] = (byte) (address >> 8);  req[5] = (byte) address;
        req[6] = (byte) (size >> 8);     req[7] = (byte) size;
        return positive(uds(req, 4000), 0x23);
    }

    // ------------------------------------------------------------ DTC record
    public static final class DtcRecord {
        public final int rawValue;      // 3-byte DTC
        public final int statusMask;
        public DtcRecord(byte hi, byte mid, byte lo, byte st) {
            rawValue = ((hi & 0xFF) << 16) | ((mid & 0xFF) << 8) | (lo & 0xFF);
            statusMask = st & 0xFF;
        }
        /** ISO 14229 letter-digit form, e.g. P0130, U0100. */
        public String code() {
            char sys = "PCBU".charAt((rawValue >> 22) & 0x03);
            return "" + sys + ((rawValue >> 20) & 0x03) + digit((rawValue >> 16) & 0x0F)
                    + digit((rawValue >> 12) & 0x0F) + digit((rawValue >> 8) & 0x0F);
        }

        public boolean active() { return (statusMask & 0x01) != 0; }
    }

    // ------------------------------------------------------------ misc
    public static String ascii(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < b.length; i++) sb.append((char) (b[i] & 0xFF));
        return sb.toString();
    }

    public static String hexBytes(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < b.length; i++) {
            if (i > 0) sb.append(' ');
            sb.append(String.format("%02X", b[i] & 0xFF));
        }
        return sb.toString();
    }

    private static char digit(int nibble) {
        return Character.toUpperCase(Character.forDigit(nibble & 0x0F, 16));
    }

    private static String hex(int v) {
        String h = Integer.toHexString(v).toUpperCase();
        return h.length() < 2 ? "0" + h : h;
    }
}
