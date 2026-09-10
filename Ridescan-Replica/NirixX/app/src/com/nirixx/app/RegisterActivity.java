package com.nirixx.app;

import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

/** New dealer registration (pending distributor approval), links from Login. */
public class RegisterActivity extends BaseActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Register Dealership");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        LinearLayout card = Ui.card(this);
        card.addView(Ui.tv(this, "New Dealer Registration", 17f, 0xFF141B2E, true));
        card.addView(Ui.tv(this, "Applications are verified by your NirixX Distributor before activation.",
                12.5f, 0xFF5A6472, false));
        field(card, "Dealership Name", InputType.TYPE_CLASS_TEXT);
        field(card, "Dealer Code (if allotted)", InputType.TYPE_CLASS_TEXT);
        field(card, "Login Email ID", InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        field(card, "Contact Number", InputType.TYPE_CLASS_PHONE);
        field(card, "Set 4-digit PIN", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        content.addView(card);

        Button reg = new Button(this);
        reg.setText("Submit Application");
        reg.setTextColor(0xFFFFFFFF);
        reg.setAllCaps(false);
        reg.setTextSize(15f);
        reg.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        reg.setBackgroundResource(R.drawable.bg_button_blue);
        content.addView(reg, new LinearLayout.LayoutParams(-1, Ui.dp(this, 50)));
        reg.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                // real flow continues: e-mail verification (OTP) → PIN setup
                go(OtpActivity.class);
            }
        });
    }

    private void field(LinearLayout parent, String hint, int inputType) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setTextSize(14f);
        e.setInputType(inputType);
        e.setSingleLine(true);
        e.setBackgroundResource(R.drawable.bg_edittext);
        e.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 14), 0);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 48));
        lp.setMargins(0, Ui.dp(this, 10), 0, 0);
        parent.addView(e, lp);
    }
}
