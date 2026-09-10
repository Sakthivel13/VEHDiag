package com.nirixx.app.sim;

import android.content.Context;
import android.os.Build;
import com.nirixx.app.Session;
import com.nirixx.app.db.Db;
import java.io.File;
import java.io.FileOutputStream;
import java.io.PrintWriter;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Persists the session's UDS traffic into a .txt log file whose byte layout
 *  matches the reference app's logs (File Header block + '<ts> I/: [dir]: -->'
 *  lines), and mirrors every row into the SQLite `logs` table. */
public final class UdsLog {

    private static PrintWriter writer;
    private static String path;

    private UdsLog() {}

    public static synchronized String path(Context c) {
        if (path == null) open(c);
        return path;
    }

    private static void open(Context c) {
        try {
            String sess = Session.ensureSession(c);
            File dir = new File(c.getExternalFilesDir(null), "Logs");
            dir.mkdirs();
            File f = new File(dir, sess + Session.selectedVin + ".txt");
            path = f.getAbsolutePath();
            writer = new PrintWriter(new FileOutputStream(f, true));
            log(c, "INFO", ">>>>>>>>>>>>>>>>>> File Header >>>>>>>>>>>>>>>>" );
            line(c, "INFO", "Device             : " + Build.MANUFACTURER.toLowerCase(Locale.US) + " (" + Build.MODEL + ")");
            line(c, "INFO", "Android            : " + Build.VERSION.RELEASE);
            line(c, "INFO", "Android SDK        : " + Build.VERSION.SDK_INT);
            line(c, "INFO", "App Name           : NirixX");
            line(c, "INFO", "App Version        : 1.6.3 (14)");
            line(c, "INFO", "Domain             : DMS");
            line(c, "INFO", "Dealer Name        : " + Session.dealerName);
            line(c, "INFO", "Dealer Code        : " + Session.dealerCode);
            line(c, "INFO", "Session ID         : " + sess);
            line(c, "INFO", "Firmware Version   : " + Session.vciFw);
            line(c, "INFO", "<<<<<<<<<<<<<<<<<< File Header <<<<<<<<<<<<<<<<");
            line(c, "INFO", "[CONNECTIVITY_TYPE]: --> " + Session.connectivity.toLowerCase(Locale.US));
            writer.flush();
        } catch (Exception ignored) { writer = null; }
    }

    public static synchronized void log(Context c, String dir, String payload) {
        if (writer == null) open(c);
        line(c, dir, payload);
    }

    private static void line(Context c, String dir, String payload) {
        String ts = SimEcu.stamp();
        if (writer != null) {
            if ("TX".equals(dir) || "RX".equals(dir)) {
                writer.println(ts + " I/: " + dir + ": --> " + payload);
            } else {
                writer.println(ts + " I/: " + payload);
            }
            writer.flush();
        }
        try { Db.get(c).log(Session.sessionKey, dir, payload); } catch (Exception ignored) { }
    }
}
