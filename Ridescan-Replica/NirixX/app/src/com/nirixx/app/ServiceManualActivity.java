package com.nirixx.app;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import com.nirixx.app.db.Db;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.List;

/** Service Manual — a REAL local document shelf.  Workshop PDFs are imported
 *  from device storage (SAF), filed under the NirixX documents directory and
 *  listed with their true size; opening hands them to an installed reader via
 *  our content provider.  No file names are invented, nothing pretends to
 *  download — OEM manual distribution needs the DMS backend (documented gap). */
public class ServiceManualActivity extends BaseActivity {

    private static final int REQ_DOC = 71;
    private Db db;
    private LinearLayout content;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("Service Manual");
        wireBack();
        db = Db.get(this);
        content = (LinearLayout) findViewById(R.id.content);
        render();
    }

    private void render() {
        content.removeAllViews();

        LinearLayout head = Ui.card(this);
        head.addView(Ui.tv(this, "WORKSHOP DOCUMENTS", 12f, 0xFF5A6472, true));
        head.addView(Ui.tv(this, "NirixX ships no third-party manuals. Import the PDF/DOC files "
                + "your distributor provided — they stay on this device and open from here.",
                12.5f, 0xFF5A6472, false));
        content.addView(head);

        android.widget.TextView imp = Ui.navyBtn(this, "IMPORT DOCUMENT");
        LinearLayout.LayoutParams ip = new LinearLayout.LayoutParams(-1, Ui.dp(this, 46));
        ip.setMargins(0, 0, 0, Ui.dp(this, 10));
        content.addView(imp, ip);
        imp.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Intent it = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                it.addCategory(Intent.CATEGORY_OPENABLE);
                it.setType("*/*");
                it.putExtra(Intent.EXTRA_MIME_TYPES,
                        new String[]{"application/pdf", "text/*"});
                startActivityForResult(it, REQ_DOC);
            }
        });

        List<String[]> docs = db.manuals();
        if (docs.size() == 0) {
            LinearLayout card = Ui.card(this);
            card.addView(Ui.tv(this, "No documents imported yet.", 13.5f, 0xFF5A6472, false));
            content.addView(card);
            return;
        }
        for (int i = 0; i < docs.size(); i++) {
            final String[] d = docs.get(i);   // id, name, path, size, added
            long sz = 0;
            try { sz = Long.parseLong(d[3]); } catch (Exception ignored) { }
            LinearLayout row = Ui.listRow(this, R.drawable.dtclibrary, d[1],
                    (sz > 0 ? String.format(java.util.Locale.US, "%.1f MB", sz / 1048576.0) : "?")
                            + "  ·  imported", false);
            android.widget.TextView open = Ui.chip(this, "OPEN", R.drawable.bg_chip, 0xFF0B8376);
            row.addView(open);
            final long id;
            long tmp; try { tmp = Long.parseLong(d[0]); } catch (Exception e) { tmp = -1; }
            id = tmp;
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { open(d[2]); }
            });
            open.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { open(d[2]); }
            });
            row.setOnLongClickListener(new View.OnLongClickListener() {
                public boolean onLongClick(View v) {
                    db.deleteManual(id);
                    new File(d[2]).delete();
                    render();
                    return true;
                }
            });
            content.addView(row);
        }
    }

    private void open(String path) {
        File f = new File(path);
        if (!f.isFile()) { toast("File not found — remove and re-import it"); return; }
        Intent it = new Intent(Intent.ACTION_VIEW);
        it.setDataAndType(DocsProvider.uriForPath(path), mime(path));
        it.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            startActivity(it);
        } catch (Exception e) {
            toast("No viewer installed for " + f.getName());
        }
    }

    private static String mime(String path) {
        String p = path.toLowerCase(java.util.Locale.US);
        if (p.endsWith(".pdf")) return "application/pdf";
        if (p.endsWith(".txt") || p.endsWith(".log")) return "text/plain";
        return "application/octet-stream";
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_DOC || resultCode != RESULT_OK || data == null) return;
        Uri src = data.getData();
        if (src == null) return;
        String name = displayName(src);
        try {
            File dir = new File(getExternalFilesDir(null), "Manuals");
            dir.mkdirs();
            File dst = new File(dir, name);
            InputStream in = getContentResolver().openInputStream(src);
            FileOutputStream out = new FileOutputStream(dst);
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            in.close(); out.close();
            db.addManual(name, dst.getAbsolutePath(), dst.length());
            toast("Imported " + name);
        } catch (Exception e) {
            toast("Import failed: " + e.getMessage());
        }
        render();
    }

    private String displayName(Uri uri) {
        String name = null;
        android.database.Cursor c = getContentResolver().query(uri, null, null, null, null);
        if (c != null) {
            int i = c.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME);
            if (i >= 0 && c.moveToFirst()) name = c.getString(i);
            c.close();
        }
        if (name == null || name.length() == 0) name = uri.getLastPathSegment();
        if (name == null) name = "document.pdf";
        return name.replaceAll("[^A-Za-z0-9._ -]", "_");
    }
}
