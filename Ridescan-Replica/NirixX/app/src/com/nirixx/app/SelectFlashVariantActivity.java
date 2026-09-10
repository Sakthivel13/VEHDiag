package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

/** Manual flash-variant picker backed by the bundled flash_variant.json. */
public class SelectFlashVariantActivity extends BaseActivity {
    private LinearLayout content;
    private int selected = -1;
    private final List<String[]> rows = new ArrayList<String[]>();
    private final List<RadioButton> radios = new ArrayList<RadioButton>();
    private android.widget.Button proceed;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Select Flash Variant");
        wireBack();
        content = (LinearLayout) findViewById(R.id.content);
        loadJson();
        build();
    }

    private void loadJson() {
        rows.clear();
        try {
            InputStream is = getAssets().open("flash_variant.json");
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while ((n = is.read(buf)) != -1) bos.write(buf, 0, n);
            is.close();
            JSONArray arr = new JSONArray(new String(bos.toByteArray(), "UTF-8"));
            for (int i = 0; i < arr.length(); i++) {
                JSONObject v = arr.getJSONObject(i);
                String variant = v.optString("variant");
                JSONArray models = v.optJSONArray("model_list");
                if (models == null) continue;
                for (int j = 0; j < models.length(); j++) {
                    JSONObject m = models.getJSONObject(j);
                    rows.add(new String[]{
                            variant,
                            m.optString("description"),
                            m.optString("value"),
                            m.optString("ecu"),
                            m.optString("norm"),
                    });
                }
            }
        } catch (Exception e) {
            rows.add(new String[]{"RR310_REFRESH", "Old software for vehicles produced before 31.07.2022 (Pulse make Ignition coil)", "RR310_REFRESH", "EMS", "BSVI"});
            rows.add(new String[]{"RR310_REFRESH", "New software for vehicles produced after 31.07.2022 (Bremi make Ignition coil)", "RR310_REFRESH_NEW", "EMS", "BSVI"});
        }
    }

    private void build() {
        content.removeAllViews();

        LinearLayout banner = Ui.card(this);
        TextView b1 = Ui.tv(this, rows.size() + " flash files available", 15f, 0xFF141B2E, true);
        TextView b2 = Ui.tv(this, "Vehicle: " + Session.selectedVehicle + "  ·  " + Session.selectedVariant
                + "\nMultiple hardware revisions detected — confirm the correct flash file.", 12f, 0xFF5A6472, false);
        b2.setPadding(0, Ui.dp(this, 4), 0, 0);
        banner.addView(b1);
        banner.addView(b2);
        content.addView(banner);

        content.addView(Ui.section(this, "VARIANT → ECU → FLASH FILE MAP"));
        int limit = Math.min(rows.size(), 40);
        for (int i = 0; i < limit; i++) {
            content.addView(rowFor(i));
        }
        if (rows.size() > limit) {
            TextView more = Ui.tv(this, "+ " + (rows.size() - limit) + " more variants in flash_variant.json", 12f, 0xFF5A6472, false);
            more.setPadding(Ui.dp(this, 6), 0, 0, Ui.dp(this, 10));
            content.addView(more);
        }

        proceed = new android.widget.Button(this);
        proceed.setText("Proceed");
        proceed.setTextColor(0xFFFFFFFF);
        proceed.setTextSize(15f);
        proceed.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        proceed.setAllCaps(false);
        proceed.setBackgroundResource(R.drawable.bg_button_blue);
        proceed.setEnabled(false);
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 50));
        pp.setMargins(0, Ui.dp(this, 6), 0, Ui.dp(this, 8));
        content.addView(proceed, pp);
        proceed.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                if (selected < 0) return;
                String[] r = rows.get(selected);
                Session.selectedFlashFile = r[2];
                Session.selectedEcu = r[3];
                Session.selectedVariant = r[0];
                go(FlashActivity.class);
            }
        });
    }

    private View rowFor(final int idx) {
        final String[] r = rows.get(idx);
        final RadioButton rb = new RadioButton(this);
        radios.add(rb);
        LinearLayout card = Ui.card(this);
        card.setPadding(Ui.dp(this, 12), Ui.dp(this, 12), Ui.dp(this, 12), Ui.dp(this, 12));

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(android.view.Gravity.CENTER_VERTICAL);
        top.addView(rb);
        LinearLayout mid = new LinearLayout(this);
        mid.setOrientation(LinearLayout.VERTICAL);
        mid.setPadding(Ui.dp(this, 8), 0, 0, 0);
        mid.addView(Ui.tv(this, r[2], 14.5f, 0xFF141B2E, true));
        mid.addView(Ui.tv(this, r[0] + "  ·  " + r[3] + "  ·  " + r[4], 11.5f, 0xFF0B8376, true));
        top.addView(mid, new LinearLayout.LayoutParams(0, -2, 1f));
        top.addView(Ui.chip(this, r[4], R.drawable.bg_chip, 0xFF0B8376));
        card.addView(top);
        if (r[1] != null && r[1].trim().length() > 0) {
            TextView desc = Ui.tv(this, r[1], 12f, 0xFF5A6472, false);
            desc.setPadding(Ui.dp(this, 40), Ui.dp(this, 6), 0, 0);
            card.addView(desc);
        }

        View.OnClickListener pick = new View.OnClickListener() {
            public void onClick(View v) {
                selected = idx;
                for (int k = 0; k < radios.size(); k++) radios.get(k).setChecked(k == idx);
                proceed.setEnabled(true);
            }
        };
        rb.setOnClickListener(pick);
        card.setOnClickListener(pick);
        return card;
    }
}
