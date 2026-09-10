# Product Requirements Document: RideScan

**Package:** `com.ridescantp.mahle.ridescantp`
**Developer:** MAHLE (diagnostics platform provider), built for TVS Motor Company dealer network
**Version analyzed:** 2.3.6 (build revision `e86ca92`)
**Document status:** Reconstructed from static APK analysis — not an official source document. Sections marked *(inferred)* are reasonable interpretations based on observed code structure, not confirmed product decisions. Use this as a reference scaffold, not a substitute for the original spec.

---

## 1. Purpose & Background

RideScan is an Android field-diagnostics application used by TVS dealership technicians to connect to a vehicle's ECU(s) via a VCI (Vehicle Communication Interface) dongle, run diagnostics, flash ECU firmware, and generate customer-facing health reports.

*(inferred)* The product exists to replace/standardize a paper-and-laptop-based dealer diagnostic workflow with a single mobile tool that covers the full spread of TVS's ECU supplier ecosystem (Continental, Bosch, Pricol, Sedemac, Mikuni, Keihin, INEL, ISG) under one login and one report format.

## 2. Goals & Objectives

- Provide a unified diagnostic + flashing interface across TVS's motorcycle/scooter lineup, regardless of which ECU supplier is fitted to a given model/variant.
- Reduce dealer service time by auto-selecting correct flash images per VIN/variant rather than requiring manual technician judgment.
- Standardize service documentation via auto-generated PDF reports (Vehicle Health Report, Diagnostic Report, Battery Health Report).
- Support offline/field use in dealer service bays with unreliable connectivity (local VCI firmware assets bundled in-app).
- Provide dealership-level access control (SSO login, PIN-based recovery) to restrict flashing capability to authorized technicians.

## 3. Target Users *(inferred)*

| Persona | Description | Primary Needs |
|---|---|---|
| Dealer Service Technician | Front-line user performing diagnosis/flashing | Fast VIN scan → correct ECU flow, minimal manual config |
| Service Advisor / Dealer Admin | Manages dealer account, reviews reports | Report generation, dealer info management |
| TVS Backend / DMS | Consumes uploaded diagnostic data | Structured data sync via `amsmssi.com/DMS/` |

## 4. Scope

### In scope
- Bluetooth (Classic + BLE) pairing with VCI hardware (TZ VCI, TZ Mini VCI, TZ New VCI, TechPro variants)
- ECU read/write (flashing) across 10+ supplier-specific modules
- Live diagnostics: DTC read, live parameters/data recording, IO control, routine control
- Report generation and viewing (PDF, via iText)
- Screen recording of diagnostic sessions *(inferred: for QA/dispute evidence)*
- Dealer authentication (SSO + local PIN/OTP recovery)
- VCI dongle firmware self-update
- In-app update mechanism (self-installs APK updates — `REQUEST_INSTALL_PACKAGES` permission)

### Out of scope *(inferred, based on absence of evidence)*
- Consumer/end-rider-facing features (no evidence of a rider-facing mode — this is a B2B dealer tool)
- Payment processing
- Multi-OEM support (structure is TVS-model-specific)

## 5. Functional Requirements

### 5.1 Authentication & Access
- FR-1: User must authenticate via SSO dealer login before accessing diagnostic functions.
- FR-2: Support PIN-based login with forgot-PIN → OTP → reset-PIN recovery flow.
- FR-3: Support user type selection (e.g., technician vs. admin role) *(inferred from `UserTypeActivity`)*.

### 5.2 Vehicle Identification & Setup
- FR-4: Support VIN-based lookup to auto-identify vehicle model, variant, and applicable ECU configuration.
- FR-5: Maintain a vehicle list/history per dealer account.
- FR-6: Support manual variant/flash-file selection when VIN auto-detection is unavailable (`SelectFlashVarientActivity`), using a variant-to-ECU mapping table (see `flash_variant.json` in Section 7).

### 5.3 Device Connectivity
- FR-7: Pair with VCI hardware over Bluetooth Classic and BLE.
- FR-8: Support multiple VCI hardware generations (TZ VCI, TZ Mini VCI, TZ New VCI, TechPro) each with independent firmware update flows.
- FR-9: Detect and guide recovery/re-flash of VCI dongle firmware itself (bundled `.s19` Renesas 78K0R image suggests dongle-side MCU recovery capability).

