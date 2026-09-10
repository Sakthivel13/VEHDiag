package com.nirixx.app;

import android.app.Service;
import android.content.Intent;
import android.os.Handler;
import android.os.IBinder;

/** Session capture indicator (honest marker service).
 *
 *  The reference app ships real video recording (its dex carries
 *  com.hbisoft.hbrecorder with a persistent overlay bubble).  NirixX does NOT
 *  fabricate that: this service currently marks the session's active capture
 *  window so logs can be correlated, and the UI says exactly that.  True
 *  MediaProjection-based video capture is an open work item — tracked in
 *  MISSING_DEPENDENCIES.md (consent flow + VirtualDisplay/MediaRecorder). */
public class ScreenRecordOverlayService extends Service {
    public static boolean recording = false;
    public static long startedAt = 0L;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && "stop".equals(intent.getAction())) {
            recording = false;
            stopSelf();
            return START_NOT_STICKY;
        }
        recording = true;
        startedAt = System.currentTimeMillis();
        new Handler().postDelayed(new Runnable() {
            public void run() {
                // heartbeat — keeps the capture-window marker alive; renders nothing.
            }
        }, 1000);
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
