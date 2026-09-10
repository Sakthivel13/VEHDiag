package com.nirixx.app;

import android.app.Dialog;
import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Guided gear-learning procedure for applicable ECUs. */
public class GearLearningActivity extends BaseActivity {
    private final Handler h = new Handler();

    private static final String[] STEPS = {
        "Ensure engine is switched OFF and vehicle is on level ground.",
        "Turn ignition ON, do not start the engine.",
        "Keep throttle fully closed for 5 seconds.",
        "Initiate gear-learning from this screen.",
        "Rotate throttle slowly to WOT and release, twice.",
        "Wait for the ECU to confirm learned positions.",
        "Switch ignition OFF for 30 seconds to save values.",
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Gear Learning Procedure");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        content.addView(Ui.section(this, "PRE-CONDITIONS & PROCEDURE"));
        LinearLayout card = Ui.card(this);
        for (int i = 0; i < STEPS.length; i++) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            TextView n = Ui.tv(this, String.valueOf(i + 1), 13f, 0xFFFFFFFF, true);
            n.setBackground(Ui.roundRect(0xFF0B8376, 20, this));
            n.setGravity(android.view.Gravity.CENTER);
            LinearLayout.LayoutParams np = new LinearLayout.LayoutParams(Ui.dp(this, 26), Ui.dp(this, 26));
            np.setMargins(0, Ui.dp(this, 6), Ui.dp(this, 12), 0);
            row.addView(n, np);
            row.addView(Ui.tv(this, STEPS[i], 13.5f, 0xFF141B2E, false), new LinearLayout.LayoutParams(0, -2, 1f));
            card.addView(row);
        }
        content.addView(card);

        android.widget.Button begin = new android.widget.Button(this);
        begin.setText("Start Gear Learning");
        begin.setTextColor(0xFFFFFFFF);
        begin.setAllCaps(false);
        begin.setTextSize(15f);
        begin.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        begin.setBackgroundResource(R.drawable.bg_button_blue);
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 50));
        bp.setMargins(0, Ui.dp(this, 6), 0, Ui.dp(this, 8));
        content.addView(begin, bp);
        begin.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Ui.dialog(GearLearningActivity.this, "Start gear learning?",
                        "Confirm ignition is ON, engine OFF, throttle closed.",
                        "Start", new Runnable() {
                            public void run() { runLearn(); }
                        }, "Cancel", null).show();
            }
        });
    }

    private void runLearn() {
        // Initiation is a UDS routine (31 01 <rid>) whose id is not published
        // for these ECMs — instead of pretending, the app says exactly that.
        if (!com.nirixx.app.core.diag.DiagOps.live()) {
            Ui.resultDialog(this, R.drawable.ic_warn, "No VCI Link",
                    "Connect the NirixiLINK to run gear learning on the vehicle.",
                    "OK", null).show();
            return;
        }
        Ui.resultDialog(this, R.drawable.ic_warn, "Routine ID Pending",
                "Gear-learning is routine 31 01 <id> — the routine id is not published "
                        + "for this ECM yet (OEM definition pack required, see "
                        + "MISSING_DEPENDENCIES.md). No command was sent; the ECU state "
                        + "is unchanged.", "OK", null).show();
    }

    @Override
    protected void onDestroy() {
        h.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
}
