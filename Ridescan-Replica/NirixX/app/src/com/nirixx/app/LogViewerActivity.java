package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.db.Db;
import com.nirixx.app.sim.UdsLog;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** Live session log viewer — renders the UDS trace stored in the SQLite `logs`
 *  table for the current session (the same rows mirrored to the .txt log file). */
public class LogViewerActivity extends BaseActivity {

    private LinearLayout list;
    private String filter = "ALL";
    private List<String[]> rows;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Log Viewer");
        LinearLayout content = (LinearLayout) findViewById(R.id.content);
        Session.ensureSession(this);

        content.addView(Ui.crumbs(this, new String[]{"Home", "Log Viewer"}));

        LinearLayout meta = Ui.card(this);
        meta.addView(Ui.kvRow(this, "Session ID", Session.sessionKey, false));
        meta.addView(Ui.kvRow(this, "Connectivity", Session.connectivity, false));
        meta.addView(Ui.kvRow(this, "Log file", UdsLog.path(this), true));
        content.addView(meta);

        LinearLayout filters = new LinearLayout(this);
        filters.setOrientation(LinearLayout.HORIZONTAL);
        final String[] lv = {"ALL", "TX", "RX", "INFO"};
        for (int i = 0; i < lv.length; i++) {
            final String l = lv[i];
            TextView chip = Ui.chip(this, l, R.drawable.bg_chip_grey, 0xFF3A4663);
            chip.setPadding(Ui.dp(this, 14), Ui.dp(this, 6), Ui.dp(this, 14), Ui.dp(this, 6));
            chip.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { filter = l; render(); }
            });
            LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-2, -2);
            cp.setMargins(Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4), Ui.dp(this, 6));
            filters.addView(chip, cp);
        }
        content.addView(filters);

        LinearLayout cons = new LinearLayout(this);
        cons.setOrientation(LinearLayout.VERTICAL);
        cons.setBackgroundResource(R.drawable.bg_console);
        cons.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));
        list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        cons.addView(list);
        LinearLayout.LayoutParams kp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 340));
        kp.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 8));
        content.addView(cons, kp);

        rows = Db.get(this).sessionLogs(Session.sessionKey);
        render();

        TextView more = Ui.navyBtn(this, "OPEN FILE VIEWER");
        more.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(FileViewerActivity.class); }
        });
        content.addView(more);
    }

    private void render() {
        list.removeAllViews();
        if (rows == null || rows.isEmpty()) {
            list.addView(Ui.tv(this,
                    "No frames logged yet for this session.\nStart a VIN read / live data / flashing and come back.",
                    11.5f, 0xFF8A93A8, false));
            return;
        }
        SimpleDateFormat df = new SimpleDateFormat("HH:mm:ss.SSS", Locale.US);
        int shown = 0;
        for (int i = 0; i < rows.size(); i++) {
            String[] l = rows.get(i);   // ts, dir, payload
            if (!"ALL".equals(filter) && !filter.equals(l[1])) continue;
            int color = "TX".equals(l[1]) ? 0xFF9AD0FF
                    : "RX".equals(l[1]) ? 0xFF9BEFC4 : 0xFFC9CFDE;
            String line = df.format(new Date(Long.parseLong(l[0]))) + " I/: "
                    + ("TX".equals(l[1]) || "RX".equals(l[1]) ? l[1] + ": --> " : "") + l[2];
            TextView t = Ui.tv(this, line, 10.5f, color, false);
            t.setTypeface(android.graphics.Typeface.MONOSPACE);
            t.setPadding(0, Ui.dp(this, 3), 0, Ui.dp(this, 3));
            list.addView(t);
            if (++shown >= 200) break;
        }
        if (shown == 0) {
            list.addView(Ui.tv(this, "Nothing matches the " + filter + " filter.", 11f, 0xFF8A93A8, false));
        }
    }
}
