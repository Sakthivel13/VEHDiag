package com.nirixx.app;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/** Base shell: every layout that contains the reference app-bar / session-bar
 *  ids gets them wired automatically (back, user->Account, brand tile, session
 *  id, version, connectivity icon). */
public abstract class BaseActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
    }

    @Override
    public void setContentView(int layoutResID) {
        super.setContentView(layoutResID);
        shell();
    }

    private void shell() {
        wireBack();
        View user = findViewById(R.id.imgUser);
        if (user != null) user.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(AccountActivity.class); }
        });
        View brand = findViewById(R.id.imgBrand);
        if (brand != null) brand.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(NotificationActivity.class); }
        });
        TextView sess = (TextView) findViewById(R.id.txtSession);
        if (sess != null) sess.setText(Session.ensureSession(this));
        ImageView conn = (ImageView) findViewById(R.id.imgConn);
        if (conn != null) {
            conn.setImageResource("WIFI".equals(Session.connectivity) ? R.drawable.ic_wifi
                    : "USB".equals(Session.connectivity) ? R.drawable.ic_usb
                    : R.drawable.bluetooth);
        }
    }

    /** Show the ECU code chip + status dot in the app bar (ECU-context pages). */
    protected void showEcuChip(String code, boolean ok) {
        LinearLayout chip = (LinearLayout) findViewById(R.id.chipEcu);
        if (chip == null) return;
        chip.setVisibility(View.VISIBLE);
        TextView t = (TextView) findViewById(R.id.txtEcuCode);
        if (t != null) t.setText(code);
        View d = findViewById(R.id.dotEcu);
        if (d != null) d.setBackgroundResource(ok ? R.drawable.bg_dot_green : R.drawable.bg_dot_red);
    }

    protected void setTitle(String title) {
        TextView t = (TextView) findViewById(R.id.tvTitle);
        if (t != null) t.setText(title);
    }

    protected void wireBack() {
        View b = findViewById(R.id.btnBack);
        if (b != null) {
            b.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { onBackPressed(); }
            });
        }
    }

    protected void hideBack() {
        View b = findViewById(R.id.btnBack);
        if (b != null) b.setVisibility(View.INVISIBLE);
    }

    /** Role-guarded navigation: every screen transition funnels through here,
     *  so a Dealer Service account genuinely cannot open engineering modules
     *  (roles are enforced, not merely hidden). */
    protected void go(Class<?> target) {
        String module = com.nirixx.app.core.role.Roles.moduleForScreen(target.getSimpleName());
        if (!com.nirixx.app.core.role.Roles.can(Session.userType, module)) {
            Ui.dialog(this, "Not permitted",
                    "Role \u201c" + Session.userType + "\u201d has no access to this module.\n\n"
                            + "Sign in as Dealer Engineer for engineering functions.",
                    "OK", null, null, null).show();
            return;
        }
        startActivity(new Intent(this, target));
    }

    protected void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
    }
}
