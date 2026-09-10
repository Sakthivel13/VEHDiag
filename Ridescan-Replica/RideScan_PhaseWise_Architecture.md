# RideScan — Phase-Wise Architecture

**Document status:** This maps the Architecture doc's components onto the Workplan/Roadmap's phases — i.e., which layers, packages, services, and dependencies would need to exist *by* each phase for that phase's features to work. Like the Roadmap itself, phase boundaries are reconstructed from feature dependency logic, not observed build history. Component names are the confirmed ones from the Architecture/Folder-Structure docs; the phase groupings are the inferred part.

---

## Phase 0 — Foundation Architecture

**Goal of this phase:** nothing else can be built until identity, connectivity, and persistence exist.

```
┌─────────────────────────────────────┐
│              UI Layer                  │
│  Splash → Welcome → Tutorial → Login    │
│  → SSO / ForgotPin / OTP → UserType     │
│  → Home (shell only, tiles inert)         │
├─────────────────────────────────────┤
│            ViewModel Layer               │
│  LoginViewModel, HomeViewModel (stub)      │
├─────────────────────────────────────┤
│              Data Layer                    │
│  Remote: Retrofit/OkHttp client scaffolding  │
│    → Bootstrap/config call (BootstrapResponse) │
│  Local: Room DB schema created (empty tables)   │
├─────────────────────────────────────┤
│            Hardware Layer                        │
│  btlibrary: BluetoothUtil, SerialService,           │
│  SerialSocket, SerialListener — pairing only,         │
│  no protocol payload logic yet                          │
└─────────────────────────────────────┘
```

**New in this phase:** `data/model` auth DTOs (`DealerInfo`, `DealerInfoResponse`, `ForgotPasswordResponse`, `NewPinResponse`, `OTPRequestResponse`), `btlibrary` package in full, Room setup, base networking client.
**Permissions introduced:** `INTERNET`, `BLUETOOTH*`, `ACCESS_NETWORK_STATE`.
**Dependencies introduced:** Retrofit2, OkHttp3, Room, Kotlin Coroutines/Flow.

---

## Phase 1 — Core Diagnostics Architecture

**Goal:** prove the UDS/ISO-TP pipeline works, read-only.

```
┌─────────────────────────────────────┐
│              UI Layer                  │
│  VehicleList, AddDevice, SelectECU,     │
│  VINBasedDiagnosis, ManualDiagnostic,     │
│  ReadDTCs, LiveParameter, LiveDataRecording │
├─────────────────────────────────────┤
│            ViewModel Layer               │
│  One ViewModel per screen above            │
│  + a shared "DiagnosticSessionManager"       │
│    coordinating UDS request/response state     │
│    (inferred — not directly observed, but        │
│    necessary given the fan-out of screens          │
│    all needing an active UDS session)                │
├─────────────────────────────────────┤
│              Data Layer                                │
│  Remote: DTC/LiveParameter response models bound         │
│    to backend sync (DtcErrorCodeResponse,                  │
│    LiveParameterResponse)                                    │
│  Local: Room caching of read DTC/parameter history              │
├─────────────────────────────────────┤
│            Hardware Layer                                        │
│  btlibrary now carries real payloads:                              │
│  UDS request framing (service 0x19 DTC read, 0x22                    │
│  read-data-by-identifier) over ISO-TP segmentation                     │
│  on top of the existing serial transport                                 │
└─────────────────────────────────────┘
```

**New in this phase:** `ui/read_DTCs`, `ui/live_parameter`, `ui/live_data_recording`, `ui/manual_diagnostic`, `ui/vin_based_diagnosis`, `ui/select_ECU`, `ui/vehicle_list`, `ui/add_device` packages; `DTCsDatum`, `DtcErrorCodeData/Response`, `LiveParameter`, `LiveParameterResponse`, `LiveDataRecording`, `ECUModel` data models.
**Architectural decision locked in here:** the UDS session/transport abstraction built in this phase becomes the shared foundation every later phase (write ops, flashing) depends on — meaning any UDS-layer bug from this phase propagates forward into every subsequent phase's reliability.

---

## Phase 2 — Write Operations & Routine Diagnostics Architecture

**Goal:** extend the same UDS pipeline to write-capable services, still non-destructive.

