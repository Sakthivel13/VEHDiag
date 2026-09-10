# NirixX — two-wheeler diagnostics & flashing suite

> **Beyond Diagnostics.**

> 📚 **Deep reference analysis:** the complete evidence-driven study of the reference
> application (protocol logs, video, PDF, package tree) and its NirixX mapping lives in
> [`docs/analysis/`](docs/analysis/README.md) — 21 documents covering functional spec,
> screen map, roles, VCI & vehicle communication, per-feature protocol specs, VHR, flashing,
> logging/recording, state machines, implementation matrix, and test strategy.

NirixX is a complete, standalone Android dealer-diagnostics application built inside this
repository: a full workflow implementation inspired by the reference tool analyzed in the
repo-root documentation (PRD, architecture, wireframes, project structure, roadmap) — shipped
under its own brand, with its own visual identity, its own signing identity, and **100%
original code and artwork**.

> **What it is / what it isn't.**
> NirixX is a working diagnostics client: since **v1.5.0** it speaks **real UDS (ISO 14229)
> over real ISO-TP (ISO 15765-2)** through real Bluetooth-SPP / Wi-Fi-TCP / USB-CDC links to
> an ELM327-class VCI, and acquires the vehicle VIN from the ECU. Where a dependency cannot
> legally or physically ship (vendor VCI SDKs, OEM seed-key algorithms, per-model ODX packs,
> campaign binaries, DMS backend) the code exposes a clean interface and the gap is documented
> in `MISSING_DEPENDENCIES.md` — **nothing is silently faked**: screens that cannot run real
> data say so on-screen, and the simulation path is an explicitly-labelled *training mode*.
> Every screen, flow and string was written from scratch, and every image was AI-generated
> for NirixX — the reference app's binary, logos, photos and brand assets are **not**
> redistributed anywhere in this module; the reference APK stays untouched at the repo root
> as analysis material only.

---

## 1. Deliverable

**`NirixX.apk`** — 39.2 MB (deliberately richer than the 29.5 MB reference build, and every
extra byte is real, on-screen content)

| Property | Value |
|---|---|
| Package | `com.nirixx.app` |
| Label / tagline | **NirixX** · "Beyond Diagnostics" |
| Version | `1.6.3` (versionCode 14) |
| SDK window | **minSdk 24 (Android 7.0) → targetSdk 34 (Android 14)** |
| Signature | own NirixX keystore, **APK Signature Scheme v2 + v3** |
| Architecture | universal (pure Java, no native libs → all ABIs) |
| Footprint | **50 activities · 3 services · 1 provider** · 87 Java sources · 120 drawable resources |
| Database | **SQLite** (`nirixx.db` v2, offline-first, zero third-party deps) |
| Dependencies | zero third-party libraries — Android framework only (no AndroidX) |
| Build | one command: `bash build.sh` (~2 min, hermetic, offline) |
| Verification | `tools/verify_apk.py` → **21/21 checks PASS** |
| Unit tests | `tests/run_tests.sh` → **all core suites PASS** (VIN rules, ISO-TP, UDS, NRC) |

---

## 2. v1.6.0 — the honesty pass (current build)

v1.5.0 made the *link layer* real; v1.6.0 hunts down every remaining fabricated value in the
app and replaces it with a real measurement or an honest "not available" state.

**Screens now driven by the live engine (via `core/diag/DiagOps` — single serial executor,
every frame traced into the session log):**

- **DTCs** — real `19 02 FF` / `14 FF FF FF`; cards show the ECU's actual codes with library
  descriptions (or "not in library"), active/stored from the real status byte; clear is
  confirmed by an automatic re-read. The old `Math.random()` outcome is deleted.
- **Live Parameter / Data Watcher** — real SAE J1979 polling (`core/uds/Obd`: RPM 0x0C,
  speed 0x0D, coolant 0x05, intake temp 0x0F, MAP 0x0B, throttle 0x11, module voltage 0x42);
  rows without a published address render "definition pending" and never move.
