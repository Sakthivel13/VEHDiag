package com.nirixx.app;

import android.app.Dialog;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

/** SSO dealership login (alternate enterprise login from Login screen). */
public class SsoLoginActivity extends BaseActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("SSO Dealership Login");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        LinearLayout card = Ui.card(this);
        card.addView(Ui.tv(this, "Sign in with NirixX ID", 17f, 0xFF141B2E, true));
        card.addView(Ui.tv(this, "Use the credentials issued to your workshop by NirixX Mobility.",
                12.5f, 0xFF5A6472, false));

        final EditText code = field(card, "Dealer Code", InputType.TYPE_CLASS_TEXT);
        final EditText email = field(card, "Login Email ID", InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        final EditText pass = field(card, "SSO Password", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        content.addView(card);

        Button login = new Button(this);
        login.setText("Login with SSO");
        login.setTextColor(0xFFFFFFFF);
        login.setAllCaps(false);
        login.setTextSize(15f);
        login.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        login.setBackgroundResource(R.drawable.bg_button_blue);
        content.addView(login, new LinearLayout.LayoutParams(-1, Ui.dp(this, 50)));

        login.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                if (code.getText().toString().trim().length() < 4) { toast("Enter your dealer code"); return; }
                if (email.getText().toString().trim().length() < 4) { toast("Enter your Email ID"); return; }
                Session.dealerEmail = email.getText().toString().trim();
                final Dialog d = Ui.progressDialog(SsoLoginActivity.this, "Validating with SSO…");
                d.show();
                v.postDelayed(new Runnable() {
                    public void run() {
                        d.dismiss();
                        go(UserTypeActivity.class);
                        finish();
                    }
                }, 1100);
            }
        });
    }

    private EditText field(LinearLayout parent, String hint, int inputType) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setTextSize(14f);
        e.setInputType(inputType);
        e.setSingleLine(true);
        e.setBackgroundResource(R.drawable.bg_edittext);
        e.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 14), 0);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 48));
        lp.setMargins(0, Ui.dp(this, 12), 0, 0);
        parent.addView(e, lp);
        return e;
    }
}
