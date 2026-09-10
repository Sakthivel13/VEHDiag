package com.nirixx.app;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Account & session details — backed by the users/roles/configs tables. */
public class AccountActivity extends BaseActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Account Details");
        LinearLayout content = (LinearLayout) findViewById(R.id.content);
        Session.ensureSession(this);

        content.addView(Ui.sectionBar(this, "DEALER PROFILE", null));
        LinearLayout card = Ui.card(this);
        card.addView(Ui.kvRow(this, "Dealership", Session.dealerName, false));
        card.addView(Ui.kvRow(this, "Dealer Code", Session.dealerCode, false));
        card.addView(Ui.kvRow(this, "Email", Session.dealerEmail.length() > 0 ? Session.dealerEmail : "—", false));
        card.addView(Ui.kvRow(this, "Branch ID", Session.dealerBranch.length() > 0 ? Session.dealerBranch : "—", false));
        card.addView(Ui.kvRow(this, "Phone", Session.dealerPhone.length() > 0 ? Session.dealerPhone : "—", false));
        card.addView(Ui.kvRow(this, "Designation", Session.userType, true));
        content.addView(card);

        content.addView(Ui.sectionBar(this, "APPLICATION & SESSION", null));
        LinearLayout app = Ui.card(this);
        app.addView(Ui.kvRow(this, "App Version", "1.6.3 (build 14)", false));
        app.addView(Ui.kvRow(this, "Signed in as", Session.userType, false));
        app.addView(Ui.kvRow(this, "Session ID", Session.sessionKey == null ? "—" : Session.sessionKey, false));
        app.addView(Ui.kvRow(this, "Connectivity", Session.connectivity, false));
        app.addView(Ui.kvRow(this, "VCI", Session.vciConnected
                ? (Session.vciName + "  ·  fw " + Session.vciFw) : "Not connected", false));
        app.addView(Ui.kvRow(this, "Vehicle", Session.selectedVehicle + "  ·  " + Session.selectedVin, true));
        content.addView(app);

        content.addView(Ui.sectionBar(this, "MORE TOOLS", null));
        Object[][] tools = new Object[][]{
            {"Dealer Information", DealerInformationActivity.class},
            {"File Viewer", FileViewerActivity.class},
            {"System Monitoring", SystemMonitoringActivity.class},
            {"Physical Evaluation", PhysicalEvaluationActivity.class},
            {"Data Watcher", DataWatcherActivity.class},
            {"App Update", UpdateDescriptionActivity.class},
        };
        for (int i = 0; i < tools.length; i++) {
            final Object[] t = tools[i];
            LinearLayout row = Ui.listRow(this, R.drawable.setting_1, (String) t[0], "", true);
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { go((Class<?>) t[1]); }
            });
            content.addView(row);
        }

        final TextView rec = Ui.navyBtn(this, ScreenRecordOverlayService.recording
                ? "Stop Session Capture" : "Start Session Capture");
        rec.setBackgroundResource(R.drawable.bg_box_outline);
        rec.setTextColor(0xFF14276F);
        LinearLayout.LayoutParams recp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 48));
        recp.setMargins(0, Ui.dp(this, 12), 0, 0);
        content.addView(rec, recp);
        content.addView(Ui.tv(this, "Capture indicator marks this diagnostic session's active "
                + "window in the log. On-screen video recording (MediaProjection) is tracked in "
                + "MISSING_DEPENDENCIES.md and is not claimed.", 11.5f, 0xFF9AA3B4, false));
        rec.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                android.content.Intent it = new android.content.Intent(AccountActivity.this, ScreenRecordOverlayService.class);
                if (!ScreenRecordOverlayService.recording) {
                    startService(it);
                    rec.setText("Stop Session Capture");
                    toast("Session capture indicator ON (timeline marker only)");
                } else {
                    it.setAction("stop");
                    startService(it);
                    rec.setText("Start Session Capture");
                    toast("Session capture indicator OFF");
                }
            }
        });

        TextView out = Ui.navyBtn(this, "Logout");
        out.setBackgroundResource(R.drawable.bg_button_red);
        LinearLayout.LayoutParams op = new LinearLayout.LayoutParams(-1, Ui.dp(this, 48));
        op.setMargins(0, Ui.dp(this, 10), 0, Ui.dp(this, 8));
        content.addView(out, op);
        out.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Ui.dialog(AccountActivity.this, "Logout?",
                        "You will need to sign in again to use diagnostic functions.",
                        "Logout", new Runnable() {
                            public void run() {
                                Session.dealerEmail = "";
                                Session.vciConnected = false;
                                Session.vciName = "";
                                Intent it = new Intent(AccountActivity.this, LoginActivity.class);
                                it.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK | Intent.FLAG_ACTIVITY_NEW_TASK);
                                startActivity(it);
                                finish();
                            }
                        }, "Cancel", null).show();
            }
        });
    }
}