- **IO Control / Routines / Write-DID** — real `2F`, real `31`, real `2E`. Write-DID performs
  a genuine `27 01` seed fetch and shows it; the key step is gated on the OEM algorithm
  (dependency #3) exactly as documented. Rows without a published DID/routine id are
  labelled, not actuated.
- **Battery Health** — real adapter rail (ATRV) + module voltage (PID 0x42) + public 12 V
  lead-acid SoC bands; CCA/internal-resistance/ripple explicitly marked "not measurable via CAN".
- **Flashing (ECU + supplier modules)** — the reference 4-phase UI now runs a REAL transfer:
  imported binary (SAF) → `10 03` → `31 01 FF00` → `34` → `36 × n` → `37` → `11 01`, with
  progress from actual blocks and true NRC reporting on refusal. Flash preconditions are
  measured (rail via ATRV, tablet charge via BatteryManager) instead of a fake video gate.
- **Firmware / Notifications / App Update / IUPR / VHR** — all fabricated content removed:
  identity strings read from the adapter (ATI), notifications reflect real device state,
  release notes describe what actually shipped, VHR tables list only values genuinely
  sampled in the session ("NM" otherwise), System Monitoring counts real frames.
- **Service Manual / Live Recording** — real document shelf (import, true sizes, open via
  the new framework-only `DocsProvider`) and real CSV recorder/replayer.
- **Registration flow wired** (Login → Register → OTP → New PIN) with the OTP-backend gap
  stated on-screen; navigation graph fully connected — zero unreachable screens.

**Storage:** DB **v3** adds `tests.addr` (bus addresses: `did:`/`pid:`/`m09:`/`rid:`/`io:` —
grammar in `core/diag/TestAddr`), `manuals`, `flash_bins`.

**Tests:** 8 JVM suites now (added J1979 decode, addr grammar, battery bands) — all pass.

---

## 2A. v1.5.0 — production-real diagnostic stack

The upgrade from "reference-parity UI with a data layer" to a **real diagnostics client**.
Full analysis: `ARCHITECTURE.md`; explicit gap ledger: `MISSING_DEPENDENCIES.md`.

**Real protocol stack** (`core/`, pure Java, framework-only, unit-tested on the JVM):

- `core/uds/IsoTp.java` — ISO 15765-2: SF/FF/CF/FC session layer with block-size & STmin
  sender pacing, flow-control emission on FF, N_Bs/P2 timeouts, and `awaitResponse()` for
  NRC 0x78 (response-pending) sequences.
- `core/uds/UdsClient.java` — ISO 14229 services: 0x10 session, 0x11 reset, 0x14 clear-DTC,
  0x19 read-DTC (parses `59 02` records → P/C/B/U codes), 0x22 read-DID (incl. F190 VIN),
  0x27 security access, 0x28 communication control, 0x2E write-DID, 0x31 routine control,
  0x34/0x36/0x37 download pipeline, 0x3E tester-present, 0x85 control-DTC-setting. Negative
  responses raise `UdsError(sid, nrc)`; 0x78 is waited out (≤40 × 5 s).
- `core/uds/Nrc.java` — 30+ NRCs with technician remediation hints
  (e.g. 0x22 → "Conditions not correct — verify ignition ON, vehicle stationary, battery > 11 V").
- `core/vin/VinRules.java` — ISO 3779 validation (I/O/Q excluded) + the **authoritative
  33-model vehicle table** (model → variant systems → VIN prefix), longest-prefix-first match.
- `core/vci/` — real transports: `BtLink` (RFCOMM SPP), `WifiLink` (TCP, default
  192.168.0.10:35000), `UsbLink` (USB-host CDC-ACM, runtime permission flow), and
  `ElmCan` — the real ELM327 dialect init (ATZ/E0/L0/H1/AT0/SP6/SH/CRA) with header-aware
  hex frame parsing and adapter-id capture.
- `core/diag/DiagEngine.java` — owns the chain `link → ElmCan → IsoTp → UdsClient`:
  open link → diagnostic session (10 01, 10 03 fallback) → read VIN (22 F190) → ISO 3779
  validate → match against the 33-model table. Every stage reports structured failure
  (stage, error, NRC + hint). It **never fabricates** a VIN or a match.
- `core/role/Roles.java` — module-level RBAC. **Dealer Service** = connect, auto-VIN,
  diagnose (live/DTC/IO/routine), VHR, reports, battery, logs, recording. **Dealer
  Engineer** = everything incl. flashing, VIN-write, campaigns, VCI firmware, app update.
  Enforced in `BaseActivity.go()` (navigation) **and** hard-guarded in the operation
  activities themselves (`FlashActivity`, `WriteDataActivity`).

**Where it lands in the UI:**

- *Add Device*: BT list pairs real links; **Wi-Fi panel = real `WifiManager` scan** for
  `NirixiLINK*` hotspots + editable endpoint; **USB panel = real `UsbManager` enumeration**
  with VID/PID and runtime permission. Connect → `DiagEngine.connectAndIdentify()` on a
  worker thread → vehicle identified → Diagnostic Section (matched) or Vehicle List
  (VIN read, unmatched); failure shows stage + NRC hint with RETRY / manual selection.
- *VIN Diagnosis*: with a live engine it performs the **real VIN read** (frame-level console +
  `UdsLog`); without hardware it runs the clearly-badged **TRAINING LINK (no VCI)** path.
- *Vehicle DB v2*: the supplied 33-model table is the only vehicle source (exact VIN first,
  then longest-prefix rule match); ECU rows per model derive from its variant-systems string
  (EMS/ABS/ICU/ISG/EV → tx/rx ids, manufacturer, tests) — data-driven, no `if (vehicle == …)`.
- *VHR physical tab*: real photo capture via SAF (`ACTION_OPEN_DOCUMENT`) → copied into
  `Reports/`, thumbnailed, stored against the VHR item.

**Integration boundaries (implemented interfaces, missing third-party halves):** Kvaser /
TechPro vendor SDKs, OEM 0x27 seed-key algorithm, per-model ODX/CDD packs, campaign binaries
+ eligibility backend, DMS backend, EV battery-pack definitions. Each row in
`MISSING_DEPENDENCIES.md` states why, where it plugs in, what's already implemented behind
the interface, and the exact action to close it.

---

## 2B. v1.4.0 — reference-UI parity + real database

Driven page-by-page by the `Ridescan UI Reference Images/` folder (137 screenshots, two UDS
session logs, the sample `TVS Ronin … _VHR.pdf` and the DMS communication captures):

- **UI language now matches the reference everywhere**: white app bar (back, dark title,
  `EMS-OBDII ●` status chip, user icon, brand tile), light-blue `#C9D8F2` section bars,
  navy `#14276F` primary buttons, outlined input boxes, breadcrumb rows
  (`Home » TVS Jupiter New » EMS-OBDII » IO Control`), and the **bottom session bar on every
  screen** — document icon + session id (`vciSerial + ddMMyyyyHHmmss`), version badge
  (`V 1.4.0`), connectivity glyph.
- **VCI is honest now**: fictional catalogues are deleted. Login shows the VCI dropdown +
  `ADD/PAIR VCI` link plus **Bluetooth / Wi-Fi / USB connectivity tiles**; the same three
  interfaces drive `AddDeviceActivity` (BT scan list, Wi-Fi hotspot picker
  `NirixiLINK_504856…`, USB OTG panel). Everything identifies as the NirixiLINK family with
  firmware `1.07` (as in the captured session logs).
- **Real database, not mock strings**: `db/Db.java` — SQLiteOpenHelper with roles, users,
  vehicles (image/type/VIN-format/description), ECUs-per-vehicle (tx/rx ids, protocol,
  emission), tests per ECU (live, IO, routine, write-DID with min/max), DTC library, flash
  files, VHR physical items, sessions, logs, stream samples, test inputs, IUPR history,
  VHR reports and configs (`support_number → +917969478770`, app version, last VCI, domain).
  SQLite was chosen over MongoDB deliberately: this is an offline workshop tool — an embedded
  DB needs no server, works with zero permissions, and is framework-built-in (no libraries).
- **Auto VIN flow**: `10 01 → 22 F190` with the same 7F-22-response-then-62 sequence the real
  logs show → DB lookup → matched vehicle card with **OPEN DIAGNOSTIC SECTION** /
  **VEHICLE HEALTH REPORT**; unknown VIN → the vehicle home grid (per-vehicle card with
  artwork, description, type, VIN format & sample).
- **Diagnostic Section (Select ECU) page**: vehicle image from the DB, status tiles
  (fault status, **live-streaming battery voltage**, updates), `Diagnostic` bar, ECU list
  with green/red availability legend and Manufacturer / CAN Protocol / Emission expansion.
- **ECU Diagnosis grid** → a dedicated page per tile, all reference-shaped:
  Live Parameters (category dropdown + info cards with min/max), Diagnostic Trouble Codes
  (`19 02` read / `14 FF` clear), **Write Data Identifier with encoded password**
  (`27 01` seed → key → `27 02` → `2E` write), Input Output Control (toggle rows → `2F`),
  ECU Flashing (conditions dialog with video gate + green call pill
  **+91 7969478770**, 4-segment Download→Load→Flashing→Reset progress, numbered timestamped
  logs), Routine Control, IUPR Test (primary CVN/CAL-ID/ratios + secondary form + history).
- **Vehicle Health Report rebuilt**: tabs **DEALER | DIAGNOSTIC | IO CONTROL |
  PHYSICAL EVALUATION | SUMMARY**, live collectors feeding a **real 2-page A4 PDF**
  (`android.graphics.PdfDocument`) replicating the sample report: dark banner with vehicle
  art + red slashes, dealer & vehicle info block, `I. Engine Management System` vehicle-data
  table with Min/Max/Value/Status ✓, IO-control results, physical evaluation with photo
  thumbs, shield + verdict shield summary page, `#NirixXCares` strip and disclaimer. PDFs
  land in `Reports/`, are indexed in the `vhr_reports` table and listed in Reports.
- **Session logging exactly like the product**: every screen mirrors UDS traffic through
  `sim/UdsLog` into `Logs/<sessionId><VIN>.txt` with the reference File-Header block
  (device, Android, app version, dealer, session id, firmware, connectivity) and
  `yyyy-MM-dd HH:mm:ss.SSS I/: TX: --> 7E0 -> …` lines — and the same rows go to the
  SQLite `logs` table for the Log Viewer (ALL/TX/RX/INFO filters).
- **Extras wired in**: screen-record toggle (Account), customer-call pill (dialer intent),
  AI assistant chat answering flashing/DTC/VCI/report/IUPR questions, File Viewer browsing
  the real on-disk artifacts.

**Install note:** v1.4.0 is signed with this repo's committed dev keystore
(`NirixX/keystore/nirixx.jks`, alias `nirixx`). If an older NirixX build signed with a
different local key is installed, **uninstall it first** — Android refuses mixed-signature
updates.

**CI:** `NirixX/ci/build.yml.example` is a ready GitHub Actions workflow (ubuntu runner,
JDK 17, android-34 SDK; runs `build.sh` then `verify_apk.py` and uploads the APK artifact).
Drop it into `.github/workflows/` to enable — this sandbox token has no `workflows`
permission, so it cannot be committed under that path from here.

---

## 3. How we got here — full build history

### Phase 0 — Reference analysis (repo root)
The repo root holds the complete reverse-engineering analysis of the reference dealer app:
`RideScan_PRD.md`, `RideScan_Architecture.md`, `RideScan_PhaseWise_Architecture.md`,
`RideScan_Project_Structure.md`, `RideScan_UIUX_Wireframes.md`, `RideScan_Workplan_Roadmap.md`,
`RideScan_Code_Audit_Findings.md`, `RideScan_DevOps_Tooling.md`, plus extracted artifacts
(manifest, resource dumps, `flash_variant.json`). Everything NirixX does is specified there.

### Phase 1 — Look-alike mock (commit `14f7c04`, "hermetic pipeline")
- Built a **fully offline Android toolchain** in a network-restricted sandbox and assembled a
  Gradle-free pipeline: `aapt2` (resource compile/link against an API-34 `android.jar`) →
  ECJ (Java compilation) → `dx` (dexing) → `apksigner` (v2+v3 signing).
- First working APK: splash/welcome/login/home plus the core screens (~25 activities) with a
  shared `Ui` widget kit and `BaseActivity` scaffolding.

### Phase 2 — Full module inventory (commit `4747f1f`)
- Completed the entire PRD §12 module map: **47 activities + 4 services** — full auth graph,
  VCI pairing, VIN flows, 6-ECU diagnostics, ~25 supplier flash modules, cluster flashing,
  VCI firmware, reports hub, support tooling (logs/files/chat/monitoring).
- Real `flash_variant.json` (repo-supplied reference data) parsed at runtime for the VIN-driven
  flash-variant flow.

### Phase 3 — NirixX rebrand (commit `1db4fcd`, v1.0.0)
- Own identity end to end: package `com.ridescan.replica` → **`com.nirixx.app`**, label
  **NirixX**, own keystore (`CN=NirixX, O=NirixX Mobility`), new color tokens
  (`brand_primary/brand_deep/brand_accent/…`, `Theme.NirixX`).
- **All pre-existing artwork stripped** and replaced with AI-generated originals: N-bolt logo,
  wordmark, hero motorcycle, VCI dongle, ECU module, report banners (see §6).
- Every brand string, link, channel id and shared-prefs key scrubbed (case-insensitive sweep,
  verified zero residual traces).

### Phase 4 — VCI coverage + real Bluetooth stack (commit `1cdae76`, v1.1.0)
- **10-model VCI catalog** (6 NirixX hardware generations + 4 third-party Android adapters).
- New `com.nirixx.app.vci` package: a genuine Android Bluetooth transport layer with the
  simulator plugged behind it (see §5).
- 20 new artworks → APK passed the reference's size with real content (36 MB).
- Identity refresh: deep-teal chrome accent, "Beyond Diagnostics" tagline, welcome secondary
  action, home hero banner.

### Phase 5 — Modern-Android readiness (commit `836ebd4`, v1.2.0)
- **targetSdk 29 → 34**, runtime-permission helper (`Perms`), typed foreground service,
  adaptive launcher icon, display-cutout support, explicit `exported`, storage-permission caps,
  install-everywhere `uses-feature` flags (§7).

### Phase 6 — Permission UX + self-check (commit `c17e700`, v1.3.0)
- Bluetooth **rationale dialog** before the system prompt (demo-mode escape hatch).
- **Auto-rescan** the instant access is granted (`onRequestPermissionsResult` → live scan).
- **System Self-Check** screen: live green-tick device scoring with FIX deep-links (§8).

### Phase 6.1 — Hotfix: launch crash + Play-safe profile (v1.3.1)
- **Fixed the Android-14 launch crash** ("App Status Error. Install again" right after a
  successful install): the session foreground service was typed `connectedDevice`, whose
  runtime prerequisite — Bluetooth permissions *already granted* — cannot hold on a fresh
  install, so `startForeground()` threw `SecurityException` and killed the process.
  `ClientService` is now typed **`dataSync`** (no runtime prerequisites) with nested
  fallbacks, and the `startService` call site is guarded. DEX confirmed format 035 → loads
  on every API 24+ runtime.
- **Play Protect profile cleaned:** removed `REQUEST_INSTALL_PACKAGES` and
  `SYSTEM_ALERT_WINDOW` — the two classic sideload risk-triggers (only mock stubs used
  them). The remaining "unknown developer" notice is inherent to *any* sideloaded APK not
  distributed via Play and only clears by shipping through Play Console.
- v1 (JAR) signing intentionally omitted: irrelevant at minSdk 24+ (Android 7.0 verifies v2
  natively) and unsupported by the offline signer build.

### Phase 6.2 — Forensics: alignment + self-reporting crash handler (v1.3.2)
- Wrote `tools/zipalign.py` (raw-zip writer) fixing STORED-entry alignment — `resources.arsc`
  was landing at offset %4 == 2; Android loads it regardless, but the APK is now canonical.
- Added `NirixXApp` (Application) with an uncaught-exception handler that persists the full
  trace; `SplashActivity` surfaces it in a *"NirixX stopped unexpectedly"* dialog on the next
  launch (turns any device-only crash into a paste-able bug report).
- `camera` / `camera.autofocus` marked `required="false"`.

### Phase 6.3 — Reference comparison + decisive probe experiment (v1.3.3)
- Line-by-line package comparison against the reference app (from `classes-dex2jar.jar` +
  `resources.txt`): the original ships **DEX 039, v2-signature-only** — ours (DEX 035, v2+v3)
  is the more conservative, wider-compatible artifact; signature/format ruled out as causes of
  the device-side launch failure.
- ECJ switched to `-1.7` classfiles; built **`NirixX-Probe.apk`** (255 KB, one hello screen,
  zero permissions, same pipeline + keystore) to bisect device-block vs app-content faults.

### Phase 6.4 — Automated verification suite + reachability fix (v1.3.4, **current**)
- New **`tools/verify_apk.py`** (`python3 tools/verify_apk.py` → exit 0 = shippable): parses
  badging, verifies v2/v3 signatures, checks STORED-entry alignment from *local* zip headers,
  parses all 217 DEX classes with androguard, proves every manifest-declared component exists
  in the DEX, cross-checks **all 49 screens** (content layout exists, every `findViewById`
  id resolves in the correct layout, every navigation target is declared), builds the screen
  reachability graph from `SplashActivity`, and runs a 21-point Android 12/13/14/15 checklist.
  Human-readable output: **`VERIFICATION.md`** (21/21 passed, 0 errors, 0 warnings).
- **Fixed a real UX gap the suite caught:** `AccountActivity` (and the five screens it hubs —
  Dealer Information, File Viewer, System Monitoring, Physical Evaluation, Data Watcher) had
  no incoming navigation. Home's dealer footer now opens the Account screen; all 49 screens
  are reachable from the launcher. Version labels corrected to the honest NirixX numbering.

### Phase 6.5 — Launch forensics: white-screen-then-close root-caused & fixed (v1.6.3, **current**)
User report: on the phone the app showed only a white screen, then closed itself — every time,
with no error dialog. Two independent causes were found and fixed:

1. **The shipped v1.6.2 DEX was structurally broken (root cause).** `Ui.errorBar` captured two
   non-`final` locals — legal Java 8 "effectively final" but an **error at the app's ECJ `-1.7`
   source level**. ECJ reports the error yet keeps going, **silently dropping the whole
   `Ui.java` unit** (all 6 classes), and `build.sh` never checked ECJ's output. The packaged
   `classes.dex` therefore referenced `Lcom/nirixx/app/Ui;` without defining it — so every
   screen built with Ui helpers died with `NoClassDefFoundError`, including the crash-report
   dialog itself (a white flash, then an endless silent loop). Verified byte-level with
   androguard against the published v1.6.2 APK: **old dex has no `Ui.class`; the new one
   defines `Ui` + `Ui$1..5`.** Fixes: `Ui.errorBar` now captures `final` variables;
   `build.sh` aborts on any ECJ `ERROR` and asserts critical classes were emitted;
   `verify_apk.py` gained a gate proving **every app source class is defined in the dex**
   (this exact failure mode is now impossible to ship again).
2. **A policy-sensitive call at process birth (hardening).** `NirixXApp.onCreate()` started
   `AppCloseService` with `startService()` *before* installing the crash handler — on
   Android 12+ OEM edge paths (installer "Open", recents re-launch on MIUI/ColorOS/Funtouch)
   that can throw and kill the process before the first frame, with zero captured evidence.
   The handler is now installed first, no system calls remain in `Application.onCreate`, and
   `AppCloseService` starts when a VCI actually connects (the only moment its task-removal
   cleanup matters). `SplashActivity` additionally guards its own first frame: if inflation
   ever fails, the trace is recorded *and* shown on a raw view instead of a silent white
   screen; and a new **launch watchdog** detects "died before any UI with no Java trace" —
   i.e. an OS/Play-Protect/OEM kill — and tells the user exactly how to whitelist the app
   instead of failing silently.

Gates after the fix: JVM tests 9/9 · `verify_apk.py` 21/21 (now 367 dex classes) ·
`audit_links.py` 0/0.

---

## 3. Feature inventory (all 49 activities)

### 3.1 Authentication & onboarding
| Screen | Purpose |
|---|---|
| `SplashActivity` | Brand splash, first-run routing, version tag |
| `TutorialActivity` | 3-slide first-run carousel with dots / Skip |
| `WelcomeActivity` | Hero + Get Started + "I already have a NirixX ID" |
| `LoginActivity` | Dealer Email + 4-digit PIN (SSO-style banner card) |
| `SsoLoginActivity` | NirixX ID sign-in |
| `RegisterActivity` | New workshop application (distributor approval copy) |
| `OtpActivity` | OTP verification for PIN recovery |
| `NewPinActivity` | Set a new PIN |
| `UserTypeActivity` | Role selection (technician / manager / admin) |

### 3.2 Home & connectivity
| Screen | Purpose |
|---|---|
| `HomeActivity` | 17-tile module grid, VCI status card, dealer footer, hero banner |
| `AddDeviceActivity` | Rationale → runtime prompt → **live scan + sim pool** → pair |
| `VciCatalogActivity` | All 10 supported VCIs with renders, specs, "Use this VCI" |
| `SystemCheckActivity` | Runtime self-check with FIX actions (§8) |

### 3.3 Vehicles & VIN flows
| Screen | Purpose |
|---|---|
| `VehicleListActivity` | Demo garage (5 vehicles), add-vehicle dialog |
| `VinDiagnosisActivity` | VIN entry/scan → vehicle identity card → diagnostics |
| `VinFlashingActivity` | VIN-driven flashing entry (extends diagnosis flow) |
| `ManualDiagnosticActivity` | Direct model/variant selection without VIN |

### 3.4 Diagnostics
| Screen | Purpose |
|---|---|
| `SelectECUActivity` | 6 ECU families (EMS, ABS, Cluster, Keyless, ISG, TPMS) |
| `ECUDiagnosisActivity` | Per-ECU menu hub |
| `ReadDTCsActivity` | DTC list, freeze frames, clear (UDS 0x14 sim) |
| `LiveParameterActivity` | Animated live-data stream (RPM/speed/temp/voltage…) |
| `LiveDataRecordingActivity` | Recorded-session capture + replay list |
| `IOControlActivity` | Momentary actuator tests with safety auto-off |
| `RoutineControlActivity` | UDS routine console (start/stop/status) |
| `IuprTestActivity` | AIS-137 IUPR primary/secondary monitors |
| `GearLearningActivity` | Gear-position learning routine |
| `DataWatcherActivity` | Raw UDS frame watcher (TX/RX log) |

### 3.5 Flashing
| Screen | Purpose |
|---|---|
| `SupplierFlashListActivity` | ~25 supplier modules in 7 families, per-family module art |
| `SupplierFlashActivity` | Generic staged engine: IMAGE/Bootloader pickers → odometer dialog → erase → program → verify |
| `SelectFlashVariantActivity` | Variant table backed by the real `flash_variant.json` |
| `FlashActivity` | VIN-driven flash progress with live log |
| `ClusterFlashListActivity` | 7 cluster platforms (J125 … U796) |
| `VciFirmwareListActivity` | Firmware update entry per NirixX hardware generation |
| `FirmwareUpdateActivity` | S-record transfer pipeline + recovery note |

### 3.6 Reports & data
| Screen | Purpose |
|---|---|
| `ReportsActivity` | Report hub with generated banner art |
| `DiagnosticReportActivity` | Session report + simulated DMS upload |
| `VhrActivity` | NirixX Vehicle Health Report (4 tabs + PDF export stub) |
| `BatteryHealthActivity` | SoH gauge + battery metrics |
| `LogViewerActivity` | Session logs with level filters |
| `FileViewerActivity` | Generated/report file browser |

### 3.7 Support & app management
| Screen | Purpose |
|---|---|
| `NotificationActivity` | Update/alert center |
| `ServiceManualActivity` | Manual library |
| `SupportChatActivity` | NirixX Assistant (canned technician Q&A) |
| `AccountActivity` | Dealer profile |
| `DealerInformationActivity` | Dealer edit form |
| `PhysicalEvaluationActivity` | Walkaround inspection checklist |
| `SystemMonitoringActivity` | App/resource monitor |
| `UpdateDescriptionActivity` | Release notes for the in-app update |
| `UpdateActivity` | Mock self-update download/install flow |

### 3.8 Services
| Service | Purpose |
|---|---|
| `ClientService` | Foreground session notification (`dataSync`-typed FGS, crash-safe) |
| `AppCloseService` | Session cleanup on task removal |
| `OverlayService` | Overlay control stub |
| `ScreenRecordOverlayService` | Recording-state flag for live-data capture |

---

## 4. Identity & design system

| Element | Value |
|---|---|
| Primary | `#141A4A` midnight indigo (headers, splash, status bar) |
| Deep | `#0A0E2C` (dark theme base) |
| Chrome accent | `#0B8376` deep teal · `#18E0C8` electric teal (buttons, tints, links) |
| Art accent | `#2BD9FF` cyan glow (stays inside generated artwork) |
| Success | `#23C79A` · Warning `#E8A33D` · Attention `#E63946` |
| Type | system `sans` + generated oblique wordmark with cyan underline |
| Icon | adaptive "N-bolt" monogram (see §6) |

Shared widget kit (`Ui.java`) — `tv`, `chip`, `card`, `listRow`, `kvRow`, `section`,
`roundRect`, `dialog`, `progressDialog`, `resultDialog`, `dp` — keeps all 49 screens visually
consistent; `BaseActivity` supplies title/back/navigation/toast plumbing.

---

## 5. VCI support & transport architecture

### 5.1 Supported hardware (10 models)
| NirixX hardware | Link | | Third-party Android adapters | Link |
|---|---|---|---|---|
| NRX Pro VCI (flagship) | BT Classic + BLE + Wi-Fi | | ELM327-compatible (SPP) | BT Classic |
| TZ VCI (Classic) | BT Classic (SPP) | | ELM327-compatible (BLE) | BLE 4.0+ |
| TZ Mini VCI | BT Classic (SPP) | | J2534 pass-thru | Wi-Fi |
| TZ New VCI | BLE 5.0 + USB-C | | USB K-Line | USB OTG |
| TZ 24V HD VCI | BT Classic (SPP) | | | |
| NirixX Link Pod | BLE 5.2 | | | |

### 5.2 `com.nirixx.app.vci` — a genuine stack, not a mock seam
```
 UI screens (AddDevice / VciCatalog / diagnostics …)
        │
   VciManager ── scan(): real BT discovery (bonded + ACTION_FOUND) merged with sim pool
        │          connect(): picks transport, falls back to sim transparently
        ▼
 ┌─────────────┬──────────────┬─────────────┐
 │ VciTransport│  interface   │ (states,    │
 │             │              │  byte pump) │
 └──────┬──────┴──────┬───────┴──────┬──────┘
        │             │              │
 BluetoothSpp    BleTransport    SimTransport
 Transport       (GATT UART      (scripted UDS
 (real RFCOMM    scaffold: MTU   responses —
 socket I/O)     247, CCC,       every screen
                 per-VCI UUIDs)  works offline)
```
The swap from simulation to live hardware is a one-line decision in `VciManager.connect()` —
the exact seam where a production UDS session layer (0x10/0x22/0x27/0x31/0x34–0x37) plugs in.

---

## 6. Artwork pipeline (all original, zero copied assets)

- **15 AI-rendered masters** (logo, hero bike, dongle, ECU, banner, 9 VCI renders, ABS module)
  ≈ 28 MB of source art, generated for NirixX with product-render prompts (no logos/text).
- **PIL slot-filling** (`nirixx_art.py`, `nirixx_art2.py`, not committed): crops, mirrors,
  hue-shifts, vignettes and teal grades turn masters into ~30 final drawables —
  9 VCI catalog renders, ELM-BLE variant, per-family flash module art (`mod_abs`, `mod_bcm`,
  `mod_cluster`, `mod_fi`, `mod_isg`, `mod_keyfob`), tutorial/home/update/report banners.
- **Adaptive icon**: N-bolt silhouette auto-derived from the master logo into a teal
  foreground glyph + indigo gradient background (`mipmap-anydpi-v26` + `xxxhdpi` fallback).
- Report banners reused across Reports/VHR/Diagnostic-Report with flipped/graded variants.

---

## 7. Modern-Android readiness (v1.2.0)

| Area | Handling |
|---|---|
| Android 12+ Bluetooth | `BLUETOOTH_SCAN` (`neverForLocation`) + `BLUETOOTH_CONNECT` at runtime via `Perms`; sim fallback when denied; API 29–30 gets legacy `ACCESS_FINE_LOCATION` |
| Android 13+ notifications | `POST_NOTIFICATIONS` requested once at first Home launch |
| Android 14+ FGS | `ClientService` typed `dataSync` + `FOREGROUND_SERVICE_DATA_SYNC` (no runtime prerequisites — cannot crash a fresh install), typed `startForeground()` with fallbacks on API 29+ |
| Manifest hygiene | explicit `exported` on every component, immutable `PendingIntent`, `RECEIVER_EXPORTED` on API 33+, `enableOnBackInvokedCallback` (predictive back), storage perms capped with `maxSdkVersion` |
| Display | adaptive launcher icon, `shortEdges` display-cutout, themed status/nav bars |
| Install surface | BT / BLE / Wi-Fi / camera all `required="false"` → installs on any phone or tablet; minSdk 24 ≈ 99% field coverage; universal ABI APK |

---

## 8. Permission UX & System Self-Check (v1.3.x)

**Pairing flow** — `AddDeviceActivity`
1. Sim pool renders instantly (screen is never dead).
2. If nearby-device access is missing → rationale dialog ("used only to discover diagnostic
   hardware — never your location") with **Allow & Scan** / **Continue in demo mode**.
3. Grant → `onRequestPermissionsResult` → toast + **automatic live rescan**.
4. Deny → stays in demo mode with an explanatory status line; rescan re-offers the rationale.

**System Self-Check** (`SystemCheckActivity`, Home tile)
- Live device-scored checklist with bold pass counter, re-scored every `onResume`:
  API-34 target · Bluetooth hardware (N/A-aware) · Bluetooth radio on (FIX → enable prompt) ·
  nearby-devices permission / pre-12 location (FIX → request) · notifications
  (FIX → runtime ask or system settings) · display-over-other-apps (FIX → settings) ·
  install unknown apps for self-update (FIX → settings).
- Amber "ACTION" rows flip to green "PASS" the moment the user returns from Settings.

---

## 9. Hermetic build pipeline

One command, no Gradle, no network:

```bash
bash build.sh    # → NirixX.apk (signed v2+v3), ~95 s
```

| Step | Tool | Job |
|---|---|---|
| 1 | `aapt2 compile` | resource table from `app/res` |
| 2 | `aapt2 link` | link vs API-34 `android.jar`, manifest, assets, generate `R.java` |
| 3 | ECJ (`-1.8`) | compile `R.java` + 63 framework-only Java sources |
| 4 | `dx` (built from AOSP dalvik source) | classes → `classes.dex` |
| 5 | zip packaging | inject dex into the unsigned APK |
| 6 | `keytool` + `apksigner` | NirixX keystore (git-ignored), **v2+v3** signature |

Verified after every build with `apksigner verify --verbose` and an androguard parse
(package, label, sdk window, component counts, adaptive-icon presence).

## 10. Repository layout

```
NirixX/
├── NirixX.apk                  # deliverable (signed, v2+v3)
├── NirixX-Probe.apk            # 255 KB minimal same-pipeline probe (device-block experiment)
├── VERIFICATION.md             # generated proof: 21/21 checks, all 49 screens verified
├── build.sh                    # hermetic pipeline (steps above)
├── manifest/AndroidManifest.xml
├── tools/
│   ├── zipalign.py             # raw-zip 4-byte alignment of STORED entries
│   └── verify_apk.py           # full static verification suite (exit 0 = shippable)
├── app/
│   ├── assets/flash_variant.json    # repo-supplied flash-variant reference data
│   ├── res/                         # layouts, values, 77 drawables (all original art)
│   └── src/com/nirixx/app/          # 63 Java files, framework-only
│        ├── Ui.java / BaseActivity.java / Session.java / Perms.java
│        ├── core/                   # v1.5.0 real stack (see §2): uds/ vin/ vci/ diag/ role/
│        ├── vci/                    # VCI model/manager (device naming, last-live registry)
│        └── … 49 activities + 4 services
└── README.md (this file)
```

## 11. Honest limitations

- No emulator/device exists in this build environment (no KVM, and Google image servers are
  unreachable): everything is **statically verified** — since v1.3.4 by the 21/21 suite in
  `VERIFICATION.md` (signature, DEX parse, per-screen id resolution, reachability, Android
  12+ checklist). Runtime behavior is best validated on a real Android 13/14 phone; the
  built-in crash reporter turns any device-only crash into a paste-able trace on next launch.
- UDS is **real** when a VCI is paired (§2): session, VIN, DTCs, writes over ISO-TP. The
  simulated path remains only as an explicitly-badged *training mode* when no link is live.
  Vendor-VCI SDKs (Kvaser/TechPro), the OEM seed-key algorithm, ODX packs, campaign binaries
  and the DMS backend are third-party halves that cannot ship here — each is behind an
  implemented interface and listed in `MISSING_DEPENDENCIES.md`.
- Image-generation quota shaped Phase 4: several module arts are PIL-recomposed from masters
  rather than wholly new renders (visually distinct, same quality bar).

## 12. Roadmap hooks

- ~~UDS session layer~~ **DONE in v1.5.0** — full ISO-TP + UDS client in `core/uds` (see §2).
- Real PDF export (embedded writer) for VHR/diagnostic reports.
- VCI detail pages with per-model spec sheets; OTA delta updates in the stub self-update flow.

---

### Provenance & licensing

NirixX's code, layout, strings, and artwork were created from scratch for this project. The
reference application that informed the PRD remains proprietary to its owner; none of its
binaries, artwork, logos or brand assets are redistributed in this module. Demo data (vehicle
models, VIN formats, supplier names, `flash_variant.json`) is factual/interoperability
information supplied with this repository. Install and evaluate the APK at your own
discretion; it performs no real vehicle writes.
