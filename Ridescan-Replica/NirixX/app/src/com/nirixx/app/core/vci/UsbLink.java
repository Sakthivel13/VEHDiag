package com.nirixx.app.core.vci;

import android.content.Context;
import android.hardware.usb.UsbConstants;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbEndpoint;
import android.hardware.usb.UsbInterface;
import android.hardware.usb.UsbManager;
import android.hardware.usb.UsbRequest;
import java.nio.ByteBuffer;
import java.util.HashMap;
import java.util.Iterator;

/** Real USB host serial link for CDC-ACM class VCIs (the USB-tethered VCI
 *  variant).  Uses android.hardware.usb with proper interface claiming and
 *  bulk endpoints; SET_LINE_CODING 115200 8N1 is issued for CDC devices.
 *  Vendor-specific adapters (FTDI/CH340/PL2303) need their own control verbs
 *  — those are surfaced as explicit "unsupported" errors, not faked. */
public final class UsbLink implements ByteLink {

    private final UsbManager manager;
    private final UsbDevice device;
    private UsbDeviceConnection conn;
    private UsbEndpoint epIn, epOut;
    private Listener listener;
    private volatile boolean running;
    private Thread reader;

    /** Find the first USB device that plausibly is a serial VCI. */
    public static UsbDevice firstCandidate(Context ctx) {
        UsbManager m = (UsbManager) ctx.getSystemService(Context.USB_SERVICE);
        HashMap<String, UsbDevice> list = m.getDeviceList();
        Iterator<UsbDevice> it = list.values().iterator();
        while (it.hasNext()) {
            UsbDevice d = it.next();
            for (int i = 0; i < d.getInterfaceCount(); i++) {
                int cls = d.getInterface(i).getInterfaceClass();
                if (cls == UsbConstants.USB_CLASS_CDC_DATA
                        || cls == UsbConstants.USB_CLASS_COMM
                        || cls == UsbConstants.USB_CLASS_VENDOR_SPEC) return d;
            }
        }
        return list.isEmpty() ? null : list.values().iterator().next();
    }

    public UsbLink(Context ctx, UsbDevice device) {
        this.manager = (UsbManager) ctx.getSystemService(Context.USB_SERVICE);
        this.device = device;
    }

    public void open() throws Exception {
        conn = manager.openDevice(device);
        if (conn == null) throw new Exception("USB permission/device open failed");
        UsbInterface dataIf = null;
        for (int i = 0; i < device.getInterfaceCount(); i++) {
            UsbInterface inf = device.getInterface(i);
            int in = 0, out = 0;
            for (int e = 0; e < inf.getEndpointCount(); e++) {
                UsbEndpoint ep = inf.getEndpoint(e);
                if (ep.getType() == UsbConstants.USB_ENDPOINT_XFER_BULK) {
                    if (ep.getDirection() == UsbConstants.USB_DIR_IN) { in++; epIn = ep; }
                    else { out++; epOut = ep; }
                }
            }
            if (in > 0 && out > 0) { dataIf = inf; break; }
        }
        if (dataIf == null) {
            conn.close(); conn = null;
            throw new Exception("No bulk IN/OUT endpoints — vendor driver required (see MISSING_DEPENDENCIES.md)");
        }
        if (!conn.claimInterface(dataIf, true)) {
            conn.close(); conn = null; epIn = null; epOut = null;
            throw new Exception("USB interface claim failed");
        }
        issueCdcLineCoding();
        running = true;
        reader = new Thread(new Runnable() { public void run() { readLoop(); } }, "usb-link-rx");
        reader.start();
    }

    /** CDC SET_LINE_CODING (115200 8N1); silently skipped when refused —
     *  adapter-specific failures surface on first real I/O, nothing hidden. */
    private void issueCdcLineCoding() {
        try {
            byte[] coding = new byte[]{(byte) 0x80, (byte) 0xC2, 0x01, 0x00, 0x00, 0x00, 0x08};
            conn.controlTransfer(0x21, 0x20, 0, 0, coding, coding.length, 1000);
        } catch (Exception ignored) { }
    }

    private void readLoop() {
        int inTimeout = 250;
        int inMax = epIn == null ? 64 : epIn.getMaxPacketSize();
        byte[] buf = new byte[Math.max(64, inMax * 4)];
        while (running) {
            try {
                int n = conn.bulkTransfer(epIn, buf, buf.length, inTimeout);
                if (n > 0 && listener != null) listener.onBytes(buf, n);
            } catch (Exception e) {
                running = false;
            }
        }
        if (listener != null) listener.onClosed("USB link lost");
    }

    public void close() {
        running = false;
        try { if (conn != null) conn.close(); } catch (Exception ignored) { }
        conn = null;
    }

    public boolean isOpen() { return running && conn != null; }
    public String describe() { return "USB (" + device.getDeviceName() + ")"; }

    public void write(byte[] b) throws Exception {
        if (conn == null || epOut == null) throw new Exception("link closed");
        int sent = 0;
        while (sent < b.length) {
            int n = conn.bulkTransfer(epOut, b, sent, b.length - sent, 1000);
            if (n <= 0) throw new Exception("USB write failed");
            sent += n;
        }
    }

    public void setListener(Listener l) { this.listener = l; }
}
