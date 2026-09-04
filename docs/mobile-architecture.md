# VEHDiag — Android client architecture

Status: **architecture documented; minimal OTA-style client shipped.**
The `downloads/VEHDiag.apk` produced by `scripts/build-apk.py` is a real,
signed, installable APK whose `MainActivity` hosts a WebView pointing at the
VEHDiag release page. That gives the sideload channel an **OTA-updatable web
client** today; the native Bluetooth diagnostic client below is the roadmap.

This sandbox has no JDK, Android SDK or device (see
`docs/PRODUCTION_AUDIT.md` §Environment), so native modules are specified here
and built/verified in CI once a signing key + SDK are available.

## Module layout (planned `apps/mobile`)

```
apps/mobile/
  app/src/main/AndroidManifest.xml
  app/src/main/java/com/vehdiag/app/
    MainActivity.kt              # shell: routes to web client or Bluetooth UI
    bluetooth/
      Elm327Discovery.kt         # BLE + classic SPP scan, RSSI ranking
      Elm327Connection.kt        # SPP socket lifecycle, reconnect/backoff
      AtCommandChannel.kt        # line protocol: CR terminator, echo off,
                                 # 100 ms pacing, prompt handling
    diag/
      ScanEngine.kt              # port of the 8-stage orchestrator
      LiveDataSampler.kt         # PID polling loop (bounded rate, OBD-II timing)
      PidCodec.kt                # port of diagnostics/obd PIDS table
    ota/
      UpdateManager.kt           # polls /downloads/SHA256SUMS.txt + GitHub
                                 # releases, verifies SHA-256 before install
    MainViewModel.kt             # state holder; survives rotation
```

## Contracts (kept identical with the web platform)

- **Vehicle profiles & DIDs**: `diagnostics/ecu` registry is the source of
  truth; the Android build generates `PidCodec.kt`/`DidTable.kt` from it in CI
  (script `scripts/gen-kotlin.js`, added with the module).
- **API**: `com.vehdiag.app` speaks the same `/api/v1` contracts; tokens
  stored via `EncryptedSharedPreferences`; all traffic HTTPS.
- **OTA**: update manifest = `downloads/SHA256SUMS.txt` + GitHub Releases
  assets; the APK's SHA-256 must match the manifest before `PackageInstaller`
  is invoked (signature verified by the platform, v1 for sideload; release
  channel moves to v2/v3 scheme signed by the CI secret).

## Bluetooth specifics

- Classic SPP for ELM327 v1.5 dongles (UUID `00001101-0000-1000-8000-00805F9B34FB`);
  BLE for ELM327 v2.x clones where advertised.
- AT bootstrap sequence: `ATZ`, `ATE0`, `ATL0`, `ATSP6` (pinned), then `0100`
  to confirm PID support — identical to the simulator's documented behaviour
  so the same test fixtures drive both.

## Security

- Never store PII in logs; diagnostic data stays on-device unless the user
  syncs a session to their account.
- No rooting, no SELinux bypass, no access to other apps' storage.
- The app requests only Bluetooth + Network permissions, declared with
  runtime rationale.
