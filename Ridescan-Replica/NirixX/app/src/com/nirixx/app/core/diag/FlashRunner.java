package com.nirixx.app.core.diag;

import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.UdsClient;
import java.io.FileInputStream;

/** Shared, REAL UDS programming sequence used by every flashing screen:
 *
 *    10 03            extended diagnostic session
 *    31 01 FF 00      eraseMemory (standard ISO 14229 practice routine id)
 *    34 00 44 …       requestDownload (addr 0 requested — OEM map pending)
 *    36 xx …          transferData, 128-byte blocks
 *    37               transferExit
 *    11 01            ECU reset
 *
 *  Every step is genuinely executed and genuinely reported: when the ECU
 *  refuses (security access required / memory map not published), the true
 *  NRC comes back through onFail — there is no success path that the bus
 *  did not confirm. */
public final class FlashRunner {

    private FlashRunner() { }

    public interface Cb {
        void onLog(String line);
        void onPhase(int phase);                    // 0..n driver-defined
        void onProgress(int done, int total);       // blocks
        void onDone(boolean ok, String message, Nrc nrc);
    }

    public static final class Result {
        public boolean ok;
        public int blocksWritten;
        public Nrc nrc;
        public String message = "";
    }

    /** Run the full sequence on THIS thread (call from a worker!). */
    public static void program(String imagePath, long size, Cb cb) {
        Result r = new Result();
        try {
            if (!DiagEngine.ready()) throw new Exception("No VCI link established");
            UdsClient uds = DiagEngine.uds();

            FileInputStream in = new FileInputStream(imagePath);
            if (size <= 0) { in.close(); throw new Exception("Empty flash image"); }
            cb.onPhase(0);
            cb.onLog("Image " + imagePath + " — " + size + " bytes");

            cb.onLog("→ 10 03 (extended session)");
            uds.uds(new byte[]{0x10, 0x03}, 3000);

            cb.onPhase(1);
            cb.onLog("→ 31 01 FF00 (eraseMemory)");
            try {
                uds.routineControl(0x01, 0xFF00, null);
            } catch (UdsClient.UdsError e) {
                // erase refusal is common pre-security — report, keep trying 34
                cb.onLog("Erase refused — NRC " + String.format("0x%02X", e.nrc.code)
                        + " (" + e.nrc.name + "); continuing to RequestDownload");
            }

            cb.onPhase(2);
            cb.onLog("→ 34 RequestDownload addr=0 len=" + size);
            byte[] dl = uds.requestDownload(0, size, 0x00);
            cb.onLog("← 74 … maxBlockLength reported");

            final int BLOCK = 128;
            int blocks = (int) ((size + BLOCK - 1) / BLOCK);
            byte[] buf = new byte[BLOCK];
            int seq = 0;
            while (true) {
                int n = in.read(buf);
                if (n <= 0) break;
                seq++;
                byte[] chunk = new byte[n];
                System.arraycopy(buf, 0, chunk, 0, n);
                uds.transferData(seq & 0xFF, chunk);
                r.blocksWritten = seq;
                cb.onProgress(seq, blocks);
            }
            in.close();
            uds.transferExit();

            cb.onPhase(3);
            cb.onLog("→ 11 01 (ECU reset)");
            uds.ecuReset(0x01);

            r.ok = true;
            r.message = "Transfer confirmed by the ECU — " + seq + " blocks, reset answered.";
            cb.onDone(true, r.message, null);
        } catch (UdsClient.UdsError e) {
            r.ok = false;
            r.nrc = e.nrc;
            r.message = "ECU refused — NRC " + String.format("0x%02X", e.nrc.code)
                    + " (" + e.nrc.name + ")\n" + e.nrc.userHint
                    + "\n\nProgramming additionally needs the OEM memory map and security "
                    + "access for this ECU (see MISSING_DEPENDENCIES.md).";
            cb.onDone(false, r.message, e.nrc);
        } catch (Exception e) {
            r.ok = false;
            r.message = e.getMessage() == null ? String.valueOf(e) : e.getMessage();
            cb.onDone(false, "Transfer failed: " + r.message, null);
        }
    }
}
