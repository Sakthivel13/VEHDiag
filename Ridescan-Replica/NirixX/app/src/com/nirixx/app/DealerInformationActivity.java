package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;

/** Editable dealer information (VhrDealerInformation source in the original). */
public class DealerInformationActivity extends BaseActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Dealer Information");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        content.addView(Ui.section(this, "USED IN GENERATED REPORTS"));
        LinearLayout card = Ui.card(this);
        final EditText name = field(card, "Dealership name", Session.dealerName);
        final EditText code = field(card, "Dealer code", "NRX-TN-CHE-0417");
        final EditText branch = field(card, "Branch", "Chennai — Anna Salai");
        final EditText phone = field(card, "Contact number", "+91 98400 12345");
        final EditText gst = field(card, "GSTIN", "33ABCDE1234F1Z5");
        content.addView(card);

        android.widget.Button save = new android.widget.Button(this);
        save.setText("Save");
        save.setTextColor(0xFFFFFFFF);
        save.setAllCaps(false);
        save.setTextSize(15f);
        save.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        save.setBackgroundResource(R.drawable.bg_button_blue);
        content.addView(save, new LinearLayout.LayoutParams(-1, Ui.dp(this, 50)));
        save.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                String n = name.getText().toString().trim();
                if (n.length() > 0) Session.dealerName = n;
                toast("Dealer information updated");
                finish();
            }
        });
    }

    private EditText field(LinearLayout parent, String hint, String value) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setText(value);
        e.setTextSize(14f);
        e.setSingleLine(true);
        e.setBackgroundResource(R.drawable.bg_edittext);
        e.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 14), 0);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 48));
        lp.setMargins(0, Ui.dp(this, 10), 0, 0);
        parent.addView(e, lp);
        return e;
    }
}
