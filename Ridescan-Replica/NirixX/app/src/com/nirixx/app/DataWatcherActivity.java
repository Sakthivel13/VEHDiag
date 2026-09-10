package com.nirixx.app;

import android.os.Bundle;
import android.os.Handler;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.Obd;
import java.util.Locale;

/** Big-value watch panel.  Channels are polled from the vehicle with the real
 *  SAE J1979 PIDs; without a live link they stay at "—" and the screen says
 *  why.  Nothing is randomised. */
public class DataWatcherActivity extends BaseActivity {
    private final Handler h = new Handler();
    private boolean running = true;
    private TextView v1, v2, v3;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Data Watcher");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);
        content.addView(Ui.section(this, "WATCH CHANNELS" + (DiagOps.live() ? "  ·  LIVE" : "")));

        if (!DiagOps.live()) {
            LinearLayout warn = Ui.card(this);
            warn.addView(Ui.tv(this, "NO LIVE VCI LINK", 12f, 0xFFB26A00, true));
            warn.addView(Ui.tv(this, "Channels hold at — until a NirixiLINK is connected.",
                    12.5f, 0xFF5A6472, false));
            content.addView(warn);
        }

        LinearLayout card = Ui.card(this);
        v1 = watchRow(card, "Engine Speed", "rpm");
        v2 = watchRow(card, "Control Module Voltage", "V");
        v3 = watchRow(card, "Vehicle Speed", "km/h");
        content.addView(card);
        tick();
    }

    private TextView watchRow(LinearLayout parent, String name, String unit) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(android.view.Gravity.CENTER_VERTICAL);
        row.setPadding(0, Ui.dp(this, 14), 0, Ui.dp(this, 14));
        LinearLayout ll = new LinearLayout(this);
        ll.setOrientation(LinearLayout.VERTICAL);
        ll.addView(Ui.tv(this, name, 13f, 0xFF5A6472, true));
        row.addView(ll, new LinearLayout.LayoutParams(0, -2, 1f));
        TextView v = Ui.tv(this, "—", 30f, 0xFF0B8376, true);
        row.addView(v);
        row.addView(Ui.tv(this, " " + unit, 13f, 0xFF9AA6B4, false));
        parent.addView(row);
        return v;
    }

    private void tick() {
        if (!running) return;
        if (!DiagOps.live()) { h.postDelayed(new Runnable() { public void run() { tick(); } }, 1500); return; }
        final int[] pending = {3};
        final Runnable done = new Runnable() {
            public void run() {
                if (--pending[0] <= 0 && running)
                    h.postDelayed(new Runnable() { public void run() { tick(); } }, 700);
            }
        };
        DiagOps.obdPid(this, Obd.PID_ENGINE_RPM, new DiagOps.Cb<Double>() {
            public void ok(Double v) { v1.setText(String.valueOf((long) v.doubleValue())); done.run(); }
            public void err(String w, String d, Nrc n) { v1.setText("ERR"); done.run(); }
        });
        DiagOps.obdPid(this, Obd.PID_CONTROL_MODULE_V, new DiagOps.Cb<Double>() {
            public void ok(Double v) { v2.setText(String.format(Locale.US, "%.2f", v)); done.run(); }
            public void err(String w, String d, Nrc n) { v2.setText("ERR"); done.run(); }
        });
        DiagOps.obdPid(this, Obd.PID_VEHICLE_SPEED, new DiagOps.Cb<Double>() {
            public void ok(Double v) { v3.setText(String.valueOf(v.intValue())); done.run(); }
            public void err(String w, String d, Nrc n) { v3.setText("ERR"); done.run(); }
        });
    }

    @Override
    protected void onDestroy() {
        running = false;
        super.onDestroy();
    }
}
