package com.nirixx.app.core.vci;

/** A byte-stream serial link (BLUETOOTH SPP / Wi-Fi TCP / USB CDC).
 *  Implementations are real Android transports; the reader thread must be
 *  running after open(). */
public interface ByteLink {

    interface Listener {
        void onBytes(byte[] data, int n);
        void onClosed(String reason);
    }

    void open() throws Exception;
    void close();
    boolean isOpen();
    String describe();

    /** Blocking-free write; implementations queue on their own writer. */
    void write(byte[] b) throws Exception;

    void setListener(Listener l);
}
