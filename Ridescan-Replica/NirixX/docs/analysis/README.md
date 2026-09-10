# NirixX — Reference Application Analysis (RIDE Scan 2.0)

Clean-room, evidence-driven reverse-engineering study of the reference two-wheeler
dealer diagnostics application ("RIDE Scan 2.0", package
`com.ridescantp.mahle.ridescantp`, app versions observed **2.2.5 (190)** and **2.3.0**),
and the mapping of every validated behavior to the NirixX implementation
(`com.nirixx.app`, current build v1.6.1).

This document set is the **source of truth for "what the reference app does"** and for
NirixX's functional-parity backlog. It was produced from the repository artifacts only —
no external speculation. Anything that could not be concluded from evidence is marked
explicitly.

## Evidence legend

| Label | Meaning |
|---|---|
| **[LOG]** | Captured application log files (real on-vehicle sessions) |
| **[VIDEO]** | Reference screen recording `VID-20260317-WA0039.mp4` (frame-no. cited) |
| **[IMG]** | Reference photographs/screenshots in `Ridescan UI Reference Images/` |
| **[PDF]** | Generated Vehicle Health Report PDF artifact |
| **[SRC]** | Decompiled APK: `classes-dex2jar.jar`, binary `AndroidManifest.xml`, `resources.txt` strings |
| **[JSON]** | `flash_variant.json` flash package catalogue |
| **[XREF]** | Conclusion corroborated by ≥2 independent evidence types |
| **[INFERENCE]** | Reasoned conclusion, not directly observed — validate before relying |
| **[UNKNOWN]** | Not determinable from available evidence — **requires validation**; nothing was invented for these |

## Deliverable index (maps to the analysis brief §32)

| # | Document | Covers brief sections |
|---|---|---|
| 01 | [Functional Specification](01_functional_specification.md) | §2 lifecycle, §20 sessions, §21 profile, §22 notifications, §23 updates |
| 02 | [Screen & Navigation Map](02_screen_map.md) | §5 UI/UX screen-by-screen |
| 03 | [Roles & Permission Matrix](03_roles.md) | §4 authentication & roles |
| 04 | [VCI Connection Workflow](04_vci_connection.md) | §3 |
| 05 | [Vehicle Communication & Diagnostics Architecture](05_vehicle_communication.md) | §6 identification, §7 diagnostics kernel |
| 06 | [Live Parameter Specification](06_live_parameters.md) | §8 |
| 07 | [DID Read/Write Specification](07_did.md) | §9 |
| 08 | [DTC Specification](08_dtc.md) | §10 |
| 09 | [GTS — Guided Troubleshooting](09_gts.md) | §11 |
| 10 | [Freeze Frame Specification](10_freeze_frame.md) | §12 |
| 11 | [Routine Control Specification](11_routine_control.md) | §13 |
| 12 | [Input/Output Control Specification](12_io_control.md) | §14 |
| 13 | [IUPR Primary/Secondary Specification](13_iupr.md) | §15 |
| 14 | [ECU Flashing Workflow](14_flashing.md) | §16 |
| 15 | [Vehicle Health Diagnostics & Report](15_vehicle_health.md) | §17 |
| 16 | [Logging & Screen Recording](16_logging_recording.md) | §18, §19 |
| 17 | [Error Handling & State Machines](17_state_machines.md) | §24, §25 |
| 18 | [NirixX Implementation Matrix](18_implementation_matrix.md) | §27 (+§28–§30 pointers) |
| 19 | [Test Strategy](19_test_strategy.md) | §31 |
| 20 | [Evidence Register](20_evidence_register.md) | §26 — claim → evidence mapping |
| 21 | [Alignment Audit v1.6.2](21_alignment_audit.md) | Code-level parity check vs reference + fixes shipped in build 13 |

Related standing docs: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) (NirixX architecture,
§28), [`../../MISSING_DEPENDENCIES.md`](../../MISSING_DEPENDENCIES.md) (missing inputs),
[`../../VERIFICATION.md`](../../VERIFICATION.md) (tooling & gates).

---

## 1. Repository & reference-material inventory (brief §1)

Root artifacts (committed, read-only analysis material):

