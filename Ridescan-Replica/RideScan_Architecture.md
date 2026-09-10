# RideScan — System Architecture

**Package:** `com.ridescantp.mahle.ridescantp` · **Version analyzed:** 2.3.6
**Document status:** Reconstructed from static APK analysis (dex string inspection, manifest inspection, package/class naming). This reflects what's structurally observable, not internal design docs. Confidence is noted per section — items backed by direct string/class evidence are marked **(confirmed)**; interpretive leaps are marked **(inferred)**.

---

## 1. High-Level System Overview

```
┌─────────────────────┐        Bluetooth (Classic/BLE)      ┌──────────────────┐        UDS / ISO-TP over CAN      ┌─────────────┐
│   RideScan Android   │ ───────────────────────────────────▶│   VCI Dongle      │───────────────────────────────────▶│  Vehicle ECU │
│   App (dealer device)│◀─────────────────────────────────── │ (TZ VCI / TZ Mini │◀───────────────────────────────────│ (EMS/ABS/ICU/│
└──────────┬───────────┘                                     │  / TechPro)       │                                    │  Cluster...) │
           │  HTTPS (Retrofit/OkHttp)                         └──────────────────┘                                    └─────────────┘
           ▼
┌──────────────────────┐
│  Backend DMS API      │
│  amsmssi.com/DMS/     │
│  (dealer mgmt, flash   │
│   files, report sync)  │
└──────────────────────┘
```

