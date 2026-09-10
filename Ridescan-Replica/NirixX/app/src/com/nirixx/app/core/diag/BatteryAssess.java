package com.nirixx.app.core.diag;

/** 12-volt lead-acid resting-voltage state-of-charge bands.  Thresholds are the
 *  standard published chart (open-circuit voltage at ~25 °C, battery at rest):
 *  ≥12.6 full · 12.4 ≈75% · 12.2 ≈50% · 12.0 ≈25% · <11.8 discharged, and the
 *  charging window 13.5–14.8 V with the engine running.  Pure logic, unit
 *  tested on the JVM. */
public final class BatteryAssess {

    private BatteryAssess() { }

    public static final double CHARGE_MIN = 13.5;
    public static final double CHARGE_MAX = 14.8;

    /** State of charge estimate in percent from a resting voltage. */
    public static int socPercent(double volts) {
        if (volts >= 12.70) return 100;
        if (volts >= 12.60) return 95;
        if (volts >= 12.50) return 90;
        if (volts >= 12.40) return 75;
        if (volts >= 12.30) return 65;
        if (volts >= 12.20) return 50;
        if (volts >= 12.00) return 25;
        if (volts >= 11.80) return 10;
        return 0;
    }

    /** true when the voltage indicates the charging system is running. */
    public static boolean isCharging(double volts) {
        return volts >= CHARGE_MIN && volts <= CHARGE_MAX + 0.9;  // some reg/rect run to 15.5 V
    }

    /** Technician-readable assessment of a key-ON (resting-ish) reading. */
    public static String assessment(double volts) {
        if (volts <= 0) return "No reading";
        if (isCharging(volts))
            return "Charging system active (" + fmt(volts) + " V) — alternator/stator output present";
        if (volts > CHARGE_MAX + 0.9)
            return "Over-voltage " + fmt(volts) + " V — check regulator/rectifier";
        int soc = socPercent(volts);
        if (soc >= 75) return "Battery OK — approx. " + soc + "% charge at rest";
        if (soc >= 50) return "Battery partially discharged (≈" + soc + "%) — recommend recharge";
        return "Battery low (≈" + soc + "%) — recharge and re-test; check for parasitic drain";
    }

    public static String fmt(double v) {
        return String.format(java.util.Locale.US, "%.2f", v);
    }
}
