package com.nirixx.app;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.db.Db;

/** NirixX Assistant — in-app help chat plus the customer helpline
 *  (number comes from the configs table, mirroring the reference flashing dialog). */
public class SupportChatActivity extends BaseActivity {

    private LinearLayout chat;
    private final Handler h = new Handler();

    private static final String[][] QNA = {
        {"flash", "For ECU flashing: Diagnostics → pick vehicle → ECU Diagnosis → ECU Flashing. Watch the conditions video, keep the app in the foreground and wait for 'ECU Flashing completed'. If anything crashes, call the helpline shown above."},
        {"dtc", "To read fault codes: VIN Based Diagnosis (or Diagnostics → vehicle) → Select ECU → Diagnostic Trouble Codes → Read DTCs. Note freeze-frame data before Clear."},
        {"vci", "The VCI page offers three physical interfaces only — Bluetooth, Wi-Fi and USB. Pick your NirixiLINK on the login screen or Home → VCI Connect, enable Location for BT scanning, then connect."},
        {"bluetooth", "Bluetooth pairing: Home → VCI Connect → Bluetooth tile → scan → tap your NirixiLINK_xxxxxx. Keep the dongle powered and within a metre of the phone."},
        {"wifi", "Wi-Fi: connect the phone to the VCI's hotspot (NirixiLINK_xxxxxx), then Home → VCI Connect → Wi-Fi tile → Connect."},
        {"usb", "USB: attach the VCI with an OTG cable — the app enumerates it under VCI Connect → USB."},
        {"firmware", "VCI firmware: Home → VCI Firmware Update → pick the connected NirixiLINK. Recovery uses the bundled image."},
        {"report", "Reports: Home → Health Report for a fresh VHR (Dealer / Diagnostic / IO Control / Physical Evaluation / Summary tabs), PDF saved under File Viewer → REPORTS and listed under Reports."},
        {"iupr", "IUPR runs from ECU Diagnosis → IUPR Test (Primary / Secondary tabs). History is stored in the database."},
        {"record", "Screen recording: Account → Start Session Recording. Stop it from the same button; the session marking is stored for support."},
        {"vin", "Auto VIN: Home → VIN Based Diagnosis → READ VIN. When the VIN matches the database you get Diagnostic Section / VHR shortcuts; unknown VINs open the vehicle grid for manual selection."},
        {"call", "Tap the green pill above — it dials NirixX support directly (+91 79694 78770)."},
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("NirixX Assistant");
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        // ---- helpline (reference: flashing conditions dialog) --------------
        final String number = Db.get(this).config("support_number", "+917969478770");
        LinearLayout help = Ui.card(this);
        help.setGravity(android.view.Gravity.CENTER_HORIZONTAL);
        help.addView(Ui.tv(this, "If any App Crashes Please Contact.", 13f, 0xFF5A6472, false));
        LinearLayout pill = Ui.phonePill(this, pretty(number));
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(-2, -2);
        pp.setMargins(0, Ui.dp(this, 8), 0, 0);
        help.addView(pill, pp);
        pill.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                startActivity(new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + number)));
            }
        });
        content.addView(help);

        // ---- chat area ------------------------------------------------------
        chat = new LinearLayout(this);
        chat.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams chp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 320));
        chp.setMargins(0, Ui.dp(this, 8), 0, 0);
        content.addView(chat, chp);

        botSay("Welcome to NirixX Assistant!\nAsk me about flashing, DTCs, VCI pairing (Bluetooth / Wi-Fi / USB), firmware, reports, IUPR, auto VIN or screen recording.");
        suggest("How do I flash an ECU?", "flash");
        suggest("Pair the VCI over Wi-Fi", "wifi");
        suggest("Generate a health report", "report");
        suggest("Call customer care", "call");

        LinearLayout rowIn = new LinearLayout(this);
        rowIn.setOrientation(LinearLayout.HORIZONTAL);
        rowIn.setGravity(android.view.Gravity.CENTER_VERTICAL);
        final EditText in = new EditText(this);
        in.setHint("Type a question…");
        in.setTextSize(13.5f);
        in.setSingleLine(true);
        in.setBackgroundResource(R.drawable.bg_box_outline);
        in.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 12), 0);
        rowIn.addView(in, new LinearLayout.LayoutParams(0, Ui.dp(this, 46), 1f));
        TextView send = Ui.navyBtn(this, "Send");
        send.setPadding(Ui.dp(this, 18), 0, Ui.dp(this, 18), 0);
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-2, Ui.dp(this, 46));
        sp.setMargins(Ui.dp(this, 8), 0, 0, 0);
        rowIn.addView(send, sp);
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(-1, -2);
        rp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
        content.addView(rowIn, rp);

        send.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                String q = in.getText().toString().trim();
                if (q.length() == 0) return;
                in.setText("");
                userSay(q);
                answer(q.toLowerCase(java.util.Locale.US));
            }
        });
    }

    private static String pretty(String n) {
        if (n != null && n.startsWith("+91") && n.length() == 13)
            return "+91 " + n.substring(3, 8) + " " + n.substring(8);
        return n == null ? "" : n;
    }

    private void suggest(final String label, final String key) {
        TextView chip = Ui.chip(this, label, R.drawable.bg_chip_grey, 0xFF3A4663);
        chip.setPadding(Ui.dp(this, 12), Ui.dp(this, 6), Ui.dp(this, 12), Ui.dp(this, 6));
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-2, -2);
        cp.setMargins(Ui.dp(this, 4), Ui.dp(this, 6), 0, 0);
        chat.addView(chip, cp);
        chip.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                userSay(label);
                answer(key);
            }
        });
    }

    private void botSay(String text) { bubble(text, true); }
    private void userSay(String text) { bubble(text, false); }

    private void bubble(String text, boolean bot) {
        TextView t = Ui.tv(this, text, 13f, bot ? 0xFF1A2138 : 0xFFFFFFFF, false);
        t.setBackground(Ui.roundRect(bot ? 0xFFE9EDF5 : 0xFF14276F, 12, this));
        int hp = Ui.dp(this, 12), vp = Ui.dp(this, 8);
        t.setPadding(hp, vp, hp, vp);
        t.setLineSpacing(3f, 1f);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, -2);
        lp.setMargins(bot ? 0 : Ui.dp(this, 48), Ui.dp(this, 6), bot ? Ui.dp(this, 48) : 0, 0);
        lp.gravity = bot ? android.view.Gravity.LEFT : android.view.Gravity.RIGHT;
        chat.addView(t, lp);
    }

    private void answer(final String q) {
        h.postDelayed(new Runnable() {
            public void run() {
                for (int i = 0; i < QNA.length; i++) {
                    if (q.contains(QNA[i][0])) { botSay(QNA[i][1]); return; }
                }
                botSay("I'm the in-app helper — try keywords like: flash, dtc, vci, bluetooth, wifi, usb, firmware, report, iupr, vin, record, call.");
            }
        }, 650);
    }
}
