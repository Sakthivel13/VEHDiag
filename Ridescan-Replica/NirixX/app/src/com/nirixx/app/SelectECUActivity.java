package com.nirixx.app;

import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.db.Db;
import java.util.List;

/** Diagnostic Section page (reference "Select ECU"): vehicle image from the DB,
 *  live battery-voltage stream, DTC status and update tiles, then the ECU list
 *  with availability dots and expandable Manufacturer/Protocol/Emission. */
public class SelectECUActivity extends BaseActivity {

    private TextView batt;
    private final Handler h = new Handler();
    private boolean tick = true;
    private Db db;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Select ECU");
        db = Db.get(this);
        content();
        streamVolts();
    }

    private void content() {
        LinearLayout content = (LinearLayout) findViewById(R.id.content);
        content.removeAllViews();
        Db.Vehicle v = db.vehicle(Session.vehicleId);

        // ---- grey panel: vehicle image + status tiles ---------------------
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.HORIZONTAL);
        panel.setBackgroundResource(R.drawable.bg_card_grey);
        panel.setPadding(Ui.dp(this, 12), Ui.dp(this, 12), Ui.dp(this, 12), Ui.dp(this, 12));

        LinearLayout left = new LinearLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        left.setGravity(android.view.Gravity.CENTER);
        ImageView iv = new ImageView(this);
        iv.setImageResource(Ui.imgRes(this, v != null ? v.image : Session.vehicleImage));
        left.addView(iv, new LinearLayout.LayoutParams(Ui.dp(this, 150), Ui.dp(this, 120)));
        left.addView(Ui.tv(this, v != null ? v.model : Session.selectedVehicle, 13.5f, 0xFF1A2138, true));
        panel.addView(left, new LinearLayout.LayoutParams(0, -2, 1.15f));

        LinearLayout tiles = new LinearLayout(this);
        tiles.setOrientation(LinearLayout.VERTICAL);
        LinearLayout dtc = Ui.statTile(this, R.drawable.ic_engine,
                Session.dtcScanned ? (Session.faultsFound ? "Fault Codes Found" : "No Fault Codes")
                        : "DTC Status",
                Session.dtcScanned ? (Session.faultsFound ? "Tap DTC tile to review" : "Scanned — none stored")
                        : "Not scanned yet");
        ((TextView) dtc.getTag()).setTextColor(
                !Session.dtcScanned ? 0xFF5A6472 : Session.faultsFound ? 0xFFE53935 : 0xFF2E9E43);
        LinearLayout.LayoutParams m = new LinearLayout.LayoutParams(-1, -2);
        m.setMargins(0, 0, 0, Ui.dp(this, 8));
        tiles.addView(dtc, m);
        LinearLayout b = Ui.statTile(this, R.drawable.ic_battery_sm, "Battery Voltage",
                Session.batteryVolts > 0
                        ? String.format(java.util.Locale.US, "%.2f V", Session.batteryVolts)
                        : "—");
        batt = (TextView) b.getTag();
        tiles.addView(b, new LinearLayout.LayoutParams(m));
        tiles.addView(Ui.statTile(this, R.drawable.ic_refresh, "New Updates", "Available"),
                new LinearLayout.LayoutParams(m));
        panel.addView(tiles, new LinearLayout.LayoutParams(0, -2, 1f));
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(-1, -2);
        pp.setMargins(0, 0, 0, Ui.dp(this, 10));
        content.addView(panel, pp);

        dtc.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v2) {
                go(ECUDiagnosisActivity.class);
            }
        });

        // ---- Diagnostic bar + ECU list ------------------------------------
        content.addView(Ui.sectionBar(this, "Diagnostic", null));

        LinearLayout listCard = new LinearLayout(this);
        listCard.setOrientation(LinearLayout.VERTICAL);
        listCard.setBackgroundResource(R.drawable.bg_card);
        listCard.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 6));
        listCard.addView(Ui.tv(this, "Select ECU", 15.5f, 0xFF1A2138, true));

        LinearLayout legend = new LinearLayout(this);
        legend.setOrientation(LinearLayout.HORIZONTAL);
        legend.setGravity(android.view.Gravity.CENTER_VERTICAL);
        legend.setPadding(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
        legend.addView(Ui.dot(this, true));
        legend.addView(Ui.tv(this, " ECU is Available      ", 12.5f, 0xFF5A6472, false));
        legend.addView(Ui.dot(this, false));
        legend.addView(Ui.tv(this, " Bad Communication", 12.5f, 0xFF5A6472, false));
        listCard.addView(legend);

        List<Db.Ecu> ecus = db.ecus(Session.vehicleId);
        int i = 0;
        for (final Db.Ecu e : ecus) {
            final boolean ok = Session.vciConnected || e.sort <= 2;   // demo: first two always comm
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.VERTICAL);
            row.setBackgroundResource(R.drawable.bg_card_grey);
            row.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));

            LinearLayout head = new LinearLayout(this);
            head.setOrientation(LinearLayout.HORIZONTAL);
            head.setGravity(android.view.Gravity.CENTER_VERTICAL);
            ImageView ic = new ImageView(this);
            ic.setImageResource(e.code.startsWith("EMS") ? R.drawable.ic_engine
                    : e.code.startsWith("ICM") ? R.drawable.ic_monitor
                    : e.code.startsWith("BABS") ? R.drawable.ic_shield : R.drawable.ic_chip);
            head.addView(ic, new LinearLayout.LayoutParams(Ui.dp(this, 26), Ui.dp(this, 26)));
            head.addView(Ui.tv(this, "  " + e.name, 13.5f, 0xFF1A2138, true),
                    new LinearLayout.LayoutParams(0, -2, 1f));
            head.addView(Ui.dot(this, ok));
            TextView chev = Ui.tv(this, "\u203A", 22f, 0xFF3A4663, true);
            chev.setPadding(Ui.dp(this, 8), 0, 0, 0);
            head.addView(chev);
            row.addView(head);

            final LinearLayout detail = new LinearLayout(this);
            detail.setOrientation(LinearLayout.HORIZONTAL);
            detail.setVisibility(View.GONE);
            detail.setPadding(0, Ui.dp(this, 8), 0, 0);
            detail.addView(Ui.tv(this, "Manufacturer\n" + (e.manufacturer != null ? e.manufacturer : "—"),
                    12.5f, 0xFF5A6472, false), new LinearLayout.LayoutParams(0, -2, 1f));
            detail.addView(Ui.tv(this, "Protocol\n" + e.protocol, 12.5f, 0xFF3A4663, true),
                    new LinearLayout.LayoutParams(0, -2, 1f));
            detail.addView(Ui.tv(this, "Emission\n" + e.emission, 12.5f, 0xFF3A4663, true),
                    new LinearLayout.LayoutParams(0, -2, 1f));
            row.addView(detail);

            head.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v2) {
                    if (detail.getVisibility() == View.GONE) {
                        detail.setVisibility(View.VISIBLE);
                    } else {
                        openEcu(e);
                    }
                }
            });
            chev.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v2) { openEcu(e); }
            });

            LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(-1, -2);
            rp.setMargins(0, 0, 0, Ui.dp(this, 8));
            listCard.addView(row, rp);
        }
        content.addView(listCard);
    }

    private void openEcu(Db.Ecu e) {
        Session.selectEcu(e.id, e.name, e.code, e.tx, e.rx);
        Session.selectedFlashFile = db.flashFile(e.id);
        // re-point the live link at this ECU's CAN ids (reference per-ECU addressing)
        com.nirixx.app.core.diag.DiagOps.retuneToSessionEcu(this);
        com.nirixx.app.core.diag.DiagOps.startKeepAlive(this);
        go(ECUDiagnosisActivity.class);
    }

    /** Real rail voltage, only when a VCI is live; otherwise a literal "—". */
    private void streamVolts() {
        h.postDelayed(new Runnable() {
            public void run() {
                if (!tick) return;
                if (batt != null && !com.nirixx.app.core.diag.DiagOps.live()) {
                    batt.setText(Session.batteryVolts > 0
                            ? String.format(java.util.Locale.US, "%.2f V (last)", Session.batteryVolts)
                            : "—");
                } else if (batt != null && Session.batteryVolts > 0) {
                    batt.setText(String.format(java.util.Locale.US, "%.2f V", Session.batteryVolts));
                }
                h.postDelayed(this, 1500);
            }
        }, 1500);
    }

    @Override
    protected void onResume() { super.onResume(); tick = true; streamVolts(); }

    @Override
    protected void onPause() { tick = false; super.onPause(); }
}
