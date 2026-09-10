# 18 — NirixX Implementation Matrix (brief §27)

Status legend: ✅ implemented · ◐ partial · ✖ missing · 🧩 redesign · 🔌 hardware dep ·
🌐 backend dep · 📦 protocol dep · 🎨 UX dep · ⚠ requires validation.
NirixX = v1.6.1 (build 12). Reference versions analyzed: 2.2.5(190)/2.3.0.

| # | Reference capability | Reference behavior (evidence) | NirixX equivalent | Status | Required work |
|---|---|---|---|---|---|
| 1 | Login wizard Dealer→Designation→Login + remember + change-account | [VIDEO f01][SRC] | LoginActivity + tabs + remembered dealer | ✅ | — |
| 2 | OTP→PIN auth | [SRC strings][IMG] | OTP/PIN screens; real OTP backend absent | ◐🌐 | DMS OTP API (MISSING_DEPENDENCIES) |
| 3 | SSO dealership login | [SRC SSOActivity] | SsoLoginActivity stub (honest "not configured") | ◐🌐 | DMS SSO endpoint |
| 4 | Role-driven home (Dealer Service / Dealer Engineer) | [IMG][SRC UserType] | Roles + filtered Home grid + operation guards | ✅ | — |
| 5 | VCI pairing BT SPP + Wi-Fi + USB selector | [VIDEO][LOG][SRC btlibrary] | BtLink(SPP via ELM-style) + WifiLink + UsbLink, chooser | ◐🔌 | TechPRO Wi-Fi/USB framing UNKNOWN; Kvaser/TechPro SDKs |
| 6 | VCI identity/fw in session header (1.07) | [LOG] | Firmware/identity capture on connect (ElmCan ATI/ATRV analog) | ✅ (ELM dialect) | vendor SDK for TechPRO fields |
| 7 | VCI fw forced-update 5-skip policy | [SRC strings] | FirmwareUpdateActivity honest about channel | ◐📦 | skip-budget UI + vendor update protocol |
| 8 | Auto-VIN via 22F190 + 0902, RCRP, multi-frame | [LOG both] | UdsClient.readVin + Obd.mode09 | ✅ | — |
| 9 | Model/VIN decode → variant+image | [IMG][PDF][XREF] | VinRules 33-model table + image map | ✅ | keep table synced w/ catalogue |
| 10 | Per-model ECU topology (7E0/7E1/7E5/7F0 ±1/±8) | [LOG both] | TransportSettings per-model address books | ✅ | populate more models when captured |
| 11 | ECU discovery + per-ECU grid gating | [IMG 105128019][LOG 19/3E/22 NRCs] | SelectECU + per-ECU function map | ✅ | — |
| 12 | Live parameters (sequential 22xx) | [LOG] | LiveParameterActivity poll engine | ✅ | — |
| 13 | Param decode (names/units/scale, ~100 DIDs) | [LOG payloads][PDF units] | partial table; "definition pending" rows | ◐📦 | OEM DID definition pack |
| 13b | Per-ECU CAN re-address on select; OBD-II on 7DF functional; 3E 00 keep-alive @~3 s | [LOG both] | ElmCan.setAddress + DiagEngine.readdress + tracedFunctional + keep-alive ticker | ✅ (v1.6.2) | — |
| 14 | DataWatcher + Live Data Recording CSV | [SRC] | DataWatcher + LiveDataRecording (CSV) | ✅ | — |
| 15 | ReadDTCs 19 02 FF + RCRP + status histogram + All/Active/History | [LOG][IMG] | ReadDTCs w/ real parse + filter | ✅ | — |
| 16 | ClearDTC 14 FF FF FF + auto-rescan | [LOG2] | implemented | ✅ | — |
| 17 | DTC description dictionary | [IMG prose rows] | core descriptions from codes seen; "unknown code" honest | ◐📦 | OEM DTC text pack |
| 18 | GTS viewer per DTC | [SRC GTSViewActivity] | — | ✖ | build viewer shell; content pack dep |
| 19 | Freeze frame | not present in reference (10_freeze_frame.md) | deliberately absent | n/a | design when 19 03/04 data exists |
| 20 | DID identity reads (F190/F182/F1F4) | [LOG] | UdsClient identity set | ✅ | — |
| 21 | DID write (2E) under 10 03+27 | [LOG2 pre-chain][SRC] | WriteDataActivity: real 27 seed shown; 2E executed behind guard | ◐📦⚠ | OEM seed-key algorithm + writable-DID pack |
| 22 | RoutineControl 31 01 (+02/03) under security | [LOG2][SRC] | RoutineControl + secured chain; GearLearning edge | ◐📦 | RID catalogue pack |
| 23 | Gear Learning guided screen | [SRC] | GearLearningActivity | ✅ | — |
| 24 | IO Control 0x2F toggles + VHR auto-sequence | [LOG2][VIDEO][IMG] | DiagOps.ioControl + both surfaces | ◐📦 | IO DID map per model |
| 25 | IUPR primary/secondary + history | [SRC][LOG 0908] | IuprTest (single screen, real 09 reads) | ◐ | Secondary screen + history persistence |
| 26 | Manual diagnostic tester | [SRC] | ManualDiagnosticActivity (real catalogue) | ✅ | — |
| 27 | VHR 5-tab wizard | [VIDEO][SRC] | VhrActivity-equivalent 5-tab flow | ✅ | — |
| 28 | VHR bounded params + green/red | [VIDEO f34][IMG] | same, values only from device | ✅ | — |
| 29 | VHR physical checklist + mandatory photos + inline camera | [VIDEO f13–f31][PDF p2] | checklist + SAF photo import (no in-app camera) | ◐🎨 | Camera2 framework-only capture (next-feature candidate) |
| 30 | VHR verdict + PDF `<Variant>_<VIN>_VHR.pdf` + auto-upload | [VIDEO f37][PDF] | verdict card + report export via DocsProvider; upload absent | ◐🌐 | DMS upload API |
| 31 | Diagnostic report screen | [SRC] | DiagnosticReportActivity | ✅ | — |
| 32 | Battery health report | [SRC] | BatteryHealth + ATRV/PID42 real volts | ✅ | EV pack DIDs when published |
| 33 | Flashing: 15 supplier flows, HEX download, secret-key dialogs | [IMG][SRC][JSON] | FlashRunner (UDS 34/36/37) + SupplierFlash + variant JSON imported as data-driven table | ◐📦🔌 | supplier flows per family; campaign binaries; seed-key algos |
| 34 | VIN-based flashing | [SRC] | VinFlashingActivity | ✅ (flow) | same deps as 33 |
| 35 | VIN-based diagnostics | [SRC][LOG] | VINBasedDiagnosis | ✅ | — |
| 36 | Service manual shelf | [SRC] | ServiceManualActivity (real import/shelf) | ✅ | content packs |
| 37 | Intro videos (ExoPlayer) | [SRC strings] | IntroVideosActivity (own SAF-imported shelf + framework playback) | ✅ (v1.6.2) | — |
| 38 | AI chatbot | [SRC "RIDE Scan Chatbot!"] | AiAssistantActivity (local rule engine) | ◐🌐 | backend LLM/rules service |
| 39 | Logs: file per session, viewer, upload | [LOG][SRC LogViewer/FileViewer] | session logs + logging infra + viewer | ◐🌐 | DMS upload |
| 40 | Screen recording bubble (HBRecorder) | [VIDEO][SRC] | honest session-capture **indicator** only (no video recorded); real MediaProjection pipeline pending | ◐ 🎨 | consent flow + VirtualDisplay/MediaRecorder (v1.6.2 copy explicitly says no video is recorded) |
| 41 | System monitoring | [SRC] | SystemMonitoringActivity (real telemetry) | ✅ | — |
| 42 | Notifications (bell+list) | [SRC][IMG] | NotificationActivity (real state rows) | ◐🌐 | push channel |
| 43 | App update screens | [SRC Update*] | Update/UpdateDescription (honest states) | ◐🌐 | update server |
| 44 | Session id `<vci><ddMMyyyy><HHmmss>` + footer chip | [XREF ×4] | same format parity | ✅ | — |
| 45 | Persistent footer (session, version, connectivity) | [VIDEO][IMG] | global footer component | ✅ | — |
| 46 | Breadcrumbs + ECU chip/green dot | [IMG] | breadcrumb + ECU chip on diag screens | ✅ | — |
| 47 | Busy/outcome dialog language (orange/green/red) | [VIDEO][IMG][SRC] | same dialog grammar (own artwork) | ✅ | — |
| 48 | AppCloseService flush on task removal | [SRC] | AppCloseService + crash trace | ✅ | — |
| 49 | Per-ECU flash restriction note | [IMG 105128019] | ecu policy flags | ✅ | — |

### Net parity snapshot
- **✅ 26** · **◐ 19** (13 backend/protocol-gated) · **✖ 1** (GTS viewer) · **n/a 1** · 2 design-queue.
- Hard external dependencies (all in ../../MISSING_DEPENDENCIES.md): DMS APIs (auth/upload/push),
  OEM seed-key, ODX/DID/DTC/RID/IO packs, supplier flash docs+binaries, TechPRO/Kvaser SDKs,
  EV battery DIDs.

### §28–§30 pointers (standing)
- **Architecture target** (§28): see `../../ARCHITECTURE.md` — UI → DiagEngine → UdsClient →
  CanTransport → links; vendor SDKs isolated behind `CanTransport`; UI never touches bus objects.
- **UI implementation rules** (§29): docs 02/04/14/15 encode the interaction contract; NirixX
  follows reference *behavior*, never reference *pixels/assets* (clean-room).
- **Observability** (§30): doc 16 + `logging` config in Db; comms vs UI vs crash channels
  separated; session context (timestamp/user/role/session/VIN/VCI/ECU/service/request/response/
  result/duration/app-version) written per operation.
