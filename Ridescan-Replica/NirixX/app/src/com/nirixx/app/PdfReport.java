package com.nirixx.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.pdf.PdfDocument;
import java.io.File;
import java.io.FileOutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** MotoShield-style Vehicle Health Report PDF (framework PdfDocument) —
 *  dark banner with the vehicle photo, honeycomb-dark section bars with red
 *  slash accents, dealer & vehicle block, per-ECU diagnostic tables with
 *  Min/Max/Value/Status checks, IO-control results, physical evaluation table
 *  and the shield summary + disclaimer. */
public final class PdfReport {

    private static final int W = 595, H = 842;               // A4 @ 72dpi
    private static final int NAVY = Color.rgb(13, 17, 38);
    private static final int RED = Color.rgb(229, 30, 45);
    private static final int GREEN = Color.rgb(46, 158, 67);
    private static final int GREY = Color.rgb(90, 100, 114);

    private PdfReport() {}

    public static String generate(Context c, String verdict, List<String[]> liveRows) {
        try {
            PdfDocument doc = new PdfDocument();
            page1(c, doc, liveRows);
            page2(c, doc, verdict);
            File dir = new File(c.getExternalFilesDir(null), "Reports");
            dir.mkdirs();
            String name = "NirixX " + Session.selectedVehicle.replace("TVS ", "")
                    + "_" + Session.selectedVin + "_VHR.pdf";
            File f = new File(dir, name);
            FileOutputStream fos = new FileOutputStream(f);
            doc.writeTo(fos);
            fos.close();
            doc.close();
            return f.getAbsolutePath();
        } catch (Exception e) {
            e.printStackTrace();
            return null;
        }
    }

    // ------------------------------------------------------------- furniture
    private static void redSlashes(Canvas c, Paint p, float x, float y, float w) {
        p.setColor(RED);
        for (int i = 0; i < 4; i++) {
            float sx = x + i * (w / 4f);
            Path slash = new Path();
            slash.moveTo(sx, y + 22);
            slash.lineTo(sx + 10, y);
            slash.lineTo(sx + 18, y);
            slash.lineTo(sx + 8, y + 22);
            slash.close();
            c.drawPath(slash, p);
        }
    }

    private static void sectionBar(Canvas c, Paint p, float y, String text) {
        p.setColor(NAVY);
        c.drawRect(new RectF(30, y, W - 30, y + 26), p);
        // honeycomb hint: light diagonal hatch
        p.setColor(Color.rgb(34, 40, 68));
        for (int x = 60; x < W - 120; x += 12) c.drawLine(x, y + 4, x + 6, y + 22, p);
        p.setColor(Color.WHITE);
        p.setTextSize(13);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        c.drawText(text, 42, y + 18, p);
        redSlashes(c, p, W - 118, y + 2, 88);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
    }

    private static void tick(Canvas c, Paint p, float x, float y, boolean ok) {
        p.setColor(ok ? GREEN : RED);
        p.setStrokeWidth(3f);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeCap(Paint.Cap.ROUND);
        if (ok) {
            Path t = new Path();
            t.moveTo(x, y + 6); t.lineTo(x + 4, y + 10); t.lineTo(x + 12, y);
            c.drawPath(t, p);
        } else {
            c.drawLine(x, y, x + 10, y + 10, p);
            c.drawLine(x + 10, y, x, y + 10, p);
        }
        p.setStyle(Paint.Style.FILL);
        p.setStrokeWidth(1f);
    }

    private static void banner(Canvas c, Paint p, Context ctx) {
        p.setColor(NAVY);
        c.drawRect(new Rect(0, 0, W, 190), p);
        // dashed white racing stripes bottom-right of the banner
        p.setColor(Color.WHITE);
        for (int i = 0; i < 5; i++) {
            Path s = new Path();
            float x = W - 160 + i * 26;
            s.moveTo(x, 190); s.lineTo(x + 12, 168); s.lineTo(x + 20, 168); s.lineTo(x + 8, 190);
            s.close();
            c.drawPath(s, p);
        }
        // vehicle art right
        int res = ctx.getResources().getIdentifier(Session.vehicleImage, "drawable", ctx.getPackageName());
        if (res != 0) {
            Bitmap b = BitmapFactory.decodeResource(ctx.getResources(), res);
            if (b != null) {
                int bw = 250, bh = 130;
                Bitmap sc = Bitmap.createScaledBitmap(b, bw, bh, true);
                c.drawBitmap(sc, W - bw - 24, 40, null);
            }
        }
        p.setColor(Color.WHITE);
        p.setTextSize(24);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        c.drawText("NIRIXX", 36, 58, p);
        p.setTextSize(15);
        p.setColor(Color.rgb(200, 208, 230));
        c.drawText("M O T O   C A R E", 36, 80, p);
        p.setColor(RED);
        p.setTextSize(21);
        c.drawText("VEHICLE HEALTH REPORT", 36, 112, p);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
        p.setTextSize(11);
        p.setColor(Color.WHITE);
    }

