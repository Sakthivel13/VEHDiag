# 02 — Complete Screen / Navigation Map

Reference UI inventory from decompiled packages (**45 `ui/` packages, 125 screen classes**)
[SRC], cross-checked against video, photos, logs. Screen names = actual Activity classes.
Sub-entries (inner classes) omitted. NirixX equivalents tracked in 18_implementation_matrix.md.

## Global UI conventions [XREF: VIDEO/IMG/LOG]
- **App bar**: back arrow + title left; **ECU chip + green dot** center during diagnostics;
  **avatar / bell(+badge) / overflow** right.
- **Breadcrumbs**: `Home ≫ <Model> ≫ <ECU> ≫ <Screen>` under the app bar on deep screens.
- **Footer**: session-id chip • `V <version>` • connectivity icon — present during active session.
- **Busy modal**: orange "Requesting…" with operation + note. **Outcome dialogs**: green=success /
  red=failure headers. **Validation**: red snackbar.
- Tablet (SM-T225, 800×1280) and phone (382×850 dp video) layouts share structure; grids reflow.

## Navigation graph (authoritative)

```
SplashActivity
 ├─(first run)→ WelcomeActivity → TutorialActivity
 └─→ LoginActivity
       ├─→ SSOActivity (dealership SSO)            [SRC] trigger UNKNOWN
       ├─→ RegisterActivity
       ├─→ ForgotPinActivity → OTPActivity → NewPinActivity
       └─→ HomeActivity
             ├─→ UserTypeActivity (designation)     └─→ RaiderSelectionActivity [role/home variant, SRC]
             ├─→ AddDeviceActivity (VCI pairing)    / VCI_Diagnostic_Activity / firmware_update/*
             ├─→ VehicleListActivity ──→ SelectOptionActivity ──→ SelectECUActivity ─┐
             ├─→ VINBasedDiagnosisActivity ──→ (ECU flow) ────────────────────────────┤
             ├─→ ManualDiagnosticActivity ────────────────────────────────────────────┤
             ▼                                                                        ▼
       ECUDiagnosisActivity ◄───────────────────────────────────────────────────(ECU chosen)
             ├─→ LiveParameterActivity        (22xxxx poll grid / charts)
             ├─→ DataWatcherActivity          (live watch w/ log capture)
             ├─→ ReadDTCsActivity             (All/Active filter, CLEAR DTC)
             │      └─→ GTSViewActivity       (per-DTC troubleshooting viewer)
             ├─→ WriteDataActivity            (DID write, SecurityAccess-gated)
             ├─→ RoutineControlActivity ──→ GearLearningActivity (A Assure/DTE routine)
             ├─→ IOControlActivity            (per-ECU actuations, Ok toggles)
             ├─→ IUPRTestPrimaryActivity / IUPRTestSecondaryActivity / IUPRHistoryActivity
             └─→ ecu_flashing/* (15 supplier flows, 14_flashing.md)

HomeActivity (cont.)
 ├─→ VINBasedFlashingActivity (VIN-driven flash path)
 ├─→ VhrActivity → vehicle_health_report/Vhr{DealerInformation,DiagnosticReport,IOControl}Activity
 │     → PhysicalEvaluationActivity → NewReportSummaryActivity → (PDF view) FileViewerActivity
 ├─→ DiagnosticReportActivity (stored session reports)
 ├─→ BatteryHealthReportActivity
 ├─→ LiveDataRecordingActivity (+ CSV export)
 ├─→ LogViewerActivity / FileViewerActivity
 ├─→ ServiceManualActivity / VideoPlayerActivity (intro videos, ExoPlayer strings)
 ├─→ SystemMonitoringActivity
 ├─→ NotificationActivity
 ├─→ AccountDetailsActivity / DealerInformationActivity
 └─→ UpdateActivity / UpdateDescriptionActivity (app update)

Background/service layer: service/{ClientService, FileUploadWorker, AppCloseService},
btlibrary/{SerialService, SerialSocket, BluetoothUtil} (SPP), HBRecorder (screen recording).
```

## Screen-by-screen dossier

