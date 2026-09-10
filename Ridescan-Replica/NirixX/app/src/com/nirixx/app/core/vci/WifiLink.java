package com.nirixx.app.core.vci;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;

/** Real Wi-Fi serial link: TCP socket to the VCI hotspot.
 *  ELM327-class Wi-Fi dongles conventionally serve 192.168.0.10:35000;
 *  both values are configurable — nothing is fabricated. */
public final class WifiLink implements ByteLink {

    private final String host;
    private final int port;
    private Socket socket;
    private OutputStream out;
    private Listener listener;
    private volatile boolean running;
    private Thread reader;

    public WifiLink(String host, int port) { this.host = host; this.port = port; }

    public void open() throws Exception {
        socket = new Socket();
        socket.connect(new InetSocketAddress(host, port), 5000);
        socket.setTcpNoDelay(true);
        out = socket.getOutputStream();
        running = true;
        reader = new Thread(new Runnable() { public void run() { readLoop(); } }, "wifi-link-rx");
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
        } catch (Exception e) { }
        running = false;
        if (listener != null) listener.onClosed("Wi-Fi link lost");
    }

    public void close() {
        running = false;
        try { if (socket != null) socket.close(); } catch (Exception ignored) { }
    }

    public boolean isOpen() { return running && socket != null && socket.isConnected(); }
    public String describe() { return "Wi-Fi (" + host + ":" + port + ")"; }

    public void write(byte[] b) throws Exception {
        if (out == null) throw new Exception("link closed");
        out.write(b);
        out.flush();
    }

    public void setListener(Listener l) { this.listener = l; }
}
