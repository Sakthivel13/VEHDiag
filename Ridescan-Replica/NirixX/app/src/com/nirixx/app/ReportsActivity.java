package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import com.nirixx.app.db.Db;
import java.io.File;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** Reports hub — generate new reports and browse the ones already produced
 *  (persisted in the vhr_reports table + Reports/ folder). */
public class ReportsActivity extends BaseActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Reports");
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        content.addView(Ui.crumbs(this, new String[]{"Home", "Reports"}));
        content.addView(Ui.sectionBar(this, "GENERATE NEW REPORT", null));

        Object[][] reps = new Object[][]{
            {"Diagnostic Report", "DTCs, live data snapshot and flash feedback for the session",
                    Integer.valueOf(R.drawable.ic_doc), DiagnosticReportActivity.class},
            {"Vehicle Health Report (VHR)", "Dealer / Diagnostic / IO Control / Physical / Summary + PDF",
                    Integer.valueOf(R.drawable.vehicle_health_report), VhrActivity.class},
            {"Battery Health Report", "State of health, voltage and CCA analysis",
                    Integer.valueOf(R.drawable.battery_health_report), BatteryHealthActivity.class},
        };
        for (int i = 0; i < reps.length; i++) {
            final Object[] rp = reps[i];
            LinearLayout row = Ui.listRow(this, ((Integer) rp[2]).intValue(), (String) rp[0], (String) rp[1], true);
            row.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14));
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { go((Class<?>) rp[3]); }
            });
            content.addView(row);
        }

        content.addView(Ui.sectionBar(this, "GENERATED REPORTS", null));
        List<String[]> rows = Db.get(this).vhrReports();
        if (rows.isEmpty()) {
            LinearLayout empty = Ui.card(this);
            empty.addView(Ui.tv(this, "No reports generated yet", 14f, 0xFF1A2138, true));
            empty.addView(Ui.tv(this, "Run a Vehicle Health Report — the PDF lands here and in File Viewer.",
                    12.5f, 0xFF5A6472, false));
            content.addView(empty);
            return;
        }
        SimpleDateFormat df = new SimpleDateFormat("dd MMM yyyy, HH:mm", Locale.US);
        for (int i = 0; i < rows.size(); i++) {
            final String[] r = rows.get(i);   // session_key, vehicle_id, vin, path, verdict, created
            File f = new File(r[3]);
            String sub = r[2] + "  ·  " + r[4] + "  ·  " + df.format(new Date(Long.parseLong(r[5])))
                    + (f.exists() ? "  ·  " + (f.length() / 1024) + " KB" : "");
            LinearLayout row = Ui.listRow(this, R.drawable.ic_doc, f.getName(), sub, false);
            row.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    Ui.dialog(ReportsActivity.this, new File(r[3]).getName(),
                            "VIN: " + r[2] + "\nVerdict: " + r[4] + "\nPath: " + r[3]
                                    + "\n\nOpen it from File Viewer › REPORTS.",
                            "OK", null, null, null).show();
                }
            });
            content.addView(row);
        }
    }
}
