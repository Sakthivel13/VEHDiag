package com.nirixx.app;

import android.os.Bundle;
import android.view.View;

public class WelcomeActivity extends BaseActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(0xFFB7C4D0);
        if (android.os.Build.VERSION.SDK_INT >= 23) {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        }
        setContentView(R.layout.activity_welcome);
        findViewById(R.id.btnGetStarted).setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(LoginActivity.class); }
        });
        findViewById(R.id.btnSso).setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { go(SsoLoginActivity.class); }
        });
    }
}
