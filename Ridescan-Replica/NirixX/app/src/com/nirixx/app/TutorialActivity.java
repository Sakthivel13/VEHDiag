package com.nirixx.app;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/** First-run tutorial: 3 slides with dots, Next / Skip, matching the original onboarding. */
public class TutorialActivity extends BaseActivity {
    private static final int[] SLIDES = new int[]{ R.drawable.tut_workshop, R.drawable.vciimage, R.drawable.welcome_bike };
    private static final String[] TITLES = new String[]{ "Your workshop, upgraded", "Connect via any NirixX VCI", "Flash, report & go" };
    private static final String[] SUBS = new String[]{
        "Read DTCs, stream live parameters and run actuator tests across every ECU supplier.",
        "Pair over Bluetooth Classic, BLE, Wi-Fi or USB — a real transport stack, with simulation built in.",
        "VIN-based flashing, vehicle health reports and DMS sync — one tool for the whole bay." };

    private LinearLayout dotStrip;
    private ImageView hero;
    private TextView title, sub, skip;
    private Button next;
    private int idx = 0;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setTheme(R.style.Theme_NirixX_Dark);
        setContentView(buildView());
        show(0);
    }

    private View buildView() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(0xFFF2F5F8);

        skip = Ui.tv(this, "Skip", 13f, 0xFF5A6472, true);
        int sp = Ui.dp(this, 18);
        skip.setPadding(sp, sp, sp, Ui.dp(this, 6));
        skip.setGravity(android.view.Gravity.RIGHT);
        root.addView(skip, new LinearLayout.LayoutParams(-1, -2));
        skip.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { finishTutorial(); }
        });

        hero = new ImageView(this);
        hero.setScaleType(ImageView.ScaleType.CENTER_CROP);
        root.addView(hero, new LinearLayout.LayoutParams(-1, 0, 1f));

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(Ui.dp(this, 26), Ui.dp(this, 20), Ui.dp(this, 26), Ui.dp(this, 20));
        root.addView(card, new LinearLayout.LayoutParams(-1, -2));

        dotStrip = new LinearLayout(this);
        dotStrip.setOrientation(LinearLayout.HORIZONTAL);
        card.addView(dotStrip);

        title = Ui.tv(this, "", 21f, 0xFF141B2E, true);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-2, -2);
        tp.setMargins(0, Ui.dp(this, 12), 0, 0);
        card.addView(title, tp);
        sub = Ui.tv(this, "", 13.5f, 0xFF5A6472, false);
        sub.setLineSpacing(1.3f, 1f);
        card.addView(sub, tp);

        next = new Button(this);
        next.setTextColor(0xFFFFFFFF);
        next.setTextSize(15f);
        next.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        next.setAllCaps(false);
        next.setBackgroundResource(R.drawable.bg_button_blue);
        LinearLayout.LayoutParams np = new LinearLayout.LayoutParams(-1, Ui.dp(this, 50));
        np.setMargins(0, Ui.dp(this, 18), 0, 0);
        card.addView(next, np);
        next.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                if (idx >= SLIDES.length - 1) finishTutorial(); else show(idx + 1);
            }
        });
        return root;
    }

    private void show(int i) {
        idx = i;
        hero.setImageResource(SLIDES[i]);
        title.setText(TITLES[i]);
        sub.setText(SUBS[i]);
        next.setText(i == SLIDES.length - 1 ? "Get Started" : "Next");
        dotStrip.removeAllViews();
        for (int k = 0; k < SLIDES.length; k++) {
            View d = new View(this);
            d.setBackground(Ui.roundRect(k == i ? 0xFF0B8376 : 0xFFCFD8E2, 6, this));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    k == i ? Ui.dp(this, 22) : Ui.dp(this, 8), Ui.dp(this, 8));
            lp.setMargins(0, 0, Ui.dp(this, 6), 0);
            dotStrip.addView(d, lp);
        }
    }

    private void finishTutorial() {
        getSharedPreferences("nirixx", MODE_PRIVATE).edit().putBoolean("tutorial_seen", true).apply();
        startActivity(new Intent(this, LoginActivity.class));
        finish();
    }
}
