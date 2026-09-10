# 13 — IUPR Primary / Secondary Specification

## 1. Screens (structural evidence) [SRC]
- `iupr_test/IUPRTestPrimaryActivity` (3 inner classes — list/logic/dialog)
- `iupr_test/IUPRTestSecondaryActivity` (distinct secondary flow)
- `iupr_test/IUPRHistoryActivity` (persisted results)

## 2. Wire evidence (mode 09 usage) [LOG both]
| Request | Bus | Response | Reading |
|---|---|---|---|
| `09 02` | 7DF | `49 02 01 <VIN ASCII>` | VIN (17 B) — cross-check vs UDS F190 |
| `09 04` | 7DF | `49 04 01 "N597IBS6B1A3a120"` | CALID (EMS SW id family) |
| `09 06` | 7DF | (retried 3× on log1 → `7F0911`) | CVN — unsupported on older EMS |
| `09 08` | — | 9 request frames present across logs | **IPT = IUPR counters** |
| mode 09 on `7E0` (physical) | log1 | `7F 09 11` ×31 | mode 09 is functional-broadcast only on these ECUs |

⇒ IUPR data = **SAE J1979 mode 09, infotype 0x08 (In-use Performance Tracking)** on `7DF`;
Primary/Secondary split = the screen-level grouping of monitor counters (standard: Primary =
comprehensive/continuous monitors buckets; Secondary = specific component monitors per OEM
grouping). Exact bucket mapping for TVS monitors: **UNKNOWN — Requires Validation** (needs pack).
Calculation per J1979: `ratio = numerator / denominator` per monitor; denominator increments w/
driving-cycle conditions; thresholds for "healthy" display are OEM-defined → UNKNOWN.

## 3. UI behavior
- Entry from diagnostic function set; Primary & Secondary are separate screens; results can be
  **stored to History** (per-vehicle). [SRC class set]
- Refresh behavior: on-demand (each visit re-queries), no continuous polling seen (no repeated
  0908 bursts inside short windows). [LOG][INFERENCE]
- Display: monitor name + numerator/denominator or ratio + status coloring. [INFERENCE from
  J1979 data shape + app color language]

## 4. ELM-style fallback (NirixX)
NirixX `IuprTest` executes mode-09 IPT reads through the real transport chain with NRC-11
(unsupported) surfaces exactly like the reference does on older EMS (honest "not supported"
state). Secondary screen + history persistence = gap (single-screen today) — tracked in
18_implementation_matrix.md.

## 5. Logging & reports
IUPR reads land in session logs as normal RX/TX lines; History screen = local persistence;
VHR does **not** include IUPR (absent from PDF). [PDF][LOG]
