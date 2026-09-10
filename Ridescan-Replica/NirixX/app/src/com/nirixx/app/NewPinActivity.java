package com.nirixx.app;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

public class NewPinActivity extends BaseActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Set New PIN");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        LinearLayout card = Ui.card(this);
        card.addView(Ui.tv(this, "Enter 4 digit PIN", 15f, 0xFF141B2E, true));
        final EditText p1 = pinField(card, "New PIN");
        final EditText p2 = pinField(card, "Confirm New PIN");
        card.addView(Ui.tv(this, "PIN must contain 4 characters.", 12f, 0xFF9AA6B4, false));
        content.addView(card);

        Button done = new Button(this);
        done.setText("Confirm");
        done.setTextColor(0xFFFFFFFF);
        done.setAllCaps(false);
        done.setTextSize(15f);
        done.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        done.setBackgroundResource(R.drawable.bg_button_blue);
        content.addView(done, new LinearLayout.LayoutParams(-1, Ui.dp(this, 50)));
        done.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                String a = p1.getText().toString().trim();
                if (a.length() != 4) { toast("PIN must contain 4 characters."); return; }
                if (!a.equals(p2.getText().toString().trim())) { toast("PINs do not match"); return; }
                Ui.resultDialog(NewPinActivity.this, R.drawable.ic_flash_success, "PIN Updated",
                        "Your new PIN is active. Please sign in again.", "Login",
                        new Runnable() {
                            public void run() {
                                Intent it = new Intent(NewPinActivity.this, LoginActivity.class);
                                it.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK | Intent.FLAG_ACTIVITY_NEW_TASK);
                                startActivity(it);
                                finish();
                            }
                        }).show();
            }
        });
    }

    private EditText pinField(LinearLayout parent, String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setTextSize(15f);
        e.setInputType(android.text.InputType.TYPE_CLASS_NUMBER | android.text.InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        e.setSingleLine(true);
        e.setBackgroundResource(R.drawable.bg_edittext);
        e.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 14), 0);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 48));
        lp.setMargins(0, Ui.dp(this, 12), 0, 0);
        parent.addView(e, lp);
        return e;
    }
}
