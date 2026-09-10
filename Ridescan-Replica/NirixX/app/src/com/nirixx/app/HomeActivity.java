package com.nirixx.app;

import android.os.Bundle;
import android.view.View;
import android.widget.GridLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Home — reference-style dealer dashboard: vehicle hero (artwork from the DB),
 *  VCI connectivity strip (Bluetooth / Wi-Fi / USB), quick vehicle info and the
 *  feature grid.  No fictional VCI catalogues anywhere. */
public class HomeActivity extends BaseActivity {

    private static final int NAVY = 0xFF3A4663;
    private static final int GREY = 0xFF5A6472;

    /** label, icon, target, RBAC module (filtered by the signed-in role). */
    private static final Object[][] TILES = new Object[][]{
        {"VIN Based\nDiagnosis", Integer.valueOf(R.drawable.vindiagnostic), VinDiagnosisActivity.class, "vin_diag"},
        {"Diagnostics", Integer.valueOf(R.drawable.manualdiagnostic), VehicleListActivity.class, "vehicles"},
        {"ECU\nFlashing", Integer.valueOf(R.drawable.flash_blue), SupplierFlashListActivity.class, "flash"},
        {"VIN Based\nFlashing", Integer.valueOf(R.drawable.vinflashing), VinFlashingActivity.class, "vin_flash"},
        {"Cluster\nFlashing", Integer.valueOf(R.drawable.racing_bike1), ClusterFlashListActivity.class, "flash"},
        {"Manual\nDiagnostic", Integer.valueOf(R.drawable.vintroubleshooting), ManualDiagnosticActivity.class, "vin_flash"},
        {"Health\nReport", Integer.valueOf(R.drawable.vehicle_health_report), VhrActivity.class, "vhr"},
        {"Reports", Integer.valueOf(R.drawable.ic_doc), ReportsActivity.class, "reports"},
        {"Battery\nHealth", Integer.valueOf(R.drawable.battery_health_report), BatteryHealthActivity.class, "battery"},
        {"Data\nRecording", Integer.valueOf(R.drawable.vci), LiveDataRecordingActivity.class, "recording"},
        {"VCI\nConnect", Integer.valueOf(R.drawable.bluetooth), AddDeviceActivity.class, "vci"},
        {"VCI\nFirmware", Integer.valueOf(R.drawable.firmwarecloud), VciFirmwareListActivity.class, "vci_fw"},
        {"Vehicle\nList", Integer.valueOf(R.drawable.motorcycle), VehicleListActivity.class, "vehicles"},
        {"Service\nManual", Integer.valueOf(R.drawable.dtclibrary), ServiceManualActivity.class, "service_manual"},
        {"Intro\nVideos", Integer.valueOf(R.drawable.ic_play), IntroVideosActivity.class, "videos"},
        {"Log\nViewer", Integer.valueOf(R.drawable.dtc_blue), LogViewerActivity.class, "logs"},
        {"AI\nAssistant", Integer.valueOf(R.drawable.ic_chat), SupportChatActivity.class, "ai_assistant"},
        {"System\nCheck", Integer.valueOf(R.drawable.setting_1), SystemCheckActivity.class, "system_check"},
        {"App\nUpdate", Integer.valueOf(R.drawable.flash), UpdateDescriptionActivity.class, "app_update"},
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_screen);
        setTitle("NirixX");
        hideBack();

        if (!getSharedPreferences("nirixx", MODE_PRIVATE).getBoolean("notif_asked", false)) {
            Perms.ensureNotifications(this);
            getSharedPreferences("nirixx", MODE_PRIVATE).edit().putBoolean("notif_asked", true).apply();
        }

        LinearLayout content = (LinearLayout) findViewById(R.id.content);
        Session.ensureSession(this);

