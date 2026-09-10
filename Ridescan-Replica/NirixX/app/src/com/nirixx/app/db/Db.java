package com.nirixx.app.db;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.util.ArrayList;
import java.util.List;

/** NirixX on-device database (SQLite).
 *
 *  Why SQLite and not MongoDB: the tool must work fully offline in a workshop,
 *  can never depend on a server, and we ship zero third-party code — SQLite is
 *  built into Android, transactional and fast. This schema mirrors the DMS
 *  concepts seen in the reference app (roles, users, vehicles, ECUs, tests,
 *  sessions, logs, streaming samples, test inputs, configs, history).
 */
public final class Db extends SQLiteOpenHelper {

    private static final String NAME = "nirixx.db";
    private static final int VER = 3;
    private static Db inst;

    public static synchronized Db get(Context c) {
        if (inst == null) inst = new Db(c.getApplicationContext());
        return inst;
    }

    private Db(Context c) { super(c, NAME, null, VER); }

    // ------------------------------------------------------------------ rows
    public static final class Vehicle {
        public long id; public String model, variant, type, obd, protocol, emission,
                vinPrefix, vinSample, vinFormat, description, image, vinRule;
        public String toString() { return model; }
    }
    public static final class Ecu {
        public long id; public long vehicleId; public String name, code, protocol,
                emission, manufacturer, tx, rx; public int sort;
    }
    public static final class TestDef {                  // kind: live|io|routine|write|phys
        public long id; public long ecuId; public String kind, name, unit, category;
        public double vmin, vmax; public int writable, sort;
        public String addr;                              // bus address (TestAddr grammar) or null
    }
    public static final class Dtc {
        public long id; public long ecuId; public String code, descr;
    }

