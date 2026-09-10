package com.nirixx.app;

import android.app.Application;
import android.content.Context;
import android.content.SharedPreferences;
import java.io.PrintWriter;
import java.io.StringWriter;

/** Application shell: captures any uncaught crash so the next launch can show
 *  exactly what failed and where — the first thing a device-only bug needs.
 *
 *  Order is the whole point here:
 *   1. the crash handler is installed BEFORE anything else can throw;
 *   2. no policy-sensitive system call happens in this method at all.
 *
 *  An earlier revision called startService(AppCloseService) as the very first
 *  statement.  On Android 12+ OEM edge paths (installer "Open" button, recents
 *  re-launch on MIUI/ColorOS/Funtouch, battery-restricted launches)
 *  Context.startService() can throw IllegalStateException — the process then
 *  dies before the first frame and before the handler existed, which presents
 *  exactly as "white screen, app closes itself, no dialog ever".  The service
 *  is now started when a VCI actually connects — the only moment its
 *  task-removal cleanup matters. */
public class NirixXApp extends Application {

    public static final String PREFS = "nirixx_crash";
    public static final String LAUNCH = "nirixx_launch";

    @Override
    public void onCreate() {
        super.onCreate();
        installCrashHandler();          // must be first — nothing may precede it
        watchdog();
    }

    private void installCrashHandler() {
        try {
            final Thread.UncaughtExceptionHandler upstream = Thread.getDefaultUncaughtExceptionHandler();
            Thread.setDefaultUncaughtExceptionHandler(new Thread.UncaughtExceptionHandler() {
                public void uncaughtException(Thread thread, Throwable error) {
                    try {
                        StringWriter sw = new StringWriter();
                        error.printStackTrace(new PrintWriter(sw));
                        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                                .putString("trace", "thread: " + thread.getName() + "\n" + sw.toString())
                                .putLong("at", System.currentTimeMillis())
                                .commit();
                    } catch (Exception ignored) { }
                    if (upstream != null) {
                        upstream.uncaughtException(thread, error);
                    } else {
                        android.os.Process.killProcess(android.os.Process.myPid());
                        System.exit(10);
                    }
                }
            });
        } catch (Exception ignored) { }
    }

    /** Launch watchdog.  Records how far launch got: "app_created" (here),
     *  "ui_shown" (splash has pixels), "alive" (routed past the splash).
     *  If the previous run reached only "app_created" and left no Java trace,
     *  the process was ended by the OS itself (native abort / Play Protect /
     *  OEM battery-security kill) — never by app code.  SplashActivity turns
     *  that fact into concrete unblock instructions for the user. */
    private void watchdog() {
        try {
            SharedPreferences lp = getSharedPreferences(LAUNCH, MODE_PRIVATE);
            String stage = lp.getString("stage", null);
            boolean noTrace = getSharedPreferences(PREFS, MODE_PRIVATE).getString("trace", null) == null;
            if ("app_created".equals(stage) && noTrace) {
                lp.edit().putBoolean("killed_before_ui", true).commit();
            }
            lp.edit().putString("stage", "app_created")
                    .putLong("at", System.currentTimeMillis())
                    .commit();
        } catch (Exception ignored) { }
    }

    /** The launcher screen has real content on screen. */
    public static void stageUiShown(Context c) {
        try {
            c.getSharedPreferences(LAUNCH, MODE_PRIVATE).edit().putString("stage", "ui_shown").commit();
        } catch (Exception ignored) { }
    }

    /** The app routed past the splash — a fully healthy launch. */
    public static void stageAlive(Context c) {
        try {
            c.getSharedPreferences(LAUNCH, MODE_PRIVATE).edit().putString("stage", "alive").commit();
        } catch (Exception ignored) { }
    }
}