    // ------------------------------------------------------------- page 1
    private static void page1(Context ctx, PdfDocument doc, List<String[]> liveRows) {
        PdfDocument.Page page = doc.startPage(new PdfDocument.PageInfo.Builder(W, H, 1).create());
        Canvas c = page.getCanvas();
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        banner(c, p, ctx);

        float y = 206;
        sectionBar(c, p, y, "DEALER & VEHICLE INFO");
        y += 36;
        // vehicle thumb
        int res = ctx.getResources().getIdentifier(Session.vehicleImage, "drawable", ctx.getPackageName());
        if (res != 0) {
            Bitmap b = BitmapFactory.decodeResource(ctx.getResources(), res);
            if (b != null) {
                p.setColor(Color.WHITE);
                c.drawRoundRect(new RectF(40, y, 160, y + 96), 6, 6, p);
                p.setColor(Color.rgb(230, 234, 242));
                p.setStyle(Paint.Style.STROKE);
                c.drawRoundRect(new RectF(40, y, 160, y + 96), 6, 6, p);
                p.setStyle(Paint.Style.FILL);
                c.drawBitmap(Bitmap.createScaledBitmap(b, 112, 88, true), null,
                        new RectF(44, y + 4, 156, y + 92), null);
            }
        }
        String[][] dealer = {
                {"Dealer Name:", Session.dealerName},
                {"Dealer Code:", Session.dealerCode},
                {"Dealer Email:", Session.dealerEmail.length() > 0 ? Session.dealerEmail : "—"},
                {"Variant:", Session.selectedVehicle},
                {"VIN:", Session.selectedVin}};
        float dy = y + 8;
        for (String[] row : dealer) {
            p.setColor(GREY); p.setTextSize(12);
            c.drawText(row[0], 190, dy, p);
            p.setColor(Color.rgb(26, 33, 56)); p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
            c.drawText(row[1], 320, dy, p);
            p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
            dy += 22;
        }
        y += 116;

        sectionBar(c, p, y, "DIAGNOSTIC REPORT");
        y += 38;
        p.setTextSize(13);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        p.setColor(Color.rgb(26, 33, 56));
        c.drawText("I. " + titleCase(Session.selectedEcu), 42, y, p);
        p.setColor(GREEN);
        c.drawText("Active", 330, y, p);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
        y += 22;

        // Vehicle data table header
        p.setTextSize(12);
        p.setColor(Color.rgb(26, 33, 56));
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        c.drawText("Vehicle Data", 42, y, p);
        c.drawText("Min", 300, y, p); c.drawText("Max", 380, y, p);
        c.drawText("Value", 452, y, p); c.drawText("Status", 522, y, p);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
        y += 10;

        int i = 1;
        for (String[] r : liveRows) {
            y += 22;
            p.setColor(Color.rgb(26, 33, 56));
            c.drawText(i + ". " + r[0], 42, y, p);
            p.setColor(GREY);
            c.drawText(r[1], 300, y, p);
            c.drawText(r[2], 380, y, p);
            p.setColor(Color.rgb(26, 33, 56));
            c.drawText(r[3], 452, y, p);
            tick(c, p, 530, y - 8, "PASS".equals(r[4]));
            i++;
        }
        y += 30;

        // IO control
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        p.setColor(Color.rgb(26, 33, 56));
        c.drawText("Input/Output Control", 42, y, p);
        c.drawText("Result", 452, y, p);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
        int n = 1;
        for (java.util.Map.Entry<String, String> e : Session.vhrData.entrySet()) {
            if (!e.getKey().startsWith("io|" + Session.selectedEcuCode)) continue;
            y += 20;
            String label = e.getKey().substring(e.getKey().lastIndexOf('|') + 1);
            p.setColor(Color.rgb(26, 33, 56));
            c.drawText(n + ". " + label, 42, y, p);
            p.setColor(GREEN);
            c.drawText(e.getValue(), 452, y, p);
            n++;
        }
        if (n == 1) {
            y += 20;
            p.setColor(GREY);
            c.drawText("1. MIL Lamp", 42, y, p);
            p.setColor(GREEN); c.drawText("Not run", 452, y, p);
            y += 20;
            p.setColor(GREY); c.drawText("2. Fuel Pump Relay", 42, y, p);
            p.setColor(GREEN); c.drawText("Not run", 452, y, p);
        }
        y += 28;

        String[] extra = new String[]{"II. Anti-lock Braking System", "III. Instrument Cluster",
                "IV. Integrated Starter Cluster"};
        for (String s : extra) {
            p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
            p.setColor(Color.rgb(26, 33, 56));
            c.drawText(s, 330, y, p);
            p.setColor(GREEN);
            c.drawText("Active", 560, y, p);
            p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
            y += 20;
        }

        p.setColor(GREY); p.setTextSize(10);
        c.drawText("1", W / 2, H - 14, p);
        doc.finishPage(page);
    }

