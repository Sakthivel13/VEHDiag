package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.db.Db;
import java.util.List;

/** Vehicle home screen — every model in the database as its own grid card:
 *  image (from DB), model, description, type, protocol badges and VIN format. */
public class VehicleListActivity extends BaseActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Vehicle Selection");
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        content.addView(Ui.crumbs(this, new String[]{"Home", "Vehicle Selection"}));
        content.addView(Ui.section(this, "CHOOSE VEHICLE"));

        List<Db.Vehicle> vehicles = Db.get(this).vehicles();
        for (final Db.Vehicle v : vehicles) {
            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setBackgroundResource(R.drawable.bg_card);
            card.setPadding(0, Ui.dp(this, 8), 0, Ui.dp(this, 12));

            ImageView iv = new ImageView(this);
            iv.setImageResource(Ui.imgRes(this, v.image));
            card.addView(iv, new LinearLayout.LayoutParams(-1, Ui.dp(this, 150)));
            card.addView(pad(Ui.tv(this, v.model, 16.5f, 0xFF1A2138, true)));
            card.addView(pad(Ui.tv(this, v.description, 12.5f, 0xFF5A6472, false)));

            LinearLayout badges = new LinearLayout(this);
            badges.setOrientation(LinearLayout.HORIZONTAL);
            badges.setPadding(Ui.dp(this, 12), Ui.dp(this, 6), Ui.dp(this, 12), 0);
            badges.addView(Ui.chip(this, v.type, R.drawable.bg_chip_grey, 0xFF3A4663));
            badges.addView(Ui.chip(this, v.obd + " · " + v.protocol, R.drawable.bg_chip_grey, 0xFF14276F));
            badges.addView(Ui.chip(this, v.emission, R.drawable.bg_chip_grey, 0xFF2E7D32));
            card.addView(badges);

            card.addView(pad(Ui.tv(this, "VIN format:  " + v.vinFormat, 12f, 0xFF5A6472, false)));
            TextView sample = Ui.tv(this, "e.g. " + v.vinSample + "   ·   Variant " + v.variant,
                    12f, 0xFF5A6472, false);
            card.addView(pad(sample));

            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
            lp.setMargins(0, 0, 0, Ui.dp(this, 12));
            content.addView(card, lp);

            card.setOnClickListener(new View.OnClickListener() {
                public void onClick(View vw) {
                    Db.Ecu first = null;
                    List<Db.Ecu> es = Db.get(VehicleListActivity.this).ecus(v.id);
                    if (!es.isEmpty()) first = es.get(0);
                    Session.selectVehicle(v.id, v.model, v.variant, v.type, v.vinSample, v.image);
                    if (first != null) Session.selectEcu(first.id, first.name, first.code, first.tx, first.rx);
                    Session.selectedFlashFile = Db.get(VehicleListActivity.this).flashFile(Session.ecuId);
                    toast(v.model + " selected");
                    go(SelectECUActivity.class);
                    finish();
                }
            });
        }
    }

    private TextView pad(TextView t) {
        t.setPadding(Ui.dp(this, 12), Ui.dp(this, 2), Ui.dp(this, 12), 0);
        return t;
    }
}
