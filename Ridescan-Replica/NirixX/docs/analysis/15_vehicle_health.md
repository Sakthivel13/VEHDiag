# 15 — Vehicle Health Diagnostics & Report (VHR)

The flagship consumer-visible workflow. Evidence base is complete: full video run, the exact
generated PDF, two phone screenshot sets, package structure. [VIDEO][PDF][IMG][SRC]

## 1. Structure — 5-tab wizard [VIDEO f04→f37][SRC ui/vehicle_health_report/* + physical_evaluation + report_summary_new]
`VhrActivity` hosts tabs: **DEALER → DIAGNOSTIC → IO CONTROL → PHYSICAL EVALUATION → SUMMARY**,
implemented as VhrDealerInformationActivity / VhrDiagnosticReportActivity / VhrIOControlActivity /
PhysicalEvaluationActivity / NewReportSummaryActivity. [SRC]

### Tab 1 — DEALER [VIDEO f04]
VIN banner (`MD637AN11R2D01275`); pre-filled Dealer Name / Email / Code; optional **Customer
Mobile No (Optional)**; NEXT (validation on required set).

### Tab 2 — DIAGNOSTIC [IMG 20260317 #2/#5: header "EMS - LIVE DATA"]
Auto live-read of the bounded VHR parameter set per ECU (see 06_live_parameters.md table),
values with min–max, green/red; NEXT. (Frame f05-f06 of video are this tab mid-run behind
IO modals.) Sequential per-ECU; ECU header switches as it scans. [INFERENCE for per-ECU loop]

### Tab 3 — IO CONTROL [VIDEO f07–f10][IMG 20260317 #2]
Per-ECU accordion (EMS; #BABS) with toggle "Ok" switches + **auto-sequenced actuations**:
each fires a modal "Requesting… <name>" (orange header, circular-arrow glyph, progress bar,
note "Don't close the application, While complete the diagnostics."). Observed sequence on EMS:
MIL Lamp → Fuel Pump Relay → Actuate Starter Relay → Upstream Lambda Heater; ABS: Start Wheel
Speed Test. Results recorded per actuation (Ok). [VIDEO][PDF]

### Tab 4 — PHYSICAL EVALUATION [VIDEO f13–f31][IMG 20260317 #3/#4]
Model-adaptive checklist; **every item = photo + value**. Input kinds observed:
| Item (Ronin run) | Input | Range shown | Value entered |
|---|---|---|---|
| Drive chain slackness | number, mm | 18–23 | 22 |
| Front tyre pressure | number, PSI | 25–25 | 25 |
| Rear tyre pressure | number, PSI | 32–32 | 32 |
| Dip stick oil level | radio Min/Ok/Max | — | (photo) |
| Clutch play / Clutch lever free play | 👍Ok / 👎Not Ok or mm number | 8–12 | (photo)/12 |
| **Customer image** | photo | — | — |
| (alt model run) Engine oil level and oil condition | number, ml | 1650–1700 | 1700 |
Validation: NEXT with anything missing → red snackbar **"Please fill & upload picture of all
the fields"** [VIDEO f31]. Photos captured **in-app** (full-screen camera preview slides in
from the right; confirm ✓ / retake ✕ / rotate ↻). [VIDEO f19–f25]

### Tab 5 — SUMMARY [VIDEO f34–f37][IMG #1/#5]
- Per-ECU cards: "Engine Management System" parameter list — name, live value (green/red),
  `Min: x  Max: y`; "IO Control" section with ECU dropdown.
- **Verdict card**: green ✓ "Good Condition" (failed case text unknown — PDF shows "Passed";
  hypothesized "Attention Required" — Requires Validation).
- `OPEN PDF` button; caption **"PDF Uploaded Successfully"** (auto-upload to DMS).
- OPEN PDF → system chooser (PDF viewers, Drive, WhatsApp share). [VIDEO f37–f42]

## 2. PDF artifact (exact layout) [PDF]
File `TVS Ronin_MD637AN11R2D01275_VHR.pdf` — naming **`<Variant>_<VIN>_VHR.pdf`**, 2 pages,
1.4 MB, cover art "TVS MOTOSHIELD VEHICLE HEALTH REPORT" w/ model image.
- p1: `DEALER & VEHICLE INFO` (Dealer Name/Code/Email, Variant, VIN) → `DIAGNOSTIC REPORT`:
  `I. Engine Management System — Active`; **Vehicle Data** table (Name | Min | Max | Value + Status):
  Battery Voltage 10.5/14.5/13.8 V; Engine Temperature 65/110/65.66 °C; Throttle Position Sensor
  0/100/0.0; Intake Air Pressure Sensor 3/115/3.4 kpa; Intake Air Temperature −40/130/43.6 °C;
  Engine Speed 1000/2500/1643.0 rpm. `Input/Output Control Result`: MIL Lamp Ok, Fuel Pump Relay
  Ok, Actuate Starter Relay Ok, Upstream Lambda Heater Ok. `II. Anti-lock Braking System — Active`,
  `1. Start Wheel Speed Test Ok`; `III. Instrument Cluster — Active`; `IV. Integrated Starter
  Cluster — Active` (ISG).
- p2: `PHYSICAL EVALUATION` table (item | range | value/status): Drive chain slackness 18-23→22;
  Front tyre 25; Rear tyre 32; Dip stick oil level Ok; Clutch play Ok. `REPORT SUMMARY`:
  `Vehicle Health Condition   Date: 2026-03-17   Passed`.
- Item numbering/labels match on-screen checklist exactly. [XREF]

## 3. Health-status computation (how "Passed" is derived) [PDF][IMG][INFERENCE]
Inputs: per-param in-range check (min≤value≤max), per-ECU DTC/alive status ("Active"), IO
actuation results (all Ok), physical checklist values in range. Verdict = conjunction: all ECUs
active ∧ params in range ∧ IO Ok ∧ physicals in range → **Passed / "Good Condition"**; any
red param or failed actuation → non-passed state (observed RED on quick-shift 4.99 V vs 2.2–2.8
in the alt run — that run would not "Pass" [IMG]).
Exact weighting (e.g. warning vs critical buckets): **UNKNOWN / Requires Validation**.

## 4. Persistence & upload
- Generated instantly post-SUMMARY; auto-uploaded (FileUploadWorker/ClientService) with the
  success caption; shareable via standard intents. [VIDEO][SRC]
- Resilience: queued upload (WorkManager family) — retry policy UNKNOWN. [SRC][INFERENCE]

## 5. NirixX parity status
5-tab wizard, bounded live table, IO auto-sequence, physical checklist (currently SAF file
import for photos; **in-app camera capture = open dependency**, exactly matching the gap list),
verdict card, PDF-equivalent report generation + DocsProvider export; upload backend = MISSING
(DMS). Deltas: reference verdict thresholds table unknown; NirixX shows thresholds transparently
instead of guessing (honesty rule).