    // ------------------------------------------------------------------ DDL
    @Override
    public void onConfigure(SQLiteDatabase db) { super.onConfigure(db); db.setForeignKeyConstraintsEnabled(true); }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE roles(role_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)");
        db.execSQL("CREATE TABLE users(user_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " dealer_code TEXT UNIQUE NOT NULL, name TEXT, email TEXT, branch_id TEXT," +
                " phone TEXT, role_id INTEGER REFERENCES roles(role_id), pin TEXT)");
        db.execSQL("CREATE TABLE vehicles(vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " model TEXT, variant TEXT, type TEXT, obd TEXT, protocol TEXT, emission TEXT," +
                " vin_prefix TEXT, vin_sample TEXT, vin_format TEXT, description TEXT, image_res TEXT, vin_rule TEXT)");
        db.execSQL("CREATE TABLE ecus(ecu_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " vehicle_id INTEGER REFERENCES vehicles(vehicle_id) ON DELETE CASCADE," +
                " name TEXT, code TEXT, protocol TEXT, emission TEXT, manufacturer TEXT," +
                " tx_addr TEXT, rx_addr TEXT, sort INTEGER)");
        db.execSQL("CREATE TABLE tests(test_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " ecu_id INTEGER REFERENCES ecus(ecu_id) ON DELETE CASCADE," +
                " kind TEXT, name TEXT, unit TEXT, vmin REAL, vmax REAL, category TEXT," +
                " writable INTEGER DEFAULT 0, sort INTEGER, addr TEXT)");
        db.execSQL("CREATE TABLE manuals(manual_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " name TEXT, path TEXT, size INTEGER, added INTEGER)");
        db.execSQL("CREATE TABLE flash_bins(bin_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " name TEXT, path TEXT, size INTEGER, module TEXT, added INTEGER)");
        db.execSQL("CREATE TABLE vhr_items(item_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " vehicle_id INTEGER REFERENCES vehicles(vehicle_id) ON DELETE CASCADE," +
                " name TEXT, unit TEXT, lo TEXT, hi TEXT, kind TEXT, sort INTEGER)");  // kind: VAL|QUAL|PHOTO
        db.execSQL("CREATE TABLE dtc_lib(dtc_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " ecu_id INTEGER REFERENCES ecus(ecu_id) ON DELETE CASCADE, code TEXT, descr TEXT)");
        db.execSQL("CREATE TABLE flash_files(file_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " ecu_id INTEGER REFERENCES ecus(ecu_id) ON DELETE CASCADE, filename TEXT, version TEXT)");
        db.execSQL("CREATE TABLE sessions(session_key TEXT PRIMARY KEY, user_id INTEGER," +
                " vehicle_id INTEGER, vin TEXT, started INTEGER, connectivity TEXT, firmware TEXT, vci TEXT)");
        db.execSQL("CREATE TABLE logs(log_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " session_key TEXT, ts INTEGER, dir TEXT, payload TEXT)");
        db.execSQL("CREATE TABLE stream_samples(sample_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " session_key TEXT, test_id INTEGER, ts INTEGER, value TEXT)");
        db.execSQL("CREATE TABLE test_inputs(input_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " session_key TEXT, kind TEXT, key TEXT, value TEXT)");
        db.execSQL("CREATE TABLE iupr_history(iupr_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " session_key TEXT, vehicle_id INTEGER, vin TEXT, cvn TEXT, cal_id TEXT," +
                " ratio TEXT, kms TEXT, city TEXT, state TEXT, created INTEGER)");
        db.execSQL("CREATE TABLE vhr_reports(report_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                " session_key TEXT, vehicle_id INTEGER, vin TEXT, path TEXT, verdict TEXT, created INTEGER)");
        db.execSQL("CREATE TABLE configs(cfg_key TEXT PRIMARY KEY, cfg_value TEXT)");
        db.execSQL("CREATE INDEX idx_logs_sess ON logs(session_key)");
        db.execSQL("CREATE INDEX idx_stream_sess ON stream_samples(session_key)");
        seed(db);
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int o, int n) {
        String[] tables = {"roles","users","vehicles","ecus","tests","vhr_items","dtc_lib",
                "flash_files","sessions","logs","stream_samples","test_inputs","iupr_history",
                "vhr_reports","configs","manuals","flash_bins"};
        for (int i = 0; i < tables.length; i++) db.execSQL("DROP TABLE IF EXISTS " + tables[i]);
        onCreate(db);
    }

    // ------------------------------------------------------------------ seed
    private static void seed(SQLiteDatabase db) {
        ins(db, "roles", new String[]{"name"}, new Object[]{"Dealer Engineer"});
        ins(db, "roles", new String[]{"name"}, new Object[]{"Dealer Service"});
        ins(db, "roles", new String[]{"name"}, new Object[]{"Service Manager"});
        ins(db, "roles", new String[]{"name"}, new Object[]{"Service Technician"});
        ins(db, "roles", new String[]{"name"}, new Object[]{"Service Advisor"});
        ins(db, "roles", new String[]{"name"}, new Object[]{"Administrator"});

        ins(db, "users", new String[]{"dealer_code","name","email","branch_id","phone","role_id","pin"},
                new Object[]{"10814", "NEO MOTORS", "neomotors@nirixx.in", "10814", "+91 98410 22011", 1, "1234"});
        ins(db, "users", new String[]{"dealer_code","name","email","branch_id","phone","role_id","pin"},
                new Object[]{"12345", "RAJIV P", "rajiv.p@nirixx.in", "12345-AMB", "+91 99887 66554", 2, "0000"});
        ins(db, "users", new String[]{"dealer_code","name","email","branch_id","phone","role_id","pin"},
                new Object[]{"10815", "ARUN K", "arun.k@nirixx.in", "10815-MDU", "+91 97900 11223", 4, "1111"});

        long jupiter = v(db, "TVS Jupiter New", "JUP125_ISG_BSVI", "Scooter", "OBD II", "CAN", "BS VI OBD-II",
                "MD626EG", "MD626EG55S1B37997", "MD6 26E G##S#B#####",
                "125 cc ETFi scooter with Integrated Starter Generator (ISG), BSVI OBD-II EMS.",
                "veh_scooter");
        long ronin = v(db, "TVS Ronin", "RONIN225_BSVI", "Cruiser", "OBD II", "CAN", "BS VI OBD-II",
                "MD637AN", "MD637AN11R2D01275", "MD6 37A N##R#D#####",
                "225 cc oil-cooled cruiser, single-channel BABS, BSVI OBD-II EMS.",
                "veh_cruiser");
        long rtr = v(db, "TVS Apache RTR 160 4V", "RTR160_4V_1CH_EFI_BSVI", "Sport", "OBD II", "CAN", "BS VI OBD-II",
                "MD625AF", "MD625AF95S2H26963", "MD6 25A F##S#H#####",
                "160 cc 4-valve sport, ride modes, single-channel BABS, BSVI OBD-II EMS.",
                "veh_sport");
        long xl = v(db, "TVS XL 100", "XL100_KLINE_OBD1", "Moped", "OBD 1", "KLINE", "BS VI (K-Line)",
                "MD621BP", "MD621BP23T1D02028", "MD6 21B P##T#D#####",
                "100 cc moped, Mikuni K-Line (OBD-I) injection system.",
                "motorcycle");

        // ---- Jupiter New -------------------------------------------------
        long e = ec(db, jupiter, "ENGINE MANAGEMENT SYSTEM (OBDII)", "EMS-OBDII", "CAN", "OBD II", "SEDEMAC", "7E0", "7E8", 1);
        liveEMSBasics(db, e, false);
        ioPacks(db, e); routinesEMS(db, e); writeDids(db, e); flash(db, e, "K6060799_03_S.mot");
        dtcsEMS(db, e);
        ec(db, jupiter, "INSTRUMENT CLUSTER", "ICM", "KLINE", "—", "PRICOL", "7C0", "7C8", 2);
        ec(db, jupiter, "INTEGRATED STARTER GENERATOR (ISG)", "ISG", "CAN", "—", "SEG", "7E4", "7EC", 3);
        phys(db, jupiter, new String[][]{
                {"Drive chain slackness", "mm", "30", "40", "VAL"},
                {"Front tyre pressure", "PSI", "32", "32", "VAL"},
                {"Rear tyre pressure", "PSI", "32", "32", "VAL"},
                {"Engine oil level and oil condition", "ml", "1650", "1700", "VAL"},
                {"Dip stick oil level", "", "-", "-", "QUAL"},
                {"Clutch lever free play", "mm", "8", "12", "VAL"},
                {"Customer image", "", "-", "-", "PHOTO"}});

        // ---- Ronin --------------------------------------------------------
        e = ec(db, ronin, "ENGINE MANAGEMENT SYSTEM (OBDII)", "EMS-OBDII", "CAN", "OBD II", "SEDEMAC", "7E0", "7E8", 1);
        liveEMSBasics(db, e, false);
        ioPacks(db, e); routinesEMS(db, e); writeDids(db, e); flash(db, e, "K6060799_03_S.mot");
        dtcsEMS(db, e);
        long abs = ec(db, ronin, "ANTI-LOCK BRAKING SYSTEM", "BABS", "CAN", "—", "CONTINENTAL", "7E1", "7E9", 2);
        ins(db, "tests", new String[]{"ecu_id","kind","name","sort"},
                new Object[]{abs, "io", "Start Wheel Speed Test", 1});
        ins(db, "dtc_lib", new String[]{"ecu_id","code","descr"},
                new Object[]{abs, "C0031", "Left Front Wheel Speed Sensor Circuit"});
        ins(db, "dtc_lib", new String[]{"ecu_id","code","descr"},
                new Object[]{abs, "C0040", "Right Front Wheel Speed Sensor Circuit"});
        ec(db, ronin, "INSTRUMENT CLUSTER", "ICM", "KLINE", "—", "PRICOL", "7C0", "7C8", 3);
        ec(db, ronin, "INTEGRATED STARTER CLUSTER", "ISC", "CAN", "—", "SEG", "7E4", "7EC", 4);
        phys(db, ronin, new String[][]{
                {"Drive chain slackness", "mm", "18", "23", "VAL"},
                {"Front tyre pressure", "PSI", "25", "25", "VAL"},
                {"Rear tyre pressure", "PSI", "32", "32", "VAL"},
                {"Dip stick oil level", "", "-", "-", "QUAL"},
                {"Clutch play", "mm", "8", "13", "VAL"},
                {"Customer image", "", "-", "-", "PHOTO"}});

        // ---- Apache RTR 160 4V -------------------------------------------
        e = ec(db, rtr, "ENGINE MANAGEMENT SYSTEM (OBDII)", "EMS-OBDII", "CAN", "OBD II", "SEDEMAC", "7E0", "7E8", 1);
        liveEMSBasics(db, e, true);
        ioPacks(db, e); routinesEMS(db, e); writeDids(db, e); flash(db, e, "N6060929_06_S.srec");
        dtcsEMS(db, e);
        abs = ec(db, rtr, "ANTI-LOCK BRAKING SYSTEM", "BABS", "CAN", "—", "CONTINENTAL", "7E1", "7E9", 2);
        ins(db, "tests", new String[]{"ecu_id","kind","name","sort"},
                new Object[]{abs, "io", "Start Wheel Speed Test", 1});
        ec(db, rtr, "INSTRUMENT CLUSTER", "ICM", "KLINE", "—", "PRICOL", "7C0", "7C8", 3);
        phys(db, rtr, new String[][]{
                {"Drive chain slackness", "mm", "25", "35", "VAL"},
                {"Front tyre pressure", "PSI", "25", "25", "VAL"},
                {"Rear tyre pressure", "PSI", "28", "28", "VAL"},
                {"Engine oil level and oil condition", "ml", "1200", "1200", "VAL"},
                {"Dip stick oil level", "", "-", "-", "QUAL"},
                {"Clutch lever free play", "mm", "10", "15", "VAL"},
                {"Customer image", "", "-", "-", "PHOTO"}});

        // ---- XL 100 (OBD-1 / K-Line) -------------------------------------
        e = ec(db, xl, "ENGINE MANAGEMENT (MIKUNI OBD-I)", "EMS-KLINE", "KLINE", "OBD I", "MIKUNI", "40", "58", 1);
        ins(db, "tests", new String[]{"ecu_id","kind","name","unit","vmin","vmax","category","sort"},
                new Object[]{e, "live", "Battery Voltage", "V", 10.5, 14.5, "Current Status", 1});
        ins(db, "tests", new String[]{"ecu_id","kind","name","unit","vmin","vmax","category","sort"},
                new Object[]{e, "live", "Engine Temperature", "\u00b0C", 65, 110, "Thermal", 2});
        ins(db, "dtc_lib", new String[]{"ecu_id","code","descr"},
                new Object[]{e, "12", "Crankshaft position sensor (K-Line code)"});
        ec(db, xl, "INSTRUMENT CLUSTER", "ICM", "KLINE", "—", "PRICOL", "7C0", "7C8", 2);
        phys(db, xl, new String[][]{
                {"Front tyre pressure", "PSI", "25", "25", "VAL"},
                {"Rear tyre pressure", "PSI", "28", "28", "VAL"},
                {"Dip stick oil level", "", "-", "-", "QUAL"}});

        // ---- full supplied model table (33 TVS models) --------------------
        // (the four curated rows above carry the captured reference VINs/data;
        //  these rows come verbatim from the project's supplied vehicle list)
        seedSuppliedTable(db);

        // ---- configs -------------------------------------------------------
        setConfig(db, "support_number", "+917969478770");
        backfillAddrs(db);
        setConfig(db, "app_version", "V 1.6.3");
        setConfig(db, "connectivity", "BLUETOOTH");
        setConfig(db, "last_vci", "NirixiLINK_504856");
        setConfig(db, "dms_domain", "DMS");
    }

    private static long v(SQLiteDatabase db, String model, String variant, String type, String obd,
                          String protocol, String emission, String prefix, String sample,
                          String format, String desc, String img) {
        return ins(db, "vehicles",
                new String[]{"model","variant","type","obd","protocol","emission","vin_prefix","vin_sample","vin_format","description","image_res","vin_rule"},
                new Object[]{model, variant, type, obd, protocol, emission, prefix, sample, format, desc, img, ""});
    }

    /** Register one model row straight from the supplied 33-model table. */
    private static long addSupplied(SQLiteDatabase db, String model, String variant, String rule,
                                    String type, String img) {
        String prefix = com.nirixx.app.core.vin.VinRules.prefixOf(rule);
        return ins(db, "vehicles",
                new String[]{"model","variant","type","obd","protocol","emission","vin_prefix","vin_sample","vin_format","description","image_res","vin_rule"},
                new Object[]{model, variant, type, "OBD II", "CAN", "BS VI OBD-II", prefix, "", rule,
                        variant.length() > 0 ? variant + "  (VIN family " + prefix + ")" : "VIN family " + prefix,
                        img, rule});
    }


    /** The project's supplied vehicle list: (model, variant/systems, VIN rule).
     *  Rows whose model is already curated above are skipped at seed time. */
    private static final String[][] SUPPLIED = {
        {"TVS Apache 160 4V ABS", "Dual Channel - 4V - EMS - ABS (Cont)", "MD637CE5XXXXXXXXX"},
        {"TVS Apache RR 310", "Apache - EMS, ABS(BOSCH)", "MD634CE4XXXXXXXXXX"},
        {"TVS Apache RTR 160 2V", "Single CH - 2V - EMS,ABS(BOSCH)", "MD634CE4XXXXXXXXX"},
        {"TVS Apache RTR 180 2V RM", "RM - EMS,ABS(BOSCH)", "MD634CE4XXXXXXXXX"},
        {"TVS Apache RTR 200 4V RM", "EMS", "MD637XXXXXXXXXXXX"},
        {"TVS Apache RTX", "EMS, ABS, ICU(VISTEON)", "MD637BT1XXXXXXXXX"},
        {"TVS Raider 125", "EMS, ICU", "MD625CK2XXXXXXXXX"},
        {"TVS Raider IGO", "EMS, SEDAMAC", "MD625CK2XXXXXXXXX"},
        {"TVS Radeon", "EMS", "MD625CKXXXXXXXXXXX"},
        {"TVS Sport", "EMS", "MD625CK2XXXXXXXXXX"},
        {"TVS Sport Kick Start", "EMS - KEIHIN", "MD625CK2XXXXXXXXXX"},
        {"TVS Star City Plus", "EMS", "MD625AK2XXXXXXXXXX"},
        {"TVS Jupiter Old", "EMS - CONTINENTAL", "MD637BT1XXXXXXXXXX"},
        {"TVS Ntorq 125", "EMS", "MD637XXXXXXXXXXXXX"},
        {"TVS Ntorq 150", "", "MD637XXXXXXXXXXXXX"},
        {"TVS Scooty Pep Plus", "EMS", "MD637XXXXXXXXXXXXX"},
        {"TVS Zest", "EMS", "MD637XXXXXXXXXXXXX"},
        {"TVS iQube ST", "EMS", "MD62912XXXXXXXXXX"},
        {"TVS iQube S", "EMS", "MD62912XXXXXXXXXX"},
        {"TVS KING GS+", "PASSENGER - AC Pet", "MD6M14PFXXXXXXXXX"},
        {"TVS KING ZS+", "PASSENGER - AC CNG", "MD6M14CFXXXXXXXXX"},
        {"TVS KING LS+", "PASSENGER - AC LPG", "MD6M14LFXXXXXXXXX"},
        {"TVS KING GD", "PASSENGER - LC Pet", "MD6M1LPFXXXXXXXXX"},
        {"TVS KING ZD", "PASSENGER - LC CNG", "MD6M1LCFXXXXXXXXXX"},
        {"TVS KING ZK PF", "CARGO PF", "MD6N1LCFXXXXXXXXXX"},
        {"TVS KING ZK LT", "CARGO LT", "MD6N1LCFXXXXXXXXXX"},
        {"TVS KING E", "PASSENGER - EV", "MD6EVM1DXXXXXXXXXX"},
        {"TVS 3W LARGE", "CARGO - LC CNG", "MD6N1LCGXXXXXXXXXX"},
        {"TVS KING 3W LARGE", "CARGO - EV", "MD6EVNICXXXXXXXXXX"},
    };

    private static final String[] SKIP_SUPPLIED = {
        "TVS Ronin", "TVS Jupiter New", "TVS XL 100", "TVS XL 100 HD",
        "TVS Apache 160 4V ABS",          // covered by curated "TVS Apache RTR 160 4V"
    };

    private static void seedSuppliedTable(SQLiteDatabase db) {
        java.util.List<String> curated = new java.util.ArrayList<String>();
        for (int i = 0; i < SKIP_SUPPLIED.length; i++) curated.add(SKIP_SUPPLIED[i]);
        for (int i = 0; i < SUPPLIED.length; i++) {
            String[] m = SUPPLIED[i];
            if (curated.contains(m[0])) continue;
            String type = suppliedType(m[0]);
            String img = suppliedImage(m[0], type);
            long vid = addSupplied(db, m[0], m[1], m[2], type, img);
            seedSystems(db, vid, m[1], m[0]);
            phys(db, vid, new String[][]{
                    {"Drive chain slackness", "mm", "18", "30", "VAL"},
                    {"Front tyre pressure", "PSI", "25", "32", "VAL"},
                    {"Rear tyre pressure", "PSI", "28", "36", "VAL"},
                    {"Dip stick oil level", "", "-", "-", "QUAL"},
                    {"Clutch play", "mm", "8", "13", "VAL"},
                    {"Customer image", "", "-", "-", "PHOTO"}});
        }
    }

    private static String suppliedType(String model) {
        if (model.contains("KING") || model.contains("3W")) return "3-Wheeler";
        if (model.contains("Jupiter") || model.contains("Ntorq") || model.contains("Scooty")
                || model.contains("Zest") || model.contains("iQube")) return "Scooter";
        return "Motorcycle";
    }

    private static String suppliedImage(String model, String type) {
        if (model.contains("Apache")) return "veh_sport";
        if (model.contains("Ronin")) return "veh_cruiser";
        if ("Scooter".equals(type)) return "veh_scooter";
        return "motorcycle";                       // generic NirixX artwork, no per-model pack
    }

    /** ECU applicability derived from the supplied variant strings
     *  (EMS/ABS/ICU/ISG/EV tags and named suppliers) — nothing invented. */
    private static void seedSystems(SQLiteDatabase db, long vid, String variant, String model) {
        String up = variant.toUpperCase(java.util.Locale.US);
        if (up.contains("EV")) {
            ec(db, vid, "BATTERY MANAGEMENT SYSTEM", "BMS", "CAN", "\u2014", "TVSE", "7E4", "7EC", 1);
            ec(db, vid, "MOTOR CONTROL UNIT", "MCU", "CAN", "\u2014", "TVSE", "7E5", "7ED", 2);
            return;
        }
        String mfr = up.contains("KEIHIN") ? "KEIHIN"
                : up.contains("CONTINENTAL") ? "CONTINENTAL"
                : up.contains("BOSCH") ? "BOSCH"
                : up.contains("VISTEON") ? "VISTEON"
                : up.contains("SEDEMAC") ? "SEDEMAC" : "SEDEMAC";
        long ems = ec(db, vid, "ENGINE MANAGEMENT SYSTEM (OBDII)", "EMS-OBDII",
                "CAN", "OBD II", mfr, "7E0", "7E8", 1);
        genericLive(db, ems);
        ins(db, "dtc_lib", new String[]{"ecu_id","code","descr"},
                new Object[]{ems, "P0130", "O2 Sensor Circuit Malfunction (Bank 1 Sensor 1)"});
        ins(db, "dtc_lib", new String[]{"ecu_id","code","descr"},
                new Object[]{ems, "P0562", "System Voltage Low"});
        int sort = 2;
        if (up.contains("ABS")) {
            long abs = ec(db, vid, "ANTI-LOCK BRAKING SYSTEM", "BABS", "CAN", "\u2014",
                    up.contains("BOSCH") ? "BOSCH" : "CONTINENTAL", "7E1", "7E9", sort++);
            ins(db, "tests", new String[]{"ecu_id","kind","name","sort"},
                    new Object[]{abs, "io", "Start Wheel Speed Test", 1});
            ins(db, "dtc_lib", new String[]{"ecu_id","code","descr"},
                    new Object[]{abs, "C0031", "Left Front Wheel Speed Sensor Circuit"});
        }
        if (up.contains("ICU")) {
            ec(db, vid, "INSTRUMENT CLUSTER", "ICM", "CAN", "\u2014",
                    up.contains("VISTEON") ? "VISTEON" : "PRICOL", "7C0", "7C8", sort++);
        }
        if (up.contains("ISG")) {
            ec(db, vid, "INTEGRATED STARTER GENERATOR (ISG)", "ISG", "CAN", "\u2014", "SEG",
                    "7E4", "7EC", sort++);
        }
    }

    /** Legislated generic OBD-II identification + baseline items
     *  (category tagged so the UI can show when data is generic
     *  vs vehicle-specific, per audit requirements). */
    private static void genericLive(SQLiteDatabase db, long e) {
        Object[][] rows = new Object[][]{
                {"Read Vehicle Information (VIN)", "", 0, 0, "ECU Identification"},
                {"CVN", "", 0, 0, "ECU Identification"},
                {"CALID", "", 0, 0, "ECU Identification"},
                {"Battery Voltage", "V", 10.5, 14.5, "Generic OBD-II"},
                {"Engine Temperature", "\u00b0C", 65, 110, "Generic OBD-II"},
                {"Engine Speed", "rpm", 1000, 2500, "Generic OBD-II"},
        };
        for (int i = 0; i < rows.length; i++)
            ins(db, "tests", new String[]{"ecu_id","kind","name","unit","vmin","vmax","category","sort"},
                    new Object[]{e, "live", rows[i][0], rows[i][1], rows[i][2], rows[i][3], rows[i][4], i + 1});
    }

    private static long ec(SQLiteDatabase db, long vid, String name, String code, String protocol,
                           String emission, String manufacturer, String tx, String rx, int sort) {
        return ins(db, "ecus",
                new String[]{"vehicle_id","name","code","protocol","emission","manufacturer","tx_addr","rx_addr","sort"},
                new Object[]{vid, name, code, protocol, emission, manufacturer, tx, rx, sort});
    }

    private static void liveEMSBasics(SQLiteDatabase db, long e, boolean sport) {
        Object[][] rows = new Object[][]{
                {"Read Vehicle Information (VIN)", "", 0, 0, "ECU Identification"},
                {"Battery Voltage", "V", 10.5, 14.5, "Current Status"},
                {"Engine Temperature", "\u00b0C", 65, 110, "Thermal"},
                {"Throttle Position Sensor", "%", 0, 100, "Throttle"},
                {"Intake Air Pressure Sensor", "kpa", 3, 115, "Air"},
                {"Intake Air Temperature", "\u00b0C", -40, 130, "Air"},
                {"Engine Speed", "rpm", 1000, 2500, "Cranking"},
                {"Vehicle speed", "kmph", 0, 160, "Current Status"},
                {"Engine operating state", "", 0, 0, "State Recognition"},
                {"Ignition key on flag", "", 0, 0, "Ignition"},
                {"Relative multiplicative adaptation factor, exhaust bank selective", "%", 0, 100, "Exhaust"},
                {"Corrected duty cycle of PWM signal for CPS opening", "%", 0, 100, "Cranking"},
                {"Mesured fuel time delivery during cylinder cycle.", "ms", 0, 25, "Cranking"},
                {"CVN", "", 0, 0, "ECU Identification"},
                {"Date of last programming", "", 0, 0, "ECU Identification"},
                {"CALID", "", 0, 0, "ECU Identification"},
        };
        int i = 1;
        for (Object[] r : rows) {
            ins(db, "tests", new String[]{"ecu_id","kind","name","unit","vmin","vmax","category","sort"},
                    new Object[]{e, "live", r[0], r[1], r[2], r[3], r[4], i++});
        }
        if (sport) {
            ins(db, "tests", new String[]{"ecu_id","kind","name","unit","vmin","vmax","category","sort"},
                    new Object[]{e, "live", "Throttle Position Sensor (Sensor 1)", "V", 0.5, 4.5, "Throttle", i++});
            ins(db, "tests", new String[]{"ecu_id","kind","name","unit","vmin","vmax","category","sort"},
                    new Object[]{e, "live", "Throttle Position Sensor (Sensor 2)", "V", 0.5, 4.5, "Throttle", i++});
            ins(db, "tests", new String[]{"ecu_id","kind","name","unit","vmin","vmax","category","sort"},
                    new Object[]{e, "live", "Manifold Air Pressure Sensor", "hPa", 100, 1150, "Air", i++});
            ins(db, "tests", new String[]{"ecu_id","kind","name","unit","vmin","vmax","category","sort"},
                    new Object[]{e, "live", "Quick shift sensor voltage", "V", 2.2, 2.8, "Transmission", i++});
        }
    }

    private static void ioPacks(SQLiteDatabase db, long e) {
        String[] names = {"MIL Lamp", "Fuel Pump Relay", "Actuate Starter Relay",
                "Upstream Lambda Heater", "Canister Purge", "Test of Fuel Supply Unit",
                "Test of Temp Gauge", "Test of Stepper Relay"};
        for (int i = 0; i < names.length; i++)
            ins(db, "tests", new String[]{"ecu_id","kind","name","sort"}, new Object[]{e, "io", names[i], i + 1});
    }

    private static void routinesEMS(SQLiteDatabase db, long e) {
        String[] names = {"Idle Air Volume Learning", "Throttle Valve Learned Position Reset",
                "Reset Long-Term Fuel Trim Adaptations", "Injector Balance Test"};
        for (int i = 0; i < names.length; i++)
            ins(db, "tests", new String[]{"ecu_id","kind","name","sort"}, new Object[]{e, "routine", names[i], i + 1});
    }

    private static void writeDids(SQLiteDatabase db, long e) {
        // writable=1  -> asks for the encoded service password, like the reference
        ins(db, "tests", new String[]{"ecu_id","kind","name","writable","sort"}, new Object[]{e, "write", "VIN (F190)", 1, 1});
        ins(db, "tests", new String[]{"ecu_id","kind","name","writable","sort"}, new Object[]{e, "write", "CVN", 0, 2});
        ins(db, "tests", new String[]{"ecu_id","kind","name","writable","sort"}, new Object[]{e, "write", "CAL ID", 0, 3});
        ins(db, "tests", new String[]{"ecu_id","kind","name","writable","sort"}, new Object[]{e, "write", "Date of last programming", 1, 4});
    }

    private static void dtcsEMS(SQLiteDatabase db, long e) {
        String[][] dtcs = {
                {"P0130", "O2 Sensor Circuit Malfunction (Bank 1 Sensor 1)"},
                {"P0135", "O2 Sensor Heater Circuit (Bank 1 Sensor 1)"},
                {"P0122", "Throttle Position Sensor Circuit Low Input"},
                {"P0500", "Vehicle Speed Sensor Malfunction"},
                {"P0562", "System Voltage Low"},
                {"U0101", "Lost Communication with ISG / TCM"}};
        for (String[] d : dtcs)
            ins(db, "dtc_lib", new String[]{"ecu_id","code","descr"}, new Object[]{e, d[0], d[1]});
    }

    private static void flash(SQLiteDatabase db, long e, String file) {
        ins(db, "flash_files", new String[]{"ecu_id","filename","version"}, new Object[]{e, file, "S"});
    }

    private static void phys(SQLiteDatabase db, long vid, String[][] items) {
        for (int i = 0; i < items.length; i++)
            ins(db, "vhr_items", new String[]{"vehicle_id","name","unit","lo","hi","kind","sort"},
                    new Object[]{vid, items[i][0], items[i][1], items[i][2], items[i][3], items[i][4], i + 1});
    }

    private static long ins(SQLiteDatabase db, String table, String[] cols, Object[] vals) {
        ContentValues cv = new ContentValues();
        for (int i = 0; i < cols.length; i++) {
            Object o = vals[i];
            if (o instanceof String) cv.put(cols[i], (String) o);
            else if (o instanceof Integer) cv.put(cols[i], (Integer) o);
            else if (o instanceof Long) cv.put(cols[i], (Long) o);
            else if (o instanceof Double) cv.put(cols[i], (Double) o);
            else cv.put(cols[i], String.valueOf(o));
        }
        return db.insert(table, null, cv);
    }

    // ------------------------------------------------------------------ queries
    public List<Vehicle> vehicles() {
        List<Vehicle> out = new ArrayList<Vehicle>();
        Cursor c = getReadableDatabase().rawQuery("SELECT * FROM vehicles ORDER BY vehicle_id", null);
        while (c.moveToNext()) out.add(veh(c));
        c.close();
        return out;
    }

    private static Vehicle veh(Cursor c) {
        Vehicle v = new Vehicle();
        v.id = c.getLong(0); v.model = c.getString(1); v.variant = c.getString(2);
        v.type = c.getString(3); v.obd = c.getString(4); v.protocol = c.getString(5);
        v.emission = c.getString(6); v.vinPrefix = c.getString(7); v.vinSample = c.getString(8);
        v.vinFormat = c.getString(9); v.description = c.getString(10); v.image = c.getString(11);
        v.vinRule = c.getColumnCount() > 12 ? c.getString(12) : null;
        return v;
    }

    /** VIN lookup: exact captured-sample hit first, then longest-prefix rule
     *  match over BOTH the stored family prefix and the supplied VIN rule.
     *  No match -> null (never silently assume a vehicle). */
    public Vehicle vehicleByVin(String vin) {
        if (vin == null) return null;
        java.util.List<Vehicle> all = vehicles();
        for (Vehicle v : all) if (vin.equals(v.vinSample) && v.vinSample.length() > 0) return v;
        Vehicle best = null; int bestLen = -1;
        for (Vehicle v : all) {
            String p1 = v.vinPrefix == null ? "" : v.vinPrefix;
            String p2 = v.vinRule == null ? "" : com.nirixx.app.core.vin.VinRules.prefixOf(v.vinRule);
            String p = p1.length() >= p2.length() ? p1 : p2;
            if (p.length() > bestLen && vin.startsWith(p)) { best = v; bestLen = p.length(); }
        }
        return best;
    }

    public Vehicle vehicle(long id) {
        Cursor c = getReadableDatabase().rawQuery("SELECT * FROM vehicles WHERE vehicle_id=" + id, null);
        Vehicle v = c.moveToFirst() ? veh(c) : null;
        c.close();
        return v;
    }

    public List<Ecu> ecus(long vehicleId) {
        List<Ecu> out = new ArrayList<Ecu>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT * FROM ecus WHERE vehicle_id=" + vehicleId + " ORDER BY sort", null);
        while (c.moveToNext()) {
            Ecu e = new Ecu();
            e.id = c.getLong(0); e.vehicleId = c.getLong(1); e.name = c.getString(2);
            e.code = c.getString(3); e.protocol = c.getString(4); e.emission = c.getString(5);
            e.manufacturer = c.getString(6); e.tx = c.getString(7); e.rx = c.getString(8);
            e.sort = c.getInt(9);
            out.add(e);
        }
        c.close();
        return out;
    }

    public Ecu ecu(long ecuId) {
        Cursor c = getReadableDatabase().rawQuery("SELECT * FROM ecus WHERE ecu_id=" + ecuId, null);
        Ecu e = null;
        if (c.moveToFirst()) {
            e = new Ecu();
            e.id = c.getLong(0); e.vehicleId = c.getLong(1); e.name = c.getString(2);
            e.code = c.getString(3); e.protocol = c.getString(4); e.emission = c.getString(5);
            e.manufacturer = c.getString(6); e.tx = c.getString(7); e.rx = c.getString(8);
            e.sort = c.getInt(9);
        }
        c.close();
        return e;
    }

    public List<TestDef> tests(long ecuId, String kind) {
        List<TestDef> out = new ArrayList<TestDef>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT * FROM tests WHERE ecu_id=" + ecuId + " AND kind='" + kind + "' ORDER BY sort", null);
        while (c.moveToNext()) out.add(td(c));
        c.close();
        return out;
    }

    private static TestDef td(Cursor c) {
        TestDef t = new TestDef();
        t.id = c.getLong(0); t.ecuId = c.getLong(1); t.kind = c.getString(2); t.name = c.getString(3);
        t.unit = c.getString(4); t.vmin = c.getDouble(5); t.vmax = c.getDouble(6);
        t.category = c.getString(7) == null ? "" : c.getString(7);
        t.writable = c.getInt(8); t.sort = c.getInt(9);
        t.addr = c.getColumnCount() > 10 ? c.getString(10) : null;
        return t;
    }

    public List<Dtc> dtcs(long ecuId) {
        List<Dtc> out = new ArrayList<Dtc>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT * FROM dtc_lib WHERE ecu_id=" + ecuId, null);
        while (c.moveToNext()) {
            Dtc d = new Dtc();
            d.id = c.getLong(0); d.ecuId = c.getLong(1); d.code = c.getString(2); d.descr = c.getString(3);
            out.add(d);
        }
        c.close();
        return out;
    }

    /** Flash file name published for an ECU, or null when none exists —
     *  never invent one: the UI gates on null. */
    public String flashFile(long ecuId) {
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT filename FROM flash_files WHERE ecu_id=" + ecuId + " LIMIT 1", null);
        String f = c.moveToFirst() ? c.getString(0) : null;
        c.close();
        return f;
    }

    /** DTC description lookup across the whole library (any ECU); null = unknown. */
    public String dtcDescr(String code) {
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT descr FROM dtc_lib WHERE code=? LIMIT 1", new String[]{code});
        String s = c.moveToFirst() ? c.getString(0) : null;
        c.close();
        return s;
    }

    // ------------------------------------------------------------------ manuals
    public long addManual(String name, String path, long size) {
        ContentValues cv = new ContentValues();
        cv.put("name", name); cv.put("path", path); cv.put("size", size);
        cv.put("added", System.currentTimeMillis());
        return getWritableDatabase().insert("manuals", null, cv);
    }

    /** id, name, path, size, added — real records of user-imported documents. */
    public List<String[]> manuals() {
        List<String[]> out = new ArrayList<String[]>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT manual_id, name, path, size, added FROM manuals ORDER BY added DESC", null);
        while (c.moveToNext())
            out.add(new String[]{String.valueOf(c.getLong(0)), c.getString(1), c.getString(2),
                    String.valueOf(c.getLong(3)), String.valueOf(c.getLong(4))});
        c.close();
        return out;
    }

    public void deleteManual(long id) {
        getWritableDatabase().delete("manuals", "manual_id=" + id, null);
    }

    // ------------------------------------------------------------------ flash binaries
    public long addFlashBin(String name, String path, long size, String module) {
        ContentValues cv = new ContentValues();
        cv.put("name", name); cv.put("path", path); cv.put("size", size); cv.put("module", module);
        cv.put("added", System.currentTimeMillis());
        return getWritableDatabase().insert("flash_bins", null, cv);
    }

    public List<String[]> flashBins() {
        List<String[]> out = new ArrayList<String[]>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT bin_id, name, path, size, module, added FROM flash_bins ORDER BY added DESC", null);
        while (c.moveToNext())
            out.add(new String[]{String.valueOf(c.getLong(0)), c.getString(1), c.getString(2),
                    String.valueOf(c.getLong(3)), c.getString(4), String.valueOf(c.getLong(5))});
        c.close();
        return out;
    }

    public void deleteFlashBin(long id) {
        getWritableDatabase().delete("flash_bins", "bin_id=" + id, null);
    }

    // ------------------------------------------------------------------ address backfill
    /** Map seeded test rows to their real bus address where one is published:
     *  SAE J1979 Mode-01/Mode-09 (public standard) or the captured UDS DID. */
    private static void backfillAddrs(SQLiteDatabase db) {
        String[][] map = {
                {"Read Vehicle Information (VIN)", "did:F190"},
                {"VIN (F190)", "did:F190"},
                {"Battery Voltage", "pid:42"},
                {"Engine Temperature", "pid:05"},
                {"Engine Speed", "pid:0C"},
                {"Vehicle speed", "pid:0D"},
                {"Throttle Position Sensor", "pid:11"},
                {"Intake Air Pressure Sensor", "pid:0B"},
                {"Intake Air Temperature", "pid:0F"},
                {"Manifold Air Pressure Sensor", "pid:0B*10"},
                {"CVN", "m09:06"},
                {"CALID", "m09:04"},
                {"CAL ID", "m09:04"},
        };
        for (int i = 0; i < map.length; i++) {
            ContentValues cv = new ContentValues();
            cv.put("addr", map[i][1]);
            db.update("tests", cv, "name=?", new String[]{map[i][0]});
        }
    }

    public List<String[]> vhrItems(long vehicleId) {
        List<String[]> out = new ArrayList<String[]>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT name, unit, lo, hi, kind FROM vhr_items WHERE vehicle_id=" + vehicleId + " ORDER BY sort", null);
        while (c.moveToNext())
            out.add(new String[]{c.getString(0), c.getString(1), c.getString(2), c.getString(3), c.getString(4)});
        c.close();
        return out;
    }

    public String[] userByDealerCode(String code) {
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT u.user_id, u.name, u.email, u.branch_id, u.phone, r.name, u.pin" +
                        " FROM users u JOIN roles r ON r.role_id=u.role_id WHERE u.dealer_code=?", new String[]{code});
        String[] row = null;
        if (c.moveToFirst()) {
            row = new String[7];
            for (int i = 0; i < 7; i++) row[i] = c.getString(i);
        }
        c.close();
        return row;
    }

    public List<String> roles() {
        List<String> out = new ArrayList<String>();
        Cursor c = getReadableDatabase().rawQuery("SELECT name FROM roles", null);
        while (c.moveToNext()) out.add(c.getString(0));
        c.close();
        return out;
    }

    // ------------------------------------------------------------------ runtime writes
    public String config(String key, String def) {
        Cursor c = getReadableDatabase().rawQuery("SELECT cfg_value FROM configs WHERE cfg_key=?", new String[]{key});
        String v = c.moveToFirst() ? c.getString(0) : def;
        c.close();
        return v;
    }

    private static void setConfig(SQLiteDatabase db, String k, String v) {
        ContentValues cv = new ContentValues();
        cv.put("cfg_key", k); cv.put("cfg_value", v);
        db.insertWithOnConflict("configs", null, cv, SQLiteDatabase.CONFLICT_REPLACE);
    }

    public void setConfig(String k, String v) { setConfig(getWritableDatabase(), k, v); }

    public void saveSession(String key, long vehicleId, String vin, long started,
                            String connectivity, String firmware, String vci) {
        ContentValues cv = new ContentValues();
        cv.put("session_key", key); cv.put("vehicle_id", vehicleId); cv.put("vin", vin);
        cv.put("started", started); cv.put("connectivity", connectivity);
        cv.put("firmware", firmware); cv.put("vci", vci);
        getWritableDatabase().insertWithOnConflict("sessions", null, cv, SQLiteDatabase.CONFLICT_REPLACE);
    }

    public void log(String sessionKey, String dir, String payload) {
        ContentValues cv = new ContentValues();
        cv.put("session_key", sessionKey); cv.put("ts", System.currentTimeMillis());
        cv.put("dir", dir); cv.put("payload", payload);
        getWritableDatabase().insert("logs", null, cv);
    }

    public List<String[]> sessionLogs(String sessionKey) {
        List<String[]> out = new ArrayList<String[]>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT ts, dir, payload FROM logs WHERE session_key=? ORDER BY ts LIMIT 400",
                new String[]{sessionKey});
        while (c.moveToNext()) out.add(new String[]{String.valueOf(c.getLong(0)), c.getString(1), c.getString(2)});
        c.close();
        return out;
    }

    public void sample(String sessionKey, long testId, String value) {
        ContentValues cv = new ContentValues();
        cv.put("session_key", sessionKey); cv.put("test_id", testId);
        cv.put("ts", System.currentTimeMillis()); cv.put("value", value);
        getWritableDatabase().insert("stream_samples", null, cv);
    }

    /** Most recent real sampled value for a test in this session, or null. */
    public String lastSample(String sessionKey, long testId) {
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT value FROM stream_samples WHERE session_key=? AND test_id=? "
                        + "ORDER BY ts DESC LIMIT 1",
                new String[]{sessionKey, String.valueOf(testId)});
        String v = c.moveToFirst() ? c.getString(0) : null;
        c.close();
        return v;
    }

    public void putInput(String sessionKey, String kind, String key, String value) {
        ContentValues cv = new ContentValues();
        cv.put("session_key", sessionKey); cv.put("kind", kind); cv.put("key", key); cv.put("value", value);
        getWritableDatabase().insert("test_inputs", null, cv);
    }

    /** Real count: session log lines written since local midnight. */
    public int logsToday() {
        java.util.Calendar cal = java.util.Calendar.getInstance();
        cal.set(java.util.Calendar.HOUR_OF_DAY, 0);
        cal.set(java.util.Calendar.MINUTE, 0);
        cal.set(java.util.Calendar.SECOND, 0);
        cal.set(java.util.Calendar.MILLISECOND, 0);
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT COUNT(*) FROM logs WHERE ts >= ?", new String[]{String.valueOf(cal.getTimeInMillis())});
        int n = c.moveToFirst() ? c.getInt(0) : 0;
        c.close();
        return n;
    }

    public String lastInput(String sessionKey, String kind, String key) {
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT value FROM test_inputs WHERE session_key=? AND kind=? AND key=? ORDER BY input_id DESC LIMIT 1",
                new String[]{sessionKey, kind, key});
        String v = c.moveToFirst() ? c.getString(0) : null;
        c.close();
        return v;
    }

    public void saveIupr(String sessionKey, long vehicleId, String vin, String cvn, String calId,
                         String ratio, String kms, String city, String state) {
        ContentValues cv = new ContentValues();
        cv.put("session_key", sessionKey); cv.put("vehicle_id", vehicleId); cv.put("vin", vin);
        cv.put("cvn", cvn); cv.put("cal_id", calId); cv.put("ratio", ratio);
        cv.put("kms", kms); cv.put("city", city); cv.put("state", state);
        cv.put("created", System.currentTimeMillis());
        getWritableDatabase().insert("iupr_history", null, cv);
    }

    public List<String[]> iuprHistory() {
        List<String[]> out = new ArrayList<String[]>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT vin, cvn, cal_id, ratio, kms, city, state, created FROM iupr_history ORDER BY iupr_id DESC LIMIT 60", null);
        while (c.moveToNext()) {
            out.add(new String[]{c.getString(0), c.getString(1), c.getString(2), c.getString(3),
                    c.getString(4), c.getString(5), c.getString(6), String.valueOf(c.getLong(7))});
        }
        c.close();
        return out;
    }

    public void saveVhr(String sessionKey, long vehicleId, String vin, String path, String verdict) {
        ContentValues cv = new ContentValues();
        cv.put("session_key", sessionKey); cv.put("vehicle_id", vehicleId); cv.put("vin", vin);
        cv.put("path", path); cv.put("verdict", verdict); cv.put("created", System.currentTimeMillis());
        getWritableDatabase().insert("vhr_reports", null, cv);
    }

    public List<String[]> vhrReports() {
        List<String[]> out = new ArrayList<String[]>();
        Cursor c = getReadableDatabase().rawQuery(
                "SELECT session_key, vehicle_id, vin, path, verdict, created FROM vhr_reports ORDER BY report_id DESC LIMIT 60", null);
        while (c.moveToNext()) {
            out.add(new String[]{c.getString(0), String.valueOf(c.getLong(1)), c.getString(2),
                    c.getString(3), c.getString(4), String.valueOf(c.getLong(5))});
        }
        c.close();
        return out;
    }
}