Three tiers **(confirmed for tiers 1 & 2, inferred for tier 3's internal implementation)**:
1. **Mobile client** — Android app performing UI, session orchestration, local caching, and BLE/Serial protocol handling.
2. **VCI hardware bridge** — a Bluetooth-connected dongle that translates between the phone's serial byte stream and the vehicle's CAN bus, speaking UDS (ISO 14229) — directly evidenced by strings like *"SEDEMAC With UDS"* and ECU descriptions referencing UDS-based EMS units.
3. **Backend DMS** — dealer management system reachable at `amsmssi.com/DMS/`, responsible for dealer auth, flash file distribution, and diagnostic/report data sync.

## 2. Client Application Architecture (MVVM)

**(confirmed)** — dex strings show per-feature `*ViewModel.kt` classes (e.g. `U558SEDEMAC_EMSFlashViewModel`, `TZ24vVCIFirmwareUpdateViewModel`, `U577PremiumClusterFlashViewModel`), Kotlin Coroutines + Flow (`StateFlowImpl`, `SharedFlowImpl`, `AbstractFlow`), and AndroidX `ViewModelStores`. This is a standard **MVVM** app: one Activity + one ViewModel per feature screen, with reactive state exposed via `StateFlow`/coroutines rather than LiveData-only patterns.

```
UI Layer (Activity/Fragment, ~97 activities)
        │  observes
        ▼
ViewModel Layer (per-feature, holds UI state as StateFlow)
        │  calls
        ▼
Data Layer
   ├── Remote: Retrofit + OkHttp → DMS backend API
   ├── Local: Room (SQLite) → cached dealer/vehicle/session data
   └── Bundled assets: flash_variant.json, VCI firmware (.s19)
        │
        ▼
Hardware Layer: btlibrary (Bluetooth serial) → VCI dongle → vehicle ECU
```

There is no evidence of Hilt/Dagger/Koin dependency injection — object wiring is likely manual (constructor injection or a lightweight service-locator pattern) **(inferred, based on absence of DI framework markers)**.

## 3. Package Structure (as observed)

```
com.ridescantp.mahle.ridescantp
├── data/
│   └── model/            # Large flat set of DTOs/POJOs — request & response models
│                          # per feature (EcuFlash, FlashVariant, DTCsDatum, IUPR*, 
│                          # DealerInfo, FobKeyResponse, LiveParameter, etc.)
├── btlibrary/             # Bluetooth Classic serial transport layer
│   ├── BluetoothUtil
│   ├── SerialListener      # callback interface for incoming serial data
│   ├── SerialService        # foreground service maintaining the BT connection
│   ├── SerialSocket          # wraps the RFCOMM/BLE socket
│   ├── Constants
│   └── TextUtil
├── ui/
│   ├── login/, register/, forgotpin/, sso_dealership_login/, usertype/
│   ├── home/, main/, splash/, welcome/, tutorial/
│   ├── vehicle_list/, add_device/, vin_based_diagnosis/, vin_based_flashing/, select_ECU/
│   ├── ecu_diagnosis/, read_DTCs/, live_parameter/, live_data_recording/,
│   │   io_control/, routine_control/, iupr_test/, manual_diagnostic/,
│   │   gear_learning_procedure/, data_watcher/, system_monitoring/
│   ├── ecu_flashing/
│   │   ├── abs_flashing/{abs_flashing_conti, babs_flashing, babs2_flashing, kabs_flashing}/
│   │   ├── conti_flashing/{conti_flash, conti2_flash}/
│   │   ├── inel_flashing/, isg_flashing/{isg_flash, isg_flash_jupiter, isg_flash_raider}/
│   │   ├── keihin_flashing/keihin_flash_sport/
│   │   ├── kems_flash/kems_flash_recovery/
│   │   ├── keyless_ecu_flashing/
│   │   ├── mikuni_flashing/{kems_flash, mikuni_can_flash}/
│   │   ├── pricol_flashing/{pricol_flash, pricol_2/4/5_flash, pricol_apache_flash,
│   │   │                    pricol_bto_flash, pricol_tpms_flash, pricol_u400_flash,
│   │   │                    mid_variant_pricol2_flash}/
│   │   ├── sedemac_ems_flashing/{sedemac_ems_flashing, sedemac_xl_100_obd2b_flash,
│   │   │                          u558_sedemac_ems_flashing}/
│   │   ├── j125_cluster_flashing/, n597_cluster_flashing/,
│   │   │   u577_cluster_flashing/{basic, premium}/, u732_cluster_flashing/{rlcd, tft}/,
│   │   │   u796_cluster_flashing/
│   │   ├── ecu_flashing/ (generic ECUFlashingActivity + SelectFlashVarientActivity)
│   │   └── ronin_flash_variant/
│   ├── firmware_update/{techpro, tz_24v_vci, tz_mini_vci, tz_new_vci, tz_vci}/
│   ├── diagnostic_report/, report_summary_new/, vehicle_health_report/{vhr, dealer_info,
│   │   diagnostic_report, io_control}/, battery_health_report/
│   ├── log_viewer/, file_viewer/, servicemanual/, video_player/
│   ├── account_details/, dealerinformation/, notification/, update/, update_description/
│   └── gtsviews/, physical_evaluation/, raider_selection/, selectoption/, write_data/
└── service/
    ├── ClientService        # likely the main BT/session coordinator
    ├── OverlayService        # screen-record overlay
    ├── ScreenRecordOverlayService
    └── AppCloseService        # cleanup on app termination
```

## 4. Communication Layers

### 4.1 Phone ↔ VCI Dongle **(confirmed transport, inferred protocol detail)**
- Transport: Bluetooth Classic (RFCOMM serial) via the `btlibrary` package — this matches the structure of the well-known open-source Android Bluetooth Serial library pattern (`SerialService`/`SerialSocket`/`SerialListener`), adapted in-house.
- BLE permissions (`BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT`) are also declared, suggesting dual support for BLE-based VCI hardware alongside Classic.
- Payload protocol: UDS (ISO 14229) over ISO-TP (ISO 15765-2)/CAN, based on ECU descriptions explicitly referencing UDS-based EMS units. The app builds and parses UDS service requests/responses (e.g. DTC read = service 0x19, IO control = 0x2F-class services, routine control = 0x31, flashing = 0x34/0x36/0x37-class transfer services) at the ViewModel/data layer before handing bytes to `SerialService`. *(Service-ID mapping is inferred from standard UDS conventions matching the app's feature set — not directly observed in strings, since these are typically byte constants rather than readable text.)*

### 4.2 Phone ↔ Backend (DMS) **(confirmed library, inferred endpoint shapes)**
- Retrofit2 + OkHttp3 confirmed via dex strings (`retrofit2.KotlinExtensions`, multipart/form-urlencoded annotation-processing errors, OkHttp logger references).
- Multipart support implies file upload endpoints — most likely for report/log upload and possibly flash-feedback payloads (`FlashFeedbackRequest`, `FlashReportResponse` model classes observed).
- Base host: `amsmssi.com/DMS/` **(confirmed string, path structure/endpoints not enumerated — likely obfuscated or dynamically built)**.
- Model classes observed (non-exhaustive) map cleanly to API request/response DTOs: `DealerInfoResponse`, `EcuFlashResponse`, `DtcErrorCodeResponse`, `IOControlResponse`, `IUPRResponse`, `LiveParameterResponse`, `AppUpdateResponse`, `GetVCIUpdateResponse`, `FobKeyResponse`, `BootstrapResponse` (likely an app-init/config-fetch call), `ConfirmGTSResponse` (GTS = likely "Global Test/Traceability System" or similar internal TVS system — name only, function inferred).

### 4.3 Local Persistence **(confirmed)**
- `android.database.sqlite.*` classes present alongside Room migration-related strings (`RoomDatabase.Builder.addMigration`) confirm Room-over-SQLite as the local store, used for caching dealer/vehicle/session data and enabling offline continuity between backend syncs.

## 5. Security Architecture

- **Native security module** — `libridescan_security.so` (stripped ELF, shipped for armeabi-v7a/arm64-v8a/x86/x86_64). Not reverse-engineered as part of this analysis; based on naming and placement (loaded early, used across flash-flow classes) it most plausibly handles one or more of: flash-payload integrity/signature verification, anti-tamper/root-detection, or license/session token generation. **This function is inferred from context, not confirmed from disassembly** — I didn't disassemble or analyze its internal logic.
- **Auth**: SSO-based dealer login plus a local PIN with OTP-based recovery — a two-tier model (network SSO for account-level access, local PIN for fast re-entry during a shift) **(inferred from activity flow)**.
- **Authorization boundary**: Flashing screens are gated behind the same login/session used for diagnostics — no evidence of a separate elevated-privilege flow distinguishing "diagnose" vs. "flash" permissions at the client level; if such separation exists, it's likely enforced server-side per dealer/technician role.

## 6. Data Assets & Configuration-Driven Behavior

- **`flash_variant.json`** (bundled asset): a static lookup table driving which flash binary/config applies to a given vehicle variant + build-date/hardware-revision combination. This keeps flash logic data-driven rather than hardcoded per activity — new variants can likely be added via this config (or its backend-synced equivalent) without a full app release, though the copy observed is bundled at build time.
- **`vcf-renesas_78k0r.s19`** (bundled asset): dongle-side firmware/recovery image for a Renesas 78K0R MCU, used by the VCI firmware-update flows to recover/re-flash the dongle itself.

## 7. Background & Session Services

- `SerialService` — foreground service maintaining the live Bluetooth connection to the VCI, decoupled from Activity lifecycle so a flash/diagnostic session can survive screen navigation.
- `ClientService` — likely the top-level session/state coordinator between UI and the BT + network layers **(inferred from name/position, not internals)**.
- `OverlayService` / `ScreenRecordOverlayService` — system-alert-window-based overlay controls for in-session screen recording (hbRecorder-backed).
- `AppCloseService` — cleanup hook to release BT resources / persist state on app termination.
- AndroidX WorkManager present — used for scheduled/deferrable background work (e.g. deferred report upload, update checks) rather than time-critical flashing operations, which would run on the foreground `SerialService` instead.

## 8. Reporting Pipeline

```
Diagnostic session data (Room, in-memory ViewModel state)
        │
        ▼
Report assembly (VhrDiagnosticReportActivity / NewReportSummaryActivity / etc.)
        │
        ▼
PDF rendering (iTextPDF: styledxmlparser, svg, io.font modules present)
        │
        ▼
Local file (FileViewerActivity) ──▶ optional upload to DMS (Retrofit multipart)
```

## 9. Third-Party Dependency Map

| Layer | Library | Role |
|---|---|---|
| Networking | Retrofit2 + OkHttp3 | REST client to DMS backend |
| Persistence | AndroidX Room (SQLite) | Local structured cache |
| Concurrency | Kotlin Coroutines + Flow | Async orchestration, reactive UI state |
| Background work | AndroidX WorkManager | Deferrable/background jobs |
| Location | Play Services Location | Supports BLE scan permission requirements |
| PDF | iTextPDF (+ styledxmlparser, svg modules) | Report generation |
| Crypto/Certs | BouncyCastle | Certificate/crypto operations (likely TLS or signed-payload verification support) |
| Barcode | journeyapps/ZXing wrapper | VIN/asset scanning |
| Screen recording | hbRecorder | Session capture |
| Downloads | Ketch | Managed download of updates/firmware |

## 10. Deployment & Update Model

- **App updates**: in-app download + self-install flow (`REQUEST_INSTALL_PACKAGES`, `UpdateActivity`, `UpdateDescriptionActivity`, `AppUpdateResponse` model) — bypasses Play Store distribution, consistent with an internal/dealer-network-only distribution model rather than public release.
- **VCI firmware updates**: separate per-hardware-generation update flows, each with its own Activity and presumably its own backend-versioned firmware payload (`GetVCIUpdateResponse`, `FirmwareVersion`, `FwDetail` models).
- **Config updates**: `BootstrapResponse` model suggests an app-init call to the backend that may deliver remote config/feature flags on launch, though `flash_variant.json` itself ships as a bundled static asset rather than a purely server-driven table.

## 11. Known Gaps in This Reconstruction

- Exact UDS/ISO-TP framing implementation (timing parameters, session/security-access sequences) is not visible via string analysis — this lives in bytecode logic, not string literals.
- `libridescan_security.so` internals are unexamined by design.
- Backend API surface (exact endpoint paths, auth token scheme) is not enumerable from the client binary alone.
- No DI framework detected — actual object-graph wiring approach is assumed, not confirmed.

---
*End of reconstructed architecture document.*