| Screen (class) | Purpose & behavior | Key evidence |
|---|---|---|
| SplashActivity | Boot, stored-account check, version/update check | [SRC][INFERENCE] |
| WelcomeActivity / TutorialActivity | First-run onboarding carousel | [SRC] |
| LoginActivity | Dealer→Designation→Login wizard; VCI dropdown + ADD/PAIR VCI; BT/WiFi/USB chooser; "Do you want to change your account?" | [VIDEO f01][IMG 114][SRC] |
| SSOActivity | Dealership SSO login | [SRC] — flow UNKNOWN |
| RegisterActivity | New dealer registration (email policy @tvsmdealers.co.in) | [SRC strings] |
| ForgotPin/OTP/NewPin | 6-digit email OTP → set new 4-digit PIN | [SRC strings][IMG sheetB: OTP dialogs] |
| UserTypeActivity | Role/designation selection (Dealer Service vs Dealer Engineer) | [SRC][XREF roles 03] |
| MainActivity | Post-login container/host | [SRC] |
| HomeActivity | Role-driven capability grid; bike banner; status footer | [IMG burst r2–3][SRC] |
| RaiderSelectionActivity | Secondary landing/selector (name literal in dex) | [SRC] — exact role UNKNOWN |
| AddDeviceActivity | VCI discovery/pairing (BT SPP via BluetoothUtil; Wi-Fi TechPRO) | [SRC][LOG connectivity type] |
| VCI_Diagnostic_Activity | VCI self-test/identity screen | [SRC] |
| VehicleListActivity | Browse vehicle catalogue → pick model → SelectOption | [IMG burst lists][SRC] |
| SelectOptionActivity | Per-model function menu (diagnostics vs flashing vs VHR …) | [SRC][INFERENCE] |
| SelectECUActivity | ECU picker; discovered ECUs as chips; model-specific set | [SRC][XREF logs: multiple addr answered] |
| VINBasedDiagnosisActivity | VIN-first flow: decode → model/ECU auto-binding → diagnosis | [SRC][LOG auto-VIN chain] |
| VINBasedFlashingActivity | VIN-driven campaign/flash selection | [SRC][IMG "Please select FL VIN"-style screen] |
| ECUDiagnosisActivity | Per-ECU hub: 5 function cards; Faults pill w/ red badge; live Battery Voltage card; New Updates card; Service Remainder; VIN banner; per-ECU flash restriction note | [IMG 105128019] |
| LiveParameterActivity | Multi-param live grid; per-DID sequential polling (~60–100 ms cadence between requests); value color = in/out-of-range on VHR-style views | [LOG 22xxxx loops][IMG] |
| DataWatcherActivity | Focused watch view for selected params (with record-to-log) | [SRC] |
| ReadDTCsActivity | Filter dropdown (**All** + others), refresh, **CLEAR DTC** red action; rows = code + description + state | [IMG 105007386][LOG 19/14 sequences] |
| GTSViewActivity | Guided troubleshooting viewer (content per DTC) | [SRC] — content source UNKNOWN |
| WriteDataActivity | DID write; extended session + SecurityAccess (27 01/02) precede | [SRC][LOG2 11:06 sequence] |
| RoutineControlActivity | Routine list → start/stop/result (31 01/02/03) | [SRC][LOG2 31 01 0211] |
| GearLearningActivity | Guided gear-learning routine flow | [SRC] |
| IOControlActivity | Per-ECU IO list w/ toggle switches + "Requesting…" modal per actuation | [IMG IO tab][LOG2 2F A800] |
| IUPRTestPrimary/Secondary/HistoryActivity | Mode-09 IPT (09 08) counters, primary/secondary split, stored history | [SRC][LOG 0908 ×9] |
| ManualDiagnosticActivity | Free-form/manual service tester (engineer) | [SRC][INFERENCE] |
| VhrActivity + Vhr*Activities + PhysicalEvaluationActivity + NewReportSummaryActivity | 5-tab VHR wizard (dealer→diagnostic→IO→physical→summary) | [VIDEO][PDF][SRC] |
| DiagnosticReportActivity | Per-session diagnostic report list/detail | [SRC] |
| BatteryHealthReportActivity | Battery health capture & report | [SRC] |
| ecu_flashing/* screens | Variant selection ("Select a File System (Proprietary)"), HEX download, secret-key dialog, progress, flash result | [IMG][SRC strings] |
| firmware_update/tz_new_vci_firmware_update | VCI firmware flow with 5-skip policy | [SRC strings] |
| LiveDataRecordingActivity | Start/stop param recording → CSV | [SRC] |
| LogViewerActivity / FileViewerActivity | On-device log files / generated files viewer | [SRC][LOG naming] |
| ServiceManualActivity | Manual shelf/reader | [SRC] |
| VideoPlayerActivity | Intro/training videos (ExoPlayer) | [SRC strings] |
| SystemMonitoringActivity | Tablet/system vitals screen | [SRC] |
| NotificationActivity | Notification list | [SRC][IMG bell badge] |
| AccountDetailsActivity / DealerInformationActivity | Profile & dealer info; logout | [SRC] |
| UpdateActivity / UpdateDescriptionActivity | App update notice + description | [SRC] |
| Screen recording | No dedicated Activity — floating overlay bubble + "Recording your screen"; "Drag down to stop the recording" (HBRecorder) | [VIDEO bubble][SRC] |

## UI state rules observed
- ECU chip shows **green dot** only while that ECU answers tester-present; dot/chip greys on loss. [IMG][INFERENCE from dot semantics]
- Out-of-range values render **red**, in-range **green** (VHR summary + diagnostic tab). [IMG 20260317 + f34]
- Mandatory-field validation blocks NEXT (photo + number required per checklist item). [VIDEO f31]
- Flashing screens hide back-exit during transfer ("Do not close the app…"). [SRC strings]

## Unknowns / Requires Validation
- Exact contents of SelectOptionActivity menu per model. [SRC only]
- Whether RaiderSelectionActivity is role home or vehicle sub-picker.
- Live parameter screen charting (graphs) — no media captured; assumed list+values form from logs cadence. [INFERENCE]
- ManualDiagnostic free grammar (service entry keypad?) — [SRC strings suggest keypad dialogs in burst r6].
