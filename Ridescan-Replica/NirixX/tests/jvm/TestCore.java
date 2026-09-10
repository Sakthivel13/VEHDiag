import com.nirixx.app.core.diag.BatteryAssess;
import com.nirixx.app.core.diag.TestAddr;
import com.nirixx.app.core.uds.IsoTp;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.Obd;
import com.nirixx.app.core.uds.UdsClient;
import com.nirixx.app.core.vin.VinRules;
import java.util.ArrayList;
import java.util.List;

/** Off-device unit tests for the real protocol stack.
 *
 *  The scripted ECU replays frames taken from the captured reference logs:
 *  TX 1001 -> RX 5001003201F4 ; TX 22F190 -> RX 7F2278 then 62F190<VIN hex> ;
 *  plus a multi-frame ISO-TP response and a hard negative (0x22). */
public final class TestCore {

    static int failures = 0;

    public static void main(String[] args) throws Exception {
        testVinRules();
        testIsoTpMultiFrame();
        testUdsConversationFromLog();
        testNegativeResponse();
        testNrcTable();
        testObdDecode();
        testIptDecode();
        testAddrParse();
        testBatteryBands();
        if (failures > 0) { System.out.println("FAILED: " + failures); System.exit(1); }
        System.out.println("ALL CORE TESTS PASS");
    }

    // ---------------------------------------------------------- SAE J1979 decode
    static void testObdDecode() {
        // RPM: (256A+B)/4 — 0x1A,0xF8 → (0x1AF8)/4 = 1726
        Double rpm = Obd.decodePid(0x0C, new byte[]{0x41, 0x0C, 0x1A, (byte) 0xF8});
        bool(rpm != null && Math.abs(rpm - 1726.0) < 0.01, "RPM 41 0C 1A F8 → 1726");
        // Coolant: A-40 → 0x78 = 120 → 80 °C
        Double ct = Obd.decodePid(0x05, new byte[]{0x41, 0x05, 0x78});
        bool(ct != null && ct == 80.0, "coolant 0x78 → 80 C");
        // Module voltage: (256A+B)/1000 — 0x2E,0x1E → 11806/1000 = 11.806 V
        Double mv = Obd.decodePid(0x42, new byte[]{0x41, 0x42, 0x2E, 0x1E});
        bool(mv != null && Math.abs(mv - 11.806) < 0.001, "module volts → 11.806");
        // TPS: A*100/255 — 0x80 → 50.2%
        Double tp = Obd.decodePid(0x11, new byte[]{0x41, 0x11, (byte) 0x80});
        bool(tp != null && Math.abs(tp - 50.196) < 0.01, "TPS 0x80 → 50.2%");
        // wrong PID echo must be rejected, not mis-decoded
        bool(Obd.decodePid(0x0C, new byte[]{0x41, 0x05, 0x00}) == null, "mismatched PID rejected");
        // Mode 09 ASCII record: 49 02 01 <"MD637…">
        byte[] vinRec = Obd.decodeInfo(0x02, new byte[]{0x49, 0x02, 0x01, 'M', 'D'});
        bool(vinRec != null && vinRec.length == 2 && "MD".equals(Obd.asciiInfo(vinRec)),
                "mode09 VIN record decode");
        ok("OBD-II decode (J1979)");
    }

    // ---------------------------------------------------------- SAE J1979 IPT (Mode 09 $08)
    static void testIptDecode() {
        // with NODI count byte: two monitors → pairs 3/4 and 9/2
        String s = Obd.decodeIpt(new byte[]{0x02, 0x00, 0x03, 0x00, 0x04, 0x00, 0x09, 0x00, 0x02});
        bool("M1 3/4  ·  M2 9/2".equals(s), "IPT with count byte → " + s);
        // without count byte: raw pairs
        String s2 = Obd.decodeIpt(new byte[]{0x00, 0x0A, 0x00, 0x14});
        bool("M1 10/20".equals(s2), "IPT without count byte → " + s2);
        // odd length (not decodable into pairs) → null, never a guess
        bool(Obd.decodeIpt(new byte[]{0x01, 0x02, 0x03}) == null, "IPT junk rejected");
        bool(Obd.decodeIpt(null) == null, "IPT null rejected");
        ok("IUPR IPT decode (J1979 $08)");
    }