### 5.4 ECU Diagnostics
- FR-10: Read and clear Diagnostic Trouble Codes (DTCs).
- FR-11: Display live ECU parameters in real time.
- FR-12: Record live data sessions for later review (`LiveDataRecordingActivity`).
- FR-13: Support IO Control (actuator tests) and Routine Control (supplier-defined service routines).
- FR-14: Support IUPR (In-Use Performance Ratio) test — primary and secondary — for emissions-monitor readiness checks.
- FR-15: Support guided manual diagnostic workflows outside the automated flow (`ManualDiagnosticActivity`).
- FR-16: Support gear-learning procedure for applicable transmission/ECU types.

### 5.5 ECU Flashing
- FR-17: Support ECU flashing across all major supplier ECU families used across the TVS lineup: Continental (Conti, Conti2), Bosch-family ABS (ABS Conti, BABS, BABS2, KABS), Pricol (base, 2/4/5-variant, Apache, BTO, TPMS, U400, mid-variant), Mikuni/KEMS (incl. CAN variant, recovery mode), Sedemac EMS (incl. XL100 OBD2B, U558 variants), Keihin (Sport variant), INEL, ISG (incl. Jupiter, Raider variants), Keyless ECU.
- FR-18: Support instrument cluster flashing for multiple cluster hardware generations: J125, N597, U577 (basic & premium), U732 (RLCD & TFT), U796.
- FR-19: Support VIN-based flashing flow that auto-selects the correct binary given vehicle identity (`VINBasedFlashingActivity`).
- FR-20: Validate flash-variant compatibility against vehicle build date / hardware revision before allowing flash (evidenced by variant descriptions like "vehicles produced before/after 31.07.2022" tied to specific hardware, e.g. ignition coil supplier changes).
- FR-21: Protect flashing operations via the native security layer (`libridescan_security.so`) — likely covering integrity checks, anti-tamper, or credential/signature validation for flash payloads. *(Implementation not analyzed — out of scope for this document.)*

### 5.6 Reporting
- FR-22: Generate a Vehicle Health Report (VHR) combining dealer info, diagnostic results, and IO control results.
- FR-23: Generate a standalone Battery Health Report.
- FR-24: Generate a Diagnostic Report summary, viewable and exportable as PDF (iText-based rendering).
- FR-25: Maintain a log viewer and file viewer for raw diagnostic/service artifacts.
- FR-26: Provide access to service manuals within the app (`ServiceManualActivity`).

### 5.7 Session Support Tools
- FR-27: Support in-app screen recording of diagnostic sessions with an overlay control, for QA, training, or dispute-resolution purposes *(inferred)*.
- FR-28: Support notification-driven background services for long-running operations (flashing, recording) via foreground services.

### 5.8 Platform & Update Management
- FR-29: Support self-update via in-app APK download/install.
- FR-30: Provide an onboarding/tutorial flow for first-time users.
- FR-31: Provide a notification center for dealer-relevant alerts/updates.

## 6. Non-Functional Requirements

- NFR-1 (Connectivity): Must operate reliably over Bluetooth in dealer-bay RF environments; must tolerate connection drops mid-diagnosis without corrupting flash operations.
- NFR-2 (Offline capability): Firmware and variant-mapping assets are bundled in-app (not fetched live), enabling operation with degraded connectivity.
- NFR-3 (Security): Flashing operations gated by a native (compiled, stripped) security module — implies a requirement that flash authorization logic not be easily bypassed or inspected client-side.
- NFR-4 (Auditability): Screen recording and log/file viewers suggest a requirement for session traceability, likely for warranty/QA compliance.
- NFR-5 (Device compatibility): Native library ships for armeabi-v7a, arm64-v8a, x86, x86_64 — supports both older and current Android device architectures used in dealer-issued tablets/phones.
- NFR-6 (Location): Requires fine/background location — likely a Bluetooth-scanning requirement on modern Android (BLE scan requires location permission on many OS versions) rather than a feature in itself.

## 7. Data & Configuration

**`flash_variant.json`** — a static config mapping vehicle *variant* codes to one or more *model* entries, each specifying:
- `description` (human-readable distinguishing detail, e.g., hardware revision/supplier notes)
- `value` (the specific flash-file key to apply)
- `ecu` (target ECU, e.g., `EMS`, `EMS-OBDII`)
- `norm` (emissions norm, e.g., `BSVI`)

This table is the mechanism by which FR-6/FR-20 (manual and automatic variant selection) resolve ambiguity — e.g., distinguishing pre/post 31 July 2022 builds of the same model due to a component supplier change.

