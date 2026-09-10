package com.nirixx.app.core.diag;

import android.content.Context;
import com.nirixx.app.Session;
import com.nirixx.app.db.Db;

/** Persists VCI transport details in the configs table — nothing hardcoded
 *  beyond factory defaults that the UI lets the technician override. */
public final class TransportSettings {

    private TransportSettings() {}

    public static final String DEFAULT_WIFI_IP = "192.168.0.10";   // ELM-WiFi convention
    public static final int DEFAULT_WIFI_PORT = 35000;


    public static String wifiIp(Context c) {
        return Db.get(c).config("wifi_vci_ip", DEFAULT_WIFI_IP);
    }

    public static int wifiPort(Context c) {
        try { return Integer.parseInt(Db.get(c).config("wifi_vci_port", "" + DEFAULT_WIFI_PORT)); }
        catch (Exception e) { return DEFAULT_WIFI_PORT; }
    }

    public static void saveWifi(Context c, String ip, String port) {
        if (ip != null && ip.length() > 0) Db.get(c).setConfig("wifi_vci_ip", ip);
        if (port != null && port.length() > 0) Db.get(c).setConfig("wifi_vci_port", port);
    }

    public static void saveBt(Context c, String name, String serial) {
        if (name != null && name.length() > 0) Db.get(c).setConfig("last_vci", name);
        if (serial != null && serial.length() > 0) {
            Db.get(c).setConfig("vci_serial", serial);
            Session.vciSerial = serial;
        }
    }

    /** Called right after a successful engine bring-up. */
    public static void onConnected(Context c, String linkType, String displayName) {
        Db.get(c).setConfig("connectivity", linkType);
        Session.connectivity = linkType;
        if (displayName != null && displayName.length() > 0) {
            Db.get(c).setConfig("last_vci", displayName);
        }
        // derive a stable 6-digit serial for the session-id scheme
        // (<vciSerial><ddMMyyyy><HHmmss> — see docs/analysis/16):
        // 1) trailing digits of the adapter's own display name (TechPRO_504856 → 504856);
        // 2) deterministic 6-digit hash of this tablet's build fingerprint.
        //    (Never a captured third-party serial.)
        String serial = Db.get(c).config("vci_serial", "");
        if (serial.length() == 0) {
            serial = deriveSerial(displayName);
            Db.get(c).setConfig("vci_serial", serial);
        }
        Session.vciSerial = serial;
    }

    private static String deriveSerial(String displayName) {
        if (displayName != null) {
            String d = displayName.replaceAll("[^0-9]", "");
            if (d.length() >= 6) return d.substring(d.length() - 6);
        }
        int h = (android.os.Build.BRAND + "|" + android.os.Build.MODEL + "|"
                + android.os.Build.FINGERPRINT).hashCode();
        return String.format(java.util.Locale.US, "%06d", (Math.abs(h) % 900000) + 100000);
    }
}
