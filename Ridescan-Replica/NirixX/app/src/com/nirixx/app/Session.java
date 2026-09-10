package com.nirixx.app;

import android.content.Context;
import com.nirixx.app.db.Db;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Static app state shared across screens — bound to the SQLite database via Db. */
public final class Session {
    private Session() {}

    // ---- signed-in dealer (users/roles tables) ----
    public static String dealerEmail = "";
    public static String dealerName = "NEO MOTORS";
    public static String dealerCode = "10814";
    public static String dealerBranch = "10814";
    public static String dealerPhone = "";
    public static String userType = "Dealer Service";

    // ---- VCI (connection is always one of BT / WIFI / USB) ----
    public static boolean vciConnected = false;
    public static String vciName = "";
    public static String vciFw = "1.07";
    public static String connectivity = "BLUETOOTH";   // BLUETOOTH | WIFI | USB
    public static String vciSerial = "504856";

    // ---- current vehicle / ECU selection (vehicles/ecus tables) ----
    public static long vehicleId = 2;                  // Ronin default row
    public static String selectedVin = "MD637AN11R2D01275";
    public static String selectedVehicle = "TVS Ronin";
    public static String selectedVariant = "RONIN225_BSVI";
    public static String vehicleType = "Cruiser";
    public static String vehicleImage = "veh_cruiser";
    public static long ecuId = 4;                      // Ronin EMS row
    public static String selectedEcu = "ENGINE MANAGEMENT SYSTEM (OBDII)";
    public static String selectedEcuCode = "EMS-OBDII";
    public static String selectedEcuShort = "EMS";
    public static String selectedFlashFile = "";        // set only from a real flash row/import
    public static String ecuTx = "7E0";
    public static String ecuRx = "7E8";

    // ---- diagnostic run state ----
    public static int dtcsCleared = 0;
    public static boolean dtcScanned = false;           // set true only by a real 19 02 exchange
    public static boolean faultsFound = false;
    public static boolean reportGenerated = false;
    public static String odometer = "—";
    public static double batteryVolts = -1;             // < 0 = never measured (no fake default)

    /** Live VHR collector: kind|key -> value (io results, physical answers, dealer tab…). */
    public static final Map<String, String> vhrData = new LinkedHashMap<String, String>();

    /** Session key in the store format: <vciSerial><ddMMyyyyHHmmss>, e.g. 50485617032026113515. */
    public static String sessionKey = null;

    /** Resolve the current vehicle row from the DB when none is selected yet
     *  (fresh install / after DB upgrade): VIN match first, Ronin as fallback. */
    public static void ensureVehicle(Context c) {
        if (vehicleId > 0) return;
        try {
            Db.Vehicle v = Db.get(c).vehicleByVin(selectedVin);
            if (v == null) {
                for (Db.Vehicle x : Db.get(c).vehicles())
                    if ("TVS Ronin".equals(x.model)) { v = x; break; }
            }
            if (v == null) return;
            selectVehicle(v.id, v.model, v.variant, v.type, v.vinSample.length() > 0 ? v.vinSample : selectedVin, v.image);
            java.util.List<Db.Ecu> es = Db.get(c).ecus(v.id);
            if (!es.isEmpty()) {
                Db.Ecu e = es.get(0);
                selectEcu(e.id, e.name, e.code, e.tx, e.rx);
            }
        } catch (Exception ignored) { }
    }

    public static String ensureSession(Context c) {
        ensureVehicle(c);
        if (sessionKey == null) {
            String ts = new SimpleDateFormat("ddMMyyyyHHmmss", Locale.US).format(new Date());
            sessionKey = vciSerial + ts;
            Db.get(c).saveSession(sessionKey, vehicleId, selectedVin,
                    System.currentTimeMillis(), connectivity, vciFw, vciName);
        }
        return sessionKey;
    }

    public static void selectVehicle(long id, String model, String variant, String type,
                                     String vinSample, String image) {
        vehicleId = id;
        selectedVehicle = model;
        selectedVariant = variant;
        vehicleType = type;
        selectedVin = vinSample;
        vehicleImage = image;
    }

    public static void selectEcu(long id, String name, String code, String tx, String rx) {
        ecuId = id;
        selectedEcu = name;
        selectedEcuCode = code;
        selectedEcuShort = code.contains("-") ? code.substring(0, code.indexOf('-')) : code;
        ecuTx = tx;
        ecuRx = rx;
    }

    /** Legacy stub data still used by a few secondary screens. */
    public static final List<String[]> vehicles = new ArrayList<String[]>();
    static {
        vehicles.add(new String[]{"TVS Ronin", "RONIN225_BSVI · BSVI", "MD637AN11R2D01275", "Today 09:41"});
        vehicles.add(new String[]{"TVS Apache RTR 160 4V", "RTR160_4V_1CH_EFI_BSVI · BSVI", "MD625AF95S2H26963", "Yesterday"});
        vehicles.add(new String[]{"TVS Jupiter New", "JUP125_ISG_BSVI · BSVI", "MD626EG55S1B37997", "Mon 11:05"});
        vehicles.add(new String[]{"TVS XL 100", "XL100_KLINE_OBD1 · K-Line", "MD621BP23T1D02028", "Sat 16:22"});
    }

    public static final String[][] DTC_DATA = new String[][]{
        {"P0130", "O2 Sensor Circuit Malfunction (Bank 1 Sensor 1)", "Active"},
        {"P0451", "EVAP Pressure Sensor Range / Performance", "Stored"},
        {"P0562", "System Voltage Low — check charging system", "Stored"},
        {"P0850", "Side-stand Switch Input Circuit", "Active"},
        {"U0100", "Lost Communication With ECM/PCM", "History"},
    };
}