**`vcf-renesas_78k0r.s19`** — Motorola S-record firmware image for a Renesas 78K0R microcontroller, bundled as an app asset. Supports FR-9 (VCI dongle-side firmware/recovery).

## 8. Third-Party Dependencies

| Library | Likely Purpose |
|---|---|
| Google Play Services (Location) | BLE scan support, geofencing/location-gated features |
| AndroidX WorkManager / Room | Background job scheduling, local persistence |
| iTextPDF | PDF report generation |
| BouncyCastle | Cryptographic operations / certificate handling |
| journeyapps (ZXing wrapper) | Barcode/QR scanning (likely VIN or dealer asset scanning) |
| hbRecorder | In-app screen recording |
| Ketch | Download management (updates, firmware assets) |

## 9. Permissions Rationale

| Permission | Feature Tie-In |
|---|---|
| Bluetooth (Classic/BLE scan/connect) | VCI pairing and communication |
| Camera | Barcode/VIN scanning |
| Location (fine/background) | Required for BLE scanning on modern Android |
| Internet / Network state | DMS sync, report upload, update checks |
| Storage (read/write/manage external) | Report/log storage, firmware asset staging |
| Foreground service (+ subtypes) | Long-running flash/recording operations |
| System alert window / overlay | Screen-record overlay controls |
| Install packages | Self-update mechanism |
| Accessibility service | *(inferred — possibly used for overlay interaction during screen recording; warrants confirmation as it's a sensitive permission)* |

## 10. Success Metrics *(inferred — not evidenced in the binary)*

Typical metrics for this product category, suggested for consideration rather than confirmed:
- Reduction in average diagnostic/flash session time per vehicle
- Flash failure/retry rate per ECU family
- Report generation completion rate
- Dealer adoption rate across network vs. legacy tooling

## 11. Risks & Open Questions

- The native security library's exact function is unknown from this analysis; if it governs flash-payload authenticity, its failure modes (e.g., offline dealer sites) should be documented separately.
- Broad `MANAGE_EXTERNAL_STORAGE` and `REQUEST_INSTALL_PACKAGES` permissions are high-privilege; worth confirming these map to active features rather than legacy/unused code paths.
- Accessibility service usage should be justified explicitly, as it's a commonly-flagged permission in app review processes.
- No consumer-facing or multi-OEM path was found — confirm this PRD's B2B-only scope matches actual product intent.

## 12. Appendix: Full Feature/Module Inventory (from Activity list)

Auth: Login, Register, ForgotPin, NewPin, OTP, SSO, UserType, Welcome, Tutorial, Splash
Vehicle: VehicleList, AddDevice, VINBasedDiagnosis, VINBasedFlashing, SelectECU
Diagnostics: ECUDiagnosis, ReadDTCs, LiveParameter, LiveDataRecording, IOControl, RoutineControl, IUPRTestPrimary/Secondary, ManualDiagnostic, GearLearning, DataWatcher, SystemMonitoring
Flashing (ECU): ECUFlashing, NewECUFlashing, SelectFlashVarient, ABSFlashingConti, BABSFlash, BABS2Flash, KABSFlash, ContiFlash, Conti2Flash, INELFlash, ISGFlash (+Jupiter, +Raider), KeihinFlashSport, KEMSFlashRecovery, KeylessECUFlashing, KEMSFlash (Mikuni), MikuniCanFlash, PricolFlash (+2/4/5/Apache/BTO/TPMS/U400/MidVariant), RoninFlashvariant, SEDEMAC_EMSFlash (+XL100OBD2B, +U558)
Flashing (Cluster): J125ClusterFlashing, N597_Cluster_Flash, U577Basic/PremiumClusterFlash, U732RLCD/TFTClusterFlash, U796ClusterFlash
VCI Firmware: FirmwareUpdate (TechPro), TZ24vVCIFirmwareUpdate, TZMiniVCIFirmwareUpdate, TZNewVCIFirmwareUpdate, TZVCIFirmwareUpdate
Reporting: DiagnosticReport, NewReportSummary, BatteryHealthReport, VhrActivity, VhrDealerInformation, VhrDiagnosticReport, VhrIOControl, LogViewer, FileViewer, ServiceManual
Account/Dealer: AccountDetails, DealerInformation, Notification, UpdateDescription, Update
Session tools: ScreenRecordOverlayService, OverlayService, ClientService, AppCloseService

---
*End of reconstructed PRD.*
