# RideScan — Workplan / Roadmap

**Document status:** Unlike the previous documents, a roadmap cannot be extracted from a compiled APK — there's no trace of sprint history, ticket data, or timelines in the binary. This is a **plausible reconstructed workplan**, built by ordering the observed feature set (Section 2 of the Architecture doc) by realistic technical dependency — i.e., what a team would sensibly have to build first for later phases to be possible. Treat this as a scaffold to compare against the real project history, not a record of it.

---

## Phasing Logic

The dependency chain is fairly clear from the app's own structure:
1. You can't diagnose/flash anything without **connectivity** (BT/VCI pairing) and **identity** (auth, vehicle ID) working first.
2. **Diagnostics** (read-only: DTCs, live params) is lower-risk and reusable across every ECU family — a natural next step, and likely used to validate the UDS/ISO-TP pipeline before trusting it with write operations.
3. **Flashing** is the highest-risk, highest-value feature, and it fans out into ~25 near-duplicate supplier-specific modules — this shape (one Activity/ViewModel per supplier+model combo) is exactly what you'd expect from a roadmap that added vehicle/ECU coverage incrementally, model by model, rather than building a generic flashing engine up front.
4. **Reporting** depends on diagnostic + flash data existing, so it logically follows.
5. **VCI firmware self-update** and **app self-update** are infrastructure/maintenance features that tend to get added once the core product is in the field and dongle-hardware revisions start shipping.

## Phase 0 — Foundation *(prerequisite for everything else)*
- Project scaffolding: Gradle setup, package structure, CI skeleton
- Auth: Login, SSO integration, PIN + OTP recovery flow
- Core networking layer: Retrofit/OkHttp client, DMS backend contract (bootstrap/config call)
- Local persistence: Room schema for dealer/vehicle/session caching
- Bluetooth transport layer (`btlibrary`): pairing, serial connection, reconnection handling
- Basic navigation shell: Splash → Welcome → Tutorial → Home

## Phase 1 — Core Diagnostics (read-only ECU communication)
- VIN-based vehicle identification, Select ECU flow
- UDS session handling over the BT/VCI transport (read-only services first: DTC read, live parameter read)
- Read DTCs, Live Parameter, Live Data Recording
- Manual Diagnostic flow (fallback path for unidentified/edge-case vehicles)
- Establishes and hardens the transport + UDS layer that every later feature depends on

## Phase 2 — Write Operations & Routine Diagnostics
- IO Control (actuator tests)
- Routine Control
- IUPR Test (primary/secondary) — emissions-readiness checks, likely tied to a regulatory requirement (BSVI norm compliance) rather than an arbitrary feature choice
- Gear Learning Procedure
- These represent controlled "write-but-not-destructive" ECU interactions — a reasonable risk step-up before flashing

## Phase 3 — ECU Flashing (rolled out incrementally per supplier/model)
Given the near-1:1 mapping between activity names and specific ECU suppliers/models, this phase was almost certainly delivered as a series of releases, each adding one or two supplier integrations rather than a single "flashing" launch:
- 3a: Generic flashing engine + first supplier integration (likely Continental/Conti, given its position as the most "generic-named" module)
- 3b: Bosch-family ABS variants (ABS Conti, BABS, BABS2, KABS)
- 3c: Pricol family — largest single supplier surface (base, 2/4/5-variant, Apache, BTO, TPMS, U400, mid-variant) — likely reflects Pricol's broad presence across the TVS model range, added incrementally per model line
- 3d: Sedemac EMS family (incl. UDS-based variants, XL100 OBD2B, U558)
- 3e: Mikuni/KEMS, Keihin, INEL, ISG (incl. Jupiter/Raider), Keyless ECU
- 3f: Instrument cluster flashing (J125, N597, U577 basic/premium, U732 RLCD/TFT, U796) — plausibly a later phase, since cluster flashing is a distinct hardware domain from EMS/ABS flashing and likely required its own protocol handling
- VIN-based auto-flashing (auto-selecting the right module from `flash_variant.json`) likely arrived after enough individual modules existed to make automatic routing worthwhile

## Phase 4 — Reporting & Compliance
- Diagnostic Report, Report Summary
- Vehicle Health Report (multi-tab: dealer info, diagnostic, IO control, summary)
- Battery Health Report
- PDF generation pipeline (iText integration)
- Log Viewer / File Viewer for raw artifact access
- Flash feedback/report sync to DMS backend (`FlashFeedbackRequest`, `FlashReportResponse`)

## Phase 5 — Field Support & Hardware Lifecycle
- VCI firmware update flows, per hardware generation (TechPro, TZ VCI, TZ Mini VCI, TZ New VCI) — added as new dongle hardware revisions were introduced to the field
- VCI dongle recovery firmware (`.s19` bundled asset) — safety net for bricked dongles
- App self-update mechanism (internal distribution, bypassing Play Store)
- Notification system for dealer-relevant alerts

## Phase 6 — Support & Quality-of-Life
- Screen recording + overlay (session capture for QA/training/dispute resolution)
- In-app chatbot/support surface
- Service manual viewer
- Physical Evaluation flow
- System Monitoring / Data Watcher (likely internal diagnostics of the app/VCI link itself, not the vehicle)

## Suggested Forward-Looking Roadmap Items *(purely illustrative — not evidenced, offered as typical next steps for a product at this maturity level)*

- Automated regression suite per ECU-family flash module (given ~25 near-duplicate flows, a shared test harness would reduce maintenance risk)
- Consolidating the ~25 supplier-specific flashing Activities into a single configuration-driven flashing engine, if not already underway — the current structure suggests linear growth-by-duplication, which tends to become a maintenance burden past a certain scale
- Expanding `flash_variant.json`-style config-driven vehicle mapping to also drive UI presentation (reducing net-new Activities per new model)
- Telemetry/crash reporting tie-in for field flash-failure diagnosis, if not already present in the DMS backend

---
*Reconstructed for planning-reference purposes only — cross-check against actual release notes, git tags, or the version-control history (`e86ca92a8698c7d8f052099c4278bf69c0012b4a` and its ancestry) for a real timeline.*
