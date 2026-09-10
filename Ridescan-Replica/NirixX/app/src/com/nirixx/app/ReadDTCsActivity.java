package com.nirixx.app;

import android.app.Dialog;
import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.UdsClient;
import com.nirixx.app.db.Db;

/** Diagnostic Trouble Codes — REAL reads only:
 *  READ  → UDS 19 02 FF through the live DiagEngine (records decoded P/C/B/U)
 *  CLEAR → UDS 14 FF FF FF, then an automatic re-read to prove the effect.
 *  With no VCI link every action reports the honest failure; nothing is drawn
 *  out of thin air. */
public class ReadDTCsActivity extends BaseActivity {

    private LinearLayout content;
    private Db db;
    private TextView read, clear;
    private UdsClient.DtcRecord[] last;          // cached result of the latest real scan
    private int filter = 0;                      // 0 All · 1 Active · 2 History
    private static final String[] FILTERS = { "All", "Active", "History" };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Read DTCs");
        showEcuChip(Session.selectedEcuCode, true);
        db = Db.get(this);
        Session.ensureSession(this);
        content = (LinearLayout) findViewById(R.id.content);
        render(null);
    }

    private void render(UdsClient.DtcRecord[] records) {
        if (records != null) last = records;
        content.removeAllViews();
        content.addView(Ui.crumbs(this, new String[]{"Home", Session.selectedVehicle,
                Session.selectedEcuCode, "Diagnostic Trouble Codes"}));

        if (!DiagOps.live()) {
            LinearLayout warn = Ui.card(this);
            warn.addView(Ui.tv(this, "NO LIVE VCI LINK", 12f, 0xFFB26A00, true));
            warn.addView(Ui.tv(this, "Connect the NirixiLINK (Login » ADD/PAIR VCI) to read real "
                    + "trouble codes from " + Session.selectedEcuCode + ".", 12.5f, 0xFF5A6472, false));
            content.addView(warn);
        }

        LinearLayout act = new LinearLayout(this);
        act.setOrientation(LinearLayout.HORIZONTAL);
        read = Ui.navyBtn(this, "READ DTC");
        clear = Ui.navyBtn(this, "CLEAR DTC");
        LinearLayout.LayoutParams hp = new LinearLayout.LayoutParams(0, -2, 1f);
        hp.setMargins(0, 0, Ui.dp(this, 6), 0);
        LinearLayout.LayoutParams hp2 = new LinearLayout.LayoutParams(0, -2, 1f);
        hp2.setMargins(Ui.dp(this, 6), 0, 0, 0);
        act.addView(read, hp);
        act.addView(clear, hp2);
        LinearLayout.LayoutParams ap = new LinearLayout.LayoutParams(-1, -2);
        ap.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 10));
        content.addView(act, ap);

        if (last != null && last.length > 0) {
            // reference-parity filter: All / Active / History (status-byte driven)
            final TextView dd = Ui.tv(this, FILTERS[filter] + "  ▼", 13.5f, 0xFF14276F, true);
            dd.setBackgroundResource(R.drawable.bg_box_outline);
            dd.setGravity(android.view.Gravity.CENTER);
            LinearLayout.LayoutParams dp = new LinearLayout.LayoutParams(Ui.dp(this, 120), Ui.dp(this, 40));
            dp.setMargins(0, 0, 0, Ui.dp(this, 8));
            content.addView(dd, dp);
            dd.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    new android.app.AlertDialog.Builder(ReadDTCsActivity.this)
                            .setTitle("DTC filter")
                            .setItems(FILTERS, new android.content.DialogInterface.OnClickListener() {
                                public void onClick(android.content.DialogInterface d, int which) {
                                    filter = which;
                                    render(null);
                                }
                            }).show();
                }
            });
        }

        if (last == null) {
            LinearLayout card = Ui.card(this);
            card.addView(Ui.tv(this, "No DTC query performed yet.", 13.5f, 0xFF5A6472, false));
            content.addView(card);
        } else if (last.length == 0) {
            LinearLayout card = Ui.card(this);
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(android.view.Gravity.CENTER_VERTICAL);
            row.addView(Ui.dot(this, true));
            row.addView(Ui.tv(this, "  No Diagnostic Trouble Codes", 15f, 0xFF2E9E43, true));
            card.addView(row);
            card.addView(Ui.tv(this, "19 02 FF returned an empty DTC list from "
                    + Session.selectedEcuCode + ".", 12.5f, 0xFF5A6472, false));
            content.addView(card);
        } else {
            int shown = 0;
            for (int i = 0; i < last.length; i++) {
                UdsClient.DtcRecord rec = last[i];
                if (filter == 1 && !rec.active()) continue;          // Active only
                if (filter == 2 && rec.active()) continue;           // History only
                shown++;
                String code = rec.code();
                String descr = db.dtcDescr(code);
                if (descr == null) descr = "Description not in the NirixX DTC library";

                LinearLayout card = new LinearLayout(this);
                card.setOrientation(LinearLayout.HORIZONTAL);
                card.setBackgroundResource(R.drawable.bg_card);
                card.setGravity(android.view.Gravity.CENTER_VERTICAL);
                card.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
                android.widget.ImageView ic = new android.widget.ImageView(this);
                ic.setImageResource(R.drawable.ic_dtc_tri);
                card.addView(ic, new LinearLayout.LayoutParams(Ui.dp(this, 26), Ui.dp(this, 26)));
                LinearLayout mid = new LinearLayout(this);
                mid.setOrientation(LinearLayout.VERTICAL);
                mid.setPadding(Ui.dp(this, 12), 0, 0, 0);
                mid.addView(Ui.tv(this, code, 15f, 0xFF1A2138, true));
                mid.addView(Ui.tv(this, descr, 12.5f, 0xFF5A6472, false));
                card.addView(mid, new LinearLayout.LayoutParams(0, -2, 1f));
                card.addView(Ui.chip(this, rec.active() ? "Active" : "Stored",
                        rec.active() ? R.drawable.bg_chip_red : R.drawable.bg_chip,
                        rec.active() ? 0xFFD32F2F : 0xFF5A6472));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
                lp.setMargins(0, 0, 0, Ui.dp(this, 8));
                content.addView(card, lp);
                db.putInput(Session.sessionKey, "dtc", code, rec.active() ? "Active" : "Stored");
            }
            if (shown == 0) {
                LinearLayout card = Ui.card(this);
                card.addView(Ui.tv(this, "No " + FILTERS[filter] + " entries in the last scan.",
                        13.5f, 0xFF5A6472, false));
                content.addView(card);
            }
        }

        read.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { doRead(); }
        });
        clear.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Ui.dialog(ReadDTCsActivity.this, "Clear all DTCs?",
                        "Sends UDS 14 FF FF FF to " + Session.selectedEcuCode
                                + ". Freeze-frame data is erased too. Proceed?",
                        "Clear", new Runnable() { public void run() { doClear(); } },
                        "Cancel", null).show();
            }
        });
    }

    private void doRead() {
        final Dialog d = Ui.progressDialog(this, "Reading DTCs (19 02 FF)…");
        d.show();
        DiagOps.readDtc(this, new DiagOps.Cb<UdsClient.DtcRecord[]>() {
            public void ok(UdsClient.DtcRecord[] recs) {
                d.dismiss();
                Session.faultsFound = recs != null && recs.length > 0;
                Session.dtcScanned = true;
                render(recs);
                toast(recs == null || recs.length == 0
                        ? "No DTCs present on " + Session.selectedEcuCode
                        : recs.length + " DTC(s) on " + Session.selectedEcuCode);
            }
            public void err(String what, String detail, Nrc nrc) {
                d.dismiss();
                Ui.resultDialog(ReadDTCsActivity.this, R.drawable.ic_warn,
                        "Read failed", detail, "OK", null).show();
            }
        });
    }

    private void doClear() {
        final Dialog d = Ui.progressDialog(this, "Clearing DTCs (14 FF FF FF)…");
        d.show();
        DiagOps.clearDtc(this, new DiagOps.Cb<Boolean>() {
            public void ok(Boolean v) {
                d.dismiss();
                Session.dtcsCleared++;
                Session.vhrData.put("dtc|cleared", "yes");
                toast("DTCs cleared — re-reading…");
                doRead();
            }
            public void err(String what, String detail, Nrc nrc) {
                d.dismiss();
                Ui.resultDialog(ReadDTCsActivity.this, R.drawable.ic_warn,
                        "Clear failed", detail, "OK", null).show();
            }
        });
    }
}
