package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import com.nirixx.app.vci.VciModel;

/** VCI dongle firmware flows, one per NirixX hardware generation. */
public class VciFirmwareListActivity extends BaseActivity {

    private static final String[] ROUTES = {
        "FirmwareUpdate", "TZVCIFirmwareUpdate", "TZMiniVCIFirmwareUpdate",
        "TZNewVCIFirmwareUpdate", "TZ24vVCIFirmwareUpdate", "PodFirmwareUpdate",
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("VCI Firmware Update");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        content.addView(Ui.section(this, "SELECT VCI HARDWARE"));
        VciModel[] all = VciModel.all();
        int routeAt = 0;
        for (int i = 0; i < all.length; i++) {
            final VciModel m = all[i];
            if (m.thirdParty) continue;
            int iconRes = getResources().getIdentifier(m.drawable, "drawable", getPackageName());
            final String route = ROUTES[routeAt % ROUTES.length];
            routeAt++;
            LinearLayout row = Ui.listRow(this, iconRes > 0 ? iconRes : R.drawable.vci,
                    m.name, m.blurb + "  ·  " + route, true);
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    android.content.Intent it = new android.content.Intent(VciFirmwareListActivity.this, FirmwareUpdateActivity.class);
                    it.putExtra("device", m.name);
                    startActivity(it);
                }
            });
            content.addView(row);
        }

        android.widget.TextView tip = Ui.tv(this,
                "Third-party adapters (ELM327-compatible, J2534, USB K-Line) update with their own vendor tools. Keep the dongle plugged into the OBD port during update — recovery uses the bundled recovery image.",
                12f, 0xFF5A6472, false);
        tip.setBackgroundResource(R.drawable.bg_card);
        tip.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
        content.addView(tip);
    }
}
