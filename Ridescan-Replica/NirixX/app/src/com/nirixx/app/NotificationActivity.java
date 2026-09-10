package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.db.Db;

/** Notifications — the truthful state of this installation.  Push-style dealer
 *  alerts arrive only once the DMS backend is integrated (documented gap);
 *  until then this page reflects what is actually true on the device. */
public class NotificationActivity extends BaseActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Notifications");
        wireBack();
        Db db = Db.get(this);
        LinearLayout content = (LinearLayout) findViewById(R.id.content);
        content.addView(Ui.section(this, "STATUS"));

        add(content, "Installed build",
                "NirixX " + db.config("app_version", "V 1.6.3")
                        + "  ·  dealer " + Session.dealerCode + " (" + Session.userType + ")",
                "now", false);
        add(content, "VCI",
                Session.vciConnected ? ("Connected: " + Session.vciName)
                        : "No VCI connected — use VCI Connect to pair the NirixiLINK.",
                "now", Session.vciConnected);
        add(content, "Pending diagnostic logs",
                db.logsToday() + " bus log lines recorded today (stored locally; DMS sync pending).",
                "today", false);

        content.addView(Ui.section(this, "DEALER ALERTS"));
        LinearLayout note = Ui.card(this);
        note.addView(Ui.tv(this,
                "Dealer alerts (campaigns, firmware notices, flash-file releases) are delivered by "
                        + "the DMS backend. That integration is pending — see MISSING_DEPENDENCIES.md — "
                        + "so no alerts are shown here rather than invented ones.",
                12.5f, 0xFF5A6472, false));
        content.addView(note);
    }

    private void add(LinearLayout content, String title, String body, String when, boolean green) {
        LinearLayout card = Ui.card(this);
        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(android.view.Gravity.CENTER_VERTICAL);
        View dot = new View(this);
        dot.setBackground(Ui.roundRect(green ? 0xFF2E9E43 : 0xFF9AA6B4, 20, this));
        LinearLayout.LayoutParams dp = new LinearLayout.LayoutParams(Ui.dp(this, 8), Ui.dp(this, 8));
        dp.setMargins(0, 0, Ui.dp(this, 8), 0);
        top.addView(dot, dp);
        top.addView(Ui.tv(this, title, 14f, 0xFF141B2E, true), new LinearLayout.LayoutParams(0, -2, 1f));
        top.addView(Ui.tv(this, when, 11f, 0xFF9AA6B4, false));
        card.addView(top);
        TextView b = Ui.tv(this, body, 12.5f, 0xFF5A6472, false);
        b.setPadding(0, Ui.dp(this, 6), 0, 0);
        card.addView(b);
        content.addView(card);
    }
}
