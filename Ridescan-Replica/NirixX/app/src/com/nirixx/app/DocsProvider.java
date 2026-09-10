package com.nirixx.app;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;

/** Minimal framework-only ContentProvider that exposes user-imported documents
 *  (service manuals, flash binaries, reports) to other apps via content:// URIs
 *  with temporary read grants — the no-AndroidX replacement for FileProvider.
 *  Paths outside the app's external-files directory are refused. */
public final class DocsProvider extends ContentProvider {

    public static final String AUTHORITY = "com.nirixx.app.docs";

    /** Build the content:// URI for an absolute file path inside our docs root. */
    public static Uri uriForPath(String absolutePath) {
        return new Uri.Builder().scheme("content").authority(AUTHORITY)
                .appendPath(Uri.encode(absolutePath)).build();
    }

    @Override public boolean onCreate() { return true; }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        String path = Uri.decode(uri.getLastPathSegment());
        if (path == null) throw new FileNotFoundException("empty");
        File f = new File(path);
        if (getContext() == null) throw new FileNotFoundException("no context");
        File base = getContext().getExternalFilesDir(null);
        String abs = f.getAbsolutePath();
        if (base == null || !abs.startsWith(base.getAbsolutePath()))
            throw new FileNotFoundException("outside docs root");
        if (!f.isFile()) throw new FileNotFoundException(abs);
        return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs,
                        String sortOrder) {
        String path = Uri.decode(uri.getLastPathSegment());
        File f = path == null ? null : new File(path);
        MatrixCursor c = new MatrixCursor(
                new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE});
        if (f != null && f.isFile())
            c.addRow(new Object[]{f.getName(), Long.valueOf(f.length())});
        return c;
    }

    @Override
    public String getType(Uri uri) {
        String path = uri.getLastPathSegment();
        if (path == null) return "application/octet-stream";
        String p = path.toLowerCase(java.util.Locale.US);
        if (p.endsWith(".pdf")) return "application/pdf";
        if (p.endsWith(".csv")) return "text/csv";
        if (p.endsWith(".txt") || p.endsWith(".log")) return "text/plain";
        if (p.endsWith(".jpg") || p.endsWith(".jpeg")) return "image/jpeg";
        if (p.endsWith(".png")) return "image/png";
        return "application/octet-stream";
    }

    @Override public Uri insert(Uri uri, ContentValues values) { return null; }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) { return 0; }
    @Override public int update(Uri uri, ContentValues values, String selection,
                                String[] selectionArgs) { return 0; }
}
