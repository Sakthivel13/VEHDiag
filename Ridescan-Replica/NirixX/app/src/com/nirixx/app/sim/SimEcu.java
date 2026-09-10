package com.nirixx.app.sim;

import android.os.Handler;
import android.os.Looper;
import com.nirixx.app.Session;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.Random;

/** Deterministic UDS/ISO-TP simulation of the EMS ECU.
 *  Produces the same 7E0/7E8 conversational trace the reference logs show:
 *  1001 session open, 22F190 VIN read (78 NRC then 62 response), 3E00
 *  tester-present keepalives, periodic live data. Emits UdsLog.Events so the
 *  UI renders a live console and the session .txt log file matches reality. */
public final class SimEcu {
    private SimEcu() {}

    public interface Listener { void onLine(String dir, String payload); }
    public interface VinListener { void onVin(String vinAscii); }
    public interface VoltListener { void onVolts(double v); }

    private static final Handler H = new Handler(Looper.getMainLooper());
    private static final Random RND = new Random(42);
    private static boolean keepaliveRunning = false;

    public static String hex(String ascii) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < ascii.length(); i++)
            b.append(String.format(Locale.US, "%02X", (int) ascii.charAt(i)));
        return b.toString();
    }

    public static String unhex(String hex) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i + 1 < hex.length(); i += 2)
            b.append((char) Integer.parseInt(hex.substring(i, i + 2), 16));
        return b.toString();
    }

    public static String stamp() {
        return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US).format(new Date());
    }

    /** Live battery voltage (reference shows e.g. 12.515625 V ticking). */
    public static double nextVolts() {
        double base = Session.batteryVolts;
        double v = base + (RND.nextDouble() - 0.5) * 0.24;
        if (v < 11.8) v = 11.8; if (v > 14.7) v = 14.7;
        Session.batteryVolts = v;
        return v;
    }

    /** Fire a VIN auto-read conversation; steps land ~80-200 ms apart like the real log. */
    public static void readVin(final String vin, final Listener out, final VinListener done) {
        final String tx = Session.ecuTx, rx = Session.ecuRx;
        final String[][] steps = new String[][]{
                {"TX", tx + " -> 1001"},
                {"RX", rx + " -> 5001003201F4"},
                {"TX", tx + " -> 22F190"},
                {"RX", rx + " -> 7F2278"},
                {"RX", rx + " -> 62F190" + hex(vin)},
        };
        for (int i = 0; i < steps.length; i++) {
            final int k = i;
            H.postDelayed(new Runnable() {
                public void run() {
                    out.onLine(steps[k][0], steps[k][1]);
                    if (k == steps.length - 1 && done != null) done.onVin(vin);
                }
            }, 480 + 320L * i);
        }
    }

    /** Periodic tester-present 3E00/7E00 exactly like the captured session log. */
    public static void startKeepalive(final Listener out) {
        if (keepaliveRunning) return;
        keepaliveRunning = true;
        final boolean[] txPhase = new boolean[]{true};
        H.postDelayed(new Runnable() {
            public void run() {
                if (!keepaliveRunning) return;
                out.onLine(txPhase[0] ? "TX" : "RX", txPhase[0] ? Session.ecuTx + " -> 3E00" : Session.ecuRx + " -> 7E00");
                txPhase[0] = !txPhase[0];
                H.postDelayed(this, txPhase[0] ? 3120 : 90);
            }
        }, 3120);
    }

    public static void stopKeepalive() { keepaliveRunning = false; }

    /** Small helper for continuous numeric live data. */
    public static String fmt(double v) { return String.format(Locale.US, "%.2f", v); }

    /** Simulated live value for a given seeded live-test definition. */
    public static String liveValue(com.nirixx.app.db.Db.TestDef t) {
        String n = t.name;
        if (n.startsWith("Read Vehicle")) return Session.selectedVin;
        if (n.equals("CVN")) return "47F2DBD1";
        if (n.equals("CALID") || n.equals("CAL ID")) return "U279EBS6V0A3a903";
        if (n.startsWith("Date of last programming")) return "19072019";
        if (n.equals("Battery Voltage")) return fmt(nextVolts()) + " V";
        if (n.equals("Engine Temperature")) return fmt(55 + RND.nextDouble() * 4) + " \u00b0C";
        if (n.equals("Engine Speed")) return fmt(1550 + RND.nextDouble() * 130) + " rpm";
        if (n.equals("Vehicle speed")) return fmt(0.0);
        if (n.equals("Engine operating state")) return "ENGSTATE_ES";
        if (n.equals("Ignition key on flag")) return "ON";
        if (n.contains("Quick shift")) {                     // deliberately out-of-range like the ref
            return fmt(4.9 + RND.nextDouble() * 0.1) + " V";
        }
        if (n.contains("(Sensor 1)")) return fmt(0.6 + RND.nextDouble() * 0.15) + " V";
        if (n.contains("(Sensor 2)")) return fmt(4.2 + RND.nextDouble() * 0.2) + " V";
        if (n.equals("Manifold Air Pressure Sensor")) return fmt(520 + RND.nextDouble() * 60) + " hPa";
        double mid = (t.vmin + t.vmax) / 2.0;
        double v = mid + (RND.nextDouble() - 0.5) * (t.vmax - t.vmin) * 0.12;
        return fmt(v) + (t.unit.length() > 0 ? " " + t.unit : "");
    }

    /** Numeric check for range colouring on the VHR diagnostic tab. */
    public static boolean inRange(com.nirixx.app.db.Db.TestDef t, String value) {
        try {
            String num = value.replaceAll("[^0-9.\\-]", "");
            if (num.length() == 0) return true;
            double v = Double.parseDouble(num);
            return t.vmax == t.vmin ? true : (v >= t.vmin && v <= t.vmax);
        } catch (Exception e) { return true; }
    }
}