| Artifact | What it is | Role as source of truth |
|---|---|---|
| `Ridescan UI Reference Images/50280823012026031513MD625AF99T1A25267.txt` | Full diagnostic comms log, 7 960 lines, 2026-01-23 15:15→, vehicle VIN `MD625AF99T1A25267`, VCI `502808` over **Bluetooth** | **[LOG] primary protocol truth** |
| `Ridescan UI Reference Images/50280829012026105706MD638AN2100000000.txt` | Full diagnostic comms log, 5 597 lines, 2026-01-29 10:57→, VIN `MD638AN2100000000` (unprogrammed serial), same VCI | **[LOG] primary protocol truth** (includes SecurityAccess, RoutineControl, IOControl, ClearDTC) |
| `Ridescan UI Reference Images/VID-20260317-WA0039.mp4` | 4 min 12 s screen recording (382×850) of a complete **Vehicle Health Report** run, app **V 2.3.0**, VCI `TechPRO_504856` over **Wi-Fi**, dealer 10814 "NEO MOTORS" | **[VIDEO] UX truth for VHR + login** |
| `Ridescan UI Reference Images/TVS Ronin_MD637AN11R2D01275_VHR.pdf` | The exact PDF produced at the end of that video run (2 pages, 1.4 MB, shared to WhatsApp in the video) | **[PDF] report truth** |
| `Ridescan UI Reference Images/IMG_20260120_*.jpg` (89 photos) | Photographed tablet (SM-T225) walkthrough 10:29–10:55 on 2026-01-20, app **V 2.2.5**, VCI `502808` BT — login, FAQ, home grids, ECU diagnosis, Read DTCs, flashing screens, dialogs, VHR | **[IMG] screen truth (tablet UI)** |
| `Ridescan UI Reference Images/IMG-20260317-WA00*.jpg` (5) + `IMG-20260114-WA00*.jpg` (2) | Screenshots: VHR on a second vehicle (quickshifter model), login (older layout, bike hero) | **[IMG] screen truth (phone UI)** |
| `AndroidManifest.xml` | Binary AXML manifest of the reference APK | **[SRC]** package/permissions cross-check |
| `classes-dex2jar.jar` | Decompiled classes of the reference APK | **[SRC] architecture truth** (package tree, libraries, services) |
| `resources.txt` | Resource/string dump incl. UI strings and library strings | **[SRC] copy/behavior truth** for dialogs & policies |
| `flash_variant.json` | 22 flash variants → per-model package list with ECU type, norm, human description | **[JSON] flash catalogue truth** |
| `PublicSuffixDatabase.list` | Bundled Mozilla PSL (network layer dependency artifact) | context only |
| `RideScan.zip` | Reference application bundle (kept sealed; never repackaged or modified per clean-room rule) | byte source of the above |
| `RideScan_*.md` (8 files) | Our own earlier planning documents | **Not reference evidence** — superseded by this set |

### Cross-referencing rule
Artifacts were analyzed as a system, e.g.: the video footer session string
`50485617032026041703` is decoded by the log-file naming scheme
(`<vciSerial><ddMMyyyy><HHmmss>`), which itself is proven by log1 header
(`Session ID 50280823012026031513`, `[CONNECTIVITY_TYPE]: bluetooth`) matching VCI
`502808` = the BT unit photographed on 2026-01-20 (`50280820012026102748`). The VHR PDF
shared on WhatsApp at the end of the video is byte-name-identical to the committed PDF.

### Key facts established by inventory
- Devices: dealer tablet **Samsung SM-T225, Android 14 (SDK 34)**; phone-class device for 2.3.0 shots. [LOG][IMG]
- VCIs: **TechPRO** line. Serial `502808` = Bluetooth classic unit; serial `504856` = Wi-Fi unit
  (`TechPRO_504856`). Strings state 0-series VCI discontinued end-Jan-2026 → 5-series Wi-Fi units. [LOG][VIDEO][SRC]
- Backend domain: **DMS** (Dealer Management System); dealer identity captured at login; GPS
  lat/long written into every log header. [LOG]
- Dealer accounts observed: `12345` (peethala.rajiv, logs), `10814` (NEO MOTORS, video/PDF). [LOG][PDF]

## Method
1. Inventory & metadata (this file).
2. Protocol mining of both logs (request/response pairing, service/NRC histograms, timing).
3. Video frame extraction (42 frames @ 6 s) + 137-photo contact-sheet review; key frames read at full resolution.
4. PDF structure extraction (text layer).
5. Decompiled package tree + resource strings for screens, libraries, policies.
6. Synthesis into per-feature specs (01–17) with per-claim evidence labels.
7. Mapping to NirixX (18) + test strategy (19) + claim-by-claim evidence register (20).

Clean-room: the NirixX codebase implements *behaviors* documented here from observed
wire/UX evidence; no reference code, artwork, or binaries are reused. The reference APK
bundle is never modified or repackaged.