```
┌─────────────────────────────────────┐
│              UI Layer                  │
│  IOControl, RoutineControl,             │
│  IUPRTestPrimary/Secondary,               │
│  IUPRHistory, GearLearning                  │
├─────────────────────────────────────┤
│            ViewModel Layer               │
│  IOControlViewModel, RoutineControlViewModel,│
│  IUPR*ViewModel — reuse DiagnosticSessionManager│
├─────────────────────────────────────┤
│              Data Layer                    │
│  IOControl / IoControlResponse,               │
│  IUPRData/History/Primary/Secondary/Report/    │
│  Response models; sync to backend for              │
│  emissions-compliance record-keeping (BSVI norm)      │
├─────────────────────────────────────┤
│            Hardware Layer                                │
│  UDS write services added: IO control (0x2F-class),         │
│  routine control (0x31)                                        │
└─────────────────────────────────────┘
```

**New in this phase:** `ui/io_control`, `ui/routine_control`, `ui/iupr_test`, `ui/gear_learning_procedure` packages; `IOControl*`, `IUPR*` data models.
**Architectural note:** no new infrastructure layers — this phase is purely UI + data-model expansion on top of Phase 1's transport, which is exactly what you'd expect from an incremental "add another UDS service type" phase rather than a structural change.

---

## Phase 3 — ECU Flashing Architecture

**Goal:** the highest-risk write path — firmware transfer to the ECU — rolled out per supplier.

```
┌─────────────────────────────────────────────┐
│                    UI Layer                       │
│  ECUFlashingActivity, NewECUFlashingActivity,        │
│  SelectFlashVarientActivity, + ~25 supplier-specific    │
│  Activities (Conti, BABS/BABS2/KABS, Pricol×9,             │
│  Sedemac×3, Mikuni/KEMS×2, Keihin, INEL, ISG×3,               │
│  Keyless, + 5 cluster-flashing Activities)                       │
├─────────────────────────────────────────────┤
│                  ViewModel Layer                     │
│  One ViewModel per Activity above (structurally           │
│  near-identical — see Code Audit doc, Section 5)             │
├─────────────────────────────────────────────┤
│                    Data Layer                              │
│  FlashModel, FlashSequence, FlashVariant/Item,                │
│  EcuFlash/EcuFlashResponse, FlashFeedbackRequest,                │
│  FlashReportResponse, FMWData, FwDetail                            │
│  Bundled asset: flash_variant.json (variant→ECU→flash-file map)      │
├─────────────────────────────────────────────┤
│                  Hardware Layer                                    │
│  UDS transfer services (0x34 request-download,                       │
│  0x36 transfer-data, 0x37 request-transfer-exit),                      │
│  security-access sequence (0x27) gated by                                │
│  libridescan_security.so                                                  │
└─────────────────────────────────────────────┘
```

**New in this phase:** the entire `ui/ecu_flashing/*` subtree (largest package in the app by screen count), `libridescan_security.so` native module, `dialog_erase_loader`/`dialog_retry_confirmation` shared UI components.
**Architectural inflection point:** this is where the "duplicate-per-supplier" pattern (flagged in the Code Audit doc) gets baked in structurally — each new ECU supplier/model added a new Activity+ViewModel+layout instead of extending a shared engine. `ECUFlashingActivity`/`NewECUFlashingActivity` existing alongside the per-supplier ones suggests a generalization attempt was made but didn't fully replace the specific implementations.

---

## Phase 4 — Reporting Architecture

**Goal:** turn accumulated diagnostic/flash data into dealer- and customer-facing documents.

```
┌─────────────────────────────────────┐
│              UI Layer                  │
│  DiagnosticReport, NewReportSummary,     │
│  BatteryHealthReport, Vhr* (4 tabs),       │
│  LogViewer, FileViewer                       │
├─────────────────────────────────────┤
│            ViewModel Layer               │
│  Report assembly ViewModels pulling from      │
│  Room (cached session data) rather than          │
│  re-querying the ECU                                │
├─────────────────────────────────────┤
│              Data Layer                                │
│  New dependency: iTextPDF (+ styledxmlparser,             │
│  svg, io.font modules) for PDF rendering                     │
│  FlashReportResponse, DealerInfo tied into report              │
│  templates                                                       │
├─────────────────────────────────────┤
│            Hardware Layer                                          │
│  (none new — this phase is purely UI/Data)                            │
└─────────────────────────────────────┘
```

**New in this phase:** `ui/diagnostic_report`, `ui/report_summary_new`, `ui/vehicle_health_report/*`, `ui/battery_health_report`, `ui/log_viewer`, `ui/file_viewer` packages; iTextPDF dependency (with its licensing consideration flagged in the DevOps doc); `FileProvider` manifest entry for sharing generated PDFs outside the app sandbox.

