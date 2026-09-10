package com.nirixx.app;

import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.Obd;
import com.nirixx.app.core.uds.UdsClient;
import com.nirixx.app.db.Db;
import java.util.List;

/** IUPR Test — Primary page (VIN, CVN, CAL ID, IUPR section + History) then
 *  the Secondary page (model details, kms, city, state, ambient conditions),
 *  submitted into the iupr_history table.  Every ECU-origin value is read
 *  live (SAE J1979 Mode 09) or honestly marked unread; ratios are not
 *  published for these ECMs and say so instead of inventing numbers. */
public class IuprTestActivity extends BaseActivity {

    private LinearLayout content;
    private Db db;
    private boolean secondary = false;

    private EditText edtKms, edtCity, edtState, edtSold;
    private TextView txtModel, boxMap, boxIat;
    private String cvn = null, calId = null, ipt = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("IUPR Test");
        showEcuChip(Session.selectedEcuCode, true);
        db = Db.get(this);
        Session.ensureSession(this);
        content = (LinearLayout) findViewById(R.id.content);
        renderPrimary();
    }

    // ------------------------------------------------------------- primary
    private void renderPrimary() {
        secondary = false;
        content.removeAllViews();
        content.addView(Ui.crumbs(this, new String[]{"Home", Session.selectedVehicle,
                Session.selectedEcuCode, "IUPR Test"}));

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackgroundResource(R.drawable.bg_card);
        card.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 4));

        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(android.view.Gravity.CENTER_VERTICAL);
        head.addView(Ui.tv(this, "IUPR Primary", 15.5f, 0xFF1A2138, true),
                new LinearLayout.LayoutParams(0, -2, 1f));
        TextView hist = new TextView(this);
        hist.setText("\u27F2  History");
        hist.setTextSize(14f);
        hist.setTextColor(0xFFFFFFFF);
        hist.setTypeface(null, android.graphics.Typeface.BOLD);
        hist.setGravity(android.view.Gravity.CENTER);
        hist.setPadding(Ui.dp(this, 18), Ui.dp(this, 8), Ui.dp(this, 18), Ui.dp(this, 8));
        hist.setBackgroundColor(0xFF63A6E8);
        head.addView(hist);
        card.addView(head);

        View spacer = new View(this);
        card.addView(spacer, new LinearLayout.LayoutParams(1, Ui.dp(this, 8)));

        card.addView(Ui.kvBox(this, "VIN",
                Session.selectedVin.length() > 0 ? Session.selectedVin : "not identified"));
        card.addView(Ui.kvBox(this, "CVN",
                cvn != null ? cvn : (DiagOps.live() ? "reading…" : "not read — no VCI link")));
        card.addView(Ui.kvBox(this, "CAL ID",
                calId != null ? calId : (DiagOps.live() ? "reading…" : "not read — no VCI link")));
        card.addView(Ui.kvBox(this, "IUPR (Mode 09 $08 IPT)",
                ipt != null ? ipt : (DiagOps.live() ? "reading…" : "not read — no VCI link")));
        card.addView(Ui.kvBox(this, "Monitor names",
                "IPT numerator/denominator pairs are shown in bus order; the per-monitor "
                        + "identity map is OEM-published material — pending the definition pack "
                        + "(see MISSING_DEPENDENCIES.md)."));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.setMargins(0, 0, 0, Ui.dp(this, 8));
        content.addView(card, lp);

        TextView next = Ui.navyBtn(this, "Next");
        LinearLayout.LayoutParams np = new LinearLayout.LayoutParams(Ui.dp(this, 150), -2);
        np.gravity = android.view.Gravity.RIGHT;
        content.addView(next, np);
        next.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { renderSecondary(); }
        });

        hist.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { showHistory(); }
        });

        if (DiagOps.live()) readIdentifiers();
    }

    private void readIdentifiers() {
        DiagOps.mode09(this, 0x06, new DiagOps.Cb<byte[]>() {
            public void ok(byte[] v) {
                cvn = UdsClient.hexBytes(v).replace(" ", "");
                if (!secondary) renderPrimary();
            }
            public void err(String w, String d, Nrc n) { cvn = "ECU refused"; if (!secondary) renderPrimary(); }
        });
        DiagOps.mode09(this, 0x04, new DiagOps.Cb<byte[]>() {
            public void ok(byte[] v) {
                String s = Obd.asciiInfo(v);
                calId = s == null ? UdsClient.hexBytes(v) : s;
                if (!secondary) renderPrimary();
            }
            public void err(String w, String d, Nrc n) { calId = "ECU refused"; if (!secondary) renderPrimary(); }
        });
        DiagOps.mode09(this, 0x08, new DiagOps.Cb<byte[]>() {
            public void ok(byte[] v) {
                String s = Obd.decodeIpt(v);
                ipt = s == null ? UdsClient.hexBytes(v).replace(" ", "") : s;
                if (!secondary) renderPrimary();
            }
            public void err(String w, String d, Nrc n) {
                ipt = "ECU refused (IPT not supported)"; if (!secondary) renderPrimary();
            }
        });
    }

    // ------------------------------------------------------------- secondary
    private void renderSecondary() {
        secondary = true;
        content.removeAllViews();
        content.addView(Ui.crumbs(this, new String[]{"Home", Session.selectedVehicle,
                Session.selectedEcuCode, "IUPR Test"}));
        content.addView(Ui.section(this, "IUPR SECONDARY"));

        content.addView(Ui.tv(this, "1. Model details", 13.5f, 0xFF5A6472, false));
        txtModel = boxLike(Session.selectedVehicle, null);
        content.addView(txtModel);

        content.addView(Ui.tv(this, "2. Kilometers driven", 13.5f, 0xFF5A6472, false));
        edtKms = editBox(InputType.TYPE_CLASS_NUMBER);
        content.addView(edtKms);

        content.addView(Ui.tv(this, "3. City", 13.5f, 0xFF5A6472, false));
        edtCity = editBox(InputType.TYPE_CLASS_TEXT);
        content.addView(edtCity);

        content.addView(Ui.tv(this, "4. State", 13.5f, 0xFF5A6472, false));
        edtState = editBox(InputType.TYPE_CLASS_TEXT);
        content.addView(edtState);

        content.addView(Ui.tv(this, "5. Ambient conditions"
                + (DiagOps.live() ? " (live)" : " — no link, enter manually or leave —"),
                13.5f, 0xFF5A6472, false));
        boxMap = boxLike(DiagOps.live() ? "reading…" : "—", "MAP");
        content.addView(boxMap);
        boxIat = boxLike(DiagOps.live() ? "reading…" : "—", "Intake Air Temperature");
        content.addView(boxIat);

        content.addView(Ui.tv(this, "6. Vehicle sold date (DD/MM/YYYY)", 13.5f, 0xFF5A6472, false));
        edtSold = editBox(InputType.TYPE_CLASS_DATETIME);
        content.addView(edtSold);

        TextView submit = Ui.navyBtn(this, "Submit IUPR Report");
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-1, -2);
        sp.setMargins(0, Ui.dp(this, 10), 0, Ui.dp(this, 12));
        content.addView(submit, sp);
        submit.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                db.saveIupr(Session.sessionKey, Session.vehicleId, Session.selectedVin,
                        cvn == null ? "unread" : cvn, calId == null ? "unread" : calId,
                        "pending-definition",
                        edtKms.getText().toString(), edtCity.getText().toString(),
                        edtState.getText().toString());
                Ui.resultDialog(IuprTestActivity.this, R.drawable.ic_flash_success,
                        "IUPR Submitted",
                        "IUPR report for " + Session.selectedVehicle + " saved to the NirixX database."
                                + (DiagOps.live() ? "" : "\n(Recorded without live ECU reads.)"),
                        "Done", new Runnable() {
                            public void run() { finish(); }
                        }).show();
            }
        });

        if (DiagOps.live()) readAmbient();
    }

    private void readAmbient() {
        DiagOps.obdPid(this, Obd.PID_INTAKE_MAP, new DiagOps.Cb<Double>() {
            public void ok(Double v) { boxMap.setText(v.intValue() + ".0 kPa     MAP"); }
            public void err(String w, String d, Nrc n) { boxMap.setText("unavailable     MAP"); }
        });
        DiagOps.obdPid(this, Obd.PID_INTAKE_AIR_TEMP, new DiagOps.Cb<Double>() {
            public void ok(Double v) { boxIat.setText(v.intValue() + ".0 °C     Intake Air Temperature"); }
            public void err(String w, String d, Nrc n) { boxIat.setText("unavailable     IAT"); }
        });
    }

    private EditText editBox(int type) {
        EditText e = new EditText(this);
        e.setInputType(type);
        e.setBackgroundResource(R.drawable.bg_box_outline);
        e.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 14), 0);
        e.setTextSize(15f);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 50));
        lp.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 12));
        e.setLayoutParams(lp);
        return e;
    }

    private TextView boxLike(String value, String suffix) {
        TextView t = new TextView(this);
        t.setText(suffix == null ? value : value + "     " + suffix);
        t.setTextSize(15f);
        t.setTextColor(0xFF1A2138);
        t.setGravity(android.view.Gravity.CENTER_VERTICAL);
        t.setBackgroundResource(R.drawable.bg_box_outline);
        t.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 14), 0);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 50));
        lp.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 12));
        t.setLayoutParams(lp);
        return t;
    }

    private void showHistory() {
        content.removeAllViews();
        content.addView(Ui.crumbs(this, new String[]{"Home", Session.selectedVehicle,
                Session.selectedEcuCode, "IUPR History"}));
        content.addView(Ui.section(this, "SUBMITTED IUPR REPORTS"));
        List<String[]> rows = db.iuprHistory();
        if (rows.isEmpty()) {
            LinearLayout card = Ui.card(this);
            card.addView(Ui.tv(this, "No IUPR reports submitted yet.", 13.5f, 0xFF5A6472, false));
            content.addView(card);
        }
        for (String[] r : rows) {
            LinearLayout card = Ui.card(this);
            card.addView(Ui.tv(this, r[0] + "   ·   ratio " + r[3], 14.5f, 0xFF1A2138, true));
            card.addView(Ui.tv(this, "CVN " + r[1] + " · CAL ID " + r[2], 12.5f, 0xFF5A6472, false));
            card.addView(Ui.tv(this, r[4] + " km · " + r[5] + ", " + r[6], 12.5f, 0xFF5A6472, false));
            content.addView(card);
        }
        TextView back = Ui.navyBtn(this, "Back to IUPR Primary");
        content.addView(back);
        back.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { renderPrimary(); }
        });
    }

    @Override
    public void onBackPressed() {
        if (secondary) { renderPrimary(); return; }
        super.onBackPressed();
    }
}
