package com.nirixx.app.vci;

import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Handler;
import java.util.ArrayList;
import java.util.List;

/**
 * Front door for all VCI connectivity.
 *
 *  • scan() performs REAL Bluetooth discovery when the radio and permissions
 *    allow it, and always merges the simulation pool so the app is fully
 *    demonstrable without hardware.
 *  • connect() picks the right transport: a real SPP socket for bonded/picked
 *    adapters, otherwise the simulation transport. All UDS/session logic in
 *    the app talks only to the VciTransport interface, so swapping simulation
 *    for live hardware is a one-line decision here.
 */
public final class VciManager {

    public interface ScanCallback {
        void onFound(String label, String detail, String linkType, String drawable, boolean live);
        void onFinished(boolean bluetoothActive);
    }

    private static final VciManager INSTANCE = new VciManager();
    public static VciManager get() { return INSTANCE; }

    private final Handler h = new Handler();
    private VciTransport active;
    private BroadcastReceiver receiver;

    private VciManager() { }

    /** label -> live BluetoothDevice from the most recent real scan/bonded list. */
    public final java.util.Map<String, BluetoothDevice> lastLive = new java.util.HashMap<String, BluetoothDevice>();

    public boolean bluetoothAvailable() {
        return BluetoothAdapter.getDefaultAdapter() != null;
    }

    public void scan(final Activity activity, final ScanCallback cb) {
        // Simulation pool always shows up (tagged SIM).
        final String[][] pool = VciModel.discoveredPool();
        for (int i = 0; i < pool.length; i++) {
            final int at = i;
            h.postDelayed(new Runnable() {
                public void run() {
                    cb.onFound(pool[at][0], pool[at][1], pool[at][2], pool[at][3], false);
                }
            }, 350L * (i + 1));
        }

        final BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        if (adapter == null) {
            h.postDelayed(new Runnable() { public void run() { cb.onFinished(false); } }, 350L * pool.length + 400);
            return;
        }

        // Real discovery: bonded devices first, then live air scan.
        try {
            if (adapter.isEnabled()) {
                List<BluetoothDevice> bonded = new ArrayList<BluetoothDevice>(adapter.getBondedDevices());
                for (final BluetoothDevice d : bonded) {
                    String nm;
                    try { nm = d.getName(); } catch (SecurityException se) { nm = null; }
                    if (nm == null) continue;
                    final String upper = nm.toUpperCase();
                    if (upper.contains("OBD") || upper.contains("VCI") || upper.contains("ELM")
                            || upper.contains("NRX") || upper.contains("TZ-") || upper.contains("NIRIXX")) {
                        final String fName = nm;
                        lastLive.put(fName, d);
                        cb.onFound(fName, "Paired adapter", "BT Classic", "vci", true);
                    }
                }
                receiver = new BroadcastReceiver() {
                    public void onReceive(Context context, Intent intent) {
                        if (BluetoothDevice.ACTION_FOUND.equals(intent.getAction())) {
                            BluetoothDevice dev = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
                            short rssi = intent.getShortExtra(BluetoothDevice.EXTRA_RSSI, (short) 0);
                            if (dev == null) return;
                            String nm;
                            try { nm = dev.getName(); } catch (SecurityException se) { nm = null; }
                            final String label = nm != null ? nm : dev.getAddress();
                            lastLive.put(label, dev);
                            cb.onFound(label, "Discovered · RSSI " + rssi + " dBm", "BT Classic", "vci", true);
                        } else if (BluetoothAdapter.ACTION_DISCOVERY_FINISHED.equals(intent.getAction())) {
                            cb.onFinished(true);
                        }
                    }
                };
                IntentFilter f = new IntentFilter();
                f.addAction(BluetoothDevice.ACTION_FOUND);
                f.addAction(BluetoothAdapter.ACTION_DISCOVERY_FINISHED);
                // System broadcasts; API 33+ flag keeps modern receivers explicit.
                if (android.os.Build.VERSION.SDK_INT >= 33) {
                    activity.registerReceiver(receiver, f, Context.RECEIVER_EXPORTED);
                } else {
                    activity.registerReceiver(receiver, f);
                }
                try { adapter.startDiscovery(); }
                catch (SecurityException se) { cb.onFinished(true); }
                // Hard stop after 12 s of scanning.
                h.postDelayed(new Runnable() { public void run() { stopScan(activity); cb.onFinished(true); } }, 12000);
            } else {
                h.postDelayed(new Runnable() { public void run() { cb.onFinished(false); } }, 350L * pool.length + 400);
            }
        } catch (SecurityException se) {
            cb.onFinished(false);
        }
    }

    public void stopScan(Activity activity) {
        BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        if (adapter != null) {
            try { adapter.cancelDiscovery(); } catch (SecurityException ignored) { }
        }
        if (receiver != null) {
            try { activity.unregisterReceiver(receiver); } catch (Exception ignored) { }
            receiver = null;
        }
    }

    /** Choose a transport for the chosen device. Real hardware → SPP socket;
     *  anything else → simulation. */
    public synchronized void connect(final Activity activity, final String addressOrNull,
                                     final String displayName, final VciTransport.Listener listener) {
        disconnect();
        BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        BluetoothDevice real = null;
        if (adapter != null && addressOrNull != null) {
            try { real = adapter.getRemoteDevice(addressOrNull); } catch (Exception ignored) { }
        }
        if (real != null) {
            active = new BluetoothSppTransport(real);
        } else {
            active = new SimTransport(displayName);
        }
        listener.onState(VciTransport.STATE_CONNECTING,
                (real != null ? "Opening live SPP link" : "No hardware found — starting simulation")
                        + " · " + displayName);
        // Simulated/demo path keeps UI timing identical to before.
        active.connect(new VciTransport.Listener() {
            public void onState(int state, String message) { listener.onState(state, message); }
            public void onBytes(byte[] data, int length) { listener.onBytes(data, length); }
            public void onError(String message) {
                // Fall back to simulation transparently if the live link fails.
                if (!(active instanceof SimTransport)) {
                    active = new SimTransport(displayName);
                    active.connect(this);
                } else {
                    listener.onError(message);
                }
            }
        });
    }

    public synchronized void disconnect() {
        if (active != null) { active.disconnect(); active = null; }
    }

    public synchronized VciTransport transport() { return active; }
}
