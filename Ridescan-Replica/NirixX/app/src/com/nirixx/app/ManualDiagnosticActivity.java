package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import com.nirixx.app.db.Db;
import java.util.List;

/** Manual diagnostic path when VIN auto-identification is unavailable — offers
 *  every vehicle in the real catalogue (the supplied 33-model table), exactly
 *  like Vehicle List, then routes into the standard ECU selection flow. */
public class ManualDiagnosticActivity extends BaseActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Manual Diagnostic");
        wireBack();
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        android.widget.TextView note = Ui.tv(this,
                "VIN auto-identification unavailable? Pick the model manually — the app routes "
                        + "to the correct ECU flow using the vehicle catalogue.",
                12.5f, 0xFF5A6472, false);
        note.setBackgroundResource(R.drawable.bg_card);
        note.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
        content.addView(note);

        content.addView(Ui.section(this, "SELECT MODEL"));
        Db db = Db.get(this);
        List<Db.Vehicle> all = db.vehicles();
        for (int i = 0; i < all.size(); i++) {
            final Db.Vehicle v = all.get(i);
            int art = artFor(v.image);
            LinearLayout row = Ui.listRow(this, art, v.model,
                    v.variant == null || v.variant.length() == 0 ? v.type : v.variant, true);
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View vw) {
                    Session.selectedVehicle = v.model;
                    Session.selectedVariant = v.variant == null ? "" : v.variant;
                    Session.selectedVin = v.vinSample == null ? "" : v.vinSample;
                    Session.vehicleId = v.id;
                    Session.vehicleType = v.type == null ? "" : v.type;
                    Session.vehicleImage = v.image == null ? "" : v.image;
                    go(SelectECUActivity.class);
                }
            });
            content.addView(row);
        }
    }

    private int artFor(String image) {
        if (image == null) return R.drawable.motorcycle;
        int id = getResources().getIdentifier(image, "drawable", getPackageName());
        return id != 0 ? id : R.drawable.motorcycle;
    }
}
