package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import com.nirixx.app.core.diag.BatteryAssess;
import com.nirixx.app.core.diag.DiagOps;
import com.nirixx.app.core.uds.Nrc;
import com.nirixx.app.core.uds.Obd;
import java.util.ArrayList;
import java.util.List;

/** Battery Health — what the bus can truthfully tell us, and only that.
 *
 *  Real sources:  ELM327 ATRV (adapter supply = the 12 V rail on the DLC) and
 *  SAE J1979 PID 0x42 (control-module voltage).  SoC % derives from the public
 *  12 V lead-acid resting-voltage chart.  CCA / internal resistance / ripple
 *  require a conductance tester and are stated as NOT measurable over CAN —
 *  never estimated.  EV traction-pack SoH needs OEM pack DIDs (documented gap). */
public class BatteryHealthActivity extends BaseActivity {

    private LinearLayout rows;
    private final List<String[]> measured = new ArrayList<String[]>();
    private double adapterV = -1, moduleV = -1;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_battery);
        wireBack();
        rows = (LinearLayout) findViewById(R.id.statRows);
        rows.setPadding(Ui.dp(this, 10), 0, Ui.dp(this, 10), 0);
        findViewById(R.id.btnGenReport).setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { genReport(); }
        });
        render();
        measure();
    }

    private void render() {
        rows.removeAllViews();
        measured.clear();

        if (!DiagOps.live()) {
            LinearLayout warn = Ui.card(this);
            warn.addView(Ui.tv(this, "NO LIVE VCI LINK", 12f, 0xFFB26A00, true));
            warn.addView(Ui.tv(this, "Connect the NirixiLINK with ignition ON to measure the "
                    + "vehicle's 12 V rail. No voltage is shown until it is actually measured.",
                    12.5f, 0xFF5A6472, false));
            rows.addView(warn);
        } else {
            addRow("Terminal Voltage (adapter, key ON)",
                    adapterV < 0 ? "measuring…" : BatteryAssess.fmt(adapterV) + " V");
            addRow("Control Module Voltage (PID 42)",
                    moduleV < 0 ? "measuring…" : BatteryAssess.fmt(moduleV) + " V");
            if (adapterV > 0) {
                addRow("Estimated State of Charge (resting chart)",
                        BatteryAssess.socPercent(adapterV) + "%");
                addRow("Assessment", BatteryAssess.assessment(adapterV));
            }
        }

        addRow("Cold Cranking Amps (CCA)", "Not measurable via CAN — needs a conductance tester");
        addRow("Internal Resistance", "Not measurable via CAN — needs a conductance tester");
        addRow("Charging Ripple", "Not sampled by this tool — scope function not present");
        addRow("EV Traction-Pack SoH", "Needs OEM battery-pack DIDs (see MISSING_DEPENDENCIES.md)");
    }

    private void addRow(String k, String v) {
        rows.addView(Ui.kvRow(this, k, v, false));
        measured.add(new String[]{k, v});
    }

    private void measure() {
        if (!DiagOps.live()) return;
        DiagOps.adapterVoltage(this, new DiagOps.Cb<Double>() {
            public void ok(Double v) { adapterV = v.doubleValue(); render(); }
            public void err(String w, String d, Nrc n) { render(); }
        });
        DiagOps.obdPid(this, Obd.PID_CONTROL_MODULE_V, new DiagOps.Cb<Double>() {
            public void ok(Double v) { moduleV = v.doubleValue(); render(); }
            public void err(String w, String d, Nrc n) { render(); }
        });
    }

    private void genReport() {
        if (measured.size() == 0 || !DiagOps.live()) {
            toast("Nothing measured yet — connect a VCI first");
            return;
        }
        String verdict = adapterV > 0 ? BatteryAssess.assessment(adapterV) : "Inconclusive";
        String path = PdfReport.generate(this, "Battery: " + verdict, measured);
        if (path == null) {
            toast("Could not write the PDF");
        } else {
            Ui.resultDialog(this, R.drawable.ic_flash_success, "Report Generated",
                    path, "OK", null).show();
        }
    }
}
