package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** Real artifact browser: walks the app's external-files directory and lists
 *  every log (.txt) and report (.pdf) the app has actually written. */
public class FileViewerActivity extends BaseActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("File Viewer");
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        content.addView(Ui.crumbs(this, new String[]{"Home", "File Viewer"}));

        File root = getExternalFilesDir(null);
        List<File> dirs = new ArrayList<File>();
        if (root != null) {
            File[] kids = root.listFiles();
            if (kids != null) {
                for (int i = 0; i < kids.length; i++) if (kids[i].isDirectory()) dirs.add(kids[i]);
            }
        }
        java.util.Collections.sort(dirs, new java.util.Comparator<File>() {
            public int compare(File a, File b) { return a.getName().compareToIgnoreCase(b.getName()); }
        });

        boolean any = false;
        SimpleDateFormat df = new SimpleDateFormat("dd MMM, HH:mm", Locale.US);
        for (int d = 0; d < dirs.size(); d++) {
            File dir = dirs.get(d);
            File[] files = dir.listFiles();
            if (files == null || files.length == 0) continue;
            java.util.Arrays.sort(files, new java.util.Comparator<File>() {
                public int compare(File a, File b) { return Long.compare(b.lastModified(), a.lastModified()); }
            });
            any = true;
            content.addView(Ui.sectionBar(this, dir.getName().toUpperCase(Locale.US), files.length + ""));
            for (int i = 0; i < files.length; i++) {
                final File f = files[i];
                String sub = dir.getName() + "/" + f.getName() + "\n"
                        + (f.length() / 1024) + " KB · " + df.format(new Date(f.lastModified()));
                int icon = f.getName().endsWith(".pdf") ? R.drawable.vehicle_health_report
                        : f.getName().endsWith(".txt") ? R.drawable.ic_doc : R.drawable.ic_folder;
                LinearLayout row = Ui.listRow(this, icon, f.getName(), sub, false);
                row.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
                row.setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) { preview(f); }
                });
                content.addView(row);
            }
        }

        if (!any) {
            LinearLayout empty = Ui.card(this);
            empty.addView(Ui.tv(this, "Application storage is empty", 14f, 0xFF1A2138, true));
            empty.addView(Ui.tv(this,
                    "Session logs (.txt) and health reports (.pdf) appear here once you run a diagnosis.",
                    12.5f, 0xFF5A6472, false));
            content.addView(empty);
        }
    }

    private void preview(File f) {
        if (f.getName().endsWith(".txt")) {
            StringBuilder sb = new StringBuilder();
            BufferedReader br = null;
            try {
                br = new BufferedReader(new InputStreamReader(new FileInputStream(f), "UTF-8"));
                List<String> lines = new ArrayList<String>();
                String l;
                while ((l = br.readLine()) != null) lines.add(l);
                int start = Math.max(0, lines.size() - 40);
                for (int i = start; i < lines.size(); i++) sb.append(lines.get(i)).append('\n');
                if (start > 0) sb.insert(0, "… (" + start + " earlier lines)\n");
            } catch (Exception e) {
                sb.append("(unable to read: ").append(e.getMessage()).append(')');
            } finally {
                try { if (br != null) br.close(); } catch (Exception ignored) { }
            }
            Ui.dialog(this, f.getName(), sb.toString(), "Close", null, null, null).show();
        } else {
            Ui.dialog(this, f.getName(),
                    f.getAbsolutePath() + "\n" + (f.length() / 1024) + " KB\n\n"
                            + (f.getName().endsWith(".pdf")
                            ? "Generated Vehicle Health Report — open with any PDF viewer from the file manager."
                            : "Binary artifact."),
                    "Close", null, null, null).show();
        }
    }
}
