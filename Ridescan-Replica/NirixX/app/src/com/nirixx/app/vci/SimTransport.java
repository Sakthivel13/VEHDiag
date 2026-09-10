package com.nirixx.app.vci;

import android.os.Handler;

/**
 * Simulation transport — scripts a canned UDS session so every screen of the
 * app is usable without hardware. Selected automatically when no real adapter
 * is present; swap usage to BluetoothSppTransport/BleTransport by pairing one.
 */
public class SimTransport implements VciTransport {

    private final Handler h = new Handler();
    private final String deviceName;
    private volatile boolean connected;
    private Listener listener;

    /** Positive UDS single-frame responses cycled for demo traffic. */
    private static final byte[][] SCRIPT = new byte[][]{
        new byte[]{0x50, 0x03, 0x00, 0x32, 0x01, (byte) 0xF4},        // DiagnosticSessionControl +
        new byte[]{0x67, 0x01, 0x34, (byte) 0xA1, (byte) 0x9C, 0x05}, // SecurityAccess seed/key +
        new byte[]{0x62, (byte) 0xF1, (byte) 0x90, 0x4D, 0x44, 0x36}, // ReadDataByIdentifier +
        new byte[]{0x71, 0x01, 0x01, 0x01, 0x00},                     // RoutineControl +
    };
    private int scriptAt;

    public SimTransport(String deviceName) {
        this.deviceName = deviceName;
    }

    public void connect(Listener l) {
        this.listener = l;
        l.onState(STATE_CONNECTING, "Simulating link to " + deviceName + "…");
        h.postDelayed(new Runnable() {
            public void run() {
                connected = true;
                listener.onState(STATE_CONNECTED, "Simulated session active");
            }
        }, 900);
    }

    public void write(byte[] frame) {
        if (!connected) return;
        h.postDelayed(new Runnable() {
            public void run() {
                byte[] resp = SCRIPT[scriptAt % SCRIPT.length];
                scriptAt++;
                if (connected && listener != null) listener.onBytes(resp, resp.length);
            }
        }, 220);
    }

    public void disconnect() { connected = false; }

    public boolean isConnected() { return connected; }

    public String describe() { return "Simulation · no hardware required"; }
}
