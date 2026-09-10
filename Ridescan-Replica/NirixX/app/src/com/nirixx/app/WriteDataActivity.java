package com.nirixx.app;

import android.app.Dialog;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.diag.TestAddr;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.Obd;
import com.nirixx.app.core.uds.UdsClient;
import com.nirixx.app.db.Db;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Write Data Identifier — strictly real.
 *  Current values are READ from the ECU (22 F1 90 / Mode 09) when a link is
 *  live; otherwise shown as "not read".  SecurityAccess is performed for real:
 *  the seed is fetched from the ECU (27 01) — the key derivation stays gated
 *  on the OEM seed-key algorithm (documented dependency #3), so the tool shows
 *  the actual seed and stops instead of pretending.  Writes (2E …) go to the
 *  ECU only on explicit confirmation, and the real response is reported. */
public class WriteDataActivity extends BaseActivity {

    private LinearLayout content;
    private Db db;
    private final Map<Long, String> currentValues = new HashMap<Long, String>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        if (!com.nirixx.app.core.role.Roles.can(Session.userType, "write_did")) {
            Ui.dialog(this, "Not permitted",
                    "This is an engineering operation restricted to the Dealer Engineer role.",
                    "OK", new Runnable() { public void run() { finish(); } }, null, null).show();
            return;
        }
        setTitle("Write Data Identifier");
        showEcuChip(Session.selectedEcuCode, true);
        db = Db.get(this);
        Session.ensureSession(this);
        content = (LinearLayout) findViewById(R.id.content);
        render();
        readCurrentValues();
    }

    private void render() {
        content.removeAllViews();
        content.addView(Ui.crumbs(this, new String[]{"Home", Session.selectedVehicle,
                Session.selectedEcuCode, "Write Data Identifier"}));

        if (!DiagOps.live()) {
            LinearLayout warn = Ui.card(this);
            warn.addView(Ui.tv(this, "NO LIVE VCI LINK", 12f, 0xFFB26A00, true));
            warn.addView(Ui.tv(this, "DID values are read off the ECU — nothing can be shown or "
                    + "written until the NirixiLINK is connected.", 12.5f, 0xFF5A6472, false));
            content.addView(warn);
        }

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackgroundResource(R.drawable.bg_card);
        card.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 4));

        List<Db.TestDef> dids = db.tests(Session.ecuId, "write");
        for (final Db.TestDef t : dids) {
            final TestAddr addr = TestAddr.parse(t.addr);
            final boolean reachable = addr != null
                    && (addr.kind == TestAddr.DID || addr.kind == TestAddr.M09);
            final String shown = currentValues.containsKey(Long.valueOf(t.id))
                    ? currentValues.get(Long.valueOf(t.id))
                    : (reachable ? (DiagOps.live() ? "reading…" : "not read — no link")
                            : "definition pending");
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(android.view.Gravity.CENTER_VERTICAL);
            row.setPadding(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
            LinearLayout mid = new LinearLayout(this);
            mid.setOrientation(LinearLayout.VERTICAL);
            mid.addView(Ui.tv(this, t.name, 14.5f, 0xFF1A2138, true));
            mid.addView(Ui.tv(this, shown, 12.5f, 0xFF5A6472, false));
            row.addView(mid, new LinearLayout.LayoutParams(0, -2, 1f));
            String chip;
            if (!reachable) chip = "PENDING";
            else chip = t.writable == 1 ? "WRITE" : "READ ONLY";
            row.addView(Ui.chip(this, chip,
                    !reachable ? R.drawable.bg_chip_grey
                            : (t.writable == 1 ? R.drawable.bg_chip_amber : R.drawable.bg_chip_grey),
                    !reachable ? 0xFF9AA6B4
                            : (t.writable == 1 ? 0xFF8A5300 : 0xFF5A6472)));
            card.addView(row, new LinearLayout.LayoutParams(-1, -2));
            if (reachable && t.writable == 1 && addr.kind == TestAddr.DID) {
                final TestAddr a2 = addr;
                row.setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) { openEditor(t, a2); }
                });
            }
        }
        content.addView(card);

        LinearLayout note = Ui.card(this);
        note.addView(Ui.tv(this, "SecurityAccess policy", 13.5f, 0xFF1A2138, true));
        note.addView(Ui.tv(this,
                "Before any write the tool performs a REAL seed request (27 01) and shows the "
                        + "seed the ECU returned. The key computation requires the OEM seed-key "
                        + "algorithm (not part of this project — see MISSING_DEPENDENCIES.md), so "
                        + "writes are attempted directly and the ECU's true answer (6E or 7F xx) "
                        + "is reported. No fake unlocks, no fake values.", 12.5f, 0xFF5A6472, false));
        content.addView(note);
    }

    /** Fetch the real current value of every reachable row. */
    private void readCurrentValues() {
        if (!DiagOps.live()) return;
        List<Db.TestDef> dids = db.tests(Session.ecuId, "write");
        for (final Db.TestDef t : dids) {
            final TestAddr addr = TestAddr.parse(t.addr);
            if (addr == null) continue;
            if (addr.kind == TestAddr.DID) {
                DiagOps.readDidRaw(this, addr.value, new DiagOps.Cb<byte[]>() {
                    public void ok(byte[] v) {
                        currentValues.put(Long.valueOf(t.id), UdsClient.ascii(v));
                        render();
                    }
                    public void err(String w, String d, Nrc n) {
                        currentValues.put(Long.valueOf(t.id), "read refused"
                                + (n != null ? " (NRC " + String.format("0x%02X", n.code) + ")" : ""));
                        render();
                    }
                });
            } else if (addr.kind == TestAddr.M09) {
                DiagOps.mode09(this, addr.value, new DiagOps.Cb<byte[]>() {
                    public void ok(byte[] v) {
                        String s = Obd.asciiInfo(v);
                        currentValues.put(Long.valueOf(t.id),
                                s == null ? UdsClient.hexBytes(v) : s);
                        render();
                    }
                    public void err(String w, String d, Nrc n) {
                        currentValues.put(Long.valueOf(t.id), "read refused"); render();
                    }
                });
            }
        }
    }

    private void openEditor(final Db.TestDef t, final TestAddr addr) {
        // step 0 — real seed read so the operator sees the actual ECU state
        final Dialog seedDlg = Ui.progressDialog(this, "SecurityAccess — requesting seed (27 01)…");
        seedDlg.show();
        new Thread(new Runnable() {
            public void run() {
                try {
                    final byte[] seed = requestSeedFromEcu();
                    runOnUiThread(new Runnable() {
                        public void run() {
                            seedDlg.dismiss();
                            showWriteDialog(t, addr, UdsClient.hexBytes(seed));
                        }
                    });
                } catch (final Exception e) {
                    runOnUiThread(new Runnable() {
                        public void run() {
                            seedDlg.dismiss();
                            showWriteDialog(t, addr, "seed request failed: "
                                    + (e.getMessage() == null ? String.valueOf(e) : e.getMessage()));
                        }
                    });
                }
            }
        }).start();
    }

    /** Real 27 01 exchange straight through the engine (returns the seed bytes). */
    private byte[] requestSeedFromEcu() throws Exception {
        if (!DiagOps.live()) throw new Exception("No VCI link established");
        return com.nirixx.app.core.diag.DiagEngine.uds().securitySeed(1);
    }

    private void showWriteDialog(final Db.TestDef t, final TestAddr addr, String seedInfo) {
        final Dialog d = new Dialog(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundResource(R.drawable.bg_dialog);
        int p = Ui.dp(this, 20);
        root.setPadding(p, p, p, Ui.dp(this, 14));
        root.addView(Ui.tv(this, "Write " + t.name, 16.5f, 0xFF1A2138, true));
        root.addView(Ui.tv(this, "ECU seed: " + seedInfo
                        + "\nKey derivation needs the OEM calculator — this write will be sent as-is "
                        + "and reported truthfully.", 12.5f, 0xFF5A6472, false));

        final EditText input = new EditText(this);
        input.setHint(t.name.startsWith("VIN") ? "17-character VIN" : "Value");
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
        input.setBackgroundResource(R.drawable.bg_box_outline);
        input.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 12), 0);
        LinearLayout.LayoutParams ip = new LinearLayout.LayoutParams(-1, Ui.dp(this, 46));
        ip.setMargins(0, Ui.dp(this, 12), 0, 0);
        root.addView(input, ip);

        TextView go = Ui.navyBtn(this, "SEND 2E WRITE");
        LinearLayout.LayoutParams gp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 46));
        gp.setMargins(0, Ui.dp(this, 14), 0, 0);
        root.addView(go, gp);
        d.setContentView(root);
        d.show();

        go.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                final String value = input.getText().toString().trim();
                if (t.name.startsWith("VIN")
                        && !com.nirixx.app.core.vin.VinRules.isValidVin(value)) {
                    toast("Not a valid 17-char VIN (letters I/O/Q excluded)");
                    return;
                }
                d.dismiss();
                doWrite(t, addr.value, value);
            }
        });
    }

    private void doWrite(final Db.TestDef t, int did, final String value) {
        final Dialog prog = Ui.progressDialog(this, "Writing " + t.name + " (2E)…");
        prog.show();
        DiagOps.writeDidAscii(this, did, value, new DiagOps.Cb<Boolean>() {
            public void ok(Boolean v) {
                prog.dismiss();
                if (t.name.startsWith("VIN")) Session.selectedVin = value;
                db.putInput(Session.sessionKey, "write", t.name, value);
                Ui.resultDialog(WriteDataActivity.this, R.drawable.ic_flash_success,
                        "Write Accepted", "The ECU confirmed (6E): " + t.name + " = " + value,
                        "OK", new Runnable() { public void run() { readCurrentValues(); } }).show();
            }
            public void err(String what, String detail, Nrc nrc) {
                prog.dismiss();
                Ui.resultDialog(WriteDataActivity.this, R.drawable.ic_warn,
                        "Write Refused", detail, "OK", null).show();
            }
        });
    }
}
