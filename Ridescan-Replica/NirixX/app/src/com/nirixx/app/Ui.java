package com.nirixx.app;

import android.app.Activity;
import android.app.Dialog;
import android.content.Context;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

/** Programmatic UI builders (cards, rows, chips, dialogs) for a consistent look. */
public final class Ui {
    private Ui() {}

    public static int dp(Context c, float v) {
        return (int) (v * c.getResources().getDisplayMetrics().density + 0.5f);
    }

    public static TextView tv(Context c, String text, float sp, int color, boolean bold) {
        TextView t = new TextView(c);
        t.setText(text);
        t.setTextSize(sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    public static TextView chip(Context c, String text, int bgRes, int textColor) {
        TextView t = tv(c, text, 11.5f, textColor, true);
        t.setBackgroundResource(bgRes);
        int h = dp(c, 10), v = dp(c, 4);
        t.setPadding(h, v, h, v);
        return t;
    }

    public static LinearLayout card(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setBackgroundResource(R.drawable.bg_card);
        int p = dp(c, 16);
        l.setPadding(p, p, p, p);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, 0, dp(c, 12));
        l.setLayoutParams(lp);
        return l;
    }

    /** A row: leading icon + title + subtitle + trailing chevron. */
    public static LinearLayout listRow(Context c, int iconRes, String title, String sub, boolean chevron) {
        LinearLayout row = new LinearLayout(c);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setBackgroundResource(R.drawable.bg_card);
        int p = dp(c, 14);
        row.setPadding(p, p, p, p);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, 0, dp(c, 10));
        row.setLayoutParams(lp);

        if (iconRes != 0) {
            ImageView iv = new ImageView(c);
            iv.setImageResource(iconRes);
            int s = dp(c, 34);
            LinearLayout.LayoutParams ip = new LinearLayout.LayoutParams(s, s);
            ip.setMargins(0, 0, dp(c, 14), 0);
            row.addView(iv, ip);
        }
        LinearLayout mid = new LinearLayout(c);
        mid.setOrientation(LinearLayout.VERTICAL);
        mid.addView(tv(c, title, 14.5f, 0xFF141B2E, true));
        if (sub != null && sub.length() > 0) {
            TextView s = tv(c, sub, 12f, 0xFF5A6472, false);
            LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-2, -2);
            sp.setMargins(0, dp(c, 2), 0, 0);
            mid.addView(s, sp);
        }
        row.addView(mid, new LinearLayout.LayoutParams(0, -2, 1f));
        if (chevron) {
            ImageView cv = new ImageView(c);
            cv.setImageResource(R.drawable.ic_chev);
            row.addView(cv, new LinearLayout.LayoutParams(dp(c, 22), dp(c, 22)));
        }
        return row;
    }

    /** Key / value row used inside cards. */
    public static LinearLayout kvRow(Context c, String k, String v, boolean last) {
        LinearLayout row = new LinearLayout(c);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        int pv = dp(c, 9);
        row.setPadding(0, pv, 0, pv);
        if (!last) {
            GradientDrawable div = new GradientDrawable();
            div.setColor(0x00000000);
            row.setPadding(0, pv, 0, pv);
        }
        row.addView(tv(c, k, 13f, 0xFF5A6472, false),
                new LinearLayout.LayoutParams(0, -2, 1.1f));
        TextView val = tv(c, v, 13f, 0xFF141B2E, true);
        val.setGravity(Gravity.RIGHT);
        row.addView(val, new LinearLayout.LayoutParams(0, -2, 0.9f));
        return row;
    }

    /** Section header label. */
    public static TextView section(Context c, String text) {
        TextView t = tv(c, text, 12f, 0xFF5A6472, true);
        t.setLetterSpacing(0.08f);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, -2);
        lp.setMargins(dp(c, 4), dp(c, 4), 0, dp(c, 8));
        t.setLayoutParams(lp);
        return t;
    }

    public static Drawable roundRect(int color, float radiusDp, Context c) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(dp(c, radiusDp));
        return g;
    }

    /** Simple card-style dialog matching the app's modals. */
    public static Dialog dialog(final Activity a, String title, CharSequence body,
                                String primary, final Runnable onPrimary,
                                String secondary, final Runnable onSecondary) {
        final Dialog d = new Dialog(a);
        d.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout root = new LinearLayout(a);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundResource(R.drawable.bg_dialog);
        int p = dp(a, 22);
        root.setPadding(p, p, p, dp(a, 16));
        root.addView(tv(a, title, 17f, 0xFF141B2E, true));
        if (body != null && body.length() > 0) {
            TextView b = tv(a, body.toString(), 13.5f, 0xFF5A6472, false);
            LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-1, -2);
            bp.setMargins(0, dp(a, 10), 0, 0);
            b.setLineSpacing(1.2f, 1f);
            root.addView(b, bp);
        }
        LinearLayout btnRow = new LinearLayout(a);
        btnRow.setOrientation(LinearLayout.HORIZONTAL);
        btnRow.setGravity(Gravity.RIGHT);
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(-1, -2);
        rp.setMargins(0, dp(a, 18), 0, 0);

        if (secondary != null) {
            TextView s = tv(a, secondary, 14f, 0xFF5A6472, true);
            s.setPadding(dp(a, 16), dp(a, 8), dp(a, 16), dp(a, 8));
            s.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { d.dismiss(); if (onSecondary != null) onSecondary.run(); }
            });
            btnRow.addView(s);
        }
        TextView pv = tv(a, primary, 14f, 0xFF0B8376, true);
        pv.setPadding(dp(a, 16), dp(a, 8), dp(a, 16), dp(a, 8));
        pv.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { d.dismiss(); if (onPrimary != null) onPrimary.run(); }
        });
        btnRow.addView(pv);
        root.addView(btnRow, rp);
        d.setContentView(root);
        if (d.getWindow() != null) {
            d.getWindow().setBackgroundDrawableResource(android.R.color.transparent);
            d.getWindow().setLayout(dp(a, 300), ViewGroup.LayoutParams.WRAP_CONTENT);
        }
        return d;
    }

    /** Loading/progress dialog (dialog_erase_loader style). */
    public static Dialog progressDialog(Context c, String title) {
        Dialog d = new Dialog(c);
        d.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout root = new LinearLayout(c);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setBackgroundResource(R.drawable.bg_dialog);
        int p = dp(c, 24);
        root.setPadding(p, p, p, p);
        ProgressBar pb = new ProgressBar(c);
        root.addView(pb, new LinearLayout.LayoutParams(dp(c, 44), dp(c, 44)));
        TextView t = tv(c, title, 14f, 0xFF141B2E, true);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-2, -2);
        tp.setMargins(0, dp(c, 14), 0, 0);
        root.addView(t, tp);
        d.setContentView(root);
        d.setCancelable(false);
        if (d.getWindow() != null) {
            d.getWindow().setBackgroundDrawableResource(android.R.color.transparent);
        }
        return d;
    }

    /** Success/failure dialog with icon (ic_flash_success style). */
    public static Dialog resultDialog(final Activity a, int iconRes, String title, String body,
                                      String primary, final Runnable onPrimary) {
        final Dialog d = new Dialog(a);
        d.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout root = new LinearLayout(a);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setBackgroundResource(R.drawable.bg_dialog);
        int p = dp(a, 24);
        root.setPadding(p, p, p, dp(a, 18));
        ImageView iv = new ImageView(a);
        iv.setImageResource(iconRes);
        root.addView(iv, new LinearLayout.LayoutParams(dp(a, 52), dp(a, 52)));
        TextView t = tv(a, title, 17f, 0xFF141B2E, true);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-2, -2);
        tp.setMargins(0, dp(a, 12), 0, 0);
        root.addView(t, tp);
        if (body != null) {
            TextView b = tv(a, body, 13f, 0xFF5A6472, false);
            b.setGravity(Gravity.CENTER);
            LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-1, -2);
            bp.setMargins(0, dp(a, 6), 0, 0);
            root.addView(b, bp);
        }
        TextView pv = tv(a, primary, 14f, 0xFF0B8376, true);
        pv.setPadding(dp(a, 16), dp(a, 10), dp(a, 16), dp(a, 10));
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(-2, -2);
        pp.setMargins(0, dp(a, 14), 0, 0);
        root.addView(pv, pp);
        pv.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { d.dismiss(); if (onPrimary != null) onPrimary.run(); }
        });
        d.setContentView(root);
        if (d.getWindow() != null) {
            d.getWindow().setBackgroundDrawableResource(android.R.color.transparent);
            d.getWindow().setLayout(dp(a, 300), ViewGroup.LayoutParams.WRAP_CONTENT);
        }
        return d;
    }

    public static FrameLayout divider(Context c) {
        FrameLayout f = new FrameLayout(c);
        f.setBackgroundResource(R.color.line_grey);
        return f;
    }

    // ================================================================ reference shell
    static final int NAVY = 0xFF3A4663;
    static final int GREY = 0xFF5A6472;
    static final int GREEN = 0xFF2E9E43;
    static final int RED = 0xFFE53935;

    /** Breadcrumb strip: "Home » TVS Jupiter New » EMS-OBDII » Live Parameter". */
    public static LinearLayout crumbs(Context c, String[] trail) {
        LinearLayout row = new LinearLayout(c);
        row.setOrientation(LinearLayout.HORIZONTAL);
        int pv = dp(c, 6);
        row.setPadding(dp(c, 4), pv, dp(c, 4), pv);
        for (int i = 0; i < trail.length; i++) {
            boolean last = i == trail.length - 1;
            TextView t = tv(c, trail[i], 13.5f, last ? 0xFF1A2138 : GREY, last);
            row.addView(t);
            if (!last) {
                TextView sep = tv(c, "  \u00BB  ", 13.5f, GREY, true);
                row.addView(sep);
            }
        }
        return row;
    }

    /** Light-blue section bar (Diagnostic / VIN - xxx | EMS-OBDII). */
    public static LinearLayout sectionBar(Context c, String left, String right) {
        LinearLayout bar = new LinearLayout(c);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setBackgroundResource(R.drawable.bg_bar_light);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(c, 14), dp(c, 12), dp(c, 14), dp(c, 12));
        TextView l = tv(c, left, 14.5f, NAVY, true);
        bar.addView(l, new LinearLayout.LayoutParams(0, -2, 1f));
        if (right != null) bar.addView(tv(c, right, 14.5f, 0xFF14276F, true));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.setMargins(0, dp(c, 6), 0, dp(c, 10));
        bar.setLayoutParams(lp);
        return bar;
    }

    /** Big navy primary button. */
    /** Bottom red validation banner (the reference tool shows its blocking
     *  field-messages like "Please fill & upload picture of all the fields"
     *  this way).  Auto-dismisses; framework-only (no design lib). */
    public static void errorBar(final Activity a, String msg) {
        final android.view.ViewGroup root =
                (android.view.ViewGroup) a.findViewById(android.R.id.content);
        final TextView bar = tv(a, "✕  " + msg, 13.5f, 0xFFFFFFFF, true);
        bar.setGravity(android.view.Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(a, 14), dp(a, 10), dp(a, 14), dp(a, 10));
        bar.setBackgroundDrawable(roundRect(0xFFDE3B40, 8f, a));
        FrameLayout.LayoutParams fp = new FrameLayout.LayoutParams(-1, -2);
        fp.gravity = android.view.Gravity.BOTTOM;
        fp.setMargins(dp(a, 12), 0, dp(a, 12), dp(a, 88));
        final FrameLayout overlay = new FrameLayout(a);
        overlay.setClickable(false);
        overlay.addView(bar, fp);
        final android.view.ViewGroup decor = (android.view.ViewGroup) root.getChildAt(0);
        decor.addView(overlay, new android.view.ViewGroup.LayoutParams(-1, -1));
        bar.postDelayed(new Runnable() {
            public void run() { decor.removeView(overlay); }
        }, 2600);
    }

    public static TextView navyBtn(Context c, String text) {
        TextView b = tv(c, text, 15f, 0xFFFFFFFF, true);
        b.setGravity(Gravity.CENTER);
        b.setBackgroundResource(R.drawable.bg_button_navy);
        b.setPadding(0, dp(c, 13), 0, dp(c, 13));
        return b;
    }

    /** Grey info tile with icon on top, like Battery Voltage / New Updates. */
    public static LinearLayout statTile(Context c, int iconRes, String l1, String l2) {
        LinearLayout g = new LinearLayout(c);
        g.setOrientation(LinearLayout.VERTICAL);
        g.setBackgroundResource(R.drawable.bg_card_grey);
        int p = dp(c, 12);
        g.setPadding(p, p, p, p);
        ImageView iv = new ImageView(c);
        iv.setImageResource(iconRes);
        g.addView(iv, new LinearLayout.LayoutParams(dp(c, 22), dp(c, 22)));
        TextView t1 = tv(c, l1, 13f, GREY, false);
        LinearLayout.LayoutParams m1 = new LinearLayout.LayoutParams(-2, -2);
        m1.setMargins(0, dp(c, 8), 0, 0);
        g.addView(t1, m1);
        TextView t2 = tv(c, l2, 14f, NAVY, true);
        g.addView(t2);
        g.setTag(t2);      // live text slot
        return g;
    }

    /** Outlined key/value box (IUPR boxes: VIN | MD62…). */
    public static LinearLayout kvBox(Context c, String k, String v) {
        LinearLayout box = new LinearLayout(c);
        box.setOrientation(LinearLayout.HORIZONTAL);
        box.setBackgroundResource(R.drawable.bg_box_outline);
        box.setGravity(Gravity.CENTER_VERTICAL);
        box.setPadding(dp(c, 14), dp(c, 13), dp(c, 14), dp(c, 13));
        box.addView(tv(c, k, 13.5f, GREY, false), new LinearLayout.LayoutParams(0, -2, 1f));
        TextView val = tv(c, v, 14.5f, 0xFF1A2138, false);
        val.setGravity(Gravity.RIGHT);
        box.addView(val);
        box.setTag(val);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.setMargins(0, 0, 0, dp(c, 10));
        box.setLayoutParams(lp);
        return box;
    }

    /** Live-parameter card: bold title + ⓘ, category, big value. Returns card; value TextView in tag. */
    public static LinearLayout paramCard(final Activity a, final String title, String category,
                                         String value, final String min, final String max, final String hint) {
        LinearLayout card_v = new LinearLayout(a);
        card_v.setOrientation(LinearLayout.VERTICAL);
        card_v.setBackgroundResource(R.drawable.bg_card);
        int p = dp(a, 14);
        card_v.setPadding(p, p, p, p);
        LinearLayout head = new LinearLayout(a);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.addView(tv(a, title, 14f, 0xFF1A2138, true), new LinearLayout.LayoutParams(0, -2, 1f));
        TextView info = tv(a, "\u24d8", 16f, GREY, false);
        info.setPadding(dp(a, 6), 0, 0, 0);
        info.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                dialog(a, title, "Category: " + title + "\nMin: " + min + "    Max: " + max
                        + (hint.length() > 0 ? "\n\n" + hint : ""), "Close", null, null, null).show();
            }
        });
        head.addView(info);
        card_v.addView(head);
        TextView cat = tv(a, "Category: " + category, 12f, GREY, false);
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-2, -2);
        cp.setMargins(0, dp(a, 5), 0, 0);
        card_v.addView(cat, cp);
        TextView val = tv(a, value, 16.5f, 0xFF1A2138, false);
        LinearLayout.LayoutParams vp = new LinearLayout.LayoutParams(-2, -2);
        vp.setMargins(0, dp(a, 5), 0, 0);
        card_v.addView(val, vp);
        card_v.setTag(val);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.setMargins(0, 0, 0, dp(a, 10));
        card_v.setLayoutParams(lp);
        return card_v;
    }

    /** IO-control row: label left, toggle switch right (inside outlined box). */
    public static LinearLayout ioRow(Context c, String label, android.widget.CompoundButton.OnCheckedChangeListener cb) {
        LinearLayout row = new LinearLayout(c);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setBackgroundResource(R.drawable.bg_box_outline);
        row.setPadding(dp(c, 14), 0, dp(c, 10), 0);
        TextView t = tv(c, label, 14f, 0xFF1A2138, true);
        row.addView(t, new LinearLayout.LayoutParams(0, -2, 1f));
        android.widget.Switch sw = new android.widget.Switch(c);
        sw.setOnCheckedChangeListener(cb);
        row.addView(sw);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, dp(c, 64));
        lp.setMargins(0, 0, 0, dp(c, 10));
        row.setLayoutParams(lp);
        return row;
    }

    /** ECU-menu tile (2-column grid): icon top-left, label bottom-left. */
    public static LinearLayout ecuTile(Context c, int iconRes, String label) {
        LinearLayout tile = new LinearLayout(c);
        tile.setOrientation(LinearLayout.VERTICAL);
        tile.setBackgroundResource(R.drawable.bg_card_grey);
        int p = dp(c, 14);
        tile.setPadding(p, p, p, p);
        ImageView iv = new ImageView(c);
        iv.setImageResource(iconRes);
        tile.addView(iv, new LinearLayout.LayoutParams(dp(c, 30), dp(c, 30)));
        TextView t = tv(c, label, 13.5f, 0xFF1A2138, false);
        LinearLayout.LayoutParams m = new LinearLayout.LayoutParams(-2, -2);
        m.setMargins(0, dp(c, 34), 0, 0);
        tile.addView(t, m);
        return tile;
    }

    /** Photo-add thumbnail used on the Physical Evaluation tab. */
    public static LinearLayout photoThumb(Context c) {
        LinearLayout box = new LinearLayout(c);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setBackgroundResource(R.drawable.bg_card_grey);
        ImageView iv = new ImageView(c);
        iv.setImageResource(R.drawable.ic_camera);
        box.addView(iv, new LinearLayout.LayoutParams(dp(c, 26), dp(c, 26)));
        TextView t = tv(c, "ADD IMAGE", 9f, 0xFF8A93A8, true);
        box.addView(t);
        int s = dp(c, 64);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(s, s);
        lp.setMargins(0, 0, dp(c, 12), 0);
        box.setLayoutParams(lp);
        return box;
    }

    /** Green helpline pill (If any App Crashes Please Contact). */
    public static LinearLayout phonePill(Context c, String number) {
        LinearLayout pill = new LinearLayout(c);
        pill.setOrientation(LinearLayout.HORIZONTAL);
        pill.setGravity(Gravity.CENTER);
        pill.setBackgroundResource(R.drawable.bg_pill_green);
        pill.setPadding(dp(c, 18), dp(c, 8), dp(c, 18), dp(c, 8));
        ImageView iv = new ImageView(c);
        iv.setImageResource(R.drawable.ic_phone);
        pill.addView(iv, new LinearLayout.LayoutParams(dp(c, 18), dp(c, 18)));
        TextView t = tv(c, "  " + number, 15f, 0xFF1B5E20, true);
        pill.addView(t);
        return pill;
    }

    /** Small rounded status dot view. */
    public static View dot(Context c, boolean okColor) {
        View v = new View(c);
        v.setBackgroundResource(okColor ? R.drawable.bg_dot_green : R.drawable.bg_dot_red);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(c, 10), dp(c, 10));
        lp.setMargins(dp(c, 8), 0, 0, 0);
        v.setLayoutParams(lp);
        return v;
    }

    /** Vehicle bus-image + name header used on Diagnostic Section pages. */
    public static int imgRes(Context c, String drawableName) {
        int id = c.getResources().getIdentifier(drawableName, "drawable", c.getPackageName());
        return id != 0 ? id : R.drawable.motorcycle;
    }
}
