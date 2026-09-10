package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.nirixx.app.db.Db;

/** App Update — honest state.  There is no update server in this project (the
 *  DMS/distribution backend is a documented gap), so instead of a fake
 *  download bar this page states the installed build, when it was built, and
 *  how updates are actually delivered. */
public class UpdateActivity extends BaseActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("App Update");
        wireBack();
        Db db = Db.get(this);
        LinearLayout content = (LinearLayout) findViewById(R.id.content);

        android.widget.ImageView art = new android.widget.ImageView(this);
        art.setImageResource(R.drawable.report_cover);
        art.setScaleType(android.widget.ImageView.ScaleType.CENTER_CROP);
        art.setBackgroundResource(R.drawable.bg_console);
        LinearLayout.LayoutParams ap = new LinearLayout.LayoutParams(-1, Ui.dp(this, 150));
        ap.setMargins(0, 0, 0, Ui.dp(this, 10));
        content.addView(art, ap);

        LinearLayout card = Ui.card(this);
        card.addView(Ui.kvRow(this, "Installed", db.config("app_version", "V 1.6.3"), false));
        card.addView(Ui.kvRow(this, "Update channel", "not configured", false));
        card.addView(Ui.kvRow(this, "Delivery", "Signed APK from your distributor / Arena build", true));
        content.addView(card);

        LinearLayout note = Ui.card(this);
        note.addView(Ui.tv(this,
                "NirixX never pretends to download an update. Over-the-air app updates require "
                        + "the distribution backend (see MISSING_DEPENDENCIES.md); until it is "
                        + "integrated, new builds are handed over as signed APKs.",
                12.5f, 0xFF5A6472, false));
        content.addView(note);

        TextView notes = Ui.navyBtn(this, "RELEASE NOTES (1.6.3)");
        LinearLayout.LayoutParams np = new LinearLayout.LayoutParams(-1, Ui.dp(this, 46));
        np.setMargins(0, Ui.dp(this, 8), 0, 0);
        content.addView(notes, np);
        notes.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(UpdateDescriptionActivity.class); }
        });
    }
}
