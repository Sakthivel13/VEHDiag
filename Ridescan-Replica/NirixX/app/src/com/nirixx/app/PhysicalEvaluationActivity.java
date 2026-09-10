package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.CompoundButton;
import android.widget.Switch;

/** Pre-service physical evaluation checklist (PhysicalEvaluation from the original). */
public class PhysicalEvaluationActivity extends BaseActivity {
    private static final String[] CHECKS = {
        "Odometer & VIN plate verified", "Battery terminals — clean & tight",
        "Wiring harness — no chafing or cuts", "OBD coupler pins — undamaged",
        "Ignition switch cycles cleanly", "Side-stand switch functional",
        "Fuses — main & ECU — intact", "No fuel leaks around injector line",
        "Intake & air filter — clean", "Ignition coil coupler — supplier revision noted",
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Physical Evaluation");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        content.addView(Ui.section(this, "WORKSHOP WALK-AROUND CHECKLIST"));
        for (int i = 0; i < CHECKS.length; i++) {
            LinearLayout card = Ui.card(this);
            LinearLayout top = new LinearLayout(this);
            top.setOrientation(LinearLayout.HORIZONTAL);
            top.setGravity(android.view.Gravity.CENTER_VERTICAL);
            top.addView(Ui.tv(this, CHECKS[i], 13.5f, 0xFF141B2E, false), new LinearLayout.LayoutParams(0, -2, 1f));
            Switch sw = new Switch(this);
            top.addView(sw);
            card.addView(top);
            content.addView(card);
        }

        android.widget.Button save = new android.widget.Button(this);
        save.setText("Save Evaluation");
        save.setTextColor(0xFFFFFFFF);
        save.setAllCaps(false);
        save.setTextSize(15f);
        save.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        save.setBackgroundResource(R.drawable.bg_button_blue);
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 50));
        sp.setMargins(0, Ui.dp(this, 6), 0, Ui.dp(this, 8));
        content.addView(save, sp);
        save.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Ui.resultDialog(PhysicalEvaluationActivity.this, R.drawable.ic_flash_success,
                        "Evaluation Saved", "Findings attached to the current session report.", "OK", null).show();
            }
        });
    }
}
