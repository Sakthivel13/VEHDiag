package com.nirixx.app.core.vci;

/** Connection-agnostic CAN transport: who (BT-SPP, Wi-Fi socket, USB-CDC)
 *  provides bytes, and converts between UDS payloads and CAN frames.
 *  Every implementation here is real — there is no simulated transport. */
public interface CanTransport {

    interface FrameListener { void onFrame(int canId, byte[] data); }
    interface ErrorListener { void onError(String reason); }

    /** Open the link and configure it for raw CAN (e.g. ELM327 AT init). */
    void open() throws Exception;
    void close();

    boolean isOpen();
    String describe();           // e.g. "ELM327 over BT-SPP (00:1D:A5:…) 500k 11bit"

    /** Transmit a complete CAN frame (max 8 data bytes, classic CAN). */
    void sendFrame(int canId, byte[] data) throws Exception;

    /** Deliver received frames; called from the reader thread. */
    void setFrameListener(FrameListener l);
    void setErrorListener(ErrorListener l);
}