    // ---------------------------------------------------------- TestAddr grammar
    static void testAddrParse() {
        TestAddr did = TestAddr.parse("did:F190");
        bool(did != null && did.kind == TestAddr.DID && did.value == 0xF190, "did:F190");
        TestAddr pid = TestAddr.parse("pid:0B*10");
        bool(pid != null && pid.kind == TestAddr.PID && pid.value == 0x0B && pid.factor == 10.0,
                "pid:0B*10 factor");
        TestAddr m = TestAddr.parse("m09:02");
        bool(m != null && m.kind == TestAddr.M09 && m.value == 2, "m09:02");
        TestAddr r = TestAddr.parse("ridge:ff00");
        bool(r == null, "garbage rejected");
        bool(TestAddr.parse(null) == null && TestAddr.parse("") == null, "null/empty rejected");
        ok("TestAddr grammar");
    }

    // ---------------------------------------------------------- battery bands
    static void testBatteryBands() {
        bool(BatteryAssess.socPercent(12.72) == 100, "12.72 V → 100%");
        bool(BatteryAssess.socPercent(12.45) == 75, "12.45 V → 75%");
        bool(BatteryAssess.socPercent(12.05) == 25, "12.05 V → 25%");
        bool(BatteryAssess.socPercent(11.5) == 0, "11.5 V → 0%");
        bool(BatteryAssess.isCharging(14.2), "14.2 V charging");
        bool(!BatteryAssess.isCharging(12.4), "12.4 V not charging");
        bool(BatteryAssess.assessment(12.62).contains("OK"), "12.62 V → OK text");
        bool(BatteryAssess.assessment(11.9).contains("low"), "11.9 V → low text");
        ok("Battery assessment bands");
    }

    // ---------------------------------------------------------- VIN rules
    static void testVinRules() {
        // shared Apache/Ronin family prefix — longest-prefix winner must be first
        int[] m = VinRules.match("MD637CE5AB1C01234");
        bool(m.length >= 2, "MD637CE5… matches Apache-160-4V-ABS & Ronin families (" + m.length + ")");
        bool(VinRules.MODELS[m[0]][0].equals("TVS Apache 160 4V ABS")
                || VinRules.MODELS[m[0]][0].equals("TVS Ronin"), "best match first");
        bool(VinRules.match("MD62912AB1C012300").length >= 2, "iQube prefix MD62912 matches S+ST");
        bool(VinRules.match("MD638AN1100000000").length == 0, "unknown VIN -> NO match (never assumed)");
        bool(!VinRules.isValidVin("MD637CE5"), "short VIN rejected");
        bool(!VinRules.isValidVin("MD637CE5ABIC01234"), "letter I rejected");
        bool(VinRules.isValidVin("MD637AN11R2D01275"), "captured Ronin VIN valid");
        String[] sys = VinRules.systemsOf("Dual Channel - 4V - EMS - ABS (Cont)");
        bool(contains(sys, "EMS") && contains(sys, "ABS") && contains(sys, "CONTINENTAL"),
                "systems parse: EMS+ABS+CONTINENTAL");
        sys = VinRules.systemsOf("Apache - EMS, ABS(BOSCH)");
        bool(contains(sys, "BOSCH"), "systems parse: BOSCH ABS");
        sys = VinRules.systemsOf("PASSENGER - EV");
        bool(contains(sys, "EV"), "systems parse: EV");
        ok("VIN rules");
    }

    // ---------------------------------------------------------- ISO-TP
    /** Scripted CAN peer. Injectables fire directly; queue fires on the next TX (e.g. FC). */
    static final class Peer implements IsoTp.Link {
        IsoTp.FrameListener app;
        List<byte[]> immediate = new ArrayList<byte[]>();
        List<byte[]> onNextTx = new ArrayList<byte[]>();
        List<String> sent = new ArrayList<String>();

