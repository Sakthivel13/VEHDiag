package com.nirixx.app.vci;

import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothProfile;
import android.content.Context;
import java.util.UUID;

/**
 * BLE (GATT) transport scaffold for new-generation VCIs, modelled on the
 * Nordic UART Service convention (write char = TX to VCI, notify char = RX).
 * Service/characteristic UUIDs are configurable per VCI family — plug the
 * values printed on the adapter label in here when real hardware is available.
 */
public class BleTransport implements VciTransport {

    public static UUID UART_SERVICE = UUID.fromString("6E400001-B5A3-F393-E0A9-E50E24DCCA9E");
    public static UUID UART_TX_WRITE = UUID.fromString("6E400002-B5A3-F393-E0A9-E50E24DCCA9E");
    public static UUID UART_RX_NOTIFY = UUID.fromString("6E400003-B5A3-F393-E0A9-E50E24DCCA9E");
    private static final UUID CCC_DESCRIPTOR = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");

    private final Context context;
    private final BluetoothDevice device;
    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic txChar;
    private volatile boolean connected;
    private Listener listener;

    public BleTransport(Context context, BluetoothDevice device) {
        this.context = context;
        this.device = device;
    }

    private final BluetoothGattCallback callback = new BluetoothGattCallback() {
        @Override
        public void onConnectionStateChange(BluetoothGatt g, int status, int newState) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                listener.onState(STATE_CONNECTING, "Discovering GATT services…");
                try { g.requestMtu(247); } catch (SecurityException se) { listener.onError("Bluetooth permission not granted"); return; }
                try { g.discoverServices(); } catch (SecurityException ignored) { }
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                connected = false;
                listener.onState(STATE_DISCONNECTED, "BLE link closed");
            }
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt g, int status) {
            BluetoothGattService svc = g.getService(UART_SERVICE);
            if (svc == null) { listener.onError("UART service not found on this device"); return; }
            txChar = svc.getCharacteristic(UART_TX_WRITE);
            BluetoothGattCharacteristic rx = svc.getCharacteristic(UART_RX_NOTIFY);
            if (rx != null) {
                try {
                    g.setCharacteristicNotification(rx, true);
                    BluetoothGattDescriptor cccd = rx.getDescriptor(CCC_DESCRIPTOR);
                    if (cccd != null) {
                        cccd.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                        g.writeDescriptor(cccd);
                    }
                } catch (SecurityException se) {
                    listener.onError("Bluetooth permission not granted");
                    return;
                }
            }
            connected = true;
            listener.onState(STATE_CONNECTED, "BLE UART ready (MTU 247)");
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c) {
            byte[] v = c.getValue();
            if (v != null && listener != null) listener.onBytes(v, v.length);
        }
    };

    public void connect(Listener l) {
        this.listener = l;
        l.onState(STATE_CONNECTING, "Opening BLE GATT…");
        try {
            gatt = device.connectGatt(context, false, callback);
        } catch (SecurityException se) {
            l.onError("Bluetooth permission not granted");
        }
    }

    public void write(byte[] frame) {
        try {
            if (gatt != null && txChar != null && connected) {
                txChar.setValue(frame);
                gatt.writeCharacteristic(txChar);
            }
        } catch (SecurityException e) {
            if (listener != null) listener.onError("Bluetooth permission not granted");
        }
    }

    public void disconnect() {
        connected = false;
        try { if (gatt != null) { gatt.disconnect(); gatt.close(); } } catch (Exception ignored) { }
        gatt = null;
    }

    public boolean isConnected() { return connected; }

    public String describe() { return "Bluetooth Low Energy · GATT UART"; }
}
