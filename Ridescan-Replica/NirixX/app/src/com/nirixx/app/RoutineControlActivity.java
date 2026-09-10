package com.nirixx.app;

import android.app.Dialog;
import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.diag.TestAddr;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.db.Db;
import java.util.List;

/** Routine Control — reference-style list of executable routines (UDS 0x31).
 *  A routine is runnable only when (a) its routine id is published in the test
 *  definition (addr = rid:XXXX) and (b) a VCI link is live.  Everything else is
 *  labelled "definition pending" — never started blindly, never simulated. */
public class RoutineControlActivity extends BaseActivity {

    private Db db;
    private LinearLayout content;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Routine Control");
        showEcuChip(Session.selectedEcuCode, true);
        db = Db.get(this);
        Session.ensureSession(this);
        content = (LinearLayout) findViewById(R.id.content);
        render();
    }

    private void render() {
        content.removeAllViews();
        content.addView(Ui.crumbs(this, new String[]{"Home", Session.selectedVehicle,
                Session.selectedEcuCode, "Routine Control"}));

        if (!DiagOps.live()) {
            LinearLayout warn = Ui.card(this);
            warn.addView(Ui.tv(this, "NO LIVE VCI LINK", 12f, 0xFFB26A00, true));
            warn.addView(Ui.tv(this, "Routines act on the real ECU — connect the NirixiLINK "
                    + "and keep ignition ON before running them.", 12.5f, 0xFF5A6472, false));
            content.addView(warn);
        }

        List<Db.TestDef> routines = db.tests(Session.ecuId, "routine");
        for (final Db.TestDef t : routines) {
            final TestAddr addr = TestAddr.parse(t.addr);
            final boolean runnable = addr != null && addr.kind == TestAddr.RID;

            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.HORIZONTAL);
            card.setGravity(android.view.Gravity.CENTER_VERTICAL);
            card.setBackgroundResource(R.drawable.bg_card);
            card.setPadding(Ui.dp(this, 14), Ui.dp(this, 10), Ui.dp(this, 10), Ui.dp(this, 10));
            LinearLayout mid = new LinearLayout(this);
            mid.setOrientation(LinearLayout.VERTICAL);
            mid.addView(Ui.tv(this, t.name, 14.5f, 0xFF1A2138, true));
            final TextView st = Ui.tv(this, runnable
                            ? "Routine " + String.format("0x%04X", addr.value)
                            : "Definition pending — routine id not published",
                    12.5f, runnable ? 0xFF5A6472 : 0xFF9AA6B4, false);
            mid.addView(st);
            card.addView(mid, new LinearLayout.LayoutParams(0, -2, 1f));
            TextView run = Ui.navyBtn(this, runnable ? "RUN" : "PENDING");
            if (!runnable) run.setAlpha(0.35f);
            card.addView(run, new LinearLayout.LayoutParams(Ui.dp(this, 96), Ui.dp(this, 40)));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
            lp.setMargins(0, 0, 0, Ui.dp(this, 10));
            content.addView(card, lp);

            run.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    if (!runnable) { toast("No published routine id — awaiting OEM definition pack"); return; }
                    if (!DiagOps.live()) { toast("No VCI link established"); return; }
                    Ui.dialog(RoutineControlActivity.this, "Run routine?",
                            t.name + " — UDS 31 01 "
                                    + String.format("%04X", addr.value)
                                    + " on " + Session.selectedEcuCode + ". Keep ignition ON.",
                            "Start", new Runnable() {
                                public void run() { runRoutine(t, addr.value, st); }
                            }, "Cancel", null).show();
                }
            });
        }

        // Guided-procedure entry: documents a real workshop procedure; performs
        // no bus traffic itself, so it is honest even without a link.
        content.addView(Ui.section(this, "GUIDED PROCEDURES"));
        LinearLayout gear = Ui.listRow(this, R.drawable.mod_isg, "Gear Learning Procedure",
                "Step-by-step gear position learning (engine OFF, ignition ON)", true);
        gear.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(GearLearningActivity.class); }
        });
        content.addView(gear);
    }

    private void runRoutine(final Db.TestDef t, int rid, final TextView st) {
        final Dialog d = Ui.progressDialog(this, "UDS 31 01 "
                + String.format("%04X", rid) + " …");
        d.show();
        st.setText("Running…");
        st.setTextColor(0xFF5A6472);
        DiagOps.routineStart(this, rid, new DiagOps.Cb<byte[]>() {
            public void ok(byte[] resp) {
                d.dismiss();
                st.setText("Started — ECU accepted (71 01)");
                st.setTextColor(0xFF2E9E43);
                Session.vhrData.put("routine|" + t.name, "Started");
                db.putInput(Session.sessionKey, "routine", t.name, "Started");
                Ui.resultDialog(RoutineControlActivity.this, R.drawable.ic_flash_success,
                        "Routine Started", t.name + " — the ECU accepted the request (71 01).",
                        "OK", null).show();
            }
            public void err(String what, String detail, Nrc nrc) {
                d.dismiss();
                st.setText("Refused" + (nrc != null
                        ? " — NRC " + String.format("0x%02X", nrc.code) : ""));
                st.setTextColor(0xFFD32F2F);
                Ui.resultDialog(RoutineControlActivity.this, R.drawable.ic_warn,
                        "Routine failed", detail, "OK", null).show();
            }
        });
    }
}
