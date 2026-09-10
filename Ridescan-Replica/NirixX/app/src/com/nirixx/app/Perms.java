package com.nirixx.app;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Build;
import java.util.ArrayList;
import java.util.List;

/** Runtime-permission helper for modern Android (12+ Bluetooth, 13+ notifications).
 *  Each ensure* asks only on the API levels where the permission is actually
 *  enforced at runtime, and returns whether everything is already granted. */
public final class Perms {

    public static final int REQ_BT = 4101;
    public static final int REQ_NOTIF = 4102;
    public static final int REQ_BLE_LEGACY = 4103;

    private Perms() { }

    private static boolean granted(Activity a, String permission) {
        return Build.VERSION.SDK_INT < 23
                || a.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
    }

    private static void request(Activity a, List<String> want, int code) {
        a.requestPermissions(want.toArray(new String[want.size()]), code);
    }

    /** Bluetooth: API 31+ needs BLUETOOTH_SCAN + BLUETOOTH_CONNECT at runtime;
     *  API 29-30 needs ACCESS_FINE_LOCATION for discovery results. */
    public static boolean ensureBluetooth(Activity a) {
        List<String> need = new ArrayList<String>();
        if (Build.VERSION.SDK_INT >= 31) {
            if (!granted(a, Manifest.permission.BLUETOOTH_SCAN)) need.add(Manifest.permission.BLUETOOTH_SCAN);
            if (!granted(a, Manifest.permission.BLUETOOTH_CONNECT)) need.add(Manifest.permission.BLUETOOTH_CONNECT);
            if (need.isEmpty()) return true;
            request(a, need, REQ_BT);
            return false;
        }
        if (Build.VERSION.SDK_INT >= 23 && !granted(a, Manifest.permission.ACCESS_FINE_LOCATION)) {
            need.add(Manifest.permission.ACCESS_FINE_LOCATION);
            request(a, need, REQ_BLE_LEGACY);
            return false;
        }
        return true;
    }

    /** Notifications: API 33+ needs POST_NOTIFICATIONS at runtime. */
    public static boolean ensureNotifications(Activity a) {
        if (Build.VERSION.SDK_INT >= 33 && !granted(a, Manifest.permission.POST_NOTIFICATIONS)) {
            List<String> need = new ArrayList<String>();
            need.add(Manifest.permission.POST_NOTIFICATIONS);
            request(a, need, REQ_NOTIF);
            return false;
        }
        return true;
    }

    /** True when everything needed for live Bluetooth discovery is granted. */
    public static boolean bluetoothGranted(Activity a) {
        if (Build.VERSION.SDK_INT >= 31) {
            return granted(a, Manifest.permission.BLUETOOTH_SCAN)
                    && granted(a, Manifest.permission.BLUETOOTH_CONNECT);
        }
        if (Build.VERSION.SDK_INT >= 23) {
            return granted(a, Manifest.permission.ACCESS_FINE_LOCATION);
        }
        return true;
    }

    /** Whether the system says we should explain before asking again. */
    public static boolean shouldShowBtRationale(Activity a) {
        if (Build.VERSION.SDK_INT >= 31) {
            return a.shouldShowRequestPermissionRationale(Manifest.permission.BLUETOOTH_SCAN)
                    || a.shouldShowRequestPermissionRationale(Manifest.permission.BLUETOOTH_CONNECT);
        }
        if (Build.VERSION.SDK_INT >= 23) {
            return a.shouldShowRequestPermissionRationale(Manifest.permission.ACCESS_FINE_LOCATION);
        }
        return false;
    }

    /** Effective notification state (channel-independent app-level switch). */
    public static boolean notificationsEnabled(Activity a) {
        if (Build.VERSION.SDK_INT >= 24) {
            android.app.NotificationManager nm =
                    (android.app.NotificationManager) a.getSystemService(Activity.NOTIFICATION_SERVICE);
            return nm != null && nm.areNotificationsEnabled();
        }
        return true;
    }

    public static boolean overlayGranted(Activity a) {
        return Build.VERSION.SDK_INT < 23 || android.provider.Settings.canDrawOverlays(a);
    }

    public static boolean packageInstallAllowed(Activity a) {
        return Build.VERSION.SDK_INT < 26 || a.getPackageManager().canRequestPackageInstalls();
    }
}
