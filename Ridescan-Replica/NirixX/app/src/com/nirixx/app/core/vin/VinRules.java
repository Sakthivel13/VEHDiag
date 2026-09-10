package com.nirixx.app.core.vin;

/** VIN → vehicle identification driven by the project's real model table
 *  (the 33-model list supplied with the project: model, variant, VIN pattern,
 *  vehicle type).  Pure Java so it is unit-testable off-device.
 *
 *  Matching rule: a pattern like "MD637CE5XXXXXXXXX" means the literal prefix
 *  must match and the total VIN length must be 17.  No fallback guessing —
 *  unidentified VINs are reported, never assumed. */
public final class VinRules {

    /** ( model, variant/systems, vinPattern, type ) — exactly as supplied. */
    public static final String[][] MODELS = {
        {"TVS Apache 160 4V ABS", "Dual Channel - 4V - EMS - ABS (Cont)", "MD637CE5XXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Apache RR 310", "Apache - EMS, ABS(BOSCH)", "MD634CE4XXXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Apache RTR 160 2V", "Single CH - 2V - EMS,ABS(BOSCH)", "MD634CE4XXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Apache RTR 180 2V RM", "RM - EMS,ABS(BOSCH)", "MD634CE4XXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Apache RTR 200 4V RM", "EMS", "MD637XXXXXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Apache RTX", "EMS, ABS, ICU(VISTEON)", "MD637BT1XXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Raider 125", "EMS, ICU", "MD625CK2XXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Raider IGO", "EMS, SEDAMAC", "MD625CK2XXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Ronin", "EMS, ABS, ICU, ISG", "MD637CE5XXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Radeon", "EMS", "MD625CKXXXXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Sport", "EMS", "MD625CK2XXXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Sport Kick Start", "EMS - KEIHIN", "MD625CK2XXXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Star City Plus", "EMS", "MD625AK2XXXXXXXXXX", "MOTOR CYCLE"},
        {"TVS XL 100", "EMS", "MD637BT1XXXXXXXXXX", "MOTOR CYCLE"},
        {"TVS XL 100 HD", "EMS", "MD637BT1XXXXXXXXXX", "MOTOR CYCLE"},
        {"TVS Jupiter Old", "EMS - CONTINENTAL", "MD637BT1XXXXXXXXXX", "SCOOTER"},
        {"TVS Jupiter New", "EMS, ISG & ICU", "MD637BT1XXXXXXXXXX", "SCOOTER"},
        {"TVS Ntorq 125", "EMS", "MD637XXXXXXXXXXXXX", "SCOOTER"},
        {"TVS Ntorq 150", "", "MD637XXXXXXXXXXXXX", "SCOOTER"},
        {"TVS Scooty Pep Plus", "EMS", "MD637XXXXXXXXXXXXX", "SCOOTER"},
        {"TVS Zest", "EMS", "MD637XXXXXXXXXXXXX", "SCOOTER"},
        {"TVS iQube ST", "EMS", "MD62912XXXXXXXXXX", "SCOOTER"},
        {"TVS iQube S", "EMS", "MD62912XXXXXXXXXX", "SCOOTER"},
        {"TVS KING GS+", "PASSENGER - AC Pet", "MD6M14PFXXXXXXXXX", "3-WHEELER"},
        {"TVS KING ZS+", "PASSENGER - AC CNG", "MD6M14CFXXXXXXXXX", "3-WHEELER"},
        {"TVS KING LS+", "PASSENGER - AC LPG", "MD6M14LFXXXXXXXXX", "3-WHEELER"},
        {"TVS KING GD", "PASSENGER - LC Pet", "MD6M1LPFXXXXXXXXX", "3-WHEELER"},
        {"TVS KING ZD", "PASSENGER - LC CNG", "MD6M1LCFXXXXXXXXXX", "3-WHEELER"},
        {"TVS KING ZK PF", "CARGO PF", "MD6N1LCFXXXXXXXXXX", "3-WHEELER"},
        {"TVS KING ZK LT", "CARGO LT", "MD6N1LCFXXXXXXXXXX", "3-WHEELER"},
        {"TVS KING E", "PASSENGER - EV", "MD6EVM1DXXXXXXXXXX", "3-WHEELER"},
        {"TVS 3W LARGE", "CARGO - LC CNG", "MD6N1LCGXXXXXXXXXX", "3-WHEELER"},
        {"TVS KING 3W LARGE", "CARGO - EV", "MD6EVNICXXXXXXXXXX", "3-WHEELER"},
    };

    private VinRules() {}

    /** Validate a candidate VIN string (ISO 3779 length / charset). */
    public static boolean isValidVin(String vin) {
        if (vin == null || vin.length() != 17) return false;
        for (int i = 0; i < 17; i++) {
            char c = vin.charAt(i);
            boolean ok = (c >= 'A' && c <= 'Z' && c != 'I' && c != 'O' && c != 'Q')
                    || (c >= '0' && c <= '9');
            if (!ok) return false;
        }
        return true;
    }

    /** Literal prefix portion of a pattern (the part before the first 'X'). */
    public static String prefixOf(String pattern) {
        int cut = pattern.indexOf('X');
        return cut < 0 ? pattern : pattern.substring(0, cut);
    }

    /** All matches by prefix rule, best (longest prefix) first.
     *  Returns indices into MODELS; caller resolves ambiguity (shared prefixes
     *  across the Apache/KING families are normal). */
    public static int[] match(String vin) {
        if (!isValidVin(vin)) return new int[0];
        java.util.ArrayList<Integer> idx = new java.util.ArrayList<Integer>();
        java.util.ArrayList<Integer> prefLen = new java.util.ArrayList<Integer>();
        for (int i = 0; i < MODELS.length; i++) {
            String p = prefixOf(MODELS[i][2]);
            if (p.length() > 0 && vin.startsWith(p)) {
                int at = 0;
                while (at < prefLen.size() && prefLen.get(at).intValue() >= p.length()) at++;
                prefLen.add(at, Integer.valueOf(p.length()));
                idx.add(at, Integer.valueOf(i));
            }
        }
        int[] out = new int[idx.size()];
        for (int i = 0; i < out.length; i++) out[i] = idx.get(i).intValue();
        return out;
    }

    /** Short system tags parsed from a variant string, e.g.
     *  "EMS, ABS, ICU, ISG" → {"EMS","ABS","ICU","ISG"}. */
    public static String[] systemsOf(String variant) {
        java.util.ArrayList<String> out = new java.util.ArrayList<String>();
        String[] keys = {"EMS", "ABS", "ICU", "ISG", "EV", "SEDEMAC", "KEIHIN",
                "CONTINENTAL", "BOSCH", "VISTEON", "CONT"};
        String up = variant.toUpperCase(java.util.Locale.US);
        for (int i = 0; i < keys.length; i++) {
            if (keys[i].equals("CONT")) continue;                 // folded into CONTINENTAL
            if (up.contains(keys[i]) && !out.contains(keys[i])) {
                if (keys[i].equals("EV") && up.contains("PASSENGER - EV")) out.add("EV");
                else if (!keys[i].equals("EV")) out.add(keys[i]);
            }
        }
        if (up.contains("(CONT")) out.add("CONTINENTAL");
        return out.toArray(new String[0]);
    }
}
