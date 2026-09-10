package com.nirixx.app.vci;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.UUID;

/**
 * Genuine Bluetooth Classic (RFCOMM / SPP) transport for NirixX-compatible VCIs
 * and generic SPP OBD adapters. Real Android Bluetooth I/O: once a device is
 * paired, bytes written here go out on the air and inbound frames are pumped
 * back to the Listener. The UDS session layer sits above this in VciManager.
 */
public class BluetoothSppTransport implements VciTransport {

    /** Well-known Serial Port Profile UUID. */
    private static final UUID SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    private final BluetoothDevice device;
    private BluetoothSocket socket;
    private OutputStream out;
    private Thread pump;
    private volatile boolean connected;
    private Listener listener;

    public BluetoothSppTransport(BluetoothDevice device) {
        this.device = device;
    }

    public void connect(Listener l) {
        this.listener = l;
        l.onState(STATE_CONNECTING, "Opening RFCOMM channel…");
        new Thread(new Runnable() {
            public void run() {
                try {
                    BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
                    if (adapter != null) {
                        try { adapter.cancelDiscovery(); }
                        catch (SecurityException se) { /* API 31+ runtime perm: ignore */ }
                    }
                    socket = device.createRfcommSocketToServiceRecord(SPP_UUID);
                    socket.connect();
                    out = socket.getOutputStream();
                    connected = true;
                    listener.onState(STATE_CONNECTED, "SPP link established");
                    startPump(socket.getInputStream());
                } catch (SecurityException se) {
                    listener.onError("Bluetooth permission not granted");
                } catch (Exception e) {
                    listener.onError("Connect failed: " + e.getMessage());
                    closeQuietly();
                }
            }
        }, "spp-connect").start();
    }

    private void startPump(final InputStream in) {
        pump = new Thread(new Runnable() {
            public void run() {
                byte[] buf = new byte[512];
                while (connected) {
                    try {
                        int n = in.read(buf);
                        if (n < 0) break;
                        listener.onBytes(buf, n);
                    } catch (Exception e) {
                        break;
                    }
                }
                connected = false;
                listener.onState(STATE_DISCONNECTED, "Link closed");
                closeQuietly();
            }
        }, "spp-pump");
        pump.start();
    }

    public void write(byte[] frame) {
        try {
            if (out != null && connected) { out.write(frame); out.flush(); }
        } catch (Exception e) {
            if (listener != null) listener.onError("Write failed: " + e.getMessage());
        }
    }

    public void disconnect() {
        connected = false;
        closeQuietly();
    }

    private void closeQuietly() {
        try { if (socket != null) socket.close(); } catch (Exception ignored) { }
        socket = null;
    }

    public boolean isConnected() { return connected; }

    public String describe() { return "Bluetooth Classic · SPP/RFCOMM"; }
}
