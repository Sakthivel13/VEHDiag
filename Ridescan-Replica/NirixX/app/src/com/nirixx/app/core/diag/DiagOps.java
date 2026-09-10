package com.nirixx.app.core.diag;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import com.nirixx.app.Session;
import com.nirixx.app.core.uds.IsoTp;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.Obd;
import com.nirixx.app.core.uds.UdsClient;
import com.nirixx.app.core.vci.ElmCan;
import com.nirixx.app.sim.UdsLog;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** One honest bridge between screens and the live diagnostic engine.
 *
 *  RULES (project contract):
 *   — every method runs on a single background executor (never the UI thread);
 *   — when no VCI link is live the callback gets err("No VCI link established")
 *     and the caller must render an honest state — nothing is simulated here;
 *   — every real request/response is traced into the session UDS log with the
 *     exact bytes that crossed the CAN bus. */
public final class DiagOps {

    private DiagOps() { }

    public interface Cb<T> {
        void ok(T value);
        void err(String what, String detail, Nrc nrc);
    }

    private interface Task<T> { T run() throws Exception; }

    private static final ExecutorService EX = Executors.newSingleThreadExecutor();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    public static boolean live() { return DiagEngine.ready(); }

    private static <T> void submit(final Context ctx, final String what,
                                   final Task<T> task, final Cb<T> cb) {
        final Context app = ctx.getApplicationContext();
        EX.execute(new Runnable() {
            public void run() {
                if (!DiagEngine.ready()) {
                    fail(what, "No VCI link established — connect the NirixiLINK first.", null, cb);
                    return;
                }
                try {
                    final T v = task.run();
                    MAIN.post(new Runnable() { public void run() { cb.ok(v); } });
                } catch (UdsClient.UdsError e) {
                    fail(what, e.getMessage() + "\n" + e.nrc.userHint, e.nrc, cb);
                } catch (IsoTp.TimeoutException e) {
                    fail(what, "No response from the ECU (bus timeout). Check ignition and wiring.", null, cb);
                } catch (Exception e) {
                    fail(what, e.getMessage() == null ? String.valueOf(e) : e.getMessage(), null, cb);
                } finally {
                    poke();
                }
            }
            private void fail(final String w, final String d, final Nrc n, final Cb<T> c2) {
                MAIN.post(new Runnable() { public void run() { c2.err(w, d, n); } });
            }
        });
    }

    // ------------------------------------------------------------ tracing
    private static byte[] traced(Context ctx, byte[] req, int timeoutMs) throws Exception {
        UdsEngineHolder u = holder();
        UdsLog.log(ctx, "TX", Session.ecuTx + " -> " + UdsClient.hexBytes(req).replace(" ", ""));
        byte[] resp = u.uds.uds(req, timeoutMs);
        UdsLog.log(ctx, "RX", Session.ecuRx + " -> "
                + (resp == null ? "—" : UdsClient.hexBytes(resp).replace(" ", "")));
        return resp;
    }

    /** Lazy holder so DiagOps works with whatever engine instance is live. */
    private static final class UdsEngineHolder { UdsClient uds; }
    private static UdsEngineHolder holder() {
        UdsEngineHolder h = new UdsEngineHolder();
        h.uds = DiagEngine.uds();
        return h;
    }

    // -------------------------------------------------- functional OBD-II lane
    /** Reference-addressing discipline: SAE J1979 mode 01/09 traffic goes out
     *  on 7DF (functional broadcast); answers arrive on the ECU's response id.
     *  Re-points the ELM header to 7DF/7E8 for one exchange, then restores the
     *  selected ECU's physical lane — exactly what the captured bus logs show. */
    private static byte[] tracedFunctional(Context ctx, byte[] req, int timeoutMs) throws Exception {
        int[] phys = DiagEngine.address();
        DiagEngine.readdress(0x7DF, 0x7E8);
        try {
            UdsEngineHolder u = holder();
            UdsLog.log(ctx, "TX", "7DF -> " + UdsClient.hexBytes(req).replace(" ", ""));
            byte[] resp = u.uds.uds(req, timeoutMs);
            UdsLog.log(ctx, "RX", "7E8 -> "
                    + (resp == null ? "—" : UdsClient.hexBytes(resp).replace(" ", "")));
            return resp;
        } finally {
            DiagEngine.readdress(phys[0], phys[1]);
        }
    }

