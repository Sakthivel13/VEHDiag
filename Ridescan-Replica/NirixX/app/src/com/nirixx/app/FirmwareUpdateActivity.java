package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.core.diag.BatteryAssess;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.uds.Nrc;

/** VCI firmware page — honest inventory only.
 *  ELM327-class adapters expose version/identity but no published field-update
 *  channel; NirixiLINK service packs require the DMS distribution backend
 *  (documented dependency).  What IS real here: the adapter's own identity
 *  string (AT I) and its measured supply rail (AT RV). */
public class FirmwareUpdateActivity extends BaseActivity {

    private LinearLayout root;
    private String info = "";
    private double volts = -1;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        if (!com.nirixx.app.core.role.Roles.can(Session.userType, "vci_fw")) {
            Ui.dialog(this, "Not permitted",
                    "VCI firmware functions require the Dealer Engineer role.",
                    "OK", new Runnable() { public void run() { finish(); } }, null, null).show();
            return;
        }
        String dev = getIntent().getStringExtra("device");
        setTitle((dev == null || dev.length() == 0 ? "VCI" : dev) + " Firmware");
        wireBack();
        root = (LinearLayout) findViewById(R.id.content);
        render();
    }

    private void render() {
        root.removeAllViews();

        LinearLayout id = Ui.card(this);
        id.addView(Ui.tv(this, "IDENTITY (REPORTED BY DEVICE)", 12f, 0xFF5A6472, true));
        id.addView(Ui.kvRow(this, "Adapter", Session.vciName.length() > 0
                ? Session.vciName : "no adapter connected", false));
        id.addView(Ui.kvRow(this, "Firmware banner",
                Session.vciFw != null && Session.vciFw.length() > 0
                        ? Session.vciFw : "not read — connect the VCI", false));
        id.addView(Ui.kvRow(this, "AT I (live)", info.length() > 0 ? info
                : (DiagOps.live() ? "tap QUERY" : "no live link"), false));
        id.addView(Ui.kvRow(this, "Supply rail (AT RV, live)",
                volts > 0 ? BatteryAssess.fmt(volts) + " V"
                        : (DiagOps.live() ? "tap QUERY" : "no live link"), true));
        root.addView(id);

        TextView q = Ui.navyBtn(this, "QUERY CONNECTED ADAPTER");
        LinearLayout.LayoutParams qp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 46));
        qp.setMargins(0, 0, 0, Ui.dp(this, 10));
        root.addView(q, qp);
        q.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { query(); }
        });

        LinearLayout up = Ui.card(this);
        up.addView(Ui.tv(this, "FIRMWARE UPDATE", 12f, 0xFF5A6472, true));
        up.addView(Ui.tv(this,
                "No field-update package is published for this adapter family:\n"
                        + "  • ELM327-compatible clones carry fixed firmware — there is no "
                        + "documented bootloader protocol to drive from an app.\n"
                        + "  • NirixiLINK service packs ship through the DMS backend once it is "
                        + "integrated (see MISSING_DEPENDENCIES.md).\n\n"
                        + "This page never pretends to flash anything.", 12.5f, 0xFF5A6472, false));
        root.addView(up);
    }

    private void query() {
        if (!DiagOps.live()) { toast("No VCI link established"); return; }
        final android.app.Dialog d = Ui.progressDialog(this, "Querying adapter…");
        d.show();
        new Thread(new Runnable() {
            public void run() {
                final String i = com.nirixx.app.core.diag.DiagEngine.elm() == null ? ""
                        : com.nirixx.app.core.diag.DiagEngine.elm().adapterInfo();
                DiagOps.adapterVoltage(FirmwareUpdateActivity.this, new DiagOps.Cb<Double>() {
                    public void ok(Double v) { finish(i, v.doubleValue()); }
                    public void err(String w, String det, Nrc n) { finish(i, -1); }
                    private void finish(final String inf, final double vv) {
                        runOnUiThread(new Runnable() {
                            public void run() {
                                d.dismiss();
                                info = inf == null ? "" : inf;
                                volts = vv;
                                render();
                            }
                        });
                    }
                });
            }
        }).start();
    }
}
