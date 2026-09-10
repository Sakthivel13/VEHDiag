package com.nirixx.app.core.vci;

import com.nirixx.app.core.uds.IsoTp;

/** ELM327-compatible CAN transport over a ByteLink — the de-facto standard
 *  command dialect used by real BT / Wi-Fi / USB OBD dongles.
 *
 *  On open() we run the real init sequence:
 *    ATZ (reset) → ATE0 (echo off) → ATL0 (linefeeds off) → ATH1 (headers on)
 *    → ATSP6 (ISO 15765-4 CAN 11/500) → ATSH <txId> → ATCRA <rxId>
 *  Frames go out as "ATSH …\rATCRA …\r<hex uds>\r"; responses are parsed from
 *  the header'd hex lines the adapter echoes back. */
public final class ElmCan implements CanTransport {

    private final ByteLink link;
    private int txId, rxId;          // mutable: re-pointed on ECU switch / functional lane
    private final StringBuilder rxBuf = new StringBuilder();
    private CanTransport.FrameListener frames;
    private CanTransport.ErrorListener errors;
    private volatile boolean open;
    private String adapterId = "ELM327-compatible";
    public String adapterId() { return adapterId; }

    /** Real link statistics for System Monitoring. */
    public final java.util.concurrent.atomic.AtomicLong framesSent =
            new java.util.concurrent.atomic.AtomicLong();
    public final java.util.concurrent.atomic.AtomicLong framesReceived =
            new java.util.concurrent.atomic.AtomicLong();

    public ElmCan(ByteLink link, int txId, int rxId) {
        this.link = link; this.txId = txId; this.rxId = rxId;
        link.setListener(new ByteLink.Listener() {
            public void onBytes(byte[] data, int n) { pump(data, n); }
            public void onClosed(String reason) {
                open = false;
                if (errors != null) errors.onError(reason);
            }
        });
    }

    // ---------------------------------------------------------------- open
    public void open() throws Exception {
        link.open();
        at("ATZ", 1600);                          // reset → echo "ELM327 v…"
        at("ATE0", 300);                          // echo off
        at("ATL0", 200);                          // linefeeds off
        at("ATH1", 200);                          // headers on (need CAN ids)
        at("ATAT0", 100);                         // fixed timing (no adaptive)
        at("ATSP6", 300);                         // protocol ISO15765-4 CAN 11bit 500k
        at("ATSH" + Integer.toHexString(txId).toUpperCase(), 150);
        at("ATCRA" + Integer.toHexString(rxId).toUpperCase(), 150);
        open = true;
    }

    /** Re-point the 11-bit CAN header pair at runtime (ATSH/ATCRA are cheap and
     *  idempotent on ELM327-class adapters). Used when the technician switches
     *  the selected ECU (EMS 7E0 / ABS 7E1 / cluster 7F0 …) and when OBD-II
     *  mode 01/09 queries must go out on the 7DF functional lane — exactly the
     *  addressing discipline seen in the reference application's bus logs.
     *  Safe when closed: the new ids just take effect at the next open(). */
    public synchronized void setAddress(int tx, int rx) throws Exception {
        if (tx == txId && rx == rxId) return;
        if (open) {
            at("ATSH" + Integer.toHexString(tx).toUpperCase(), 60);
            at("ATCRA" + Integer.toHexString(rx).toUpperCase(), 60);
        }
        txId = tx;
        rxId = rx;
    }

    public synchronized int txId() { return txId; }
    public synchronized int rxId() { return rxId; }

    private void at(String cmd, int settleMs) throws Exception {
        rxBuf.setLength(0);
        link.write((cmd + "\r").getBytes("US-ASCII"));
        Thread.sleep(settleMs);
    }

    public void close() { open = false; link.close(); }
    public boolean isOpen() { return open && link.isOpen(); }
    public String describe() { return "ELM327 over " + link.describe() + " (11bit/500k)"; }

