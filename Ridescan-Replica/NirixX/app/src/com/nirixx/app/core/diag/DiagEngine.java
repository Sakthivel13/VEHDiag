package com.nirixx.app.core.diag;

import android.content.Context;
import com.nirixx.app.Session;
import com.nirixx.app.core.uds.IsoTp;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.UdsClient;
import com.nirixx.app.core.vci.ByteLink;
import com.nirixx.app.core.vci.ElmCan;
import com.nirixx.app.core.vin.VinRules;
import com.nirixx.app.db.Db;
import com.nirixx.app.sim.UdsLog;

/** Real diagnostic engine: owns the active ByteLink + ElmCan + IsoTp +
 *  UdsClient chain and performs the VCI→CAN→UDS sequences against the
 *  vehicle.  There is NO simulated path in here — simulation lives in
 *  sim/SimEcu and is used only when no VCI is connected (clearly marked
 *  "training link" in the UI).
 *
 *  Threading contract: every method blocks — call from worker threads only.
 *
 *  Chain:
 *    ByteLink (BT-SPP / Wi-Fi TCP / USB-CDC)
 *      → ElmCan (ELM327 dialect, 11bit/500k)
 *        → IsoTp (SF/FF/CF/FC)
 *          → UdsClient (ISO 14229 services)
 */
public final class DiagEngine {

    public interface Progress {
        void onStep(String step);
        void onFrame(String dir, String frame);      // pretty hex, for console+log
    }

    public static final class Result {
        public boolean ok;
        public String vin;
        public Db.Vehicle vehicle;                    // null when unsupported
        public String stage = "";
        public String error;
        public Nrc nrc;                                // set when the ECU refused
        public String describeTransport = "";
    }

    private static ByteLink link;
    private static ElmCan can;
    private static IsoTp tp;
    private static UdsClient uds;
    private static int txId = 0x7E0, rxId = 0x7E8;
    private static Progress progress;
    private static volatile boolean established;

    private DiagEngine() {}

    public static synchronized boolean ready() {
        return established && uds != null && link != null && link.isOpen();
    }

    public static synchronized String describe() {
        return can == null ? "" : can.describe();
    }

    public static synchronized void disconnect() {
        established = false;
        try { if (link != null) link.close(); } catch (Exception ignored) { }
        link = null; can = null; tp = null; uds = null;
        Session.vciConnected = false;
    }

    /** Full bring-up: open link → ELM init → diagnostic session → VIN → vehicle.
     *  tx/rx are the physical ECU CAN ids from the selected vehicle's DB row. */
    public static synchronized Result connectAndIdentify(Context ctx, ByteLink newLink,
                                                         int tx, int rx, Progress cb) {
        Result r = new Result();
        progress = cb;
        Session.ensureSession(ctx);
        try {
            stage(r, "Opening physical link");
            disconnectQuiet();
            link = newLink;
            txId = tx; rxId = rx;
            can = new ElmCan(link, txId, rxId);
            can.setFrameTee(new ElmCan.FrameTee() {
                public void onFrame(int id, byte[] d) {
                    frameLine("RX", Integer.toHexString(id).toUpperCase() + " -> "
                            + UdsClient.hexBytes(d).replace(" ", ""));
                }
            });
            can.open();
            r.describeTransport = can.describe();
            Session.vciConnected = true;
            Session.vciName = can.describe();
            if (can.adapterId() != null && can.adapterId().length() > 0)
                Session.vciFw = can.adapterId();

            stage(r, "Opening diagnostic session");
            tp = new IsoTp(can.asLink(), txId, rxId);
            uds = new UdsClient(tp);
            openSession(r);
            established = true;
            connectedAt = System.currentTimeMillis();

            stage(r, "Reading VIN (service 22, DID F190)");
            r.vin = uds.readVin().toUpperCase(java.util.Locale.US).trim();
            if (!VinRules.isValidVin(r.vin)) {
                r.error = "ECU returned an unreadable VIN: '" + r.vin + "'";
                r.stage = "VIN validation";
                r.ok = false;
                return r;
            }
            new SessionRefresher(ctx).run(r.vin);
            r.vehicle = Db.get(ctx).vehicleByVin(r.vin);
            r.ok = true;
            return r;
        } catch (UdsClient.UdsError e) {
            r.ok = false; r.nrc = e.nrc;
            r.error = e.getMessage() + "\n" + e.nrc.userHint;
            return r;
        } catch (Exception e) {
            r.ok = false;
            if (r.stage.length() == 0) r.stage = "Link";
            r.error = e.getMessage() == null ? String.valueOf(e) : e.getMessage();
            return r;
        }
    }

