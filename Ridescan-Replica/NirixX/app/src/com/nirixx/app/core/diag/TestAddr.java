package com.nirixx.app.core.diag;

/** Parsed form of the tests.addr column — how a live/IO/routine/write row is
 *  reached on the bus.  NULL addr ⇒ "definition pending": the address is not
 *  published in any document the project owns and the UI must NOT simulate.
 *
 *  Grammar:   did:F190            UDS 0x22 read / 0x2E write of a 16-bit DID
 *             pid:0C              SAE J1979 Mode-01 PID (standard formula)
 *             pid:0B*10           PID with display multiplier (kPa → hPa …)
 *             m09:02              SAE J1979 Mode-09 info record (VIN/CVN/CALID)
 *             rid:F003            UDS 0x31 routine id
 *             io:2F01             UDS 0x2F IO-control DID (reserved)          */
public final class TestAddr {

    public static final int NONE = 0;
    public static final int DID = 1;
    public static final int PID = 2;
    public static final int M09 = 3;
    public static final int RID = 4;
    public static final int IO = 5;

    public final int kind;
    public final int value;        // did / pid / infotype / routine id
    public final double factor;    // display multiplier (1.0 unless specified)

    private TestAddr(int kind, int value, double factor) {
        this.kind = kind; this.value = value; this.factor = factor;
    }

    /** Parse or return null for null/empty/garbage — never throws. */
    public static TestAddr parse(String s) {
        if (s == null) return null;
        s = s.trim().toLowerCase(java.util.Locale.US);
        if (s.length() == 0) return null;
        try {
            double factor = 1.0;
            int star = s.indexOf('*');
            if (star >= 0) {
                factor = Double.parseDouble(s.substring(star + 1));
                s = s.substring(0, star);
            }
            int colon = s.indexOf(':');
            if (colon < 0) return null;
            String tag = s.substring(0, colon);
            int v = Integer.parseInt(s.substring(colon + 1), 16);
            if ("did".equals(tag)) return new TestAddr(DID, v, factor);
            if ("pid".equals(tag)) return new TestAddr(PID, v, factor);
            if ("m09".equals(tag)) return new TestAddr(M09, v, factor);
            if ("rid".equals(tag)) return new TestAddr(RID, v, factor);
            if ("io".equals(tag))  return new TestAddr(IO, v, factor);
            return null;
        } catch (Exception e) {
            return null;
        }
    }

    public String toString() {
        String tag = kind == DID ? "did" : kind == PID ? "pid" : kind == M09 ? "m09"
                : kind == RID ? "rid" : kind == IO ? "io" : "none";
        return tag + ":" + Integer.toHexString(value).toUpperCase()
                + (factor == 1.0 ? "" : "*" + factor);
    }
}
