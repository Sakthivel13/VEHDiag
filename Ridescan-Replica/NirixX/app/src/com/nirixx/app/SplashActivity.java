package com.nirixx.app;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import java.io.PrintWriter;
import java.io.StringWriter;

public class SplashActivity extends BaseActivity {

    private SharedPreferences crash;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(0xFF000000);
        try {
            setContentView(R.layout.activity_splash);
        } catch (Throwable t) {
            // First-frame failure must never be a silent white screen: record the
            // trace for the next launch AND show it right now on a raw view.
            recordBootFailure(t);
            super.setContentView(bootFailureView(t));
            return;
        }
        NirixXApp.stageUiShown(this);

        // If the previous run died, show the exact trace instead of the onboarding
        // flow — this is how a device-only failure gets reported back with proof.
        crash = getSharedPreferences(NirixXApp.PREFS, MODE_PRIVATE);
        String trace = crash.getString("trace", null);
        if (trace != null) {
            String show = trace.length() > 1400 ? trace.substring(0, 1400) + "\n…(truncated)" : trace;
            Ui.dialog(this, "NirixX stopped unexpectedly",
                    "The app closed with an error last time. Please share this trace when reporting:\n\n" + show,
                    "Clear & open", new Runnable() {
                        public void run() {
                            crash.edit().remove("trace").apply();
                            advance();
                        }
                    }, null, null).show();
            return;
        }

        // Reached the splash but the LAST run died before ANY screen with no Java
        // trace → the OS ended the process (Play Protect / OEM battery-security /
        // native abort). Say so plainly, with concrete unblock steps.
        final SharedPreferences launch = getSharedPreferences(NirixXApp.LAUNCH, MODE_PRIVATE);
        if (launch.getBoolean("killed_before_ui", false)) {
            Ui.dialog(this, "Android closed NirixX last time",
                    "Your previous launch was ended by the system before the first screen could open — "
                            + "no app error was recorded, so this was Android itself (Play Protect / "
                            + "device security / battery optimiser), not a NirixX defect.\n\n"
                            + "• If you force-stopped the app or swiped it away during the splash, that "
                            + "explains it — just continue.\n"
                            + "• Otherwise: Settings → Battery → allow background activity for NirixX, "
                            + "and in Play Protect / device security choose “keep/allow” for this app.\n\n"
                            + "If it ever closes again, the crash trace will now be captured and shown here.",
                    "Continue", new Runnable() {
                        public void run() {
                            launch.edit().remove("killed_before_ui").apply();
                            advance();
                        }
                    }, null, null).show();
            return;
        }
        advance();
    }

    private void advance() {
        NirixXApp.stageAlive(this);
        new Handler().postDelayed(new Runnable() {
            public void run() {
                try {
                    boolean seen = getSharedPreferences("nirixx", MODE_PRIVATE).getBoolean("tutorial_seen", false);
                    startActivity(new Intent(SplashActivity.this,
                            seen ? WelcomeActivity.class : TutorialActivity.class));
                    finish();
                } catch (Throwable t) {
                    recordBootFailure(t);
                }
            }
        }, 1600);
    }

    private void recordBootFailure(Throwable t) {
        try {
            StringWriter sw = new StringWriter();
            t.printStackTrace(new PrintWriter(sw));
            getSharedPreferences(NirixXApp.PREFS, MODE_PRIVATE).edit()
                    .putString("trace", "boot: splash\n" + sw.toString())
                    .putLong("at", System.currentTimeMillis())
                    .commit();
        } catch (Exception ignored) { }
    }

    private android.view.View bootFailureView(Throwable t) {
        android.widget.TextView tv = new android.widget.TextView(this);
        tv.setBackgroundColor(0xFF101726);
        tv.setTextColor(0xFFFFFFFF);
        int p = Ui.dp(this, 22);
        tv.setPadding(p, p, p, p);
        tv.setTextSize(13.5f);
        tv.setText("NirixX could not draw its first screen.\n\n"
                + "Please share this text when reporting:\n\n" + t);
        return tv;
    }
}