---

## Phase 5 — Field Support & Hardware Lifecycle Architecture

**Goal:** support the VCI hardware and the app itself once deployed at scale across dealers.

```
┌─────────────────────────────────────┐
│              UI Layer                  │
│  FirmwareUpdate (TechPro), TZ24v/Mini/     │
│  New/VCIFirmwareUpdate, Update,               │
│  UpdateDescription, Notification                 │
├─────────────────────────────────────┤
│            ViewModel Layer               │
│  Per-hardware-generation update ViewModels    │
├─────────────────────────────────────┤
│              Data Layer                        │
│  GetVCIUpdateResponse, FirmwareVersion,           │
│  FwDetail, LocalVCIFMW, AppUpdate/Response          │
│  Bundled asset: vcf-renesas_78k0r.s19 (dongle         │
│  recovery firmware)                                      │
├─────────────────────────────────────┤
│            Hardware Layer                                      │
│  Dongle-side firmware transfer protocol (separate                 │
│  from vehicle-ECU UDS flashing — different MCU,                     │
│  different transport assumptions, possibly the                       │
│  192.168.4.1 local-AP path flagged in the Code Audit)                  │
├─────────────────────────────────────┤
│          Distribution Layer (new)                                         │
│  In-app self-update: REQUEST_INSTALL_PACKAGES permission,                    │
│  internal APK hosting (likely via the DMS backend)                              │
└─────────────────────────────────────┘
```

**New in this phase:** `ui/firmware_update/*`, `ui/update/*`, `ui/notification` packages; the app's own update/distribution mechanism, separate from Play Store; VCI recovery firmware asset.

---

## Phase 6 — Support & Quality-of-Life Architecture

**Goal:** reduce field friction and support burden without adding vehicle-facing capability.

```
┌─────────────────────────────────────┐
│              UI Layer                  │
│  ChatBot surface (fragment/dialog,        │
│  not a manifest Activity), ServiceManual,   │
│  PhysicalEvaluation, SystemMonitoring,        │
│  DataWatcher                                    │
├─────────────────────────────────────┤
│            Service Layer (new)           │
│  OverlayService, ScreenRecordOverlayService,  │
│  AppCloseService                                │
├─────────────────────────────────────┤
│              Data Layer                            │
│  (mostly reuses existing models — this phase          │
│  is UX/support tooling, not new domain data)             │
├─────────────────────────────────────┤
│          New Dependencies                                    │
│  hbRecorder (screen recording), Ketch (download          │
│  management for support content/manuals)                    │
└─────────────────────────────────────┘
```

**New in this phase:** `service/OverlayService`, `service/ScreenRecordOverlayService`, `service/AppCloseService`; `SYSTEM_ALERT_WINDOW`, foreground-service-subtype permissions (`FOREGROUND_SERVICE_MEDIA_PROJECTION`, `FOREGROUND_SERVICE_MICROPHONE` — needed for screen+audio capture).

---

## Cross-Phase Architecture Summary

| Phase | Adds to UI | Adds to Data | Adds to Hardware/Native | Adds to Infra |
|---|---|---|---|---|
| 0 | Auth shell | Room, Retrofit client | BT pairing (no payload) | — |
| 1 | Diagnostics screens | DTC/Param models | UDS read services | — |
| 2 | Routine/IO/IUPR screens | Routine/IO/IUPR models | UDS write (non-destructive) | — |
| 3 | ~30 flashing screens | Flash models, `flash_variant.json` | UDS transfer + security-access, native `.so` | — |
| 4 | Report screens | Report models | — | iTextPDF, FileProvider |
| 5 | Firmware/update screens | Firmware/update models | Dongle-side firmware transfer | Self-distribution channel |
| 6 | Support/QoL screens | (reuse) | — | Screen-record/overlay services |

**Key structural takeaway:** the `btlibrary`/UDS transport layer built in Phase 0–1 is the single most load-bearing piece of architecture in the whole app — every later phase (write ops, flashing, even firmware updates) is a different *payload* over the *same* transport foundation. Any reliability or protocol-timing issue introduced early would surface everywhere, which is also why Phase 1 (read-only diagnostics) as a proving ground before Phase 3 (destructive flashing) is the architecturally sound order — whether or not it was the actual build order historically.

---
*As with the Roadmap doc, phase boundaries here are inferred from dependency logic, not observed commit history — useful for understanding how the pieces fit together, not as a historical record.*
