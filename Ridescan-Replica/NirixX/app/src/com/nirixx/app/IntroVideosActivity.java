package com.nirixx.app;

import android.app.Dialog;
import android.content.ContentResolver;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.VideoView;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

/** Intro / guide videos (reference: ui/video_player over bundled content).
 *
 *  Honesty rule: NirixX bundles NO reference videos.  The workshop imports its
 *  own training clips (SAF, video/*); they are copied into app-private storage
 *  and played back with the framework VideoView.  An empty shelf says so. */
public class IntroVideosActivity extends BaseActivity {

    private static final int REQ_VIDEO = 73;
    private LinearLayout content;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Intro Videos");
        wireBack();
        content = (LinearLayout) findViewById(R.id.content);
        render();
    }

    private File dir() {
        File d = new File(getFilesDir(), "videos");
        if (!d.isDirectory()) d.mkdirs();
        return d;
    }

    private void render() {
        content.removeAllViews();
        content.addView(Ui.crumbs(this, new String[]{"Home", "Intro Videos"}));
        content.addView(Ui.section(this, "TRAINING & INTRODUCTION MEDIA"));

        File[] vids = dir().listFiles();
        int count = 0;
        if (vids != null) {
            for (File f : vids) {
                if (!f.isFile() || !f.getName().endsWith(".mp4")) continue;
                count++;
                final Uri play = Uri.fromFile(f);
                LinearLayout row = Ui.listRow(this, R.drawable.ic_play,
                        f.getName().replace(".mp4", ""), (f.length() / 1024) + " KB", true);
                row.setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) { playVideo(play); }
                });
                content.addView(row);
            }
        }
        if (count == 0) {
            LinearLayout card = Ui.card(this);
            card.addView(Ui.tv(this, "NO VIDEOS IMPORTED", 12f, 0xFFB26A00, true));
            card.addView(Ui.tv(this, "NirixX ships without bundled media (clean-room build). "
                    + "Import your workshop's own introduction/training clips (.mp4) — they stay "
                    + "private to this tablet.", 12.5f, 0xFF5A6472, false));
            content.addView(card);
        }

        TextView add = Ui.navyBtn(this, "IMPORT VIDEO");
        LinearLayout.LayoutParams ap = new LinearLayout.LayoutParams(-1, -2);
        ap.setMargins(0, Ui.dp(this, 10), 0, Ui.dp(this, 10));
        content.addView(add, ap);
        add.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Intent it = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                it.addCategory(Intent.CATEGORY_OPENABLE);
                it.setType("video/*");
                startActivityForResult(it, REQ_VIDEO);
            }
        });
    }

    private void playVideo(final Uri uri) {
        final Dialog d = new Dialog(this, android.R.style.Theme_Black_NoTitleBar_Fullscreen);
        final VideoView vv = new VideoView(this);
        android.widget.MediaController mc = new android.widget.MediaController(this);
        mc.setAnchorView(vv);
        vv.setMediaController(mc);
        vv.setVideoURI(uri);
        d.setContentView(vv);
        vv.setOnPreparedListener(new android.media.MediaPlayer.OnPreparedListener() {
            public void onPrepared(android.media.MediaPlayer mp) { vv.start(); }
        });
        vv.setOnCompletionListener(new android.media.MediaPlayer.OnCompletionListener() {
            public void onCompletion(android.media.MediaPlayer mp) { d.dismiss(); }
        });
        d.show();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_VIDEO || resultCode != RESULT_OK || data == null
                || data.getData() == null) return;
        Uri src = data.getData();
        String name = displayName(src);
        if (name == null || name.length() == 0) name = "video_" + System.currentTimeMillis();
        if (!name.endsWith(".mp4")) name = name + ".mp4";
        File out = new File(dir(), name.replaceAll("[^A-Za-z0-9._-]", "_"));
        try {
            ContentResolver cr = getContentResolver();
            InputStream in = cr.openInputStream(src);
            FileOutputStream fos = new FileOutputStream(out);
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) > 0) fos.write(buf, 0, n);
            fos.close();
            in.close();
            toast("Imported " + name);
        } catch (Exception e) {
            toast("Couldn't import that video: " + e.getMessage());
        }
        render();
    }

    private String displayName(Uri uri) {
        try {
            android.database.Cursor c = getContentResolver().query(uri, null, null, null, null);
            if (c != null) {
                int i = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                String n = (c.moveToFirst() && i >= 0) ? c.getString(i) : null;
                c.close();
                return n;
            }
        } catch (Exception ignored) { }
        return null;
    }
}
