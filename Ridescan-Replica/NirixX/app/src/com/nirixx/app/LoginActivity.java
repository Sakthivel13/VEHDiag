package com.nirixx.app;

import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.EditText;
import android.widget.TextView;
import com.nirixx.app.db.Db;

/** Dealer login — mirrors the reference flow: Dealer ID auto-fills email/branch
 *  from the users table, designation & VCI pickers, connectivity selector,
 *  then a session row is opened in the database. */
public class LoginActivity extends BaseActivity {

    private EditText edtDealer, edtEmail, edtBranch;
    private TextView spnRole, spnVci, btnLogin;
    private View conBT, conWIFI, conUSB;
    private String connectivity = "BLUETOOTH";
    private String role = "Dealer Service";
    private String vci = "NirixiLINK_504856";
    private Db db;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);
        db = Db.get(this);

        edtDealer = (EditText) findViewById(R.id.edtDealer);
        edtEmail = (EditText) findViewById(R.id.edtEmail);
        edtBranch = (EditText) findViewById(R.id.edtBranch);
        spnRole = (TextView) findViewById(R.id.spnRole);
        spnVci = (TextView) findViewById(R.id.spnVci);
        btnLogin = (TextView) findViewById(R.id.btnLogin);
        conBT = findViewById(R.id.conBT);
        conWIFI = findViewById(R.id.conWIFI);
        conUSB = findViewById(R.id.conUSB);

        vci = db.config("last_vci", vci);
        spnVci.setText(vci);
        connectivity = db.config("connectivity", "BLUETOOTH");
        markConnectivity();

        // Dealer-ID -> auto-fill from users table, like the DMS lookup.
        edtDealer.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int b, int c) { }
            public void onTextChanged(CharSequence s, int a, int b, int c) { }
            public void afterTextChanged(Editable s) {
                String[] u = db.userByDealerCode(s.toString().trim());
                if (u != null) {
                    edtEmail.setText(u[2]);
                    edtBranch.setText(u[3]);
                    role = u[5];
                    spnRole.setText(role);
                }
            }
        });
        String[] u = db.userByDealerCode(edtDealer.getText().toString().trim());
        if (u != null) { edtEmail.setText(u[2]); edtBranch.setText(u[3]); role = u[5]; spnRole.setText(role); }

        spnRole.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                final java.util.List<String> roles = db.roles();
                new AlertDialog.Builder(LoginActivity.this)
                        .setTitle("Designation")
                        .setItems(roles.toArray(new String[roles.size()]),
                                new DialogInterface.OnClickListener() {
                                    public void onClick(DialogInterface d, int which) {
                                        role = roles.get(which);
                                        spnRole.setText(role);
                                    }
                                }).show();
            }
        });

        spnVci.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(AddDeviceActivity.class); }
        });
        findViewById(R.id.txtAddPair).setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(AddDeviceActivity.class); }
        });

        // New-dealer registration link (real flow: Register → OTP → New PIN)
        findViewById(R.id.txtRegister).setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(RegisterActivity.class); }
        });

        View.OnClickListener connClick = new View.OnClickListener() {
            public void onClick(View v) {
                connectivity = v == conBT ? "BLUETOOTH" : (v == conWIFI ? "WIFI" : "USB");
                db.setConfig("connectivity", connectivity);
                markConnectivity();
            }
        };
        conBT.setOnClickListener(connClick);
        conWIFI.setOnClickListener(connClick);
        conUSB.setOnClickListener(connClick);

        btnLogin.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { login(); }
        });
    }

    private void markConnectivity() {
        conBT.setBackgroundResource("BLUETOOTH".equals(connectivity) ? R.drawable.bg_tile_sel : R.drawable.bg_tile_def);
        conWIFI.setBackgroundResource("WIFI".equals(connectivity) ? R.drawable.bg_tile_sel : R.drawable.bg_tile_def);
        conUSB.setBackgroundResource("USB".equals(connectivity) ? R.drawable.bg_tile_sel : R.drawable.bg_tile_def);
    }

    private void login() {
        final String code = edtDealer.getText().toString().trim();
        final String[] u = db.userByDealerCode(code);
        if (u == null) {
            Ui.dialog(this, "Unknown Dealer ID",
                    "Dealer ID \"" + code + "\" is not in the NirixX directory.\n\n"
                            + "Seeded directory entries:\n• 10814 — NEO MOTORS (Service Manager)\n"
                            + "• 12345 — RAJIV P (Service Technician)",
                    "OK", null, null, null).show();
            return;
        }
        Session.dealerCode = code;
        Session.dealerName = u[1];
        Session.dealerEmail = edtEmail.getText().toString().trim();
        Session.dealerBranch = edtBranch.getText().toString().trim();
        Session.dealerPhone = u[4];
        Session.userType = role;
        Session.connectivity = connectivity;
        Session.vciName = vci;
        Session.sessionKey = null;            // fresh session per login
        Session.ensureSession(this);
        db.setConfig("last_vci", vci);
        toast("Signed in as " + u[1] + " · " + role);
        startActivity(new Intent(this, HomeActivity.class));
        finish();
    }
}
