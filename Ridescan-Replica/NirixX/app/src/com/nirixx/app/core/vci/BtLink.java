package com.nirixx.app.core.vci;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.UUID;

/** Real Bluetooth-SPP serial link (RFCOMM, standard SPP UUID). */
public final class BtLink implements ByteLink {

    private static final UUID SPP = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    private final BluetoothDevice device;
    private BluetoothSocket socket;
    private OutputStream out;
    private Listener listener;
    private volatile boolean running;
    private Thread reader;

    public BtLink(BluetoothDevice device) { this.device = device; }

    @SuppressLint("MissingPermission")
    public void open() throws Exception {
        BluetoothAdapter ad = BluetoothAdapter.getDefaultAdapter();
        if (ad != null && ad.isDiscovering()) ad.cancelDiscovery();
        socket = device.createRfcommSocketToServiceRecord(SPP);
        socket.connect();                                 // blocking — caller is off-UI
        out = socket.getOutputStream();
        running = true;
        reader = new Thread(new Runnable() { public void run() { readLoop(); } }, "bt-link-rx");
        reader.start();
    }

    private void readLoop() {
        try {
            InputStream in = socket.getInputStream();
            byte[] buf = new byte[512];
            int n;
            while (running && (n = in.read(buf)) > 0) {
                if (listener != null) listener.onBytes(buf, n);
            }
        } catch (Exception e) {
            // fall through to close notification
        }
        running = false;
        if (listener != null) listener.onClosed("Bluetooth link lost");
    }

    public void close() {
        running = false;
        try { if (socket != null) socket.close(); } catch (Exception ignored) { }
    }

    public boolean isOpen() { return running && socket != null && socket.isConnected(); }

    @SuppressLint("MissingPermission")
    public String describe() { return "BT-SPP (" + device.getAddress() + ")"; }

    public void write(byte[] b) throws Exception {
        if (out == null) throw new Exception("link closed");
        out.write(b);
        out.flush();
    }

    public void setListener(Listener l) { this.listener = l; }
}
