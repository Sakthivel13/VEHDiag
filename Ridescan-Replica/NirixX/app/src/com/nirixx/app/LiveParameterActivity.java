package com.nirixx.app;

import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.TextView;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.diag.TestAddr;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.Obd;
import com.nirixx.app.core.uds.UdsClient;
import com.nirixx.app.db.Db;
import java.util.ArrayList;
import java.util.List;

/** Live Parameter screen — real values only.
 *  Rows whose definition carries a published address (pid:/did:/m09:) are
 *  polled from the vehicle through DiagOps; rows without an address stay at
 *  "—" and say why.  Without a live VCI link nothing moves and the screen
 *  says so.  No mock streams. */
public class LiveParameterActivity extends BaseActivity {

    private final Handler h = new Handler();
    private boolean tick = false;
    private LinearLayout list;
    private Db db;
    private List<Db.TestDef> defs;
    private String filter = "ALL";
    private final List<TextView> valSlots = new ArrayList<TextView>();
    private final List<Db.TestDef> slotDefs = new ArrayList<Db.TestDef>();
    private final List<TestAddr> slotAddrs = new ArrayList<TestAddr>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Live Parameter");
        showEcuChip(Session.selectedEcuCode, true);
        db = Db.get(this);
        Session.ensureSession(this);

        LinearLayout content = (LinearLayout) findViewById(R.id.content);
        content.removeAllViews();
        content.addView(Ui.crumbs(this, new String[]{"Home", Session.selectedVehicle,
                Session.selectedEcuCode, "Live Parameter"}));

        if (!DiagOps.live()) {
            LinearLayout warn = Ui.card(this);
            warn.addView(Ui.tv(this, "NO LIVE VCI LINK — showing parameter definitions only",
                    12f, 0xFFB26A00, true));
            warn.addView(Ui.tv(this, "Values appear when the NirixiLINK is connected to a vehicle. "
                    + "Rows without a published address (″definition pending″) need the OEM "
                    + "definition pack.", 12.5f, 0xFF5A6472, false));
            content.addView(warn);
        }

        defs = db.tests(Session.ecuId, "live");

        final List<String> cats = new ArrayList<String>();
        cats.add("ALL");
        for (Db.TestDef t : defs) if (t.category != null && !cats.contains(t.category)) cats.add(t.category);
        Spinner spin = new Spinner(this);
        ArrayAdapter<String> ad = new ArrayAdapter<String>(this,
                android.R.layout.simple_spinner_dropdown_item, cats);
        spin.setAdapter(ad);
        spin.setBackgroundResource(R.drawable.bg_box_outline);
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 44));
        sp.setMargins(0, 0, 0, Ui.dp(this, 10));
        content.addView(spin, sp);
        spin.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                filter = cats.get(position);
                render();
            }
            public void onNothingSelected(AdapterView<?> parent) { }
        });

        list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        content.addView(list);
        render();
    }

    private void render() {
        list.removeAllViews();
        valSlots.clear();
        slotDefs.clear();
        slotAddrs.clear();
        for (Db.TestDef t : defs) {
            if (!"ALL".equals(filter) && !filter.equals(t.category)) continue;
            TestAddr a = TestAddr.parse(t.addr);
            boolean readable = a != null
                    && (a.kind == TestAddr.PID || a.kind == TestAddr.DID || a.kind == TestAddr.M09);
            LinearLayout card = Ui.paramCard(this, t.name, t.category, "—",
                    t.vmax == t.vmin ? "" : String.valueOf(t.vmin),
                    t.vmax == t.vmin ? "" : String.valueOf(t.vmax),
                    readable ? (DiagOps.live() ? ("Polling " + a.toString()) : "Address " + a.toString())
                            : "Definition pending — no published address");
            TextView val = (TextView) card.getTag();
            valSlots.add(val);
            slotDefs.add(t);
            slotAddrs.add(readable ? a : null);
            list.addView(card);
        }
        tick = true;
        scheduleSweep();
    }

    /** One full sweep of the readable rows; the next sweep starts only when
     *  this one finished (self-pacing — never overruns the single-bus executor). */
    private void scheduleSweep() { h.postDelayed(sweep, 1200); }

    private final Runnable sweep = new Runnable() {
        public void run() {
            if (!tick) return;
            if (!DiagOps.live()) { h.postDelayed(this, 2000); return; }
            int count = 0;
            for (int i = 0; i < slotAddrs.size(); i++) if (slotAddrs.get(i) != null) count++;
            if (count == 0) { h.postDelayed(this, 2000); return; }
            final int[] pending = {count};
            final Runnable done = new Runnable() {
                public void run() {
                    if (--pending[0] <= 0 && tick) h.postDelayed(sweep, 800);
                }
            };
            for (int i = 0; i < slotDefs.size(); i++) {
                final int idx = i;
                final TestAddr a = slotAddrs.get(i);
                if (a == null) continue;
                if (a.kind == TestAddr.PID) {
                    DiagOps.obdPid(LiveParameterActivity.this, a.value, new DiagOps.Cb<Double>() {
                        public void ok(Double v) { showNum(idx, a, v.doubleValue()); done.run(); }
                        public void err(String w, String d, Nrc n) { showErr(idx); done.run(); }
                    });
                } else if (a.kind == TestAddr.DID) {
                    DiagOps.readDidRaw(LiveParameterActivity.this, a.value, new DiagOps.Cb<byte[]>() {
                        public void ok(byte[] v) { showText(idx, UdsClient.ascii(v)); done.run(); }
                        public void err(String w, String d, Nrc n) { showErr(idx); done.run(); }
                    });
                } else if (a.kind == TestAddr.M09) {
                    DiagOps.mode09(LiveParameterActivity.this, a.value, new DiagOps.Cb<byte[]>() {
                        public void ok(byte[] v) {
                            String s = Obd.asciiInfo(v);
                            showText(idx, s == null ? UdsClient.hexBytes(v) : s);
                            done.run();
                        }
                        public void err(String w, String d, Nrc n) { showErr(idx); done.run(); }
                    });
                }
            }
        }
    };

    private void showNum(int idx, TestAddr a, double v) {
        if (!tick || idx >= valSlots.size()) return;
        double shown = v * a.factor;
        TextView val = valSlots.get(idx);
        Db.TestDef t = slotDefs.get(idx);
        String s = shown == Math.floor(shown) && shown < 100000
                ? String.valueOf((long) shown)
                : String.format(java.util.Locale.US, "%.2f", shown);
        val.setText(s);
        boolean inRange = t.vmax == t.vmin || (shown >= t.vmin && shown <= t.vmax);
        val.setTextColor(inRange ? 0xFF1A2138 : 0xFFE53935);
        db.sample(Session.sessionKey, t.id, s);
    }

    private void showText(int idx, String s) {
        if (!tick || idx >= valSlots.size()) return;
        TextView val = valSlots.get(idx);
        val.setText(s == null || s.length() == 0 ? "—" : s);
        val.setTextColor(0xFF1A2138);
        db.sample(Session.sessionKey, slotDefs.get(idx).id, val.getText().toString());
    }

    private void showErr(int idx) {
        if (!tick || idx >= valSlots.size()) return;
        valSlots.get(idx).setText("ERR");
        valSlots.get(idx).setTextColor(0xFFE53935);
    }

    @Override
    protected void onPause() { tick = false; super.onPause(); }
}