        // ---- dealer strip -------------------------------------------------
        LinearLayout dealer = new LinearLayout(this);
        dealer.setOrientation(LinearLayout.HORIZONTAL);
        dealer.setGravity(android.view.Gravity.CENTER_VERTICAL);
        dealer.setPadding(Ui.dp(this, 2), 0, Ui.dp(this, 2), Ui.dp(this, 6));
        TextView dtxt = Ui.tv(this, "Dealer: " + Session.dealerName
                + (Session.dealerCode.length() > 0 ? "  ·  Code " + Session.dealerCode : ""), 13f, GREY, false);
        dealer.addView(dtxt, new LinearLayout.LayoutParams(0, -2, 1f));
        TextView acct = Ui.tv(this, "Account ›", 13f, 0xFF14276F, true);
        acct.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(AccountActivity.class); }
        });
        dealer.addView(acct);
        content.addView(dealer);

        // ---- vehicle hero (image + identity from the database) ------------
        LinearLayout hero = new LinearLayout(this);
        hero.setOrientation(LinearLayout.HORIZONTAL);
        hero.setGravity(android.view.Gravity.CENTER_VERTICAL);
        hero.setBackgroundResource(R.drawable.bg_card);
        hero.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));
        ImageView bus = new ImageView(this);
        bus.setImageResource(Ui.imgRes(this, Session.vehicleImage));
        hero.addView(bus, new LinearLayout.LayoutParams(Ui.dp(this, 150), Ui.dp(this, 96)));
        LinearLayout info = new LinearLayout(this);
        info.setOrientation(LinearLayout.VERTICAL);
        info.setPadding(Ui.dp(this, 12), 0, 0, 0);
        info.addView(Ui.tv(this, Session.selectedVehicle, 16.5f, 0xFF1A2138, true));
        info.addView(Ui.tv(this, Session.selectedVariant, 12f, GREY, false));
        info.addView(Ui.tv(this, "VIN  " + Session.selectedVin, 12f, GREY, false));
        TextView type = Ui.chip(this, Session.vehicleType + " · OBD-II", R.drawable.bg_chip_grey, NAVY);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-2, -2);
        tp.setMargins(0, Ui.dp(this, 6), 0, 0);
        info.addView(type, tp);
        hero.addView(info, new LinearLayout.LayoutParams(0, -2, 1f));
        hero.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(VehicleListActivity.class); }
        });
        content.addView(hero);

        // ---- VCI connectivity strip ---------------------------------------
        vciStrip = new LinearLayout(this);
        vciStrip.setOrientation(LinearLayout.HORIZONTAL);
        vciStrip.setGravity(android.view.Gravity.CENTER_VERTICAL);
        vciStrip.setBackgroundResource(R.drawable.bg_card);
        vciStrip.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));
        vciIcon = new ImageView(this);
        vciStrip.addView(vciIcon, new LinearLayout.LayoutParams(Ui.dp(this, 26), Ui.dp(this, 26)));
        LinearLayout mid = new LinearLayout(this);
        mid.setOrientation(LinearLayout.VERTICAL);
        mid.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 8), 0);
        vciTitle = Ui.tv(this, "", 14f, 0xFF1A2138, true);
        vciSub = Ui.tv(this, "", 12f, GREY, false);
        mid.addView(vciTitle);
        mid.addView(vciSub);
        vciStrip.addView(mid, new LinearLayout.LayoutParams(0, -2, 1f));
        vciBtn = Ui.navyBtn(this, "");
        vciBtn.setTextSize(12.5f);
        vciBtn.setPadding(Ui.dp(this, 14), Ui.dp(this, 8), Ui.dp(this, 14), Ui.dp(this, 8));
        vciStrip.addView(vciBtn, new LinearLayout.LayoutParams(-2, -2));
        LinearLayout.LayoutParams vp = new LinearLayout.LayoutParams(-1, -2);
        vp.setMargins(0, Ui.dp(this, 10), 0, 0);
        content.addView(vciStrip, vp);
        vciStrip.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(AddDeviceActivity.class); }
        });

        // ---- feature grid ---------------------------------------------------
        boolean service = !com.nirixx.app.core.role.Roles.isEngineer(Session.userType);
        TextView role = Ui.chip(this, Session.userType, service
                        ? R.drawable.bg_chip_grey : R.drawable.bg_chip_grey, NAVY);
        LinearLayout.LayoutParams rlp = new LinearLayout.LayoutParams(-2, -2);
        rlp.setMargins(0, Ui.dp(this, 2), 0, Ui.dp(this, 4));
        content.addView(role, rlp);
        TextView notif = Ui.tv(this, "⤨  Notifications & updates", 12.5f, NAVY, true);
        LinearLayout.LayoutParams nlp = new LinearLayout.LayoutParams(-2, -2);
        nlp.setMargins(0, Ui.dp(this, 2), 0, Ui.dp(this, 6));
        content.addView(notif, nlp);
        notif.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(NotificationActivity.class); }
        });
        if (service) {
            content.addView(Ui.tv(this,
                    "Dealer Service flow: connect VCI → auto VIN → Diagnostic Section. "
                            + "Engineering modules require the Dealer Engineer role.",
                    12f, GREY, false));
        }
        content.addView(Ui.section(this, "SERVICES"));
        GridLayout grid = new GridLayout(this);
        grid.setColumnCount(4);
        for (int i = 0; i < TILES.length; i++) {
            final Object[] tile = TILES[i];
            if (!com.nirixx.app.core.role.Roles.can(Session.userType, (String) tile[3])) continue;
            LinearLayout cell = new LinearLayout(this);
            cell.setOrientation(LinearLayout.VERTICAL);
            cell.setGravity(android.view.Gravity.CENTER_HORIZONTAL);
            cell.setBackgroundResource(R.drawable.bg_card);
            cell.setPadding(Ui.dp(this, 4), Ui.dp(this, 14), Ui.dp(this, 4), Ui.dp(this, 12));
            ImageView icon = new ImageView(this);
            icon.setImageResource(((Integer) tile[1]).intValue());
            icon.setColorFilter(NAVY);
            cell.addView(icon, new LinearLayout.LayoutParams(Ui.dp(this, 30), Ui.dp(this, 30)));
            TextView label = Ui.tv(this, (String) tile[0], 11f, NAVY, false);
            label.setGravity(android.view.Gravity.CENTER);
            LinearLayout.LayoutParams lp2 = new LinearLayout.LayoutParams(-2, -2);
            lp2.setMargins(0, Ui.dp(this, 8), 0, 0);
            cell.addView(label, lp2);
            cell.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { go((Class<?>) tile[2]); }
            });
            GridLayout.LayoutParams gp = new GridLayout.LayoutParams();
            gp.width = 0;
            gp.height = GridLayout.LayoutParams.WRAP_CONTENT;
            gp.setMargins(Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4));
            gp.columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f);
            cell.setLayoutParams(gp);
            grid.addView(cell);
        }
        LinearLayout.LayoutParams gridLp = new LinearLayout.LayoutParams(-1, -2);
        gridLp.setMargins(Ui.dp(this, -4), 0, Ui.dp(this, -4), Ui.dp(this, 10));
        content.addView(grid, gridLp);

        refreshVci();

        // Foreground session coordinator (never allowed to take the app down)
        try {
            startService(new android.content.Intent(this, ClientService.class));
        } catch (Exception ignored) { }
    }

    private LinearLayout vciStrip;
    private ImageView vciIcon;
    private TextView vciTitle, vciSub, vciBtn;

    @Override
    protected void onResume() {
        super.onResume();
        refreshVci();
    }

    private void refreshVci() {
        if (vciStrip == null) return;
        vciIcon.setImageResource("WIFI".equals(Session.connectivity) ? R.drawable.ic_wifi
                : "USB".equals(Session.connectivity) ? R.drawable.ic_usb
                : R.drawable.bluetooth);
        if (Session.vciConnected) {
            vciTitle.setText(Session.vciName + "  •  Connected");
            vciSub.setText(Session.connectivity + " link  ·  fw " + Session.vciFw);
            vciBtn.setText("Manage");
        } else {
            vciTitle.setText("No VCI connected");
            vciSub.setText("Pair over Bluetooth / Wi-Fi / USB");
            vciBtn.setText("Connect");
        }
    }

    @Override
    public void onBackPressed() {
        Ui.dialog(this, "Exit NirixX?", "Do you want to close the application?",
                "Exit", new Runnable() { public void run() { finishAffinity(); } },
                "Cancel", null).show();
    }
}
