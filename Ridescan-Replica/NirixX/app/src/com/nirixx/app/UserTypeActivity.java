package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;

/** Role pick after login: Technician vs Service Advisor (matches UserTypeActivity). */
public class UserTypeActivity extends BaseActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Select User Type");
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        content.addView(Ui.section(this, "CONTINUE AS"));
        String[][] roles = new String[][]{
            {"Service Technician", "Full diagnostics, flashing and report generation access"},
            {"Service Advisor", "Reports, VHR generation and vehicle list management"},
            {"Dealer Admin", "Account, users, DMS sync and audit review"},
        };
        for (int i = 0; i < roles.length; i++) {
            final String[] r = roles[i];
            LinearLayout row = Ui.listRow(this, i == 0 ? R.drawable.setting_1 : (i == 1 ? R.drawable.vehicle_health_report : R.drawable.vci),
                    r[0], r[1], true);
            row.setPadding(Ui.dp(this, 18), Ui.dp(this, 16), Ui.dp(this, 18), Ui.dp(this, 16));
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    Session.userType = r[0];
                    go(HomeActivity.class);
                    finishAffinity();
                }
            });
            content.addView(row);
        }
    }
}