        public void setFrameListener(IsoTp.FrameListener l) { app = l; }

        public void sendFrame(int canId, byte[] data) {
            sent.add(canId + ":" + hex(data));
            List<byte[]> pump = new ArrayList<byte[]>(onNextTx);
            onNextTx.clear();
            for (int i = 0; i < pump.size(); i++) app.onFrame(0x7E8, pump.get(i));
        }

        void pumpImmediate() {
            for (int i = 0; i < immediate.size(); i++) app.onFrame(0x7E8, immediate.get(i));
            immediate.clear();
        }
    }

    static void testIsoTpMultiFrame() throws Exception {
        Peer peer = new Peer();
        final IsoTp tp = new IsoTp(peer, 0x7E0, 0x7E8);
        // 20-byte payload -> FF(6) + CF(7) + CF(7)
        byte[] payload = new byte[20];
        for (int i = 0; i < 20; i++) payload[i] = (byte) (0x41 + i);
        List<byte[]> frames = isotpSplit(payload);
        // peer answers our request with an FF, then waits for our FC before sending CFs
        peer.sent.clear();
        final byte[] ff = frames.get(0);
        final List<byte[]> cfRest = frames.subList(1, frames.size());
        Thread responder = new Thread(new Runnable() { public void run() {
            try { Thread.sleep(30); } catch (Exception e) {}
            peer.onNextTx.addAll(cfRest);          // will be pumped when app sends FC
            peer.app.onFrame(0x7E8, ff);
        }});
        responder.start();
        byte[] got = tp.request(new byte[]{0x22, (byte) 0xF1, (byte) 0x90}, 3000);
        responder.join(2000);
        bool(got.length == 20, "ISO-TP reassembly 20 bytes (got " + got.length + ")");
        bool(same(got, payload), "ISO-TP payload intact");
        bool(peer.sent.get(1).startsWith("2016:30"), "Flow Control emitted on FF: " + peer.sent.get(1));
        ok("ISO-TP multi-frame");
    }

    // ---------------------------------------------------------- UDS conversation
    static void testUdsConversationFromLog() throws Exception {
        Peer peer = new Peer();
        IsoTp tp = new IsoTp(peer, 0x7E0, 0x7E8);
        final UdsClient uds = new UdsClient(tp);

        // 10 01 -> 50 01 00 32 01 F4 (single frame, like the log)
        peer.onNextTx.add(sf(new byte[]{0x50, 0x01, 0x00, 0x32, 0x01, (byte) 0xF4}));
        byte[] sp = uds.sessionControl(0x01);
        bool(sp.length == 5 && (sp[0] & 0xFF) == 0x01, "sessionControl positive echo");

        // 22 F190 -> 7F 22 78 (response pending), then 62 F190 <vin ascii hex> multi-frame after a beat
        final byte[] vin = "MD637AN11R2D01275".getBytes("US-ASCII");
        byte[] didResp = new byte[3 + vin.length];
        didResp[0] = 0x62; didResp[1] = (byte) 0xF1; didResp[2] = (byte) 0x90;
        System.arraycopy(vin, 0, didResp, 3, vin.length);
        final List<byte[]> parts = isotpSplit(didResp);
        peer.onNextTx.add(sf(new byte[]{0x7F, 0x22, 0x78}));          // immediate: response pending
        Thread delayed = delayedVin(peer, parts, vin);
        delayed.start();                                              // FF after 60ms, CFs on our FC
        String vinStr = uds.readVin();
        delayed.join(3000);
        bool(vinStr.equals(new String(vin, "US-ASCII")), "readVin -> " + vinStr);

        // 19 02 FF -> two DTCs: P0130 active, U0100 stored
        byte[] dtc = new byte[]{0x59, 0x02, (byte) 0xFF,
                (byte) 0x01, (byte) 0x30, (byte) 0x00, (byte) 0x01,   // P0130 status active
                (byte) 0xC1, (byte) 0x00, (byte) 0x00, (byte) 0x08};  // U0100 pending
        peer.onNextTx.addAll(isotpSplit(dtc));
        UdsClient.DtcRecord[] recs = uds.readDtc(0xFF);
        bool(recs.length == 2, "readDtc parsed 2 records (" + recs.length + ")");
        bool("P0130".equals(recs[0].code()), "DTC[0] code = " + recs[0].code());
        bool("U0100".equals(recs[1].code()), "DTC[1] code = " + recs[1].code());
        bool(recs[0].active(), "DTC[0] active bit");
        ok("UDS conversation (from captured log)");
    }

