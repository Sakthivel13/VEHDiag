package com.nirixx.app;

import android.app.Dialog;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import com.nirixx.app.core.diag.DiagEngine;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.UdsClient;
import com.nirixx.app.db.Db;
import com.nirixx.app.sim.UdsLog;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** ECU Flashing — the reference 4-phase UI (Download → Load → Flashing → Reset)
 *  driven by a REAL UDS transfer (10 03 → 34 → 36 … → 37 → 11 01) on a REAL
 *  binary the operator imports from storage.  Preconditions are truly
 *  measured (rail voltage via ATRV, tablet charge via BatteryManager).
 *  If the ECU refuses (no published memory map / security), the refusal is
 *  reported with its true NRC — no scripted success, ever. */
public class FlashActivity extends BaseActivity {

    private static final int REQ_BIN = 72;

    private LinearLayout content, logBox;
    private final Handler h = new Handler();
    private final View[] seg = new View[4];
    private final TextView[] segCheck = new TextView[4];
    private int logNo = 1;
    private volatile boolean flashing = false;
    private volatile int phaseDone = -1;
    private Db db;
    private TextView fileRow, battRow;
    private String binPath, binName;
    private long binSize;
    private double rail = -1;
    private String cvnText = "unread", calText = "unread";

    private static final String[] PHASES = {"Download", "Load", "Flashing", "Reset"};

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        if (!com.nirixx.app.core.role.Roles.can(Session.userType, "flash")) {
            Ui.dialog(this, "Not permitted",
                    "This is an engineering operation restricted to the Dealer Engineer role.",
                    "OK", new Runnable() { public void run() { finish(); } }, null, null).show();
            return;
        }
        setTitle("ECU Flashing");
        showEcuChip(Session.selectedEcuCode, true);
        db = Db.get(this);
        Session.ensureSession(this);
        content = (LinearLayout) findViewById(R.id.content);
        preconditions();
    }

    // ---------------------------------------------------------- preconditions
    private void preconditions() {
        final Dialog d = new Dialog(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundResource(R.drawable.bg_dialog);
        int p = Ui.dp(this, 20);
        root.setPadding(p, p, p, Ui.dp(this, 12));
        TextView title = Ui.tv(this, "Check Following Condition", 17f, 0xFF1A2138, true);
        title.setGravity(android.view.Gravity.CENTER);
        root.addView(title);
        String conditions =
                "1. Don't Switch off the Ignition Key During the Flashing.\n\n"
                        + "2. Don't Switch off the Engine Kill Switch During the Flashing.\n\n"
                        + "3. Don't Press Back Button in Device till Completion of Flashing Process.\n\n"
                        + "4. Battery Voltage Should be above 12 Volts.\n\n"
                        + "5. Diagnostic Device(Tab) Charge Should be 30%.";
        TextView body = Ui.tv(this, conditions, 13.5f, 0xFF1A2138, false);
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-1, -2);
        bp.setMargins(0, Ui.dp(this, 10), 0, 0);
        root.addView(body, bp);

        // REAL measured state instead of a fake "instruction video" gate
        LinearLayout meas = new LinearLayout(this);
        meas.setOrientation(LinearLayout.VERTICAL);
        meas.setBackgroundResource(R.drawable.bg_box_outline);
        meas.setPadding(Ui.dp(this, 14), Ui.dp(this, 10), Ui.dp(this, 14), Ui.dp(this, 10));
        final TextView railTv = Ui.tv(this, "Vehicle rail: " + (DiagOps.live() ? "measuring…" : "no VCI link"),
                13f, 0xFF1A2138, false);
        final TextView tabTv = Ui.tv(this, "Tablet charge: " + tabletCharge() + "%", 13f, 0xFF1A2138, false);
        meas.addView(railTv);
        meas.addView(tabTv);
        LinearLayout.LayoutParams mp = new LinearLayout.LayoutParams(-1, -2);
        mp.setMargins(0, Ui.dp(this, 12), 0, 0);
        root.addView(meas, mp);

        TextView cc = Ui.tv(this, "If any App Crashes Please Contact.", 14.5f, 0xFF1A2138, true);
        cc.setGravity(android.view.Gravity.CENTER);
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-1, -2);
        cp.setMargins(0, Ui.dp(this, 12), 0, 0);
        root.addView(cc, cp);
        LinearLayout pill = Ui.phonePill(this, db.config("support_number", "+917969478770"));
        LinearLayout.LayoutParams pp2 = new LinearLayout.LayoutParams(-2, -2);
        pp2.gravity = android.view.Gravity.CENTER_HORIZONTAL;
        pp2.setMargins(0, Ui.dp(this, 8), 0, 0);
        root.addView(pill, pp2);
        pill.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                startActivity(new Intent(Intent.ACTION_DIAL,
                        Uri.parse("tel:" + db.config("support_number", "+917969478770"))));
            }
        });

        LinearLayout btns = new LinearLayout(this);
        btns.setOrientation(LinearLayout.HORIZONTAL);
        TextView cancel = Ui.tv(this, "CANCEL", 14.5f, 0xFF5A6472, true);
        cancel.setGravity(android.view.Gravity.CENTER);
        cancel.setPadding(0, Ui.dp(this, 12), 0, Ui.dp(this, 12));
        final TextView cont = Ui.tv(this, "CONTINUE", 14.5f, 0xFFFFFFFF, true);
        cont.setGravity(android.view.Gravity.CENTER);
        cont.setBackgroundResource(R.drawable.bg_button_navy);
        cont.setPadding(0, Ui.dp(this, 12), 0, Ui.dp(this, 12));
        btns.addView(cancel, new LinearLayout.LayoutParams(0, -2, 1f));
        LinearLayout.LayoutParams cnt = new LinearLayout.LayoutParams(0, -2, 1f);
        cnt.setMargins(Ui.dp(this, 10), 0, 0, 0);
        btns.addView(cont, cnt);
        LinearLayout.LayoutParams bpr = new LinearLayout.LayoutParams(-1, -2);
        bpr.setMargins(0, Ui.dp(this, 14), 0, 0);
        root.addView(btns, bpr);

        d.setContentView(root);
        d.setCancelable(true);
        d.show();
        cancel.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { d.dismiss(); finish(); }
        });
        cont.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v2) { d.dismiss(); buildFlashUi(); }
        });

        if (DiagOps.live()) {
            DiagOps.adapterVoltage(this, new DiagOps.Cb<Double>() {
                public void ok(Double v) {
                    rail = v.doubleValue();
                    railTv.setText("Vehicle rail: "
                            + com.nirixx.app.core.diag.BatteryAssess.fmt(rail) + " V"
                            + (rail < 12.0 ? "  (LOW — charge before flashing)" : ""));
                }
                public void err(String w, String det, Nrc n) { railTv.setText("Vehicle rail: unread"); }
            });
        }
    }

    private int tabletCharge() {
        Intent i = registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        if (i == null) return -1;
        int level = i.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = i.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
        return scale <= 0 ? -1 : (level * 100) / scale;
    }

    // ---------------------------------------------------------- flash screen
    private void buildFlashUi() {
        content.removeAllViews();
        content.addView(Ui.crumbs(this, new String[]{"Home", Session.selectedVehicle,
                Session.selectedEcuCode, "ECU Flashing"}));

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackgroundResource(R.drawable.bg_card);
        card.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14));

        LinearLayout prog = new LinearLayout(this);
        prog.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 0; i < 4; i++) {
            LinearLayout cell = new LinearLayout(this);
            cell.setOrientation(LinearLayout.VERTICAL);
            TextView label = Ui.tv(this, PHASES[i], 12.5f, 0xFF1A2138, false);
            label.setGravity(android.view.Gravity.CENTER);
            cell.addView(label);
            android.widget.FrameLayout track = new android.widget.FrameLayout(this);
            track.setBackgroundResource(R.drawable.bg_segment_grey);
            TextView check = Ui.tv(this, "\u2713", 12f, 0xFFFFFFFF, true);
            check.setGravity(android.view.Gravity.CENTER);
            track.addView(check, new android.widget.FrameLayout.LayoutParams(-1, Ui.dp(this, 16)));
            check.setVisibility(View.INVISIBLE);
            LinearLayout.LayoutParams tp2 = new LinearLayout.LayoutParams(-1, Ui.dp(this, 16));
            tp2.setMargins(0, Ui.dp(this, 4), 0, 0);
            cell.addView(track, tp2);
            seg[i] = track; segCheck[i] = check;
            LinearLayout.LayoutParams cl = new LinearLayout.LayoutParams(0, -2, 1f);
            cl.setMargins(Ui.dp(this, 2), 0, Ui.dp(this, 2), 0);
            prog.addView(cell, cl);
        }
        card.addView(prog);

        LinearLayout info = new LinearLayout(this);
        info.setOrientation(LinearLayout.VERTICAL);
        info.setBackgroundResource(R.drawable.bg_box_outline);
        info.setPadding(Ui.dp(this, 14), Ui.dp(this, 10), Ui.dp(this, 14), Ui.dp(this, 10));
        LinearLayout.LayoutParams ip = new LinearLayout.LayoutParams(-1, -2);
        ip.setMargins(0, Ui.dp(this, 12), 0, 0);
        card.addView(info, ip);
        info.addView(bullet("VIN", Session.selectedVin));
        final TextView cvnRow = bullet("CVN", cvnText);
        final TextView calRow = bullet("CAL ID", calText);
        info.addView(cvnRow);
        info.addView(calRow);
        battRow = bullet("Battery Voltage", rail > 0
                ? com.nirixx.app.core.diag.BatteryAssess.fmt(rail) + " V" : "unread");
        info.addView(battRow);
        String published = db.flashFile(Session.ecuId);
        fileRow = bullet("Flash File", binName != null ? binName
                : (published != null ? published + " (name only — binary not in store)" : "none imported"));
        info.addView(fileRow);

        // import row — a real binary from device storage
        TextView imp = Ui.navyBtn(this, binName == null ? "IMPORT FLASH FILE (.hex/.mot/.bin)"
                : "REPLACE FILE");
        LinearLayout.LayoutParams ipp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 44));
        ipp.setMargins(0, Ui.dp(this, 10), 0, 0);
        card.addView(imp, ipp);
        imp.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Intent it = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                it.addCategory(Intent.CATEGORY_OPENABLE);
                it.setType("*/*");
                startActivityForResult(it, REQ_BIN);
            }
        });

        List<String[]> bins = db.flashBins();
        if (bins.size() > 0 && binName == null) {
            TextView pickInfo = Ui.tv(this, "Tap an imported image to select it:", 12.5f, 0xFF5A6472, false);
            card.addView(pickInfo);
            for (int i = 0; i < bins.size(); i++) {
                final String[] b = bins.get(i);
                LinearLayout row = Ui.listRow(this, R.drawable.ic_chip, b[1],
                        b[3] + " bytes · module " + (b[4] == null ? "—" : b[4]), true);
                row.setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) { selectBin(b); }
                });
                card.addView(row);
            }
        }

        final TextView start = Ui.navyBtn(this, "\u26A1  START FLASH");
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(Ui.dp(this, 210), Ui.dp(this, 48));
        sp.gravity = android.view.Gravity.CENTER_HORIZONTAL;
        sp.setMargins(0, Ui.dp(this, 14), 0, 0);
        card.addView(start, sp);

        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-1, -2);
        cp.setMargins(0, 0, 0, Ui.dp(this, 10));
        content.addView(card, cp);

        logBox = new LinearLayout(this);
        logBox.setOrientation(LinearLayout.VERTICAL);
        logBox.setBackgroundResource(R.drawable.bg_box_outline);
        logBox.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));
        logBox.addView(Ui.tv(this, "Logs", 13.5f, 0xFF1A2138, true));
        LinearLayout.LayoutParams lgp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 320));
        content.addView(logBox, lgp);

        if (DiagOps.live()) {
            readId(cvnRow, 0x06);
            readId(calRow, 0x04);
        }

        start.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                if (flashing) return;
                if (binPath == null) { toast("Import a flash image first"); return; }
                if (!DiagOps.live()) { toast("No VCI link established"); return; }
                if (rail > 0 && rail < 12.0) {
                    toast("Battery below 12 V — connect a charger before flashing");
                    return;
                }
                start.setTextColor(0xFFAAB2C4);
                start.setBackgroundResource(R.drawable.bg_button_navy_dim);
                runFlash();
            }
        });
    }

    private void readId(final TextView row, final int infoType) {
        DiagOps.mode09(this, infoType, new DiagOps.Cb<byte[]>() {
            public void ok(byte[] v) {
                String s = com.nirixx.app.core.uds.Obd.asciiInfo(v);
                String t = s == null ? UdsClient.hexBytes(v) : s;
                if (infoType == 0x06) cvnText = t; else calText = t;
                row.setText("\u2022  " + (infoType == 0x06 ? "CVN        " : "CAL ID        ") + t);
            }
            public void err(String w, String d, Nrc n) { }
        });
    }

    private TextView bullet(String k, String v) {
        return Ui.tv(this, "\u2022  " + k + "        " + v, 13.5f, 0xFF1A2138, false);
    }

    private void selectBin(String[] b) {
        binName = b[1];
        binPath = b[2];
        try { binSize = Long.parseLong(b[3]); } catch (Exception e) { binSize = -1; }
        toast("Selected " + binName);
        buildFlashUi();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_BIN || resultCode != RESULT_OK || data == null) return;
        Uri src = data.getData();
        if (src == null) return;
        String name = src.getLastPathSegment();
        if (name == null) name = "image.bin";
        try {
            File dir = new File(getExternalFilesDir(null), "Binaries");
            dir.mkdirs();
            File dst = new File(dir, name.replaceAll("[^A-Za-z0-9._-]", "_"));
            InputStream in = getContentResolver().openInputStream(src);
            FileOutputStream out = new FileOutputStream(dst);
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            in.close(); out.close();
            db.addFlashBin(dst.getName(), dst.getAbsolutePath(), dst.length(),
                    Session.selectedEcuCode);
            binName = dst.getName(); binPath = dst.getAbsolutePath(); binSize = dst.length();
            toast("Imported " + binName + " (" + binSize + " bytes)");
        } catch (Exception e) {
            toast("Import failed: " + e.getMessage());
        }
        buildFlashUi();
    }

    // ---------------------------------------------------------- real transfer
    private void runFlash() {
        flashing = true;
        new Thread(new Runnable() {
            public void run() { try { doFlash(); } finally { flashing = false; } }
        }, "flash").start();
    }

    private void doFlash() {
        try {
            // ---- phase 0: read the real image ------------------------------
            log("Image: " + binName + " (" + binSize + " bytes)");
            FileInputStream in = new FileInputStream(binPath);
            if (binSize <= 0) { fail(0, "Empty image"); return; }
            final int BLOCK = 128;
            int blocks = (int) ((binSize + BLOCK - 1) / BLOCK);
            log("Blocks: " + blocks + " × " + BLOCK + " B");

            // ---- phase 1: load (extended session) --------------------------
            log("TX " + Session.ecuTx + " -> 1003");
            byte[] r = DiagEngine.uds().uds(new byte[]{0x10, 0x03}, 3000);
            log("RX " + Session.ecuRx + " -> " + UdsClient.hexBytes(r).replace(" ", ""));
            markPhase(0);
            log("Extended session active");

            // ---- phase 2: flashing (34/36/37) ------------------------------
            log("RequestDownload addr=0x00000000 size=" + binSize);
            byte[] dl = DiagEngine.uds().requestDownload(0, binSize, 0x00);
            markPhase(1);
            log("74 accepted — max block " + UdsClient.hexBytes(dl).replace(" ", ""));

            byte[] buf = new byte[BLOCK];
            int seq = 0;
            while (true) {
                int n = in.read(buf);
                if (n <= 0) break;
                seq++;
                byte[] chunk = new byte[n];
                System.arraycopy(buf, 0, chunk, 0, n);
                DiagEngine.uds().transferData(seq & 0xFF, chunk);
                if ((seq & 0x0F) == 0 || seq >= blocks) log("Block " + seq + " / " + blocks + " OK");
            }
            in.close();
            DiagEngine.uds().transferExit();
            markPhase(2);
            log("Transfer complete — " + seq + " blocks");

            // ---- phase 3: reset --------------------------------------------
            DiagEngine.uds().ecuReset(0x01);
            markPhase(3);
            log("ECU Reset — flashing sequence completed");
            db.putInput(Session.sessionKey, "flash",
                    Session.selectedEcuCode + "|" + binName, "Completed " + seq + " blocks");
            result(true, "ECU Flashing Completed",
                    binName + " programmed to " + Session.selectedEcuCode + " ("
                            + seq + " blocks). Do not switch ignition off for 30 s.");
            return;
        } catch (UdsClient.UdsError e) {
            int phase = phaseDone + 1;
            String msg = "ECU refused — NRC " + String.format("0x%02X", e.nrc.code)
                    + " (" + e.nrc.name + ")\n" + e.nrc.userHint
                    + "\n\nProgramming needs the OEM memory map + security access for this ECU.";
            log("NRC " + String.format("0x%02X", e.nrc.code) + " — transfer aborted at true ECU refusal");
            fail(phase, msg);
            db.putInput(Session.sessionKey, "flash", Session.selectedEcuCode + "|" + binName,
                    "Aborted NRC " + String.format("0x%02X", e.nrc.code));
        } catch (Exception e) {
            fail(0, "Transfer failed: "
                    + (e.getMessage() == null ? String.valueOf(e) : e.getMessage()));
        }
    }

    private void markPhase(final int upto) {
        phaseDone = upto;
        runOnUiThread(new Runnable() {
            public void run() {
                for (int i = 0; i <= upto && i < 4; i++) {
                    seg[i].setBackgroundResource(R.drawable.bg_segment_green);
                    segCheck[i].setVisibility(View.VISIBLE);
                }
            }
        });
    }

    private void log(final String msg) {
        UdsLog.log(this, "INFO", msg);
        runOnUiThread(new Runnable() {
            public void run() {
                TextView line = Ui.tv(FlashActivity.this,
                        String.valueOf(logNo++) + "   "
                                + new SimpleDateFormat("HH:mm:ss", Locale.US).format(new Date())
                                + "   " + msg,
                        12.5f, msg.startsWith("NRC") ? 0xFFD32F2F : 0xFF2E9E43, false);
                logBox.addView(line);
                final ScrollView sc = (ScrollView) findViewById(R.id.scroll);
                if (sc != null) sc.post(new Runnable() {
                    public void run() { sc.fullScroll(View.FOCUS_DOWN); }
                });
            }
        });
    }

    private void fail(int phase, final String msg) {
        result(false, phase == 0 ? "Pre-check failed" : "Flashing Aborted", msg);
    }

    private void result(final boolean ok, final String title, final String msg) {
        runOnUiThread(new Runnable() {
            public void run() {
                Ui.resultDialog(FlashActivity.this,
                        ok ? R.drawable.ic_flash_success : R.drawable.ic_warn,
                        title, msg, "Done", null).show();
            }
        });
    }
}
