# 01 — Reference Application Functional Specification

End-to-end lifecycle of RIDE Scan 2.0 as observed. Per-stage: UI, inputs, outputs,
navigation, state, errors, persistence, backend/VCI interaction. Evidence labels per §26.

## 1. Application lifecycle chain

```
Splash → (first-run Welcome/Tutorial) → Login (Dealer → Designation → Login wizard)
  → Home (role-driven grid) → VCI connect → Vehicle identification (auto-VIN or manual)
  → Diagnostic Section ─┬─ ECU Diagnosis (Live params / DTC / Write DID / Routine / IO)
                        ├─ VIN-Based Diagnosis / VIN-Based Flashing
                        ├─ Vehicle Health Report → PDF → upload/share
                        ├─ Battery Health Report
                        ├─ Flashing/Campaign, Reports, Service Manual, Intro Videos
                        ├─ Logs (Log/File viewer), Screen recording, System monitoring
                        └─ VCI (diagnostics + firmware update), App Update
  → Session teardown → Logout
```

## 2. Launch & first run
- `ui/splash/SplashActivity`, `ui/welcome/WelcomeActivity`, `ui/tutorial/TutorialActivity`
  exist. [SRC] Behavior: first-run onboarding, remembered afterwards. [INFERENCE — screens
  not captured in media; matches standard pattern and NirixX parity.]
- `ui/usertype/UserTypeActivity` — role/designation selection step. [SRC]

