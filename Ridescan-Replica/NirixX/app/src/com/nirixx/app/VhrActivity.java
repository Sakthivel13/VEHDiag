package com.nirixx.app;

import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.db.Db;
import java.util.ArrayList;
import java.util.List;

/** Vehicle Health Report — the reference tabbed wizard:
 *  DEALER | DIAGNOSTIC | IO CONTROL | PHYSICAL EVALUATION | SUMMARY.
 *  User-entered answers are stored as test inputs; the SUMMARY tab generates
 *  the MotoShield-style PDF report. */
public class VhrActivity extends BaseActivity {

    private static final String[] TABS = {"DEALER", "DIAGNOSTIC", "IO CONTROL", "PHYSICAL EVALUATION", "SUMMARY"};
    private int tab = 0;
    private LinearLayout content, host;
    private final TextView[] tabViews = new TextView[TABS.length];
    private Db db;
    private Db.Vehicle vehicle;
    private final Handler h = new Handler();
    private final List<double[]> ranges = new ArrayList<double[]>();
    private final List<String[]> liveRows = new ArrayList<String[]>();
    private String pdfPath = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Vehicle Health Report");
        db = Db.get(this);
        Session.ensureSession(this);
        vehicle = db.vehicle(Session.vehicleId);
        content = (LinearLayout) findViewById(R.id.content);
        render();
    }

    private void render() {
        content.removeAllViews();

        // tab strip (scrollable like the reference)
        HorizontalScrollView hs = new HorizontalScrollView(this);
        hs.setHorizontalScrollBarEnabled(false);
        LinearLayout strip = new LinearLayout(this);
        strip.setOrientation(LinearLayout.HORIZONTAL);
        strip.setPadding(Ui.dp(this, 4), 0, Ui.dp(this, 4), 0);
        for (int i = 0; i < TABS.length; i++) {
            final int k = i;
            LinearLayout cell = new LinearLayout(this);
            cell.setOrientation(LinearLayout.VERTICAL);
            TextView t = Ui.tv(this, TABS[i], 13.5f, i == tab ? 0xFF14276F : 0xFF9AA3B4, i == tab);
            t.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 6));
            cell.addView(t);
            View under = new View(this);
            GradientDrawable g = new GradientDrawable();
            g.setColor(i == tab ? 0xFF14276F : 0x00000000);
            under.setBackgroundDrawable(g);
            cell.addView(under, new LinearLayout.LayoutParams(-1, Ui.dp(this, 3)));
            tabViews[i] = t;
            cell.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { tab = k; render(); }
            });
            strip.addView(cell);
        }
        hs.addView(strip);
        content.addView(hs);

        host = new LinearLayout(this);
        host.setOrientation(LinearLayout.VERTICAL);
        host.setPadding(0, Ui.dp(this, 10), 0, 0);
        content.addView(host);

        switch (tab) {
            case 0: tabDealer(); break;
            case 1: tabDiagnostic(); break;
            case 2: tabIoControl(); break;
            case 3: tabPhysical(); break;
            default: tabSummary();
        }
    }

    private void next(String label) {
        TextView next = Ui.navyBtn(this, label);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.setMargins(0, Ui.dp(this, 12), 0, Ui.dp(this, 10));
        host.addView(next, lp);
        next.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                if (tab == 3 && !physicalComplete()) {
                    // reference behavior: blocking red validation bar
                    Ui.errorBar(VhrActivity.this,
                            "Please fill & upload picture of all the fields");
                    return;
                }
                if (tab < TABS.length - 1) { tab++; render(); }
            }
        });
    }

    /** PHYSICAL EVALUATION is a legal-grade checklist: every row needs its
     *  measured value/quality pick AND an attached photo before continuing —
     *  same requirement the reference app enforces with its red snackbar. */
    private boolean physicalComplete() {
        java.util.List<String[]> items = db.vhrItems(Session.vehicleId);
        for (String[] it : items) {
            String name = it[0], kind = it[4];
            Object photo = Session.vhrData.get("photo|" + name);
            boolean hasPhoto = photo != null && String.valueOf(photo).length() > 0;
            if ("PHOTO".equals(kind)) {
                if (!hasPhoto) return false;
            } else {
                Object val = Session.vhrData.get("phys|" + name);
                if (val == null || String.valueOf(val).trim().length() == 0) return false;
                if (!hasPhoto) return false;
            }
        }
        return true;
    }

    // ---------------------------------------------------------------- DEALER
    private void tabDealer() {
        LinearLayout card = Ui.card(this);
        card.addView(Ui.tv(this, "DEALER & VEHICLE INFO", 14.5f, 0xFF1A2138, true));
        card.addView(Ui.kvRow(this, "Dealer Name", Session.dealerName, false));
        card.addView(Ui.kvRow(this, "Dealer Code", Session.dealerCode, false));
        card.addView(Ui.kvRow(this, "Dealer Email", Session.dealerEmail.length() > 0 ? Session.dealerEmail : "—", false));
        card.addView(Ui.kvRow(this, "Variant", vehicle != null ? vehicle.model : Session.selectedVehicle, false));
        card.addView(Ui.kvRow(this, "VIN", Session.selectedVin, false));
        card.addView(Ui.kvRow(this, "Odometer", Session.odometer, true));
        host.addView(card);

        LinearLayout vehicleCard = new LinearLayout(this);
        vehicleCard.setOrientation(LinearLayout.VERTICAL);
        vehicleCard.setBackgroundResource(R.drawable.bg_card);
        ImageView iv = new ImageView(this);
        iv.setImageResource(Ui.imgRes(this, Session.vehicleImage));
        vehicleCard.addView(iv, new LinearLayout.LayoutParams(-1, Ui.dp(this, 150)));
        host.addView(vehicleCard);
        next("Next");
    }

    // ---------------------------------------------------------------- DIAGNOSTIC
    private void tabDiagnostic() {
        liveRows.clear(); ranges.clear();
        host.addView(Ui.tv(this, Session.selectedEcuCode.split("-")[0] + " - LIVE DATA",
                13.5f, 0xFF5A6472, true));
        List<Db.TestDef> defs = db.tests(Session.ecuId, "live");
        LinearLayout table = new LinearLayout(this);
        table.setOrientation(LinearLayout.VERTICAL);
        table.setBackgroundResource(R.drawable.bg_box_outline);
        int shown = 0;
        for (final Db.TestDef t : defs) {
            if (t.vmax == t.vmin) continue;             // identifier-strings skip the table
            if (shown++ >= 8) break;                    // first block, like the Ems-LIVE DATA page
            // REAL data only: the last value genuinely sampled this session.
            String sampled = db.lastSample(Session.sessionKey, t.id);
            final boolean measured = sampled != null;
            String value = measured ? sampled : "NM";
            boolean ok = false;
            if (measured) {
                try {
                    double pv = Double.parseDouble(sampled);
                    ok = pv >= t.vmin && pv <= t.vmax;
                } catch (Exception e) { ok = true; }
            }
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.VERTICAL);
            row.setBackgroundColor(0xFFEDF1F7);
            row.setPadding(Ui.dp(this, 12), Ui.dp(this, 9), Ui.dp(this, 12), Ui.dp(this, 9));
            LinearLayout line = new LinearLayout(this);
            line.setOrientation(LinearLayout.HORIZONTAL);
            TextView name = Ui.tv(this, t.name, 13.5f, 0xFF1A2138, true);
            name.setTypeface(null, android.graphics.Typeface.BOLD_ITALIC);
            line.addView(name, new LinearLayout.LayoutParams(0, -2, 1f));
            TextView val = Ui.tv(this, value, 14f,
                    !measured ? 0xFF9AA6B4 : (ok ? 0xFF2E9E43 : 0xFFE53935), true);
            line.addView(val);
            row.addView(line);
            row.addView(Ui.tv(this, measured
                            ? "Min:  " + trim(t.vmin) + "   Max:  " + trim(t.vmax)
                            : "Not measured this session — open Live Parameter with a VCI connected",
                    12f, 0xFF5A6472, true));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
            lp.setMargins(0, 0, 0, Ui.dp(this, 2));
            table.addView(row, lp);
            liveRows.add(new String[]{t.name,
                    measured ? trim(t.vmin) : "—", measured ? trim(t.vmax) : "—",
                    value, !measured ? "NOT MEASURED" : (ok ? "PASS" : "FAIL")});
            if (measured) Session.vhrData.put("live|" + t.name, value);
        }
        host.addView(table);
        LinearLayout note = Ui.card(this);
        note.addView(Ui.tv(this, "NM = not measured. The report lists only values actually read "
                + "during this session; measure them on the Live Parameter screen (VCI required).",
                12f, 0xFF5A6472, false));
        host.addView(note);
        next("NEXT");
    }

    private static String trim(double v) {
        return v == Math.floor(v) ? String.valueOf((long) v) : String.valueOf(v);
    }

    // ---------------------------------------------------------------- IO CONTROL
    private void tabIoControl() {
        List<Db.Ecu> ecus = db.ecus(Session.vehicleId);
        for (Db.Ecu e : ecus) {
            final Db.Ecu fe = e;
            final List<Db.TestDef> ios = db.tests(fe.id, "io");
            if (ios.isEmpty()) continue;
            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setBackgroundResource(R.drawable.bg_card);
            card.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 8));
            TextView head = Ui.tv(this, e.code.split("-")[0], 15f, 0xFF1A2138, true);
            head.setTypeface(null, android.graphics.Typeface.BOLD_ITALIC);
            card.addView(head);
            for (final Db.TestDef t : ios) {
                LinearLayout row = new LinearLayout(this);
                row.setOrientation(LinearLayout.HORIZONTAL);
                row.setGravity(android.view.Gravity.CENTER_VERTICAL);
                row.setBackgroundResource(R.drawable.bg_card_grey);
                row.setPadding(Ui.dp(this, 12), Ui.dp(this, 6), Ui.dp(this, 12), Ui.dp(this, 6));
                row.addView(Ui.tv(this, t.name, 13.5f, 0xFF1A2138, false),
                        new LinearLayout.LayoutParams(0, -2, 1f));
                final TextView okv = Ui.tv(this, "—", 13f, 0xFF9AA3B4, false);
                row.addView(okv);
                // real actuations happen on the IO Control screen (needs a published
                // DID + live link); here we only surface results recorded this session
                String recorded = db.lastInput(Session.sessionKey, "io", fe.code + "|" + t.name);
                if (recorded != null) {
                    okv.setText(recorded);
                    okv.setTextColor(0xFF2E9E43);
                } else {
                    okv.setText("not run");
                    okv.setTextColor(0xFF9AA3B4);
                }
                LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(-1, -2);
                rp.setMargins(0, Ui.dp(this, 4), 0, 0);
                card.addView(row, rp);
            }
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
            lp.setMargins(0, 0, 0, Ui.dp(this, 10));
            host.addView(card, lp);
        }
        next("Next");
    }

    // ---------------------------------------------------------------- PHYSICAL EVALUATION
    private void tabPhysical() {
        List<String[]> items = db.vhrItems(Session.vehicleId);
        for (final String[] it : items) {
            final LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.HORIZONTAL);
            card.setBackgroundResource(R.drawable.bg_card);
            card.setPadding(Ui.dp(this, 12), Ui.dp(this, 12), Ui.dp(this, 12), Ui.dp(this, 12));

            final LinearLayout thumb = Ui.photoThumb(this);
            thumb.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { pickImage(it[0]); }
            });
            thumb.setOnLongClickListener(new View.OnLongClickListener() {
                public boolean onLongClick(View v) { clearImage(it[0], thumb); return true; }
            });
            card.addView(thumb);
            showStoredImage(it[0], thumb);

            LinearLayout right = new LinearLayout(this);
            right.setOrientation(LinearLayout.VERTICAL);
            right.addView(Ui.tv(this, it[0], 14f, 0xFF1A2138, true));

            if ("VAL".equals(it[4])) {
                LinearLayout box = new LinearLayout(this);
                box.setOrientation(LinearLayout.HORIZONTAL);
                box.setBackgroundResource(R.drawable.bg_box_outline);
                box.setGravity(android.view.Gravity.CENTER_VERTICAL);
                box.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 12), 0);
                final EditText e = new EditText(this);
                e.setInputType(InputType.TYPE_CLASS_NUMBER);
                e.setBackgroundColor(0x00000000);
                e.setHint(it[2]);
                box.addView(e, new LinearLayout.LayoutParams(0, -1, 1f));
                box.addView(Ui.tv(this, it[1], 13.5f, 0xFF5A6472, false));
                LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-1, Ui.dp(this, 44));
                bp.setMargins(0, Ui.dp(this, 6), 0, 0);
                right.addView(box, bp);
                right.addView(Ui.tv(this, "Range: " + it[2] + " - " + it[3], 12f, 0xFF5A6472, false));
                e.setOnFocusChangeListener(new View.OnFocusChangeListener() {
                    public void onFocusChange(View v, boolean has) {
                        if (!has) {
                            Session.vhrData.put("phys|" + it[0], e.getText().toString());
                            db.putInput(Session.sessionKey, "phys", it[0], e.getText().toString());
                        }
                    }
                });
            } else if ("QUAL".equals(it[4])) {
                LinearLayout qual = new LinearLayout(this);
                qual.setOrientation(LinearLayout.HORIZONTAL);
                qual.setPadding(0, Ui.dp(this, 8), 0, 0);
                final TextView ok = Ui.tv(this, "\uD83D\uDC4D  Ok     ", 14f, 0xFF14276F, true);
                final TextView nok = Ui.tv(this, "\uD83D\uDC4E  Not Ok", 14f, 0xFF9AA3B4, false);
                qual.addView(ok); qual.addView(nok);
                right.addView(qual);
                View.OnClickListener set = new View.OnClickListener() {
                    public void onClick(View v) {
                        boolean isOk = v == ok;
                        ok.setTextColor(isOk ? 0xFF14276F : 0xFF9AA3B4);
                        nok.setTextColor(!isOk ? 0xFF14276F : 0xFF9AA3B4);
                        Session.vhrData.put("phys|" + it[0], isOk ? "Ok" : "Not Ok");
                        db.putInput(Session.sessionKey, "phys", it[0], isOk ? "Ok" : "Not Ok");
                    }
                };
                ok.setOnClickListener(set); nok.setOnClickListener(set);
            } else {
                right.addView(Ui.tv(this, "Tap the tile to attach a photo", 12f, 0xFF5A6472, false));
            }
            card.addView(right, new LinearLayout.LayoutParams(0, -2, 1f));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
            lp.setMargins(0, 0, 0, Ui.dp(this, 10));
            host.addView(card, lp);
        }
        next("Next");
    }

    // ---------------------------------------------------------------- photos
    private static final int REQ_IMG = 41;
    private String pendingPhotoItem;

    /** Real gallery/SAF pick — framework-only (no extra libraries, no
     *  storage permission on API 19+).  Selected image is copied into the
     *  Reports folder so it survives URI revocation and embeds into the PDF. */
    private void pickImage(String item) {
        pendingPhotoItem = item;
        android.content.Intent i = new android.content.Intent(android.content.Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(android.content.Intent.CATEGORY_OPENABLE);
        i.setType("image/*");
        try {
            startActivityForResult(i, REQ_IMG);
        } catch (Exception e) {
            toast("No gallery available on this device");
        }
    }

    private void clearImage(String item, LinearLayout thumb) {
        Session.vhrData.remove("photo|" + item);
        db.putInput(Session.sessionKey, "photo", item, "");
        android.widget.ImageView iv = (android.widget.ImageView) thumb.getChildAt(0);
        iv.setImageResource(R.drawable.ic_camera);
        iv.setScaleType(android.widget.ImageView.ScaleType.CENTER_INSIDE);
        toast("Image removed — tap to pick a new one");
    }

    private void showStoredImage(String item, LinearLayout thumb) {
        String path = Session.vhrData.get("photo|" + item);
        if (path == null || path.length() == 0) return;
        android.graphics.Bitmap bmp = decodeScaled(path, 160);
        if (bmp != null) {
            android.widget.ImageView iv = (android.widget.ImageView) thumb.getChildAt(0);
            iv.setImageBitmap(bmp);
            iv.setScaleType(android.widget.ImageView.ScaleType.CENTER_CROP);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, android.content.Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_IMG || resultCode != RESULT_OK || data == null || data.getData() == null) return;
        String item = pendingPhotoItem;
        pendingPhotoItem = null;
        if (item == null) return;
        try {
            java.io.InputStream in = getContentResolver().openInputStream(data.getData());
            java.io.File dir = new java.io.File(getExternalFilesDir(null), "Reports");
            dir.mkdirs();
            java.io.File out = new java.io.File(dir,
                    "vhr_" + item.replaceAll("[^A-Za-z0-9]+", "_") + ".jpg");
            java.io.FileOutputStream fos = new java.io.FileOutputStream(out);
            byte[] buf = new byte[8192]; int n;
            while ((n = in.read(buf)) > 0) fos.write(buf, 0, n);
            fos.close(); in.close();
            Session.vhrData.put("photo|" + item, out.getAbsolutePath());
            db.putInput(Session.sessionKey, "photo", item, out.getAbsolutePath());
            render();               // re-draw current tab so thumbnails refresh
        } catch (Exception e) {
            toast("Couldn't read that image: " + e.getMessage());
        }
    }

    private static android.graphics.Bitmap decodeScaled(String path, int maxDim) {
        try {
            android.graphics.BitmapFactory.Options o1 = new android.graphics.BitmapFactory.Options();
            o1.inJustDecodeBounds = true;
            android.graphics.BitmapFactory.decodeFile(path, o1);
            int scale = 1;
            while ((o1.outWidth / (scale * 2) > maxDim) || (o1.outHeight / (scale * 2) > maxDim)) scale *= 2;
            android.graphics.BitmapFactory.Options o2 = new android.graphics.BitmapFactory.Options();
            o2.inSampleSize = scale;
            return android.graphics.BitmapFactory.decodeFile(path, o2);
        } catch (Exception e) { return null; }
    }

    // ---------------------------------------------------------------- SUMMARY
    private void tabSummary() {
        boolean anyFail = false;
        for (String[] r : liveRows) if ("FAIL".equals(r[4])) { anyFail = true; break; }
        for (String v : Session.vhrData.values()) if ("Not Ok".equals(v)) { anyFail = true; break; }
        final String verdict = anyFail ? "Attention Needed" : "Passed";

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackgroundResource(R.drawable.bg_card);
        card.setPadding(Ui.dp(this, 16), Ui.dp(this, 20), Ui.dp(this, 16), Ui.dp(this, 20));
        LinearLayout row = new LinearLayout(this);
        row.setGravity(android.view.Gravity.CENTER_VERTICAL);
        ImageView shield = new ImageView(this);
        shield.setImageResource(R.drawable.ic_shield);
        row.addView(shield, new LinearLayout.LayoutParams(Ui.dp(this, 46), Ui.dp(this, 46)));
        TextView verdictTv = Ui.tv(this, "  " + verdict, 19f, anyFail ? 0xFFF9A825 : 0xFF2E9E43, true);
        row.addView(verdictTv);
        card.addView(row);
        card.addView(Ui.tv(this, "Vehicle Health Condition", 13f, 0xFF5A6472, false));
        card.addView(Ui.tv(this, "Date: " + new java.text.SimpleDateFormat("yyyy-MM-dd",
                java.util.Locale.US).format(new java.util.Date()), 13f, 0xFF5A6472, false));
        card.addView(Ui.tv(this, "Disclaimer: This is not a legal document. All parameters recorded "
                + "are at the time of inspection.", 11.5f, 0xFF9AA3B4, false));
        host.addView(card);

        TextView gen = Ui.navyBtn(this, "GENERATE PDF REPORT");
        LinearLayout.LayoutParams gp = new LinearLayout.LayoutParams(-1, -2);
        gp.setMargins(0, Ui.dp(this, 12), 0, 0);
        host.addView(gen, gp);
        gen.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { generate(verdict); }
        });
    }

    private void generate(final String verdict) {
        final android.app.Dialog d = Ui.progressDialog(this, "Composing PDF…");
        d.show();
        h.postDelayed(new Runnable() {
            public void run() {
                d.dismiss();
                pdfPath = PdfReport.generate(VhrActivity.this, verdict, liveRows);
                if (pdfPath != null) {
                    Session.reportGenerated = true;
                    db.saveVhr(Session.sessionKey, Session.vehicleId, Session.selectedVin, pdfPath, verdict);
                    Ui.resultDialog(VhrActivity.this, R.drawable.ic_flash_success,
                            "Report Generated",
                            Session.selectedVehicle.replace("TVS ", "") + "_" + Session.selectedVin + "_VHR.pdf"
                                    + "\n\nSaved to app storage and listed under Reports.",
                            "Open Reports", new Runnable() {
                                public void run() { go(ReportsActivity.class); finish(); }
                            }).show();
                } else {
                    toast("PDF generation failed");
                }
            }
        }, 1400);
    }
}
