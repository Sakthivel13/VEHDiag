package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;

/** Full supplier flash module catalog — mirrors the original ~25 per-supplier modules. */
public class SupplierFlashListActivity extends BaseActivity {

    static final String[] FAMILIES = {
        "CONTINENTAL", "BOSCH ABS", "PRICOL", "SEDEMAC", "MIKUNI / KEMS", "KEIHIN / INEL / ISG", "OTHERS",
    };

    private static final String[][] MODULES = {
        // name, family, image-type, notes
        {"Conti Flash", "CONTINENTAL", "Boot + App", "Continental EMS — classic flash"},
        {"Conti2 Flash", "CONTINENTAL", "Boot + App", "Continental Gen-2 EMS"},
        {"ABS Flashing — Conti", "BOSCH ABS", "App", "Continental ABS module"},
        {"BABS Flash", "BOSCH ABS", "App", "Bosch ABS — single channel"},
        {"BABS2 Flash", "BOSCH ABS", "App", "Bosch ABS Gen-2"},
        {"KABS Flash", "BOSCH ABS", "App", "KABS module — Raider / Ntorq"},
        {"Pricol Flash", "PRICOL", "Select Booloader type", "Pricol base cluster/EMS"},
        {"Pricol 2/4/5 Flash", "PRICOL", "Select Booloader type", "Pricol 2/4/5-variant family"},
        {"Pricol Apache Flash", "PRICOL", "Select Booloader type", "Apache series Pricol ECU"},
        {"Pricol BTO Flash", "PRICOL", "Select Booloader type", "Built-To-Order variants"},
        {"Pricol TPMS Flash", "PRICOL", "App", "TPMS controller"},
        {"Pricol U400 Flash", "PRICOL", "Select Booloader type", "U400 platform"},
        {"Mid Variant Pricol2 Flash", "PRICOL", "Select Booloader type", "Mid-variant second-gen"},
        {"SEDEMAC EMS Flash", "SEDEMAC", "Boot + App", "Sedemac EMS — UDS"},
        {"SEDEMAC XL100 OBD2B Flash", "SEDEMAC", "Boot + App", "XL100 OBD-II B platform"},
        {"U558 Sedemac EMS Flash", "SEDEMAC", "Boot + App", "U558 platform"},
        {"KEMS Flash (Mikuni)", "MIKUNI / KEMS", "App", "Mikuni KEMS controller"},
        {"Mikuni CAN Flash", "MIKUNI / KEMS", "App", "CAN-bus Mikuni EMS"},
        {"KEMS Flash Recovery", "MIKUNI / KEMS", "App", "Boot-mode recovery flashing"},
        {"Keihin Flash — Sport", "KEIHIN / INEL / ISG", "App", "Keihin sporty EMS"},
        {"INEL Flash", "KEIHIN / INEL / ISG", "App", "INEL ignition/EMS controller"},
        {"ISG Flash", "KEIHIN / INEL / ISG", "App", "Integrated Starter Generator"},
        {"ISG Flash — Jupiter", "KEIHIN / INEL / ISG", "App", "Jupiter ISG variant"},
        {"ISG Flash — Raider", "KEIHIN / INEL / ISG", "App", "Raider ISG variant"},
        {"Keyless ECU Flashing", "OTHERS", "App", "Keyless-go controller"},
        {"Ronin Flash Variant", "OTHERS", "Boot + App", "Ronin-specific flash path"},
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("ECU Flashing — Select Module");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        for (int f = 0; f < FAMILIES.length; f++) {
            content.addView(Ui.section(this, FAMILIES[f]));
            for (int i = 0; i < MODULES.length; i++) {
                final String[] m = MODULES[i];
                if (!FAMILIES[f].equals(m[1])) continue;
                int icon = m[0].contains("Keyless") ? R.drawable.mod_keyfob
                        : (m[0].contains("TPMS") ? R.drawable.battery
                        : (m[1].contains("BOSCH") ? R.drawable.mod_abs
                        : (m[1].contains("PRICOL") ? R.drawable.mod_cluster
                        : (m[1].contains("SEDEMAC") ? R.drawable.mod_fi
                        : (m[1].contains("MIKUNI") ? R.drawable.mod_bcm
                        : (m[1].contains("KEIHIN") ? R.drawable.mod_isg
                        : R.drawable.ecu_module))))));
                LinearLayout row = Ui.listRow(this, icon, m[0], m[2] + "  ·  " + m[3], true);
                row.setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) {
                        android.content.Intent it = new android.content.Intent(SupplierFlashListActivity.this, SupplierFlashActivity.class);
                        it.putExtra("module", m[0]);
                        it.putExtra("image_type", m[2]);
                        it.putExtra("family", m[1]);
                        startActivity(it);
                    }
                });
                content.addView(row);
            }
        }
    }
}