    /** When already connected: just re-read the VIN. */
    public static synchronized Result readVinAgain(Context ctx, Progress cb) {
        Result r = new Result();
        progress = cb;
        if (!ready()) { r.ok = false; r.stage = "Link"; r.error = "No VCI link established"; return r; }
        try {
            stage(r, "Reading VIN (service 22, DID F190)");
            r.vin = uds.readVin().toUpperCase(java.util.Locale.US).trim();
            if (!VinRules.isValidVin(r.vin)) {
                r.ok = false; r.stage = "VIN validation";
                r.error = "Unreadable VIN: '" + r.vin + "'";
                return r;
            }
            new SessionRefresher(ctx).run(r.vin);
            r.vehicle = Db.get(ctx).vehicleByVin(r.vin);
            r.ok = true;
            return r;
        } catch (UdsClient.UdsError e) {
            r.ok = false; r.nrc = e.nrc;
            r.error = e.getMessage() + "\n" + e.nrc.userHint;
            return r;
        } catch (Exception e) {
            r.ok = false; r.error = e.getMessage() == null ? String.valueOf(e) : e.getMessage();
            return r;
        }
    }

    /** Default session (like the captured logs: 10 01), escalating to extended. */
    private static void openSession(Result r) throws Exception {
        frameLine("TX", hex(txId) + " -> 1001");
        try {
            uds.sessionControl(0x01);
        } catch (UdsClient.UdsError e) {
            if (e.nrc.code == 0x11 || e.nrc.code == 0x7F || e.nrc.code == 0x12) {
                frameLine("TX", hex(txId) + " -> 1003");
                uds.sessionControl(0x03);               // extended
            } else throw e;
        }
    }

    public static synchronized UdsClient uds() { return uds; }

    /** Raw adapter handle (AT queries like ATRV) — null when not connected. */
    public static synchronized ElmCan elm() { return ready() ? can : null; }

    /** Current 11-bit CAN address pair the stack is pointed at. */
    public static synchronized int[] address() { return new int[]{txId, rxId}; }

    /** Re-point the live link at another ECU address (or the 7DF functional
     *  lane).  Rebuilds ISO-TP + UDS over the same physical link — matches the
     *  reference tool, which keeps one VCI session and walks ECU addresses
     *  (EMS 7E0/7E8 · ABS 7E1/7E9 · cluster 7F0/7F1 …) on a single connect.
     *  Must run on the DiagOps executor (never concurrently with a bus op). */
    public static synchronized void readdress(int tx, int rx) {
        if (link == null || can == null) { txId = tx; rxId = rx; return; }
        try {
            can.setAddress(tx, rx);
            if (established) {
                tp = new IsoTp(can.asLink(), tx, rx);
                uds = new UdsClient(tp);
            }
            txId = tx; rxId = rx;
        } catch (Exception ignored) { }
    }

    private static long connectedAt = 0;

    /** Wall-clock time the current link went up (0 = never). */
    public static synchronized long connectedAt() { return ready() ? connectedAt : 0; }

    // ---------------------------------------------------------------- helpers
    private static void stage(Result r, String s) {
        r.stage = s;
        if (progress != null) progress.onStep(s);
    }

    private static void frameLine(String dir, String payload) {
        if (progress != null) progress.onFrame(dir, payload);
    }

    private static String hex(int id) {
        String h = Integer.toHexString(id).toUpperCase();
        while (h.length() < 3) h = "0" + h;
        return h;
    }

    private static void disconnectQuiet() {
        try { if (link != null) link.close(); } catch (Exception ignored) { }
    }

    /** Mirrors the real read into the app Session + the session .txt log. */
    private static final class SessionRefresher {
        private final Context ctx;
        SessionRefresher(Context c) { this.ctx = c.getApplicationContext(); }
        void run(String vin) {
            Session.selectedVin = vin;
            try {
                Db.Vehicle v = Db.get(ctx).vehicleByVin(vin);
                if (v != null) {
                    Session.selectVehicle(v.id, v.model, v.variant, v.type, vin, v.image);
                    java.util.List<Db.Ecu> es = Db.get(ctx).ecus(v.id);
                    if (!es.isEmpty()) {
                        Db.Ecu e = es.get(0);
                        Session.selectEcu(e.id, e.name, e.code, e.tx, e.rx);
                        try {
                            readdress(Integer.parseInt(e.tx, 16), Integer.parseInt(e.rx, 16));
                        } catch (Exception ignored) { }
                    }
                }
            } catch (Exception ignored) { }
            UdsLog.log(ctx, "INFO", "[VIN]: --> " + vin);
        }
    }
}