    // ---------------------------------------------------------------- send
    public synchronized void sendFrame(int canId, byte[] data) throws Exception {
        if (!isOpen()) throw new Exception("VCI link not open");
        if (data.length > 8) throw new Exception("classic CAN only (<=8 bytes)");
        // ensure the adapter is addressed to our tx id (cheap for single-ECU tools)
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < data.length; i++) sb.append(String.format("%02X", data[i]));
        rxBuf.setLength(0);
        link.write((sb.toString() + "\r").getBytes("US-ASCII"));
        framesSent.incrementAndGet();
    }

    public void setFrameListener(CanTransport.FrameListener l) { this.frames = l; }
    public void setErrorListener(CanTransport.ErrorListener l) { this.errors = l; }

    /** Optional secondary listener (logging/tee) — receives every parsed frame
     *  alongside the primary IsoTp consumer. */
    public interface FrameTee { void onFrame(int canId, byte[] data); }
    private FrameTee tee;
    public void setFrameTee(FrameTee t) { this.tee = t; }

    // ---------------------------------------------------------------- receive
    /** Parse the adapter's text protocol: CAN responses come back as continuous
     *  hex (header then data) terminated by '>' or \r.  "…7E8 06 50 01 00 32 01
     *  F4" — with ATH1 the first bytes are the CAN id. */
    private void pump(byte[] data, int n) {
        String s;
        try { s = new String(data, 0, n, "US-ASCII"); } catch (Exception e) { return; }
        synchronized (rxBuf) { rxBuf.append(s); }
        String chunk = rxBuf.toString();
        int end;
        while ((end = indexOfAny(chunk, '\r', '>')) >= 0) {
            String line = chunk.substring(0, end).trim();
            chunk = chunk.substring(end + 1);
            synchronized (rxBuf) { rxBuf.setLength(0); rxBuf.append(chunk); }
            handleLine(line);
        }
    }

    private static int indexOfAny(String s, char a, char b) {
        int i = s.indexOf(a); int j = s.indexOf(b);
        if (i < 0) return j; if (j < 0) return i;
        return Math.min(i, j);
    }

    private void handleLine(String line) {
        if (line.length() == 0) return;
        if (capturing) {
            synchronized (captureLines) { captureLines.add(line.trim()); }
            return;
        }
        String up = line.toUpperCase(java.util.Locale.US).replace(" ", "");
        if (up.contains("ELM327")) { adapterId = line.trim(); return; }
        if (up.startsWith("AT") || up.equals("OK")
                || up.startsWith("?") || up.startsWith("SEARCHING")
                || up.startsWith("STOPPED") || up.startsWith("NO")  /* NO DATA */
                || up.startsWith("CAN") /* CAN ERROR */ || up.startsWith("UNABLE")) {
            if (up.startsWith("CANERROR") || up.startsWith("UNABLETOCONNECT")) {
                if (errors != null) errors.onError("Adapter: " + line);
            }
            return;
        }
        // hex: first 3 chars = 11-bit CAN id, rest = data bytes
        if (up.length() < 5) return;
        try {
            int id = Integer.parseInt(up.substring(0, 3), 16);
            int bytes = (up.length() - 3) / 2;
            byte[] d = new byte[bytes];
            for (int i = 0; i < bytes; i++)
                d[i] = (byte) Integer.parseInt(up.substring(3 + i * 2, 5 + i * 2), 16);
            framesReceived.incrementAndGet();
            if (frames != null) frames.onFrame(id, d);
            if (tee != null) tee.onFrame(id, d);
        } catch (Exception ignored) { /* non-hex noise */ }
    }

    // ------------------------------------------- synchronous AT queries
    private final java.util.List<String> captureLines = new java.util.ArrayList<String>();
    private volatile boolean capturing = false;

    /** Send an AT command and collect the raw reply lines for settleMs. */
    public synchronized String queryAt(String cmd, int settleMs) throws Exception {
        if (!isOpen()) throw new Exception("VCI link not open");
        synchronized (captureLines) { captureLines.clear(); }
        capturing = true;
        rxBuf.setLength(0);
        link.write((cmd + "\r").getBytes("US-ASCII"));
        Thread.sleep(settleMs);
        capturing = false;
        StringBuilder sb = new StringBuilder();
        synchronized (captureLines) {
            for (int i = 0; i < captureLines.size(); i++) {
                String t = captureLines.get(i).trim();
                if (t.length() == 0 || "?".equals(t)) continue;
                if ("OK".equalsIgnoreCase(t)) continue;
                if (t.equalsIgnoreCase(cmd)) continue;              // echo (ATE1 adapters)
                if (sb.length() > 0) sb.append('\n');
                sb.append(t);
            }
        }
        return sb.toString();
    }

    /** Adapter-measured supply voltage (ATRV) — the real 12 V rail the VCI sees
     *  on the diagnostic connector.  Replies look like "12.6V"/"12.6". */
    public Double readVoltageVolts() {
        try {
            String r = queryAt("ATRV", 450);
            java.util.regex.Matcher m = java.util.regex.Pattern
                    .compile("(\\d{1,2}(?:\\.\\d{1,2})?)\\s*[vV]?")
                    .matcher(r);
            if (m.find()) return Double.valueOf(m.group(1));
        } catch (Exception ignored) { }
        return null;
    }

    /** Adapter identity / firmware string (ATI). */
    public String adapterInfo() {
        try { return queryAt("ATI", 300); } catch (Exception e) { return ""; }
    }

    /** Expose as an IsoTp.Link. */
    public IsoTp.Link asLink() {
        final ElmCan self = this;
        return new IsoTp.Link() {
            public void sendFrame(int canId, byte[] data) throws Exception { self.sendFrame(canId, data); }
            public void setFrameListener(final IsoTp.FrameListener l) {
                self.setFrameListener(new CanTransport.FrameListener() {
                    public void onFrame(int canId, byte[] data) { l.onFrame(canId, data); }
                });
            }
        };
    }
}
