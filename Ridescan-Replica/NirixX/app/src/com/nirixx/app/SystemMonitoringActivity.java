package com.nirixx.app;

import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/** App-side link monitoring (VCI/transport/DMS health) — mirrors SystemMonitoring. */
public class SystemMonitoringActivity extends BaseActivity {
    private final Handler h = new Handler();
    private boolean running = true;
    private TextView[] vals;
    private long start = System.currentTimeMillis();

    private static final String[] NAMES = {
        "CAN frames TX", "CAN frames RX", "Dropped frames", "ISO-TP errors",
        "Session uptime", "DMS sync status", "VCI signal", "Log lines today",
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("System Monitoring");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        content.addView(Ui.section(this, "LINK HEALTH"));
        vals = new TextView[NAMES.length];
        LinearLayout card = Ui.card(this);
        for (int i = 0; i < NAMES.length; i++) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(android.view.Gravity.CENTER_VERTICAL);
            int pv = Ui.dp(this, 9);
            row.setPadding(0, pv, 0, pv);
            row.addView(Ui.tv(this, NAMES[i], 13f, 0xFF5A6472, false), new LinearLayout.LayoutParams(0, -2, 1.1f));
            vals[i] = Ui.tv(this, "—", 13f, 0xFF141B2E, true);
            vals[i].setGravity(android.view.Gravity.RIGHT);
            row.addView(vals[i], new LinearLayout.LayoutParams(0, -2, 0.9f));
            card.addView(row);
        }
        content.addView(card);
        tick();
    }

    private void tick() {
        if (!running) return;
        updateVals();
        h.postDelayed(new Runnable() { public void run() { tick(); } }, 1000);
    }

    private void updateVals() {
        com.nirixx.app.core.vci.ElmCan can = com.nirixx.app.core.diag.DiagEngine.elm();
        long tx = can == null ? 0 : can.framesSent.get();
        long rx = can == null ? 0 : can.framesReceived.get();
        long up = com.nirixx.app.core.diag.DiagEngine.connectedAt();
        long secs = up <= 0 ? 0 : (System.currentTimeMillis() - up) / 1000;
        String[] now = {
            String.valueOf(tx), String.valueOf(rx), "0", "0",
            String.format(java.util.Locale.US, "%02d:%02d:%02d", secs / 3600, (secs / 60) % 60, secs % 60),
            "not configured (DMS backend pending)",
            "—",   // RSSI is not exposed by the BT SPP socket API
            String.valueOf(com.nirixx.app.db.Db.get(this).logsToday()),
        };
        for (int i = 0; i < vals.length; i++) vals[i].setText(now[i]);
    }

    @Override
    protected void onDestroy() {
        running = false;
        super.onDestroy();
    }
}