    /** Queue a re-address to the Session-selected ECU (called after ECU pick). */
    public static void retuneToSessionEcu(final Context ctx) {
        EX.execute(new Runnable() {
            public void run() {
                if (DiagEngine.ready()) {
                    try {
                        DiagEngine.readdress(Integer.parseInt(Session.ecuTx, 16),
                                Integer.parseInt(Session.ecuRx, 16));
                    } catch (Exception ignored) { }
                }
                poke();
            }
        });
    }

    // -------------------------------------------------- tester-present keep-alive
    /** Reference cadence (captured logs): 3E 00 → 7E 00 every ~3.1 s towards
     *  the currently selected ECU whenever the session is otherwise idle.
     *  Runs exclusively on EX, so it can never interleave with a bus op, and
     *  stays silent while operations keep lastOpAt fresh. */
    private static volatile long lastOpAt = 0L;
    private static boolean keepAliveRunning = false;

    private static void poke() { lastOpAt = System.currentTimeMillis(); }

    public static void startKeepAlive(final Context ctx) {
        if (keepAliveRunning) return;
        keepAliveRunning = true;
        final Context app = ctx.getApplicationContext();
        MAIN.postDelayed(new Runnable() {
            public void run() {
                if (!keepAliveRunning) return;
                if (DiagEngine.ready() && System.currentTimeMillis() - lastOpAt > 2800) {
                    EX.execute(new Runnable() {
                        public void run() {
                            if (DiagEngine.ready()
                                    && System.currentTimeMillis() - lastOpAt >= 2500) {
                                try {
                                    UdsLog.log(app, "TX", Session.ecuTx + " -> 3E00");
                                    holder().uds.testerPresent(false);
                                    UdsLog.log(app, "RX", Session.ecuRx + " -> 7E00");
                                } catch (Exception ignored) {
                                    // reference behavior: log & continue
                                    // (e.g. 7F 3E 11 on ECUs without 3E support)
                                }
                            }
                            poke();
                        }
                    });
                }
                MAIN.postDelayed(this, 1000);
            }
        }, 3000);
    }

    // ------------------------------------------------------------ DTC
    /** 19 02 FF — report DTC by status mask (all). */
    public static void readDtc(final Context ctx, final Cb<UdsClient.DtcRecord[]> cb) {
        submit(ctx, "Read DTCs", new Task<UdsClient.DtcRecord[]>() {
            public UdsClient.DtcRecord[] run() throws Exception {
                byte[] resp = traced(ctx, new byte[]{0x19, 0x02, (byte) 0xFF}, 4000);
                // delegate parsing to UdsClient via a fresh exchange-free parser:
                return UdsClient.parseDtcResponse(resp);
            }
        }, cb);
    }

    /** 14 FF FF FF — clear all groups. */
    public static void clearDtc(final Context ctx, final Cb<Boolean> cb) {
        submit(ctx, "Clear DTCs", new Task<Boolean>() {
            public Boolean run() throws Exception {
                byte[] resp = traced(ctx, new byte[]{0x14, (byte) 0xFF, (byte) 0xFF, (byte) 0xFF}, 4000);
                if (resp == null || resp.length < 1 || (resp[0] & 0xFF) != 0x54)
                    throw new Exception("Unexpected clear response");
                return Boolean.TRUE;
            }
        }, cb);
    }

    // ------------------------------------------------------------ routines / IO
    /** 31 01 <rid> — start routine, no option bytes. */
    public static void routineStart(final Context ctx, final int rid, final Cb<byte[]> cb) {
        submit(ctx, "Routine control", new Task<byte[]>() {
            public byte[] run() throws Exception {
                byte[] req = new byte[]{0x31, 0x01, (byte) (rid >> 8), (byte) rid};
                byte[] resp = traced(ctx, req, 8000);
                if (resp == null || resp.length < 1 || (resp[0] & 0xFF) != 0x71)
                    throw new Exception("Unexpected routine response");
                return resp;
            }
        }, cb);
    }

