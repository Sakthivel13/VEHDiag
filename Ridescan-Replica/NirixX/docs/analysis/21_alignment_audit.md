# 21 — NirixX ↔ Reference Alignment Audit (v1.6.2, build 13)

Full-application audit performed 2026-08-23 against the evidence base in this folder
(01–20). Method: for every documented reference behavior, the NirixX **source** was
inspected at the implementing symbol; anything not provable in code was opened as a gap
and either fixed in build 13 (marked **[FIXED 13]**) or remains open (**[OPEN]**).

Verdict scale: ✅ aligned · ◐ partial (documents the delta) · ❌ was missing/misaligned.

## A. Global chrome & session discipline
| Ref behavior (evidence) | NirixX before | Status now |
|---|---|---|
| Session id `<vciSerial><ddMMyyyyHHmmss>` [XREF] | `Session.java:58/84` exact format | ✅ |
| Fallback VCI serial was hardcoded `"504856"` (the *reference's* unit, seen in video) | dishonest placeholder | ✅ **[FIXED 13]** derived from adapter name / device build (`TransportSettings.deriveSerial`) |
| Footer: session chip · `V x.y.z` · connectivity icon [VIDEO/IMG] | `BaseActivity` + `activity_screen.xml` footer | ✅ |
| Breadcrumbs `Home ≫ Model ≫ ECU ≫ Screen` [IMG] | `Ui.crumbs` on deep screens | ✅ |
| ECU chip + green dot in app bar [IMG] | `BaseActivity.chipEcu/dotEcu` | ✅ |
| Busy modal / red-green result dialogs / red validation bar [VIDEO] | dialogs existed; red inline banner added | ✅ **[FIXED 13]** `Ui.errorBar` |

## B. Vehicle communication (the deepest deltas found)
| Ref behavior (evidence) | NirixX before | Status now |
|---|---|---|
| Per-ECU CAN addresses per model: EMS 7E0/7E8 · ABS 7E1/7E9 · ICU 7F0/7F1(+1) [LOG] | ids stored in DB row + Session, **but the live link never re-pointed** — all traffic stayed on the connect-time address | ✅ **[FIXED 13]** `ElmCan.setAddress` + `DiagEngine.readdress` + `DiagOps.retuneToSessionEcu` (queued on the bus thread); auto-readdress on VIN-identify (`SessionRefresher`) and on ECU pick |
| OBD-II mode 01/09 on **7DF functional** lane (log proves 7E0-physical 09 → `7F0911`) [LOG] | went to the physical ECU header | ✅ **[FIXED 13]** `DiagOps.tracedFunctional` (7DF/7E8, restore-physical in `finally`); used by `obdPid` + `mode09` |
| Tester-present `3E 00 → 7E 00` every ~3.1 s on the held ECU while idle [LOG] | `UdsClient.testerPresent` existed, **no caller** | ✅ **[FIXED 13]** `DiagOps.startKeepAlive`: 1 s ticker → TP task on the single bus executor; silent while ops stream; NRC-continue (mirrors `7F3E11` tolerance); starts after connect & ECU pick |
| Init chain 1001→(1003 fallback)→22F190 w/ RCRP; P2 50 ms / P2* 5 s [LOG] | `openSession` + `UdsClient` RCRP wait loop | ✅ (unchanged) |
| ISO-TP reassembled-payload logging (logical, not raw frames) [LOG] | `UdsLog` logs logical payloads `TX/RX id -> hex` | ✅ |

## C. Diagnostics features
| Ref behavior (evidence) | NirixX before | Status now |
|---|---|---|
| Read DTCs 19 02 FF + RCRP + Active/Stored chips; auto re-read after 14 FF FF FF [LOG/IMG] | implemented | ✅ |
| DTC filter dropdown **All** (+Active/History) [IMG 105007386] | ❌ missing | ✅ **[FIXED 13]** dropdown, status-byte driven, empty-set card |
| DTC dedupe of repeated entries (EMS reported duplicates) [LOG2] | renders unique key rows via `dtc` input upsert; display list = raw frame order | ◐ acceptable: shows what the ECU sent (honest), filter covers views |
| ECU-Diagnosis rail: **Faults Codes Found !** · Battery Voltage live · Updates [IMG 105128019] | Battery + App-Version tiles only | ✅ **[FIXED 13]** Faults tile from the session's last real scan ("—" until a scan runs — never faked) |
| "Please contact TVS for ECU related flashing" per-ECU restriction [IMG] | policy flag exists in engine layer, no rail note | ◐ **[OPEN]** cosmetic rail note; tracked below |
| Live parameters: sequential per-DID polling, genuine values, definition-pending rows [LOG] | implemented | ✅ |
| Write DID: 10 03 → 27 01 seed shown → 2E; engineer-gated [LOG2 pre-chain] | implemented | ✅ |
| Routine Control: secured `31 01 <RID>`; Gear-Learning bridge [LOG2] | implemented | ✅ |
| IO Control: secured 2F; VHR auto-sequence w/ results into report [LOG2][VIDEO] | implemented | ✅ |
| IUPR screens Primary/Secondary/History reading **mode 09 $08 IPT** [SRC][LOG 0908] | read CALID(0904)+CVN(0906) only — labeled IUPR without IPT | ✅ **[FIXED 13]** adds live 09 08 read + `Obd.decodeIpt` (M1 n/d pairs, bus order, monitor-map honestly pending) |
| Manual Diagnostic [SRC] | catalogue-executed real ops | ✅ |

## D. Vehicle Health Report
| Ref behavior (evidence) | NirixX before | Status now |
|---|---|---|
| 5 tabs DEALER/DIAGNOSTIC/IO CONTROL/PHYSICAL EVALUATION/SUMMARY [VIDEO][SRC] | exact 5-tab wizard | ✅ |
| Physical items: model-specific ranges (18–23 mm/25/32 PSI; 30–40 mm; 1650–1700 ml) + per-item photo + Customer image [VIDEO][IMG][PDF] | same items/ranges from `vhrItems`; SAF photo import | ✅ |
| **Mandatory value+photo per row; red bar "Please fill & upload picture of all the fields"** [VIDEO f31] | ❌ tab advanced freely | ✅ **[FIXED 13]** `physicalComplete()` gate on NEXT + `Ui.errorBar` with the reference copy |
| Verdict card (Passed / attention state) + Date [VIDEO][PDF] | "Passed" / "Attention Needed" + date + disclaimer | ✅ |
| PDF `<Variant>_<VIN>_VHR.pdf`, OPEN/VIEW + share [VIDEO][PDF] | PdfReport + DocsProvider share/open | ✅ |
| DEALER tab: Customer Mobile No (Optional) [VIDEO f04] | ❌ not a field | ◐ **[OPEN]** (add when upload channel carries it to DMS) |
| Auto-upload + "PDF Uploaded Successfully" [VIDEO f37] | backendless build | 🌐 **[OPEN]** DMS dependency (MISSING_DEPENDENCIES) |
| Inline camera capture inside VHR [VIDEO f19–f25] | SAF import instead | 🎨 **[OPEN]** Camera2/MVC capture queued |

## E. Flashing / security / app-level
| Ref behavior (evidence) | NirixX | Status |
|---|---|---|
| Variant→package catalogue (22 variants, descriptions) [JSON] | same data imported, data-driven pickers | ✅ |
| Secured chain before flash; progress; result dialogs [IMG/SRC strings] | `FlashRunner` 10 03 → 31 01 FF00 → 34/36/37 → 11 01 | ✅ (wire superset unverifiable — disclosed) |
| Role gating Engineer-only flash/DID-write/VCI-fw [XREF] | Home filter + per-screen guards + audit gate E | ✅ |
| VCI firmware screen + battery precheck via real volts [SRC/INFERENCE] | FirmwareUpdate + BatteryAssess on ATRV | ✅ |
| Notifications / app-update descriptions with real state | honest operator panels | ✅ (backend rows 🌐 open) |

## F. Media, logs, recording
| Ref behavior (evidence) | NirixX before | Status now |
|---|---|---|
| Session log file `<sessionId><VIN>.txt`, full header, TX/RX lines [LOG] | `UdsLog` exact shape | ✅ (+3E lines now appear, reference-style) |
| Intro / training **videos** (VideoPlayer + ExoPlayer) [SRC] | ❌ no screen at all | ✅ **[FIXED 13]** `IntroVideosActivity` (import .mp4 via SAF → private shelf → framework playback), Home tile + "videos" module for all roles |
| Screen recording (HBRecorder bubble) [VIDEO][SRC] | ⚠ indicator service only, and its copy **implied real recording** | ◐ **[FIXED 13]** honest "Session Capture" indicator + label that no video is recorded; true MediaProjection capture **[OPEN]** (MISSING_DEPENDENCIES) |
| Log/File viewers, live-data CSV recording | implemented | ✅ |

## G. Gates after build 13 (all green)
- `build.sh` → OK, v1.6.2 (13), 50 activities.
- `tests/run_tests.sh` → **9/9 suites PASS** (new: IUPR IPT decode incl. count-byte/junk rejection).
- `tools/verify_apk.py` → **21/21, 0 errors / 0 warnings** (50 activities reachable).
- `tools/audit_links.py` → **0 errors / 0 warnings** (new edges & module mapped).

## H. Open alignment items (prioritized, all dependency-honest)
1. **P1** DMS backend: OTP/SSO, PDF+log upload captions ("PDF Uploaded Successfully"), notifications, app-update channel. 🌐
2. **P1** OEM definition packs: DID names/scales, DTC texts, RID/IO catalogues, IUPR monitor map. 📦
3. **P1** Supplier flash wire flows + campaign binaries (34/36/37 details unobserved). 📦🔌
4. **P2** MediaProjection screen-capture (consent + VirtualDisplay + MediaRecorder) to replace the indicator. 🎨
5. **P2** Camera2 capture inside VHR physical tab (reference inline camera). 🎨
6. **P2** VHR DEALER "Customer Mobile No (Optional)" field + DMS payload hook. 🌐
7. **P3** ECU-Diagnosis "contact OEM for flashing" rail note per ECU flag. 🎨
8. **P3** "New Updates Available" rail tile bound to a real update channel. 🌐
9. **P3** GTS viewer shell (content pack dependency). 📦
