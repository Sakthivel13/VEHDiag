package com.nirixx.app.core.uds;

/** SAE J1979 / ISO 15031-5 Mode 01 (current data) helpers — public, standardised
 *  PID encoding & formulas.  Only PIDs with a published standard formula are
 *  implemented; anything proprietary stays "definition pending" in the UI. */
public final class Obd {

    private Obd() { }

    // ---- supported Mode-01 PIDs (service 0x01 shows live data) ----
    public static final int PID_ENGINE_COOLANT_TEMP = 0x05;  // A - 40            °C
    public static final int PID_ENGINE_RPM          = 0x0C;  // (256A + B) / 4     rpm
    public static final int PID_VEHICLE_SPEED       = 0x0D;  // A                  km/h
    public static final int PID_INTAKE_AIR_TEMP     = 0x0F;  // A - 40             °C
    public static final int PID_THROTTLE_POSITION   = 0x11;  // A * 100 / 255      %
    public static final int PID_INTAKE_MAP          = 0x0B;  // A                  kPa
    public static final int PID_CONTROL_MODULE_V    = 0x42;  // (256A + B) / 1000  V

    /** Build a Mode-01 request for a single PID. */
    public static byte[] requestPid(int pid) {
        return new byte[]{0x01, (byte) pid};
    }

    /** Build a Mode-09 (vehicle information) request. */
    public static byte[] requestInfo(int infoType) {
        return new byte[]{0x09, (byte) infoType};
    }

    /** Decode a Mode-01 reply payload.  Expected layout: 41 &lt;pid&gt; A [B …].
     *  @return decoded value or null when the payload is not a positive reply. */
    public static Double decodePid(int pid, byte[] payload) {
        if (payload == null || payload.length < 3) return null;
        if ((payload[0] & 0xFF) != 0x41) return null;
        if ((payload[1] & 0xFF) != pid) return null;
        int a = payload[2] & 0xFF;
        int b = payload.length > 3 ? payload[3] & 0xFF : 0;
        switch (pid) {
            case PID_ENGINE_COOLANT_TEMP: return Double.valueOf(a - 40);
            case PID_INTAKE_AIR_TEMP:     return Double.valueOf(a - 40);
            case PID_ENGINE_RPM:          return Double.valueOf((a * 256 + b) / 4.0);
            case PID_VEHICLE_SPEED:       return Double.valueOf(a);
            case PID_THROTTLE_POSITION:   return Double.valueOf(a * 100.0 / 255.0);
            case PID_INTAKE_MAP:          return Double.valueOf(a);
            case PID_CONTROL_MODULE_V:    return Double.valueOf((a * 256 + b) / 1000.0);
            default: return null;   // known PID set only — never guess
        }
    }

    /** Extract the data records of a Mode-09 reply (49 &lt;info&gt; &lt;n&gt; data…). */
    public static byte[] decodeInfo(int infoType, byte[] payload) {
        if (payload == null || payload.length < 3) return null;
        if ((payload[0] & 0xFF) != 0x49 || (payload[1] & 0xFF) != infoType) return null;
        byte[] out = new byte[payload.length - 3];
        System.arraycopy(payload, 3, out, 0, out.length);
        return out;
    }

    /** ASCII-ise a Mode-09 VIN/CALID record (drops the record-count byte leading 00s). */
    public static String asciiInfo(byte[] rec) {
        if (rec == null) return null;
        StringBuilder sb = new StringBuilder();
        boolean started = false;
        for (int i = 0; i < rec.length; i++) {
            int c = rec[i] & 0xFF;
            if (!started && (c == 0 || c < 0x20)) continue;   // count / leading pad
            started = true;
            if (c >= 0x20 && c < 0x7F) sb.append((char) c);
        }
        String s = sb.toString().trim();
        return s.length() == 0 ? null : s;
    }

    /** SAE J1979 Mode 09 $08 — In-use Performance Tracking (IUPR) records.
     *  Layout: [NODI] then per monitor 4 bytes = numerator(2B) | denominator(2B).
     *  Monitor identity order is OEM-published material, so records here are
     *  labelled M1..Mn in bus order — never named or judged from guesses. */
    public static String decodeIpt(byte[] rec) {
        if (rec == null) return null;
        int off = (rec.length % 4 == 0) ? 0 : ((rec.length - 1) % 4 == 0 ? 1 : -1);
        if (off < 0) return null;
        StringBuilder sb = new StringBuilder();
        int m = 1;
        for (int i = off; i + 4 <= rec.length; i += 4) {
            int num = ((rec[i] & 0xFF) << 8) | (rec[i + 1] & 0xFF);
            int den = ((rec[i + 2] & 0xFF) << 8) | (rec[i + 3] & 0xFF);
            if (sb.length() > 0) sb.append("  ·  ");
            sb.append('M').append(m++).append(' ').append(num).append('/').append(den);
        }
        return sb.length() == 0 ? null : sb.toString();
    }

    /** A PID the UI is allowed to poll continuously (cheap, safe reads). */
    public static boolean pollable(int pid) {
        switch (pid) {
            case PID_ENGINE_COOLANT_TEMP:
            case PID_ENGINE_RPM:
            case PID_VEHICLE_SPEED:
            case PID_INTAKE_AIR_TEMP:
            case PID_THROTTLE_POSITION:
            case PID_INTAKE_MAP:
            case PID_CONTROL_MODULE_V:
                return true;
            default: return false;
        }
    }
}
