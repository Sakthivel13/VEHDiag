package com.nirixx.app.core.uds;

/** ISO 15765-2 (ISO-TP) over a raw CAN-frame link — real implementation.
 *  Single Frame / First Frame / Consecutive Frame / Flow Control, Block Size,
 *  STmin, sequence checking and N_Bs / N_Cr timeouts.
 *  Pure Java (no Android imports) so the logic is unit-testable off-device. */
public final class IsoTp {

    public static final int MAIN_TX = 0x750;
    public static final int MAIN_RX = 0x758;
    public static final int MAIN_DEFAULT_SESSION = 0x01;

    public interface Link {
        void sendFrame(int canId, byte[] data) throws Exception;
        void setFrameListener(FrameListener l);
    }
    public interface FrameListener { void onFrame(int canId, byte[] data); }

    public static final class TimeoutException extends Exception {
        public TimeoutException(String m) { super(m); }
    }
    public static final class ProtocolException extends Exception {
        public ProtocolException(String m) { super(m); }
    }

    private final Link link;
    private final int txId, rxId;

    private volatile byte[] rxPayload;
    private volatile boolean rxDone, rxError;
    private volatile String rxErr;

    private java.io.ByteArrayOutputStream rxBuf;
    private int rxLen, rxSn;
    private int fcBlockSize, fcStMinMs;
    private volatile boolean waitingFc;

    public IsoTp(Link link, int txId, int rxId) {
        this.link = link; this.txId = txId; this.rxId = rxId;
        link.setFrameListener(new FrameListener() {
            public void onFrame(int id, byte[] d) { onCan(id, d); }
        });
    }

    // ---------------------------------------------------------------- receive
    private void onCan(int id, byte[] d) {
        if (id != rxId || d.length == 0) return;
        int pci = d[0] & 0xF0;
        try {
            switch (pci) {
                case 0x00: {                                     // Single Frame
                    int len = d[0] & 0x0F;
                    if (len < 1 || len > 7) { fail("ISO-TP malformed SF len=" + len); return; }
                    if (d.length < len + 1) { fail("ISO-TP short SF"); return; }
                    rxPayload = new byte[len];
                    System.arraycopy(d, 1, rxPayload, 0, len);
                    rxDone = true;
                    break;
                }
                case 0x10: {                                     // First Frame
                    if (d.length < 2) { fail("ISO-TP short FF"); return; }
                    rxLen = ((d[0] & 0x0F) << 8) | (d[1] & 0xFF);
                    if (rxLen < 8) { fail("ISO-TP FF len<8"); return; }
                    rxBuf = new java.io.ByteArrayOutputStream();
                    rxBuf.write(d, 2, d.length - 2);
                    rxSn = 1;
                    sendFlowControl(0, 0);                       // CTS, BS=0, STmin=0
                    break;
                }
                case 0x20: {                                     // Consecutive Frame
                    if (rxBuf == null) return;                   // stray CF
                    int sn = d[0] & 0x0F;
                    if (sn != (rxSn & 0x0F)) {
                        fail("ISO-TP SN mismatch exp=" + (rxSn & 0x0F) + " got=" + sn);
                        return;
                    }
                    rxSn++;
                    rxBuf.write(d, 1, d.length - 1);
                    if (rxBuf.size() >= rxLen) {
                        byte[] full = rxBuf.toByteArray();
                        rxPayload = new byte[rxLen];
                        System.arraycopy(full, 0, rxPayload, 0, rxLen);
                        rxBuf = null;
                        rxDone = true;
                    }
                    break;
                }
                case 0x30: {                                     // Flow Control
                    int fs = d[0] & 0x0F;
                    fcBlockSize = d[1] & 0xFF;
                    fcStMinMs = stMinMillis(d[2] & 0xFF);
                    if (fs == 0) waitingFc = false;              // CTS
                    else if (fs == 2) fail("ISO-TP FC.OVFL — receiver overflow");
                    /* fs==1 (WAIT): keep waiting */
                    break;
                }
                default: break;
            }
        } catch (Exception e) {
            fail(e.getMessage() == null ? "ISO-TP rx error" : e.getMessage());
        }
    }

