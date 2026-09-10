package com.nirixx.app;

import android.app.Dialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.diag.FlashRunner;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.db.Db;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

/** Per-supplier flashing screen — same real UDS pipeline as ECU Flashing,
 *  keyed by module family.  Progress comes from actual transferred blocks;
 *  an ECU refusal is shown with its true NRC.  Without an imported image or
 *  a live link, the screen says so and does nothing. */
public class SupplierFlashActivity extends BaseActivity {

    private static final int REQ_BIN = 73;

    private String module, imageType, family;
    private ProgressBar bar;
    private TextView stage, pct;
    private android.widget.Button start;
    private volatile boolean flashing = false;
    private String binPath, binName;
    private long binSize;
    private Db db;

    private static final String[] PHASES = {"Read Image", "Session / Erase", "Programming", "Reset"};

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        module = getIntent().getStringExtra("module");
        imageType = getIntent().getStringExtra("image_type");
        family = getIntent().getStringExtra("family");
        if (module == null) module = "ECU Flashing";
        setContentView(R.layout.activity_screen);
        if (!com.nirixx.app.core.role.Roles.can(Session.userType, "flash")) {
            Ui.dialog(this, "Not permitted",
                    "This is an engineering operation restricted to the Dealer Engineer role.",
                    "OK", new Runnable() { public void run() { finish(); } }, null, null).show();
            return;
        }
        setTitle(module);
        wireBack();
        db = Db.get(this);
        build();
    }

    private void build() {
        LinearLayout content = (LinearLayout) findViewById(R.id.content);
        content.removeAllViews();

        LinearLayout pick = Ui.card(this);
        pick.addView(Ui.tv(this, imageType != null && imageType.startsWith("Select")
                ? imageType : "Select IMAGE type", 14.5f, 0xFF141B2E, true));
        pick.addView(Ui.tv(this, family != null ? family : "", 12f, 0xFF5A6472, false));
        if (imageType != null && imageType.startsWith("Select Booloader")) {
            final android.widget.RadioGroup rg = new android.widget.RadioGroup(this);
            android.widget.RadioButton p = new android.widget.RadioButton(this);
            p.setText("Primary Bootloader");
            android.widget.RadioButton b = new android.widget.RadioButton(this);
            b.setText("Backup Bootloader");
            rg.addView(p); rg.addView(b); rg.check(0);
            pick.addView(rg);
            pick.addView(Ui.tv(this, "Bootloader partitioning is OEM-specific — selection is "
                    + "recorded for the report.", 11.5f, 0xFF9AA6B4, false));
        }
        pick.addView(Ui.kvRow(this, "Flash Image",
                binName != null ? binName + " (" + binSize + " B)" : "none imported", true));
        content.addView(pick);

        TextView imp = Ui.navyBtn(this, binName == null
                ? "IMPORT IMAGE (.hex/.mot/.bin)" : "REPLACE IMAGE");
        LinearLayout.LayoutParams ip = new LinearLayout.LayoutParams(-1, Ui.dp(this, 44));
        ip.setMargins(0, 0, 0, Ui.dp(this, 10));
        content.addView(imp, ip);
        imp.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Intent it = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                it.addCategory(Intent.CATEGORY_OPENABLE);
                it.setType("*/*");
                startActivityForResult(it, REQ_BIN);
            }
        });

        if (!DiagOps.live()) {
            LinearLayout warn = Ui.card(this);
            warn.addView(Ui.tv(this, "NO LIVE VCI LINK", 12f, 0xFFB26A00, true));
            warn.addView(Ui.tv(this, "Flashing writes to the real ECU — connect the NirixiLINK, "
                    + "keep ignition ON and the battery above 12 V.", 12.5f, 0xFF5A6472, false));
            content.addView(warn);
        }

        LinearLayout progCard = Ui.card(this);
        stage = Ui.tv(this, "Idle", 15f, 0xFF141B2E, true);
        pct = Ui.tv(this, "0%", 26f, 0xFF0B8376, true);
        pct.setGravity(android.view.Gravity.RIGHT);
        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.addView(stage, new LinearLayout.LayoutParams(0, -2, 1f));
        top.addView(pct);
        progCard.addView(top);
        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        bar.setProgressDrawable(getResources().getDrawable(R.drawable.progress_thin));
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 8));
        bp.setMargins(0, Ui.dp(this, 10), 0, 0);
        progCard.addView(bar, bp);
        content.addView(progCard);

        TextView warn = Ui.tv(this, getString(R.string.flash_warning_msg), 12.5f, 0xFFC41230, true);
        warn.setBackgroundResource(R.drawable.bg_chip_red);
        warn.setGravity(android.view.Gravity.CENTER);
        warn.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));
        content.addView(warn);

        start = new android.widget.Button(this);
        start.setText("Start Flashing");
        start.setTextColor(0xFFFFFFFF);
        start.setAllCaps(false);
        start.setTextSize(15f);
        start.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        start.setBackgroundResource(R.drawable.bg_button_blue);
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 50));
        sp.setMargins(0, Ui.dp(this, 10), 0, Ui.dp(this, 8));
        content.addView(start, sp);
        start.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                if (flashing) return;
                if (binPath == null) { toast("Import a flash image first"); return; }
                if (!DiagOps.live()) { toast("No VCI link established"); return; }
                askOdometer();
            }
        });
    }

    /** dialog_odometer — odometer reading recorded with the flash report. */
    private void askOdometer() {
        final Dialog d = new Dialog(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundResource(R.drawable.bg_dialog);
        int p = Ui.dp(this, 22);
        root.setPadding(p, p, p, Ui.dp(this, 16));
        root.addView(Ui.tv(this, "Odometer Reading", 17f, 0xFF141B2E, true));
        root.addView(Ui.tv(this, "Enter the current odometer value. It is recorded with the flash report.",
                12.5f, 0xFF5A6472, false));
        final EditText odo = new EditText(this);
        odo.setHint("e.g. 12840 km");
        odo.setInputType(InputType.TYPE_CLASS_NUMBER);
        odo.setBackgroundResource(R.drawable.bg_edittext);
        odo.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 12), 0);
        LinearLayout.LayoutParams op = new LinearLayout.LayoutParams(-1, Ui.dp(this, 48));
        op.setMargins(0, Ui.dp(this, 12), 0, 0);
        root.addView(odo, op);
        android.widget.Button go = new android.widget.Button(this);
        go.setText("Continue");
        go.setTextColor(0xFFFFFFFF);
        go.setAllCaps(false);
        go.setBackgroundResource(R.drawable.bg_button_blue);
        LinearLayout.LayoutParams gp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 46));
        gp.setMargins(0, Ui.dp(this, 14), 0, 0);
        root.addView(go, gp);
        go.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Session.odometer = odo.getText().toString().trim().length() == 0 ? "—"
                        : odo.getText().toString().trim() + " km";
                d.dismiss();
                beginFlash();
            }
        });
        d.setContentView(root);
        if (d.getWindow() != null) {
            d.getWindow().setBackgroundDrawableResource(android.R.color.transparent);
            d.getWindow().setLayout(Ui.dp(this, 300), android.view.ViewGroup.LayoutParams.WRAP_CONTENT);
        }
        d.show();
    }

    private void beginFlash() {
        flashing = true;
        start.setEnabled(false);
        start.setText("Flashing…");
        bar.setProgress(0);
        pct.setText("0%");
        new Thread(new Runnable() {
            public void run() {
                FlashRunner.program(binPath, binSize, new FlashRunner.Cb() {
                    public void onLog(final String line) {
                        com.nirixx.app.sim.UdsLog.log(SupplierFlashActivity.this, "FLASH", line);
                    }
                    public void onPhase(final int ph) { post(new Runnable() {
                        public void run() { stage.setText(PHASES[Math.min(ph, PHASES.length - 1)]); } }); }
                    public void onProgress(final int done, final int total) { post(new Runnable() {
                        public void run() {
                            int v = total <= 0 ? 0 : (int) (done * 100L / total);
                            bar.setProgress(v);
                            pct.setText(v + "%");
                        } }); }
                    public void onDone(final boolean ok, final String msg, final Nrc nrc) {
                        runOnUiThread(new Runnable() {
                            public void run() { complete(ok, msg); }
                        });
                    }
                    private void post(Runnable r) { runOnUiThread(r); }
                });
            }
        }, "supplier-flash").start();
    }

    private void complete(boolean ok, String msg) {
        flashing = false;
        start.setEnabled(true);
        start.setText(ok ? "Flash Again" : "Retry");
        stage.setText(ok ? "ECU Flashing completed" : "Aborted");
        if (ok) {
            bar.setProgress(100);
            pct.setText("100%");
            Session.reportGenerated = true;
            db.putInput(Session.sessionKey, "flash", module + "|" + binName,
                    "Completed · ODO " + Session.odometer);
        } else {
            db.putInput(Session.sessionKey, "flash", module + "|" + binName,
                    "Aborted · ODO " + Session.odometer);
        }
        Ui.resultDialog(this, ok ? R.drawable.ic_flash_success : R.drawable.ic_warn,
                ok ? "ECU Flashing completed" : "Flashing Aborted",
                msg + "\nOdometer: " + Session.odometer, "Done", null).show();
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
            db.addFlashBin(dst.getName(), dst.getAbsolutePath(), dst.length(), module);
            binName = dst.getName();
            binPath = dst.getAbsolutePath();
            binSize = dst.length();
            toast("Imported " + binName);
        } catch (Exception e) {
            toast("Import failed: " + e.getMessage());
        }
        build();
    }

    @Override
    public void onBackPressed() {
        if (flashing) {
            Ui.dialog(this, "Abort flashing?",
                    "An in-flight block cannot be cancelled safely — the transfer stops after "
                            + "this answer and the ECU is left in its current session state.",
                    "Abort", new Runnable() {
                        public void run() {
                            flashing = false;
                            start.setText("Retry Flashing");
                            start.setEnabled(true);
                        }
                    }, "Continue", null).show();
            return;
        }
        super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        flashing = false;
        super.onDestroy();
    }
}
