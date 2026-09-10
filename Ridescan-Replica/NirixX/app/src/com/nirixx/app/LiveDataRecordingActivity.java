package com.nirixx.app;

import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.Obd;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Live Data Recording — real CSV sessions.
 *  RECORD polls the standard J1979 channels (RPM, TPS, module voltage, coolant,
 *  speed) and appends genuine samples to a timestamped CSV; tapping a session
 *  replays the recorded file.  Empty directory = no sessions, honestly. */
public class LiveDataRecordingActivity extends BaseActivity {

    private final Handler h = new Handler();
    private boolean recording = false, viewing = false;
    private FileWriter writer;
    private File current;
    private long t0;
    private LinearLayout content;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Live Data Recording");
        wireBack();
        content = (LinearLayout) findViewById(R.id.content);
        render();
    }

    private static File dir(android.content.Context c) {
        File d = new File(c.getExternalFilesDir(null), "Recordings");
        d.mkdirs();
        return d;
    }

    private void render() {
        content.removeAllViews();

        final TextView btn = Ui.navyBtn(this, recording ? "■ STOP RECORDING" : "● RECORD (needs live VCI)");
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 46));
        bp.setMargins(0, 0, 0, Ui.dp(this, 10));
        content.addView(btn, bp);
        btn.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { toggle(btn); }
        });

        content.addView(Ui.section(this, "RECORDED SESSIONS"));
        File[] files = dir(this).listFiles();
        int count = 0;
        if (files != null) {
            for (int i = files.length - 1; i >= 0; i--) {   // newest last modified first
                final File f = files[i];
                if (!f.getName().endsWith(".csv")) continue;
                count++;
                LinearLayout card = Ui.card(this);
                LinearLayout top = new LinearLayout(this);
                top.setOrientation(LinearLayout.HORIZONTAL);
                top.setGravity(android.view.Gravity.CENTER_VERTICAL);
                top.addView(Ui.tv(this, f.getName(), 13.5f, 0xFF141B2E, true),
                        new LinearLayout.LayoutParams(0, -2, 1f));
                top.addView(Ui.chip(this, "▶ Open", R.drawable.bg_chip, 0xFF0B8376));
                card.addView(top);
                TextView meta = Ui.tv(this, f.length() + " bytes", 12f, 0xFF5A6472, false);
                meta.setPadding(0, Ui.dp(this, 4), 0, 0);
                card.addView(meta);

                final LinearLayout graph = new LinearLayout(this);
                graph.setOrientation(LinearLayout.VERTICAL);
                graph.setBackgroundResource(R.drawable.bg_console);
                graph.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));
                graph.setVisibility(View.GONE);
                final TextView gtxt = Ui.tv(this, "", 11f, 0xFF8FD6A4, false);
                gtxt.setTypeface(android.graphics.Typeface.MONOSPACE);
                graph.addView(gtxt);
                card.addView(graph);

                card.setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) {
                        if (graph.getVisibility() == View.VISIBLE) {
                            graph.setVisibility(View.GONE);
                            return;
                        }
                        graph.setVisibility(View.VISIBLE);
                        showFile(f, gtxt);
                    }
                });
                content.addView(card);
            }
        }
        if (count == 0) {
            LinearLayout empty = Ui.card(this);
            empty.addView(Ui.tv(this, "No recordings yet. Connect a VCI, record a stream, and it "
                    + "shows up here with its real size.", 13f, 0xFF5A6472, false));
            content.addView(empty);
        }
    }

    /** Print the recorded CSV (real file content), tail-capped for the screen. */
    private void showFile(File f, TextView out) {
        StringBuilder sb = new StringBuilder();
        try {
            BufferedReader br = new BufferedReader(new FileReader(f));
            String line;
            int lines = 0;
            java.util.LinkedList<String> tail = new java.util.LinkedList<String>();
            while ((line = br.readLine()) != null) {
                tail.add(line);
                if (tail.size() > 18) tail.removeFirst();
                lines++;
            }
            br.close();
            sb.append(f.getName()).append("  ·  ").append(String.valueOf(lines)).append(" samples\n");
            for (String l : tail) sb.append(l).append('\n');
            if (lines > 18) sb.append("— tail view; full file at ")
                    .append(f.getAbsolutePath()).append(" —");
        } catch (Exception e) {
            sb.append("read error: ").append(e.getMessage());
        }
        out.setText(sb.toString());
    }

    private void toggle(TextView btn) {
        if (recording) {
            recording = false;
            try { if (writer != null) writer.close(); } catch (Exception ignored) { }
            writer = null;
            toast("Saved " + (current == null ? "" : current.getName()));
            render();
            return;
        }
        if (!DiagOps.live()) { toast("No VCI link established — nothing real to record"); return; }
        try {
            String name = "REC_" + new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US)
                    .format(new Date()) + ".csv";
            current = new File(dir(this), name);
            writer = new FileWriter(current);
            writer.write("t_s,rpm,tps_pct,batt_v,coolant_c,speed_kmh\n");
            t0 = System.currentTimeMillis();
            recording = true;
            btn.setText("■ STOP RECORDING");
            sampleLoop();
        } catch (Exception e) {
            toast("Cannot start recording: " + e.getMessage());
        }
    }

    private void sampleLoop() {
        if (!recording || writer == null || !DiagOps.live()) return;
        final double[] vals = {Double.NaN, Double.NaN, Double.NaN, Double.NaN, Double.NaN};
        final int[] pids = {Obd.PID_ENGINE_RPM, Obd.PID_THROTTLE_POSITION,
                Obd.PID_CONTROL_MODULE_V, Obd.PID_ENGINE_COOLANT_TEMP, Obd.PID_VEHICLE_SPEED};
        final int[] pending = {pids.length};
        for (int i = 0; i < pids.length; i++) {
            final int idx = i;
            DiagOps.obdPid(this, pids[i], new DiagOps.Cb<Double>() {
                public void ok(Double v) { vals[idx] = v.doubleValue(); step(); }
                public void err(String w, String d, Nrc n) { step(); }
                private void step() {
                    if (--pending[0] > 0) return;
                    long t = (System.currentTimeMillis() - t0) / 1000;
                    StringBuilder sb = new StringBuilder();
                    sb.append(t);
                    for (int k = 0; k < vals.length; k++) {
                        sb.append(',');
                        if (!Double.isNaN(vals[k]))
                            sb.append(String.format(Locale.US, "%.2f", vals[k]));
                    }
                    sb.append('\n');
                    try { writer.write(sb.toString()); writer.flush(); } catch (Exception ignored) { }
                    if (recording) h.postDelayed(new Runnable() {
                        public void run() { sampleLoop(); }
                    }, 400);
                }
            });
        }
    }

    @Override
    protected void onDestroy() {
        recording = false;
        viewing = false;
        try { if (writer != null) writer.close(); } catch (Exception ignored) { }
        super.onDestroy();
    }
}