    private void fail(String why) { rxError = true; rxErr = why; }

    private void sendFlowControl(int bs, int stmin) {
        try {
            link.sendFrame(txId, new byte[]{0x30, (byte) bs, (byte) stmin, 0, 0, 0, 0, 0});
        } catch (Exception e) { fail("FC send failed: " + e.getMessage()); }
    }

    private static int stMinMillis(int raw) {
        if (raw <= 0x7F) return raw;
        if (raw >= 0xF1 && raw <= 0xF9) return 1;
        return 0;
    }

    // ---------------------------------------------------------------- transmit
    /** Send one UDS payload, wait for one response payload. CALL OFF THE UI THREAD. */
    public synchronized byte[] request(byte[] payload, int timeoutMs) throws Exception {
        resetRx();
        if (payload.length <= 7) {
            byte[] f = new byte[8];
            f[0] = (byte) payload.length;
            System.arraycopy(payload, 0, f, 1, payload.length);
            link.sendFrame(txId, f);
        } else {
            sendMulti(payload);
        }
        return awaitRx(timeoutMs);
    }

    /** Fire-and-forget (e.g. TesterPresent sub-function 0x80 suppress-response). */
    public synchronized void sendNoReply(byte[] payload) throws Exception {
        resetRx();
        byte[] f = new byte[8];
        f[0] = (byte) payload.length;
        System.arraycopy(payload, 0, f, 1, Math.min(payload.length, 7));
        link.sendFrame(txId, f);
    }

    /** Wait for an additional response message without sending anything
     *  (used by UdsClient for NRC 0x78 Response-Pending sequences). */
    public synchronized byte[] awaitResponse(int timeoutMs) throws Exception {
        resetRx();
        return awaitRx(timeoutMs);
    }

    private void sendMulti(byte[] p) throws Exception {
        byte[] ff = new byte[8];
        ff[0] = (byte) (0x10 | ((p.length >> 8) & 0x0F));
        ff[1] = (byte) (p.length & 0xFF);
        System.arraycopy(p, 0, ff, 2, 6);
        waitingFc = true;
        link.sendFrame(txId, ff);
        waitFc(1000);                                            // N_Bs

        int off = 6, sn = 1, sent = 0;
        while (off < p.length) {
            int n = Math.min(7, p.length - off);
            byte[] cf = new byte[8];
            cf[0] = (byte) (0x20 | (sn & 0x0F));
            System.arraycopy(p, off, cf, 1, n);
            link.sendFrame(txId, cf);
            off += n; sn = (sn + 1) & 0x0F; sent++;
            if (fcBlockSize > 0 && sent >= fcBlockSize && off < p.length) {
                waitingFc = true; sent = 0;
                waitFc(1000);
            }
            if (fcStMinMs > 0) Thread.sleep(fcStMinMs);
        }
    }

    private void waitFc(long nBs) throws Exception {
        long deadline = System.currentTimeMillis() + nBs;
        while (waitingFc) {
            if (rxError) throw new ProtocolException(rxErr);
            if (System.currentTimeMillis() > deadline)
                throw new TimeoutException("N_Bs timeout — no Flow Control from ECU");
            Thread.sleep(2);
        }
    }

    private void resetRx() {
        rxPayload = null; rxDone = false; rxError = false; rxErr = null;
        rxBuf = null; rxLen = 0; rxSn = 0; fcBlockSize = 0; fcStMinMs = 0; waitingFc = false;
    }

    private byte[] awaitRx(int timeoutMs) throws Exception {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (!rxDone) {
            if (rxError) throw new ProtocolException(rxErr);
            if (System.currentTimeMillis() > deadline)
                throw new TimeoutException("P2/N_Cr timeout — ECU did not respond");
            Thread.sleep(2);
        }
        return rxPayload;
    }
}