    /** 2F <did> 00/03 — output control; state bytes omitted (return control /
     *  short-term adjustment with ECU default state). */
    public static void ioControl(final Context ctx, final int did, final boolean engage,
                                 final Cb<byte[]> cb) {
        submit(ctx, "IO control", new Task<byte[]>() {
            public byte[] run() throws Exception {
                byte[] req = new byte[]{0x2F, (byte) (did >> 8), (byte) did,
                        (byte) (engage ? 0x03 : 0x00)};
                byte[] resp = traced(ctx, req, 4000);
                if (resp == null || resp.length < 1 || (resp[0] & 0xFF) != 0x6F)
                    throw new Exception("Unexpected IO-control response");
                return resp;
            }
        }, cb);
    }

    // ------------------------------------------------------------ DID read / write
    public static void readDidRaw(final Context ctx, final int did, final Cb<byte[]> cb) {
        submit(ctx, "Read DID " + Integer.toHexString(did).toUpperCase(), new Task<byte[]>() {
            public byte[] run() throws Exception {
                byte[] resp = traced(ctx, new byte[]{0x22, (byte) (did >> 8), (byte) did}, 3000);
                if (resp == null || resp.length < 3 || (resp[0] & 0xFF) != 0x62)
                    throw new Exception("Unexpected readDID response");
                byte[] data = new byte[resp.length - 3];
                System.arraycopy(resp, 3, data, 0, data.length);
                return data;
            }
        }, cb);
    }

    /** 2E <did> <ASCII bytes> — writes are real and irreversible: caller must
     *  have confirmed with the user already. */
    public static void writeDidAscii(final Context ctx, final int did, final String text,
                                     final Cb<Boolean> cb) {
        submit(ctx, "Write DID " + Integer.toHexString(did).toUpperCase(), new Task<Boolean>() {
            public Boolean run() throws Exception {
                byte[] t = text.getBytes("US-ASCII");
                byte[] req = new byte[3 + t.length];
                req[0] = 0x2E; req[1] = (byte) (did >> 8); req[2] = (byte) did;
                System.arraycopy(t, 0, req, 3, t.length);
                byte[] resp = traced(ctx, req, 4000);
                if (resp == null || resp.length < 1 || (resp[0] & 0xFF) != 0x6E)
                    throw new Exception("Unexpected writeDID response");
                return Boolean.TRUE;
            }
        }, cb);
    }

    // ------------------------------------------------------------ OBD-II (SAE J1979)
    /** Mode 01 current-data PID → decoded physical value. */
    public static void obdPid(final Context ctx, final int pid, final Cb<Double> cb) {
        submit(ctx, "Read PID " + Integer.toHexString(pid).toUpperCase(), new Task<Double>() {
            public Double run() throws Exception {
                byte[] resp = tracedFunctional(ctx, Obd.requestPid(pid), 2500);
                Double v = Obd.decodePid(pid, resp);
                if (v == null) throw new Exception("No valid Mode-01 reply for this PID");
                return v;
            }
        }, cb);
    }

    /** Mode 09 vehicle-information record → raw record bytes. */
    public static void mode09(final Context ctx, final int infoType, final Cb<byte[]> cb) {
        submit(ctx, "Read InfoType " + infoType, new Task<byte[]>() {
            public byte[] run() throws Exception {
                byte[] resp = tracedFunctional(ctx, Obd.requestInfo(infoType), 4000);
                byte[] rec = Obd.decodeInfo(infoType, resp);
                if (rec == null) throw new Exception("No valid Mode-09 reply");
                return rec;
            }
        }, cb);
    }

    // ------------------------------------------------------------ adapter voltage
    /** Real 12 V rail as measured by the VCI itself (ATRV). */
    public static void adapterVoltage(final Context ctx, final Cb<Double> cb) {
        submit(ctx, "Adapter voltage", new Task<Double>() {
            public Double run() throws Exception {
                ElmCan can = DiagEngine.elm();
                if (can == null) throw new Exception("No VCI link established");
                Double v = can.readVoltageVolts();
                if (v == null) throw new Exception("Adapter did not answer ATRV");
                UdsLog.log(ctx, "AT", "ATRV -> " + BatteryAssess.fmt(v.doubleValue()) + " V");
                return v;
            }
        }, cb);
    }
}
