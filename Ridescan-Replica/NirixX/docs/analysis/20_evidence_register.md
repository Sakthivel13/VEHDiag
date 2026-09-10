# 20 — Evidence Register (claim → proof, brief §26)

Every structural claim in docs 01–17 traces here. Sources:
**L1** = log `50280823012026031513MD625AF99T1A25267.txt`, **L2** = log
`50280829012026105706MD638AN2100000000.txt`, **V** = video VID-20260317-WA0039 (f## frames),
**P** = VHR PDF, **I** = photos (burst `IMG_20260120_hhmmss…`, `IMG-20260317/0114-WA####`),
**D** = classes-dex2jar.jar, **R** = resources.txt, **J** = flash_variant.json, **M** = binary manifest.

## Identity & packaging
| Claim | Source | Note |
|---|---|---|
| App id `com.ridescantp.mahle.ridescantp`, versions 2.2.5 (190) / V 2.3.0 | L1/L2 headers; V footers | |
| Publisher stack Mahle/TechPro line; "Powered by MAHLE" | V f01 | |
| Device SM-T225 (tablet), Android 14/SDK34 | L1/L2 headers, I photos | |
| Libraries: HBRecorder, iText, Gson, Tink, ExoPlayer, ZXing, AndroidX, SPP serial lib | D package tree; R strings | |
| Backend domain "DMS" | L1/L2 headers | API surface UNKNOWN |
| GPS stamped at session start | L1/L2 `Latlong` | |

## Sessions & VCI
| Claim | Source | Note |
|---|---|---|
| `sessionId=<vciSerial><ddMMyyyy><HHmmss>` | L1/L2 names+headers; I footer `50280820012026102748`; V footer `50485617032026041703` + dropdown `TechPRO_504856` | XREF ×4 |
| Log file name `<sessionId><VIN>.txt` | L1/L2 | |
| Connectivity BT classic SPP for 502808 | L1 line `[CONNECTIVITY_TYPE]`; D btlibrary | |
| Wi-Fi for 504856; USB option exists | V f01 + status glyph | Wi-Fi/USB wire format UNKNOWN |
| VCI fw 1.07 in header | L1/L2 | |
| 0-series EOL Jan-2026; 5-skip VCI update | R strings | |

## Protocol
| Claim | Source |
|---|---|
| Init `7E0:10 01 → 50 01 00 32 01 F4` then `22 F1 90 → 7F 22 78 → 62 F1 90 <VIN>` | L1 15:15:16, L2 10:57:11 (byte-identical) |
| OBD VIN `7DF:09 02 → 49 02 01 <VIN>`; CALID `09 04 → "N597IBS6B1A3a120"` | L2 11:01:20 |
| Idle keep-alive `3E 00→7E 00` @ ~3.09 s, multi-ECU fan-out | L1/L2 passim |
| EMS=7E0/7E8; ABS=7E1/7E9 (L2), 7E5/7ED (L1); cluster=7F0→7F1 (L2) vs 7F0→7F8 (L1) | L1/L2 CAN-id histograms |
| RCRP (`7F xx 78`) precedes final positives (22/14/27/19/10) | L2 11:01:15, 11:06:02, 11:09:10 |
| NRC taxonomy (10/11/13/31/78; ×793 total negatives) | L1/L2 histogram (doc 05 §4) |
| Secured chain `10 03 → 27 01 (8B seed) → 27 02 (8B key, +67 02)` before 31/2F/14-class ops | L2 11:06:02–11:06:57 |
| Routine `31 01 02 11 → 71 01 02 11 01` | L2 ×2 |
| IO `2F A8 00 03 01 → 6F A8 00 03 00` | L2 11:06:57 |
| Clear `14 FF FF FF → 7F 14 78 → 54` + auto `19 02 FF` re-scan | L2 11:09:10–11:09:11 |
| DTC read `19 02 FF` only; EMS 347 B/86 entries; ABS `59 02 2F` C1200-00/U2932-00 st 2C | L2 11:01:15 / 11:10:29 |
| Status histogram 0x50×73, 0x40×3, 0x21×3, 0x04×3, 0x01×1, 0x05×2, 0x15×1 | L2 (doc 08 §2) |
| Live ~100 EMS DIDs/cycle; cluster E0xx–F2xx space | L1/L2 DID histograms (doc 06) |
| Mode 01 PIDs 0B/0F only; mode 09 on 7E0→`7F0911` (unsupported) | L1/L2 |
| IUPR = mode 09 infotype 08 (×9 frames) | L1/L2 |
| 0x2E/0x34/0x36/0x37/0x11 not on wire anywhere | L1/L2 full scan | flagged Requires Validation |

## UI/UX
| Claim | Source |
|---|---|
| Login wizard 3 tabs, fields, VCI dropdown, ADD/PAIR VCI, BT/WIFI/USB, "Powered by MAHLE" | V f01, I-0114 |
| Footer session chip + `V x.y.z` + connectivity icon on active screens | V all, I burst, 105007386 |
| App-bar: back, title, ECU chip+green dot (BABS/ICU), avatar/bell/overflow | I 105007386/105128019 |
| Breadcrumb `Home ≫ TVS APACHE RR310 Refresh ≫ BABS ≫ Read DTCs` | I 105007386 |
| ReadDTCs: All-dropdown, ⟳, red 🗑 CLEAR DTC | I 105007386 |
| ECUDiagnosis: 5 function cards; Faults badge; Battery 12.3 V card; New Updates card; Service Remainder; "Please contact TVS for ECU related flashing" | I 105128019 |
| VHR tabs DEALER/DIAGNOSTIC/IO CONTROL/PHYSICAL EVALUATION/SUMMARY | V f04–f37, I-0317 set |
| IO auto-sequence modals "Requesting… MIL Lamp/Upstream Lambda Heater" w/ "Don't close the application…" | V f07–f10 |
| Physical eval: ranges 18–23mm/25PSI/32PSI, Min-Ok-Max, 👍/👎, Customer image; mandatory-photo snackbar; inline camera preview w/ ✓/✕/↻ | V f13–f31 |
| Summary: param cards min/max green-red (Quick shift 4.99 V red @ range 2.2–2.8), verdict "Good Condition", OPEN PDF, "PDF Uploaded Successfully" | V f34–f37, I-0317 #1/#5 |
| Alt-model checklist ranges (chain 30–40, oil 1650–1700 ml, clutch 8–12) | I-0317 #3/#4 (model-adaptive) |
| Flash screens: variant/file-system chooser "Proprietary", "GET SECRET KEY" dialogs, `TVS FLASH_…` lists, green success/red failure | I burst r3–r7 (105018050 etc.) |
| OTP/PIN keypad dialogs | I burst r1–2; R strings |
| Chatbot "Welcome to RIDE Scan Chatbot!" | R strings |
| Screen-recording bubble; "Recording your screen"/"Drag down to stop…" | V all frames; R strings; D hbrecorder |

## PDF
| Claim | Source |
|---|---|
| File naming `<Variant>_<VIN>_VHR.pdf`, 2 pages, 1.4 MB, shared via WhatsApp | P + V f42 |
| Sections & exact table rows (EMS Vehicle Data 6 params w/ Min/Max/Value; IO results; ABS row; ICU/ISG "Active"; physical rows; "Passed" + date) | P text layer (doc 15 §2) |

## Flashing catalogue
| Claim | Source |
|---|---|
| 22 variants, 60 packages, ecu types EMS/EMS-OBDII/KEMS/ICU/SEMS-OBDII-B, norm BSVI, hardware-differentiator descriptions | J (doc 14 §1) |
| 15 supplier flash flows incl. n597/u732/u577 cluster, babs2, sedemac/mikuni/kems/conti/pricol/keihin/keyless | D package tree |
| CALID "N597…" ↔ n597_cluster_flashing naming consistency | L2 + D (XREF) |

## Formally UNKNOWN / Requires Validation (never silently assumed)
1. Wi-Fi/USB VCI wire protocol & ports — [V/I show existence only].
2. 0x2E write, flashing 3x wire grammar, ECUReset during flash — not captured.
3. OEM seed→key algorithm — dialog proves existence [I], math absent.
4. DID/DTC/RID/IO display dictionaries & scaling formulas — pack dependency.
5. GTS interactive behavior beyond a viewer; GTS content source.
6. Freeze frame — feature absent in observed builds, by evidence.
7. Server token TTL / session expiry; SSO trigger; push channel; upload retry policy.
8. DMS API surface (auth, OTP, uploads, campaign eligibility, file hosting).
9. Verdict weighting details beyond in-range/all-Ok conjunction.
10. Role-field storage on backend; a few ⚠ cells in 03_roles.md permission matrix.
