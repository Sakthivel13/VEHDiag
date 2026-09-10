package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.CompoundButton;
import android.widget.LinearLayout;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.diag.TestAddr;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.db.Db;
import java.util.List;

/** Input Output Control (UDS 0x2F).  An actuator toggle is enabled ONLY when
 *  the test definition has a published IO-control DID (addr = io:XXXX) and a
 *  live link — real actuations are echoed to the session log and feed the VHR
 *  IO tab.  Without a DID the row is labelled, not faked. */
public class IOControlActivity extends BaseActivity {

    private Db db;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("IO Control");
        showEcuChip(Session.selectedEcuCode, true);
        db = Db.get(this);
        Session.ensureSession(this);

        LinearLayout content = (LinearLayout) findViewById(R.id.content);
        content.removeAllViews();
        content.addView(Ui.crumbs(this, new String[]{"Home", Session.selectedVehicle,
                Session.selectedEcuCode, "IO Control"}));

        if (!DiagOps.live()) {
            LinearLayout warn = Ui.card(this);
            warn.addView(Ui.tv(this, "NO LIVE VCI LINK", 12f, 0xFFB26A00, true));
            warn.addView(Ui.tv(this, "Actuations drive real outputs — connect the NirixiLINK first.",
                    12.5f, 0xFF5A6472, false));
            content.addView(warn);
        }

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackgroundResource(R.drawable.bg_card);
        card.setPadding(Ui.dp(this, 12), Ui.dp(this, 12), Ui.dp(this, 12), Ui.dp(this, 2));

        List<Db.TestDef> ios = db.tests(Session.ecuId, "io");
        boolean anyEnabled = false;
        for (final Db.TestDef t : ios) {
            final TestAddr addr = TestAddr.parse(t.addr);
            if (addr != null && addr.kind == TestAddr.IO) {
                anyEnabled = true;
                LinearLayout row = Ui.ioRow(this, t.name.toUpperCase(),
                        new CompoundButton.OnCheckedChangeListener() {
                            public void onCheckedChanged(CompoundButton button, boolean isChecked) {
                                actuate(t, addr.value, isChecked);
                            }
                        });
                card.addView(row);
            } else {
                LinearLayout row = new LinearLayout(this);
                row.setOrientation(LinearLayout.HORIZONTAL);
                row.setGravity(android.view.Gravity.CENTER_VERTICAL);
                row.setPadding(0, Ui.dp(this, 10), 0, Ui.dp(this, 10));
                row.addView(Ui.tv(this, t.name.toUpperCase(), 13f, 0xFF9AA6B4, true),
                        new LinearLayout.LayoutParams(0, -2, 1f));
                row.addView(Ui.chip(this, "DEFINITION PENDING", R.drawable.bg_chip_grey,
                        0xFF5A6472));
                card.addView(row);
            }
        }
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.setMargins(0, 0, 0, Ui.dp(this, 8));
        content.addView(card, lp);

        LinearLayout note = Ui.card(this);
        note.addView(Ui.tv(this, anyEnabled
                        ? "Each toggle sends a real 2F <did> 03/00 exchange; the ECU reply is "
                        + "recorded into the session log and the Vehicle Health Report."
                        : "No IO-control DIDs are published for this ECU yet — the OEM definition "
                        + "pack is required (see MISSING_DEPENDENCIES.md). Nothing here is actuated.",
                12.5f, 0xFF5A6472, false));
        content.addView(note);
    }

    private void actuate(final Db.TestDef t, int did, final boolean engage) {
        if (!DiagOps.live()) { toast("No VCI link established"); return; }
        DiagOps.ioControl(this, did, engage, new DiagOps.Cb<byte[]>() {
            public void ok(byte[] resp) {
                String verdict = engage ? "Actuated" : "Released";
                Session.vhrData.put("io|" + Session.selectedEcuCode + "|" + t.name, verdict);
                db.putInput(Session.sessionKey, "io",
                        Session.selectedEcuCode + "|" + t.name, verdict);
                toast(t.name + " — " + verdict.toLowerCase() + " (6F…)");
            }
            public void err(String what, String detail, Nrc nrc) {
                Ui.resultDialog(IOControlActivity.this, R.drawable.ic_warn,
                        "Actuation refused", detail, "OK", null).show();
            }
        });
    }
}