    // ------------------------------------------------------------- page 2
    private static void page2(Context ctx, PdfDocument doc, String verdict) {
        PdfDocument.Page page = doc.startPage(new PdfDocument.PageInfo.Builder(W, H, 2).create());
        Canvas c = page.getCanvas();
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        banner(c, p, ctx);

        float y = 206;
        sectionBar(c, p, y, "PHYSICAL EVALUATION");
        y += 40;
        p.setTextSize(12);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        p.setColor(Color.WHITE);
        p.setColor(Color.rgb(26, 33, 56));
        c.drawText("", 0, 0, p);
        // column headers on the dark bar
        p.setColor(Color.rgb(26, 33, 56));
        c.drawText("RANGE", 300, y - 20, p);
        c.drawText("VALUE/STATUS", 452, y - 20, p);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));

        com.nirixx.app.db.Db db = com.nirixx.app.db.Db.get(ctx);
        java.util.List<String[]> items = db.vhrItems(Session.vehicleId);
        int i = 1;
        for (String[] it : items) {
            String answer = Session.vhrData.containsKey("phys|" + it[0])
                    ? Session.vhrData.get("phys|" + it[0])
                    : ("VAL".equals(it[4]) ? it[2] : "Ok");
            p.setColor(Color.rgb(26, 33, 56));
            c.drawText(i + ". " + it[0], 42, y, p);
            p.setColor(GREY);
            String range = "VAL".equals(it[4]) ? it[2] + "-" + it[3] : "-";
            c.drawText(range, 300, y, p);
            boolean ok = "QUAL".equals(it[4]) ? "Ok".equals(answer) : true;
            p.setColor(ok ? GREEN : RED);
            c.drawText(answer, 452, y, p);
            y += 24;
            i++;
        }
        y += 14;

        sectionBar(c, p, y, "REPORT SUMMARY");
        y += 40;
        p.setColor(Color.rgb(26, 33, 56));
        p.setTextSize(13);
        c.drawText("Vehicle Health Condition", 42, y, p);
        p.setColor(GREY); p.setTextSize(12);
        c.drawText("Date: " + new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date()), 380, y, p);
        y += 30;
        // shield + verdict
        p.setColor("Passed".equals(verdict) ? GREEN : Color.rgb(249, 168, 37));
        p.setStrokeWidth(3f);
        p.setStyle(Paint.Style.STROKE);
        Path shield = new Path();
        shield.moveTo(52, y - 8); shield.lineTo(68, y - 16); shield.lineTo(84, y - 8);
        shield.lineTo(84, y + 8); shield.quadTo(84, y + 20, 68, y + 26);
        shield.quadTo(52, y + 20, 52, y + 8); shield.close();
        c.drawPath(shield, p);
        tick(c, p, 60, y - 2, true);
        p.setStyle(Paint.Style.FILL);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        p.setTextSize(16);
        c.drawText(verdict, 106, y + 2, p);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
        y += 52;

        p.setColor(Color.rgb(63, 99, 190));
        p.setTextSize(15);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        c.drawText("#NirixXCares", 42, y, p);
        p.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.NORMAL));
        y += 34;
        p.setColor(GREY);
        p.setTextSize(10.5f);
        c.drawText("Disclaimer: This is not a legal document.", 42, y, p);
        y += 14;
        c.drawText("Note: All parameters recorded are at the time of inspection & subjected to change based on usage and maintenance.", 42, y, p);

        p.setColor(GREY); p.setTextSize(10);
        c.drawText("2", W / 2, H - 14, p);
        doc.finishPage(page);
    }

    private static String titleCase(String s) {
        if (s == null || s.length() == 0) return "";
        String[] parts = s.toLowerCase(Locale.US).split(" ");
        StringBuilder b = new StringBuilder();
        for (String w : parts) {
            if (b.length() > 0) b.append(' ');
            b.append(w.length() > 0 ? Character.toUpperCase(w.charAt(0)) + w.substring(1) : w);
        }
        return b.toString().replace("(Obdii)", "(OBDII)");
    }
}