    /** Deliver the pending-NRC then the multi-frame DID response, honouring FC. */
    static Thread delayedVin(final Peer peer, final List<byte[]> parts, final byte[] vin) {
        return new Thread(new Runnable() { public void run() {
            try {
                Thread.sleep(60);
                // FF goes now; CFs wait for our Flow Control
                for (int i = 1; i < parts.size(); i++) peer.onNextTx.add(parts.get(i));
                peer.app.onFrame(0x7E8, parts.get(0));
            } catch (Exception ignored) { }
        }});
    }

    static void testNegativeResponse() {
        Peer peer = new Peer();
        UdsClient uds = new UdsClient(new IsoTp(peer, 0x7E0, 0x7E8));
        peer.onNextTx.add(sf(new byte[]{0x7F, 0x19, 0x22}));
        try {
            uds.readDtc(0xFF);
            bool(false, "negative response must throw");
        } catch (UdsClient.UdsError e) {
            bool(e.nrc.code == 0x22, "NRC captured 0x22");
            bool(e.nrc.name.contains("Conditions Not Correct"), "NRC named: " + e.nrc.name);
        } catch (Exception e) {
            bool(false, "wrong exception: " + e);
        }
        ok("UDS negative response");
    }

    static void testNrcTable() {
        bool(Nrc.of(0x78).name.contains("Response Pending"), "NRC 78");
        bool(Nrc.of(0x36).name.contains("Attempts"), "NRC 36");
        bool(Nrc.of(0x99).name.contains("Unknown"), "NRC unknown guarded");
        ok("NRC table");
    }

    // ---------------------------------------------------------- helpers
    static byte[] sf(byte[] payload) {
        byte[] f = new byte[8];
        f[0] = (byte) payload.length;
        System.arraycopy(payload, 0, f, 1, payload.length);
        return f;
    }

    /** Split an ISO-TP payload into CAN frames (FF + CFs), padding CFs with 0x00. */
    static List<byte[]> isotpSplit(byte[] payload) {
        List<byte[]> out = new ArrayList<byte[]>();
        if (payload.length <= 7) { out.add(sf(payload)); return out; }
        byte[] ff = new byte[8];
        ff[0] = (byte) (0x10 | ((payload.length >> 8) & 0x0F));
        ff[1] = (byte) (payload.length & 0xFF);
        System.arraycopy(payload, 0, ff, 2, 6);
        out.add(ff);
        int off = 6, sn = 1;
        while (off < payload.length) {
            byte[] cf = new byte[8];
            cf[0] = (byte) (0x20 | (sn & 0x0F));
            int n = Math.min(7, payload.length - off);
            System.arraycopy(payload, off, cf, 1, n);
            out.add(cf);
            off += n; sn = (sn + 1) & 0x0F;
        }
        return out;
    }

    static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < b.length; i++) sb.append(String.format("%02X", b[i]));
        return sb.toString();
    }

    static boolean contains(String[] arr, String v) {
        for (int i = 0; i < arr.length; i++) if (arr[i].equals(v)) return true;
        return false;
    }

    static boolean same(byte[] a, byte[] b) {
        if (a.length != b.length) return false;
        for (int i = 0; i < a.length; i++) if (a[i] != b[i]) return false;
        return true;
    }

    static void bool(boolean condition, String what) {
        if (!condition) { failures++; System.out.println("  FAIL  " + what); }
    }
    static void ok(String suite) { System.out.println("  ok    " + suite); }
}
