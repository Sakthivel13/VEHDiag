package com.nirixx.app;

import android.os.Bundle;
import android.os.CountDownTimer;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

/** OTP verification: "OTP has been Send to <email> Please Enter OTP to Verify the Email ID" */
public class OtpActivity extends BaseActivity {
    private EditText otp;
    private TextView timer;
    private CountDownTimer cd;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Verify OTP");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        LinearLayout card = Ui.card(this);
        String email = Session.dealerEmail.length() > 0 ? Session.dealerEmail : "service@nirixx.io";
        card.addView(Ui.tv(this, "OTP has been Send to " + email + "\nPlease Enter OTP to Verify the Email ID",
                13.5f, 0xFF141B2E, false));

        android.widget.TextView gap = Ui.tv(this,
                "OTP delivery requires the messaging backend (not integrated yet — see "
                        + "MISSING_DEPENDENCIES.md). For this build, enter any 6-digit code to proceed.",
                11.5f, 0xFF9AA6B4, false);
        gap.setPadding(0, Ui.dp(this, 8), 0, 0);
        card.addView(gap);

        otp = new EditText(this);
        otp.setHint("● ● ● ● ● ●");
        otp.setTextSize(18f);
        otp.setGravity(android.view.Gravity.CENTER);
        otp.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
        otp.setMaxEms(6);
        otp.setBackgroundResource(R.drawable.bg_edittext);
        LinearLayout.LayoutParams op = new LinearLayout.LayoutParams(-1, Ui.dp(this, 54));
        op.setMargins(0, Ui.dp(this, 16), 0, 0);
        card.addView(otp, op);

        timer = Ui.tv(this, "Resend OTP in 00:30", 12.5f, 0xFF5A6472, true);
        timer.setPadding(0, Ui.dp(this, 12), 0, 0);
        card.addView(timer);
        content.addView(card);

        Button verify = new Button(this);
        verify.setText("Verify");
        verify.setTextColor(0xFFFFFFFF);
        verify.setAllCaps(false);
        verify.setTextSize(15f);
        verify.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        verify.setBackgroundResource(R.drawable.bg_button_blue);
        content.addView(verify, new LinearLayout.LayoutParams(-1, Ui.dp(this, 50)));
        verify.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                if (otp.getText().toString().trim().length() < 6) { toast("Enter the 6-digit OTP"); return; }
                go(NewPinActivity.class);
                finish();
            }
        });

        timer.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                if (timer.getText().toString().contains("Resend now")) {
                    toast("OTP resent");
                    startTimer();
                }
            }
        });
        startTimer();
    }

    private void startTimer() {
        if (cd != null) cd.cancel();
        cd = new CountDownTimer(30000, 1000) {
            public void onTick(long ms) {
                timer.setText(String.format(java.util.Locale.US, "Resend OTP in 00:%02d", ms / 1000));
                timer.setTextColor(0xFF5A6472);
            }
            public void onFinish() {
                timer.setText("Resend now");
                timer.setTextColor(0xFF0B8376);
            }
        }.start();
    }

    @Override
    protected void onDestroy() {
        if (cd != null) cd.cancel();
        super.onDestroy();
    }
}
