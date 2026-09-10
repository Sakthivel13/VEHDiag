package com.nirixx.app;

import android.app.Dialog;
import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

public class DiagnosticReportActivity extends BaseActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Diagnostic Report");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        android.widget.ImageView banner = new android.widget.ImageView(this);
        banner.setImageResource(R.drawable.vhr_banner_2);
        banner.setAdjustViewBounds(true);
        banner.setScaleType(android.widget.ImageView.ScaleType.FIT_CENTER);
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 160));
        bp.setMargins(0, 0, 0, Ui.dp(this, 12));
        banner.setBackgroundResource(R.drawable.bg_card);
        content.addView(banner, bp);

        content.addView(Ui.section(this, "SESSION SUMMARY"));
        LinearLayout veh = Ui.card(this);
        veh.addView(Ui.kvRow(this, "Vehicle", Session.selectedVehicle, false));
        veh.addView(Ui.kvRow(this, "VIN", Session.selectedVin, false));
        veh.addView(Ui.kvRow(this, "Variant", Session.selectedVariant, false));
        veh.addView(Ui.kvRow(this, "Flash File", Session.selectedFlashFile, false));
        veh.addView(Ui.kvRow(this, "ECU", Session.selectedEcu, false));
        veh.addView(Ui.kvRow(this, "VCI", Session.vciConnected ? Session.vciName : "Demo session", true));
        content.addView(veh);

        content.addView(Ui.section(this, "DTC FINDINGS"));
        LinearLayout dtc = Ui.card(this);
        if (Session.dtcsCleared > 0) {
            dtc.addView(Ui.kvRow(this, "DTCs at read", "5", false));
            dtc.addView(Ui.kvRow(this, "DTCs cleared", String.valueOf(Session.dtcsCleared), false));
            dtc.addView(Ui.kvRow(this, "DTCs after clear", "0", true));
        } else {
            for (int i = 0; i < Session.DTC_DATA.length; i++) {
                String[] d = Session.DTC_DATA[i];
                dtc.addView(Ui.kvRow(this, d[0], d[2], i == Session.DTC_DATA.length - 1));
            }
        }
        content.addView(dtc);

        content.addView(Ui.section(this, "IO CONTROL RESULTS"));
        LinearLayout io = Ui.card(this);
        io.addView(Ui.kvRow(this, "Fuel Pump Relay", "PASS", false));
        io.addView(Ui.kvRow(this, "Ignition Coil", "PASS", false));
        io.addView(Ui.kvRow(this, "MIL Lamp", "PASS", true));
        content.addView(io);

        content.addView(Ui.section(this, "FLASH FEEDBACK"));
        LinearLayout ff = Ui.card(this);
        ff.addView(Ui.kvRow(this, "Flash status", Session.reportGenerated ? "COMPLETED" : "NOT PERFORMED", false));
        ff.addView(Ui.kvRow(this, "Image", Session.selectedFlashFile, false));
        ff.addView(Ui.kvRow(this, "Duration", "1 min 08 s", true));
        content.addView(ff);

        Button view = new Button(this);
        view.setText("View PDF");
        view.setTextColor(0xFF0B8376);
        view.setAllCaps(false);
        view.setBackgroundResource(R.drawable.bg_button_outline);
        LinearLayout.LayoutParams vp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 46));
        vp.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 10));
        content.addView(view, vp);
        view.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                toast("PDF rendering is stubbed in the replica — report saved to /NirixX/Reports/");
            }
        });

        Button up = new Button(this);
        up.setText("Upload to DMS");
        up.setTextColor(0xFFFFFFFF);
        up.setAllCaps(false);
        up.setBackgroundResource(R.drawable.bg_button_blue);
        content.addView(up, new LinearLayout.LayoutParams(-1, Ui.dp(this, 48)));
        up.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                final Dialog d = Ui.progressDialog(DiagnosticReportActivity.this, "Uploading report to DMS…");
                d.show();
                new Handler().postDelayed(new Runnable() {
                    public void run() {
                        d.dismiss();
                        Ui.resultDialog(DiagnosticReportActivity.this, R.drawable.ic_flash_success,
                                "Uploaded", "Report synced to amsmssi.com/DMS/", "OK", null).show();
                    }
                }, 1400);
            }
        });
    }
}
