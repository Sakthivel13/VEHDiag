package com.nirixx.app.vci;

/** Transport abstraction: real Bluetooth SPP / BLE stacks plug in here,
 *  alongside the simulation transport used for demos. */
public interface VciTransport {
    int STATE_CONNECTING = 1;
    int STATE_CONNECTED = 2;
    int STATE_DISCONNECTED = 3;

    interface Listener {
        void onState(int state, String message);
        void onBytes(byte[] data, int length);
        void onError(String message);
    }

    void connect(Listener listener);
    void write(byte[] frame);
    void disconnect();
    boolean isConnected();
    String describe();
}
