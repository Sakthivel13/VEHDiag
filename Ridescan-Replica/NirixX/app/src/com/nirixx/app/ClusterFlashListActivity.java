package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;

/** Instrument cluster flashing modules (J125 / N597 / U577 / U732 / U796). */
public class ClusterFlashListActivity extends BaseActivity {
    private static final String[][] CLUSTERS = {
        {"J125 Cluster Flashing", "Basic LCD cluster — Jupiter / XL100"},
        {"N597 Cluster Flashing", "N597 platform digital cluster"},
        {"U577 Basic Cluster Flash", "U577 basic LCD generation"},
        {"U577 Premium Cluster Flash", "U577 premium with premium UI pack"},
        {"U732 RLCD Cluster Flash", "Connected cluster — RLCD"},
        {"U732 TFT Cluster Flash", "Connected cluster — full TFT (CONNECTED CLUSTER)"},
        {"U796 Cluster Flash", "Latest-gen TFT cluster platform"},
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Cluster Flashing");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);
        content.addView(Ui.section(this, "SELECT CLUSTER MODULE"));
        for (int i = 0; i < CLUSTERS.length; i++) {
            final String[] cDat = CLUSTERS[i];
            LinearLayout row = Ui.listRow(this, R.drawable.mod_cluster, cDat[0], cDat[1], true);
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    android.content.Intent it = new android.content.Intent(ClusterFlashListActivity.this, SupplierFlashActivity.class);
                    it.putExtra("module", cDat[0]);
                    it.putExtra("image_type", "Select IMAGE type");
                    it.putExtra("family", "INSTRUMENT CLUSTER");
                    startActivity(it);
                }
            });
            content.addView(row);
        }
    }
}
