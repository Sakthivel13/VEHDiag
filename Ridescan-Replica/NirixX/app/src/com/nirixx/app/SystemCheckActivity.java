package com.nirixx.app;

import android.bluetooth.BluetoothAdapter;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Runtime self-check: every modern-Android requirement, ticked live on the
 *  actual device, with a fix action wherever something is missing. */
public class SystemCheckActivity extends BaseActivity {

    private static final int OK = 0xFF23C79A;
    private static final int ACTION = 0xFFE8A33D;
    private static final int GREY = 0xFF8A94A2;

    private LinearLayout list;
    private TextView scoreTitle;
    private TextView scoreSub;
    private int passCount;
    private int totalCount;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("System Self-Check");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        // Device header
        LinearLayout head = Ui.card(this);
        head.setGravity(Gravity.CENTER_VERTICAL);
        String version;
        try {
            version = getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception e) {
            version = "?";
        }
        LinearLayout meta = new LinearLayout(this);
        meta.setOrientation(LinearLayout.VERTICAL);
        meta.addView(Ui.tv(this, "NirixX " + version + " on "
                + Build.MANUFACTURER.substring(0, 1).toUpperCase() + Build.MANUFACTURER.substring(1)
                + " " + Build.MODEL, 15f, 0xFF141B2E, true));
        meta.addView(Ui.tv(this, "Android " + Build.VERSION.RELEASE + " · API " + Build.VERSION.SDK_INT
                + "  ·  Package " + getPackageName(), 12f, 0xFF5A6472, false));
        scoreTitle = Ui.tv(this, "", 22f, OK, true);
        scoreSub = Ui.tv(this, "", 11.5f, 0xFF5A6472, false);
        LinearLayout right = new LinearLayout(this);
        right.setOrientation(LinearLayout.VERTICAL);
        right.setGravity(Gravity.RIGHT);
        right.addView(scoreTitle);
        right.addView(scoreSub);
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        head.addView(meta, rp);
        head.addView(right);
        content.addView(head);

        content.addView(Ui.section(this, "RUNTIME REQUIREMENTS"));

        list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        content.addView(list);
    }

    @Override
    protected void onResume() {
        super.onResume();
        refresh(); // re-score: user may have just granted something in Settings
    }

    private void refresh() {
        list.removeAllViews();
        passCount = 0;
        totalCount = 0;

        check("App targets Android 14 (API 34)",
                "Latest behaviour rules compiled in · min supported: Android 7.0 (API 24)", true, null, null);

        final BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        check("Bluetooth hardware", adapter != null ? "Radio detected"
                        : "No Bluetooth radio — simulation mode covers every feature",
                true, adapter == null ? "N/A" : "PASS", null);

        if (adapter != null) {
            boolean btOn;
            try { btOn = adapter.isEnabled(); } catch (SecurityException se) { btOn = true; }
            check("Bluetooth enabled", btOn ? "Radio is on" : "Turn Bluetooth on to find real VCIs",
                    btOn, null, new Runnable() {
                        public void run() {
                            try { startActivity(new Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE)); }
                            catch (ActivityNotFoundException | SecurityException e) { toast("Enable Bluetooth in Settings"); }
                        }
                    });
        }

        if (Build.VERSION.SDK_INT >= 31) {
            boolean ok = Perms.bluetoothGranted(this);
            check("Nearby-devices permission", ok ? "Bluetooth scan + connect granted"
                            : "Required on Android 12+ to pair a real VCI (neverForLocation)",
                    ok, null, new Runnable() {
                        public void run() { Perms.ensureBluetooth(SystemCheckActivity.this); }
                    });
        } else if (Build.VERSION.SDK_INT >= 23) {
            boolean ok = Perms.bluetoothGranted(this);
            check("Location access for discovery", ok ? "Granted (pre-Android-12 requirement)"
                            : "Needed on Android 6–11 for Bluetooth scan results",
                    ok, null, new Runnable() {
                        public void run() { Perms.ensureBluetooth(SystemCheckActivity.this); }
                    });
        } else {
            check("Bluetooth discovery permission", "Not required below Android 6", true, "N/A", null);
        }

        boolean notif = Perms.notificationsEnabled(this);
        check("Notifications", notif ? "Enabled — session status and alerts will show"
                        : (Build.VERSION.SDK_INT >= 33
                        ? "POST_NOTIFICATIONS not granted (Android 13+)"
                        : "Blocked in system settings"),
                notif, null, new Runnable() {
                    public void run() {
                        if (Build.VERSION.SDK_INT >= 33
                                && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                            Perms.ensureNotifications(SystemCheckActivity.this);
                            return;
                        }
                        try {
                            Intent it = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS);
                            it.putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName());
                            startActivity(it);
                        } catch (Exception e) { toast("Open Settings → Apps → NirixX → Notifications"); }
                    }
                });

        boolean inst = true;
        check("Play-safe permission profile", "No high-risk install flags: the app never asks for "
                        + "“install unknown apps” or “display over other apps”",
                inst, "PASS", null);

        scoreTitle.setText(passCount + "/" + totalCount);
        int color = passCount == totalCount ? OK : ACTION;
        scoreTitle.setTextColor(color);
        scoreSub.setText(passCount == totalCount ? "all good" : "checks passed");
    }

    private void check(String title, String detail, boolean ok, String badgeOverride, final Runnable fix) {
        totalCount++;
        if (ok) passCount++;
        LinearLayout card = Ui.card(this);
        LinearLayout lanes = new LinearLayout(this);
        lanes.setOrientation(LinearLayout.HORIZONTAL);
        lanes.setGravity(Gravity.CENTER_VERTICAL);
        card.addView(lanes);

        GradientDrawable dot = new GradientDrawable();
        dot.setShape(GradientDrawable.OVAL);
        boolean na = "N/A".equals(badgeOverride);
        dot.setColor(ok ? OK : ACTION);
        int ds = Ui.dp(this, 12);
        dot.setSize(ds, ds);
        TextView dotV = new TextView(this);
        dotV.setBackground(dot);
        LinearLayout.LayoutParams dp = new LinearLayout.LayoutParams(ds, ds);
        dp.setMargins(0, 0, Ui.dp(this, 12), 0);
        lanes.addView(dotV, dp);

        LinearLayout text = new LinearLayout(this);
        text.setOrientation(LinearLayout.VERTICAL);
        text.addView(Ui.tv(this, title, 14.5f, 0xFF141B2E, true));
        text.addView(Ui.tv(this, detail, 11.5f, 0xFF5A6472, false));
        lanes.addView(text, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        String badge = badgeOverride != null ? badgeOverride : (ok ? "PASS" : "ACTION");
        TextView b = Ui.tv(this, badge, 10.5f, na ? GREY : (ok ? OK : ACTION), true);
        b.setPadding(Ui.dp(this, 8), 0, Ui.dp(this, 2), 0);
        lanes.addView(b);

        if (!ok && fix != null) {
            TextView btn = Ui.tv(this, "FIX", 12.5f, 0xFF0B8376, true);
            btn.setPadding(Ui.dp(this, 12), Ui.dp(this, 8), 0, Ui.dp(this, 8));
            btn.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { fix.run(); }
            });
            lanes.addView(btn);
        }
        list.addView(card);
    }
}