## 3. Login (Stage: authentication)
[VIDEO f01][IMG IMG-20260114-WA0005/6][SRC][LOG]
- Three-step wizard tabs: **Dealer → Designation → Login**.
- Dealer tab fields: *Dealer ID*, *Email* (policy string: "Please use your official email ID
  ending with @tvsmdealers.co.in"), *Branch ID* (Dealer ID pre-echoed), **VCI dropdown** with
  device names (`TechPRO_504856`), **ADD/PAIR VCI** action, **Select Connectivity Type**:
  `BT / WIFI / USB` chooser; LOGIN button; footer "Powered by MAHLE". Bike hero image above form.
- "Logging in…" busy state; "Do you want to change your account? CHANGE" (remembered account).
- Credentialed dealer samples: 10814 (video/PDF), 12345 (logs). Auth itself is online (DMS);
  **OTP**: "OTP has been Send to <email>" + `ui/forgotpin/{OTPActivity,NewPinActivity}`
  + 6-digit OTP + 4-digit PIN strings ("Enter 4 digit PIN", "Enter 6 Digit OTP",
  "Forgot PIN"). [SRC][IMG sheet-B rows 1–2: OTP keypad dialogs]
- `ui/sso_dealership_login/SSOActivity` — dealership SSO path. [SRC] Trigger conditions
  UNKNOWN / Requires Validation (not captured in media).
- Session persistence: app remembers dealer+VCI between launches (video shows pre-filled form
  + "change account?" affordance). Logout available from profile overflow. [SRC menu][INFERENCE]

## 4. Home / dashboard
[IMG 2026-01-20 burst rows 2–3: red-bike header + 4-card grids][SRC home/HomeActivity]
- Grid of capability cards whose **contents differ by role** (see 03_roles.md) [XREF].
- Persistent **footer status bar** on nearly every screen: session id chip (left) +
  `V x.y.z` + connectivity glyph (BT/Wi-Fi/USB) (right). [VIDEO][IMG][LOG — session id format]
  While diagnostics run, an **ECU chip + green connection dot** sits in the top app bar
  (e.g. "BABS ●", "ICU ●"). [IMG ReadDTCs/ECUDiagnosis]
- App-bar affordances: notifications bell (badge), profile avatar, 3-dot overflow. [IMG]

## 5. Vehicle connection & identification (Stage)
[LOG][IMG][SRC] — full detail in 04_vci_connection.md and 05_vehicle_communication.md.
1. VCI enumerated/paired (BT SPP or Wi-Fi TechPRO; USB option present in chooser, unexercised in media).
2. `10 01` on functional `0x7DF` / physical `0x7E0`; any ECU answers `50 01 00 32 01 F4`
   (P2 50 ms / P2* 5000 ms). [LOG both]
3. VIN acquisition: `22 F1 90` (UDS, physical EMS) **and** OBD-II `09 02` on `7DF`
   (`49 02 01` + ASCII). [LOG both]
4. Vehicle model resolved from VIN (prefix table) → bike image, variant banner
   ("TVS APACHE RR310 Refresh", "TVS Ronin"). [IMG][PDF]
5. ECU discovery across model-specific address set; discovered ECUs become selectable chips. [IMG][XREF]
6. Unmatched/blank VIN (`MD638AN2100000000`) still proceeded: functions that require a known
   model degrade — e.g. flash catalogue resolution cannot bind a variant. [LOG2][INFERENCE]

## 6. Diagnostic section (Stage)
Per-ECU function grid (**ECU Diagnosis** screen): **Live parameters, Diagnostic trouble codes,
Write data identifier, Routine control, Input output control**; availability varies per ECU —
ICU shows exactly those 5 and footer "Please contact TVS for ECU related flashing". [IMG 105128019]
Right-rail status cards: **"Faults Codes Found !"** (red badge when DTCs), **Battery Voltage
live value** (12.3 V), **New Updates Available**; "Service Remainder 🔧" chip; VIN banner + ECU name. [IMG]
Screens: `live_parameter, read_DTCs, write_data, routine_control, io_control, data_watcher, selectoption, select_ECU, manual_diagnostic, gear_learning_procedure, iupr_test/{primary,secondary,history}, gtsviews/GTSViewActivity`. [SRC]

## 7. Vehicle Health Report (Stage)
[VIDEO entire][PDF][IMG 20260317 set][SRC ui/vehicle_health_report/*, physical_evaluation, report_summary_new/NewReportSummaryActivity]
5-tab wizard: **DEALER → DIAGNOSTIC → IO CONTROL → PHYSICAL EVALUATION → SUMMARY**.
Full spec: 15_vehicle_health.md. Outputs: in-app verdict card + generated PDF
(`<Variant>_<VIN>_VHR.pdf`, iText) + automatic backend upload ("PDF Uploaded Successfully")
+ share via system sheet (WhatsApp in video). [VIDEO f37–f42][SRC itextpdf, FileUploadWorker]

## 8. Flashing / campaign (Stage)
[IMG burst: Flash BCU screens, "Select a File System (Proprietary)", "GET SECRET KEY" dialogs,
flash-file lists `TVS FLASH_…`, green SUCCESS dialog][SRC ui/ecu_flashing/* 15 supplier flows]
[JSON 22 variants][SRC strings "Downloading HEX file", "Do not close the app until the flash is
completed"]. Full spec: 14_flashing.md.

## 9. Reports & logs (Stage)
- `diagnostic_report/DiagnosticReportActivity`, `report_summary_new/NewReportSummaryActivity`,
  `battery_health_report/BatteryHealthReportActivity` — stored per-session reports. [SRC]
- `log_viewer/LogViewerActivity`, `file_viewer/FileViewerActivity`,
  `live_data_recording/LiveDataRecordingActivity` (+CSV capture). [SRC]
- Log format & session naming: 16_logging_recording.md. [LOG]

## 10. Profile / account (Stage)
[SRC `account_details/AccountDetailsActivity`, `dealerinformation/DealerInformationActivity`]
- Shows dealer identity (name/code/email/branch), app version, role; editable subset is
  **contact fields only** per dealer-master policy. [INFERENCE — no media capture]
- Logout + "change account" flow re-enters login. [VIDEO f01 string]

## 11. Notifications (Stage)
- `notification/NotificationActivity` + bell-with-badge in app bar. [SRC][IMG]
- Types observed/inferred: app/VCI/ecu-update alerts ("New Updates Available" card) [IMG],
  system/DMS messages. Exact push channel (FCM strings present via Google Play services
  strings) [SRC][INFERENCE]; read/unread + navigation targets UNKNOWN / Requires Validation.

## 12. Updates (Stage) — three distinct channels
| Channel | Evidence | Behavior |
|---|---|---|
| **App update** | `update/UpdateActivity`, `update_description/UpdateDescriptionActivity` [SRC] | Version check at login/home; description screen; download via Play or DMS package [INFERENCE for hosting] |
| **VCI firmware update** | `firmware_update/tz_new_vci_firmware_update` [SRC]; strings: "If the update is not required this time, you can skip the VCI Upgrade now. But you are only allow to skip the upgrade only 5 times", "Email link for VCI Update Tool" [SRC] | **Forced-upgrade with 5-skip budget**; old 0-series BT VCIs discontinued end-Jan-2026 → 5-series Wi-Fi [SRC] |
| **ECU software update** | flashing flows + flash_variant.json [SRC][JSON] | Campaign/variant-driven; per-supplier protocol; "ECU Flashing completed", "ECU Reset" strings |

Update state visibility: right-rail "New Updates Available" on ECU Diagnosis. [IMG]

## 13. Session (Stage) — definition & teardown
[LOG headers][VIDEO footers][IMG]
- A diagnostic session = dealer+VCI+connectivity+vehicle bound at vehicle-identification time;
  `sessionId = <vciSerial><ddMMyyyy><HHmmss>` (see 16_logging_recording.md proof).
- Everything inside a screen-scoped operation is logged with timestamps; log file name =
  `<sessionId><VIN>.txt`.
- App-close handling: `service/AppCloseService` [SRC] flushes state on task removal.
- Logout closes session; relaunch remembers account+VCI, starts a *new* session id.
- Recovery after crash/restart of an in-flight diagnostic operation: **UNKNOWN / Requires
  Validation** (no evidence captured; treat as new session).

## 14. Global error/empty/loading language
[VIDEO][IMG][SRC strings]
- Busy modal: orange header, circular arrow glyph, "Requesting…" + operation name +
  determinate-ish bar + "Note: Don't close the application, While complete the diagnostics."
- Blocking notice: "Do not close the app until the flash is completed".
- Validation: red bottom snackbar "Please fill & upload picture of all the fields".
- Success: green header dialog ("Flash Successful"-family); failure: red header dialog.
- Empty: blank list area w/o explicit empty-state illustration observed (Read DTCs no-fault
  screen shows empty card area only). [IMG 105007386]

## 15. Permissions observed/required
[SRC manifest (binary) + library analysis][IMG]
- BT connect/scan (Android 14: `BLUETOOTH_CONNECT/SCAN`), Location (BT scan precondition string
  "Location permission"), Wi-Fi state for TechPRO, Camera (in-VHR photo capture), Storage/SAF
  equivalents, RECORD_AUDIO + MediaProjection (HBRecorder), Notifications (Android 13+),
  Network. Exact manifest permission list: decode check — see 20_evidence_register.md.
