package com.nirixx.app;

import android.app.Dialog;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.db.Db;
import com.nirixx.app.sim.UdsLog;
import com.nirixx.app.vci.VciManager;
import com.nirixx.app.vci.VciTransport;

/** Add / Pair VCI — the reference connectivity experience. Three transport
 *  tiles (BT / WIFI / USB); each shows its own panel. BT runs the real
 *  Bluetooth discovery (merged with the simulation pool), WIFI lists VCI
 *  access points, USB detects wired adapters. */
public class AddDeviceActivity extends BaseActivity implements VciManager.ScanCallback {

    private LinearLayout panel, content;
    private TextView status;
    private Dialog scanDialog;
    private View tileBT, tileWIFI, tileUSB;
    private String mode = "BLUETOOTH";
    private final Handler h = new Handler();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Add / Pair VCI");
        content = (LinearLayout) findViewById(R.id.content);

        content.addView(Ui.section(this, "SELECT CONNECTIVITY TYPE"));
        LinearLayout tiles = new LinearLayout(this);
        tiles.setOrientation(LinearLayout.HORIZONTAL);
        tileBT = connTile(tiles, R.drawable.bluetooth, "BT");
        tileWIFI = connTile(tiles, R.drawable.ic_wifi, "WIFI");
        tileUSB = connTile(tiles, R.drawable.ic_usb, "USB");
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-1, -2);
        tp.setMargins(0, 0, 0, Ui.dp(this, 12));
        content.addView(tiles, tp);

        panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        content.addView(panel);

        mode = Db.get(this).config("connectivity", "BLUETOOTH");
        showMode();
    }

    private View connTile(LinearLayout parent, int iconRes, final String name) {
        LinearLayout tile = new LinearLayout(this);
        tile.setOrientation(LinearLayout.VERTICAL);
        tile.setGravity(android.view.Gravity.CENTER);
        android.widget.ImageView iv = new android.widget.ImageView(this);
        iv.setImageResource(iconRes);
        tile.addView(iv, new LinearLayout.LayoutParams(Ui.dp(this, 24), Ui.dp(this, 24)));
        tile.addView(Ui.tv(this, name, 12.5f, 0xFF3A4663, true));
        tile.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                mode = name;
                Db.get(AddDeviceActivity.this).setConfig("connectivity", name);
                Session.connectivity = name;
                showMode();
            }
        });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, Ui.dp(this, 74), 1f);
        lp.setMargins(0, 0, Ui.dp(this, 8), 0);
        parent.addView(tile, lp);
        return tile;
    }

    private void showMode() {
        tileBT.setBackgroundResource("BLUETOOTH".equals(mode) ? R.drawable.bg_tile_sel : R.drawable.bg_tile_def);
        tileWIFI.setBackgroundResource("WIFI".equals(mode) ? R.drawable.bg_tile_sel : R.drawable.bg_tile_def);
        tileUSB.setBackgroundResource("USB".equals(mode) ? R.drawable.bg_tile_sel : R.drawable.bg_tile_def);
        Session.connectivity = mode;
        if ("WIFI".equals(mode)) showWifi();
        else if ("USB".equals(mode)) showUsb();
        else startPairingFlow();
    }

    // ------------------------------------------------------------------ BT
    private void startPairingFlow() {
        panel.removeAllViews();
        content.addView(Ui.section(this, "SCANNING FOR VCI DEVICES…"));
        if (Perms.bluetoothGranted(this)) { scan(); return; }
        scan();
        Ui.dialog(this, "Allow nearby-device access",
                "NirixX finds and pairs with your VCI over Bluetooth.\n\n"
                        + "On Android 12 and above this needs the Nearby devices permission. "
                        + "It is used only to discover diagnostic hardware.\n\n"
                        + "You can also skip: the full app works with the built-in simulation.",
                "Allow & Scan", new Runnable() {
                    public void run() { Perms.ensureBluetooth(AddDeviceActivity.this); }
                },
                "Continue in demo mode", null).show();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != Perms.REQ_BT && requestCode != Perms.REQ_BLE_LEGACY) return;
        boolean allOk = grantResults.length > 0;
        for (int i = 0; i < grantResults.length; i++)
            if (grantResults[i] != PackageManager.PERMISSION_GRANTED) { allOk = false; break; }
        toast(allOk ? "Bluetooth access granted — rescanning live devices"
                : "Using simulation (Bluetooth access not granted)");
        panel.removeAllViews();
        scan();
    }

    private void scan() {
        panel.removeAllViews();
        status = Ui.tv(this, "Looking for NirixX hardware and compatible adapters…", 12.5f, 0xFF5A6472, false);
        panel.addView(status);
        scanDialog = Ui.progressDialog(this, "Scanning nearby devices…");
        scanDialog.show();
        VciManager.get().scan(this, this);
    }

    public void onFound(final String label, final String detail, final String linkType,
                        final String drawable, final boolean live) {
        int iconRes = getResources().getIdentifier(drawable, "drawable", getPackageName());
        LinearLayout row = Ui.listRow(this, iconRes > 0 ? iconRes : R.drawable.vci,
                label, detail + "  ·  " + linkType + (live ? "  ·  LIVE" : "  ·  SIM"), true);
        row.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { connect(label, "BLUETOOTH"); }
        });
        panel.addView(row);
    }

    public void onFinished(boolean bluetoothActive) {
        if (scanDialog != null) scanDialog.dismiss();
        if (status != null) status.setText(bluetoothActive
                ? "Tap a device to pair. LIVE rows came from this phone's Bluetooth radio."
                : "Bluetooth is off or not granted — showing the simulation pool. Pairing still works (simulated).");
    }

    // ------------------------------------------------------------------ WIFI
    private void showWifi() {
        VciManager.get().stopScan(this);
        panel.removeAllViews();
        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.addView(Ui.section(this, "WIFI VCI NETWORKS (live scan)"), new LinearLayout.LayoutParams(0, -2, 1f));
        TextView refresh = Ui.tv(this, "Refresh", 12.5f, 0xFF3A4663, true);
        refresh.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { showWifi(); }
        });
        head.addView(refresh);
        panel.addView(head);

        // Real scan results from the Wi-Fi radio (may be empty off-device).
        java.util.List<android.net.wifi.ScanResult> results = new java.util.ArrayList<android.net.wifi.ScanResult>();
        try {
            android.net.wifi.WifiManager wm =
                    (android.net.wifi.WifiManager) getApplicationContext().getSystemService(WIFI_SERVICE);
            if (wm != null) {
                wm.startScan();
                java.util.List<android.net.wifi.ScanResult> got = wm.getScanResults();
                if (got != null) results = got;
            }
        } catch (SecurityException se) { results = new java.util.ArrayList<android.net.wifi.ScanResult>(); }

        final LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        panel.addView(list);
        boolean any = false;
        for (int i = 0; i < results.size(); i++) {
            android.net.wifi.ScanResult r = results.get(i);
            String ssid = r.SSID == null ? "" : r.SSID;
            if (!ssid.toUpperCase(java.util.Locale.US).contains("NIRIXILINK")) continue;
            any = true;
            final String name = ssid;
            LinearLayout row = Ui.listRow(this, R.drawable.ic_wifi,
                    name, "VCI hotspot  \u00b7  " + r.level + " dBm", false);
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { connect(name, "WIFI"); }
            });
            list.addView(row);
        }
        if (!any) {
            panel.addView(Ui.tv(this,
                    "No NirixiLINK_* hotspot in range (join the dongle's Wi-Fi first from system settings).",
                    12f, 0xFF5A6472, false));
        }

        // Manual endpoint — the values the adapter actually serves (editable).
        panel.addView(Ui.section(this, "ENDPOINT (adapter TCP socket)"));
        LinearLayout form = Ui.card(this);
        final android.widget.EditText ip = new android.widget.EditText(this);
        ip.setSingleLine(true);
        ip.setTextSize(13.5f);
        ip.setText(com.nirixx.app.core.diag.TransportSettings.wifiIp(this));
        ip.setBackgroundResource(R.drawable.bg_box_outline);
        ip.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 12), 0);
        form.addView(ip, new LinearLayout.LayoutParams(-1, Ui.dp(this, 44)));
        final android.widget.EditText port = new android.widget.EditText(this);
        port.setSingleLine(true);
        port.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
        port.setTextSize(13.5f);
        port.setText(String.valueOf(com.nirixx.app.core.diag.TransportSettings.wifiPort(this)));
        port.setBackgroundResource(R.drawable.bg_box_outline);
        port.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 12), 0);
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 44));
        pp.setMargins(0, Ui.dp(this, 8), 0, 0);
        form.addView(port, pp);
        panel.addView(form);

        TextView go = Ui.navyBtn(this, "CONNECT OVER WI-FI");
        LinearLayout.LayoutParams gp = new LinearLayout.LayoutParams(-1, -2);
        gp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
        panel.addView(go, gp);
        go.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                com.nirixx.app.core.diag.TransportSettings.saveWifi(AddDeviceActivity.this,
                        ip.getText().toString().trim(), port.getText().toString().trim());
                connect(ip.getText().toString().trim() + ":" + port.getText().toString().trim(), "WIFI");
            }
        });
    }

    // ------------------------------------------------------------------ USB
    private void showUsb() {
        VciManager.get().stopScan(this);
        panel.removeAllViews();
        panel.addView(Ui.section(this, "WIRED VCI (USB OTG) — live enumeration"));

        android.hardware.usb.UsbManager um =
                (android.hardware.usb.UsbManager) getSystemService(USB_SERVICE);
        java.util.HashMap<String, android.hardware.usb.UsbDevice> devs =
                um == null ? new java.util.HashMap<String, android.hardware.usb.UsbDevice>() : um.getDeviceList();
        if (devs == null || devs.isEmpty()) {
            LinearLayout empty = Ui.card(this);
            empty.addView(Ui.tv(this, "No USB device on the host port", 14f, 0xFF1A2138, true));
            empty.addView(Ui.tv(this,
                    "Attach the NirixiLINK with an OTG cable; it will appear here instantly.",
                    12.5f, 0xFF5A6472, false));
            panel.addView(empty);
        } else {
            java.util.Iterator<android.hardware.usb.UsbDevice> it = devs.values().iterator();
            while (it.hasNext()) {
                final android.hardware.usb.UsbDevice d = it.next();
                String label = d.getDeviceName();
                String sub = "VID " + String.format("%04X", d.getVendorId())
                        + "  \u00b7  PID " + String.format("%04X", d.getProductId());
                LinearLayout row = Ui.listRow(this, R.drawable.ic_usb, label, sub, true);
                row.setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) { usbClick(d); }
                });
                panel.addView(row);
            }
        }
        panel.addView(Ui.tv(this,
                "USB mode is used when the tablet is docked on the bench cable (CDC-ACM adapters).",
                12f, 0xFF5A6472, false));
    }

    /** USB permission flow, then the real engine bring-up. */
    private void usbClick(final android.hardware.usb.UsbDevice d) {
        final android.hardware.usb.UsbManager um =
                (android.hardware.usb.UsbManager) getSystemService(USB_SERVICE);
        if (um.hasPermission(d)) {
            connect(d.getDeviceName(), "USB");
            return;
        }
        android.content.BroadcastReceiver perm = new android.content.BroadcastReceiver() {
            public void onReceive(android.content.Context ctx, android.content.Intent i) {
                try { unregisterReceiver(this); } catch (Exception ignored) { }
                if (i.getBooleanExtra(android.hardware.usb.UsbManager.EXTRA_PERMISSION_GRANTED, false)) {
                    connect(d.getDeviceName(), "USB");
                } else {
                    toast("USB permission denied for " + d.getDeviceName());
                }
            }
        };
        android.content.IntentFilter f = new android.content.IntentFilter(ACTION_USB_PERM);
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            registerReceiver(perm, f, android.content.Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(perm, f);
        }
        android.app.PendingIntent pi = android.app.PendingIntent.getBroadcast(this, 0,
                new android.content.Intent(ACTION_USB_PERM).setPackage(getPackageName()),
                android.os.Build.VERSION.SDK_INT >= 23
                        ? android.app.PendingIntent.FLAG_IMMUTABLE : 0);
        um.requestPermission(d, pi);
    }

    // ------------------------------------------------------------------ shared
    private static final String ACTION_USB_PERM = "com.nirixx.app.USB_PERMISSION";

    /** REAL bring-up through the diagnostic engine:
     *  ByteLink → ELM327 dialect → ISO-TP → UDS session → VIN → vehicle match.
     *  If the SIM badge taught us anything, it's that a faked "connected" state
     *  is worse than an honest error — failures surface with their stage. */
    private void connect(final String name, final String linkType) {
        final Dialog d = Ui.progressDialog(this, "Connecting — " + name + " (" + linkType + ")");
        d.show();
        final com.nirixx.app.core.diag.DiagEngine.Progress cb =
                new com.nirixx.app.core.diag.DiagEngine.Progress() {
                    public void onStep(String step) { UdsLog.log(AddDeviceActivity.this, "INFO", "[LINK]: --> " + step); }
                    public void onFrame(String dir, String frame) { UdsLog.log(AddDeviceActivity.this, dir, frame); }
                };
        new Thread(new Runnable() { public void run() {
            com.nirixx.app.core.vci.ByteLink link = null;
            String buildError = null;
            try {
                if ("WIFI".equals(linkType)) {
                    link = new com.nirixx.app.core.vci.WifiLink(
                            com.nirixx.app.core.diag.TransportSettings.wifiIp(AddDeviceActivity.this),
                            com.nirixx.app.core.diag.TransportSettings.wifiPort(AddDeviceActivity.this));
                } else if ("USB".equals(linkType)) {
                    android.hardware.usb.UsbDevice dev =
                            com.nirixx.app.core.vci.UsbLink.firstCandidate(AddDeviceActivity.this);
                    if (dev != null) link = new com.nirixx.app.core.vci.UsbLink(AddDeviceActivity.this, dev);
                    else buildError = "No USB device present";
                } else {
                    android.bluetooth.BluetoothDevice dev = VciManager.get().lastLive.get(name);
                    if (dev == null) {
                        // fall back to a bonded device with the same name
                        try {
                            java.util.Set<android.bluetooth.BluetoothDevice> bonded =
                                    android.bluetooth.BluetoothAdapter.getDefaultAdapter().getBondedDevices();
                            for (android.bluetooth.BluetoothDevice b : bonded)
                                if (name.equals(b.getName())) { dev = b; break; }
                        } catch (SecurityException ignored) { }
                    }
                    if (dev != null) link = new com.nirixx.app.core.vci.BtLink(dev);
                    else buildError = "Pick a LIVE (discovered/paired) Bluetooth device — "
                            + "SIM training entries cannot open a real link";
                }
            } catch (Exception e) {
                buildError = e.getMessage();
            }

            final com.nirixx.app.core.diag.DiagEngine.Result r;
            if (link == null) {
                r = new com.nirixx.app.core.diag.DiagEngine.Result();
                r.ok = false; r.stage = "Transport";
                r.error = buildError == null ? "No physical transport available" : buildError;
            } else {
                r = com.nirixx.app.core.diag.DiagEngine.connectAndIdentify(
                        AddDeviceActivity.this, link, tx(), rx(), cb);
            }

            runOnUiThread(new Runnable() { public void run() {
                d.dismiss();
                if (r.ok) {
                    Session.vciConnected = true;
                    Session.connectivity = linkType;
                    // Task-removal cleanup hook, started only now that a real link
                    // exists (and from a user-visible screen, so Android 12+ OEM
                    // background-start edge paths can never reject it at process
                    // birth — that used to kill the app before the first frame).
                    try {
                        startService(new android.content.Intent(AddDeviceActivity.this,
                                AppCloseService.class));
                    } catch (Exception ignored) { }
                    com.nirixx.app.core.diag.TransportSettings.onConnected(
                            AddDeviceActivity.this, linkType, name);
                    com.nirixx.app.core.diag.DiagOps.startKeepAlive(
                            AddDeviceActivity.this);   // 3E 00 cadence, reference-style
                    if (r.vehicle != null) {
                        Ui.resultDialog(AddDeviceActivity.this, R.drawable.ic_flash_success,
                                "Vehicle identified",
                                "VIN  " + r.vin + "\n→  " + r.vehicle.model + "\n" + r.describeTransport,
                                "Open Diagnostic Section", new Runnable() {
                                    public void run() {
                                        go(VinDiagnosisActivity.class);
                                        finish();
                                    }
                                }).show();
                    } else {
                        Ui.resultDialog(AddDeviceActivity.this, R.drawable.ic_flash_success,
                                "VCI connected — VIN read, not matched",
                                "VIN  " + r.vin + "\nNo model in the NirixX database matches this VIN. "
                                        + "Select the vehicle manually.",
                                "Open Vehicle List", new Runnable() {
                                    public void run() {
                                        go(VehicleListActivity.class);
                                        finish();
                                    }
                                }).show();
                    }
                } else {
                    String hint = r.nrc != null && r.nrc.userHint != null && r.nrc.userHint.length() > 0
                            ? "\n\n" + r.nrc.userHint : "";
                    Ui.resultDialog(AddDeviceActivity.this, R.drawable.ic_warn,
                            "Connection failed — " + (r.stage == null ? "link" : r.stage),
                            (r.error == null ? "Unknown failure" : r.error) + hint,
                            "OK", null).show();
                }
            }});
        }}, "vci-connect").start();
    }

    private static int tx() { return Integer.parseInt(Session.ecuTx, 16); }
    private static int rx() { return Integer.parseInt(Session.ecuRx, 16); }

    @Override
    protected void onDestroy() {
        VciManager.get().stopScan(this);
        super.onDestroy();
    }
}
