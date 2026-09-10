# 08 — DTC (Read / Clear) Specification

## 1. Read workflow — fully evidenced [LOG][IMG]
```
ReadDTCsActivity (per selected ECU)
TX <ecu> 19 02 FF            # reportDTCByStatusMask, mask 0xFF — the ONLY subfunction observed
RX 7F 19 78                  # RCRP (EMS needs ~600 ms)
RX 59 02 FF <4B × n>         # statusAvailabilityMask FF, entries = 3B DTC + 1B status
```
- Filter UI: dropdown **"All"** (with at least one more option — dropdown arrow present) +
  refresh ⟳ + red **CLEAR DTC** trash action; breadcrumb `Home ≫ Model ≫ ECU ≫ Read DTCs`. [IMG 105007386]
- No other 19-subfunctions on wire: no snapshot (0x03), no extended data (0x06), no count (0x01). [LOG both]

## 2. Real decode examples
EMS (`7E0`, vehicle MD638…, 347 B → **86 entries**, 56 unique roots) [LOG2 11:01:15]:
- Dominant: `U0121-00`, `U0415-00` (lost-communication family) repeated across slots.
- Status histogram: `0x50` ×73 (notCompleted bits → **history**), `0x40`×3, `0x21`×3, `0x04`×3,
  `0x01`×1 (**active**), `0x05`×2, `0x15`×1.
- **Duplicates occur** in the raw table — the app shows the list as-is or dedupes: exact
  presentation rule Requires Validation (photo shows empty screen only). [INFERENCE: dedupe by root+status]
ABS (`7E1`, same vehicle): `59 02 2F` + `C1200-00` st `2C`, `U2932-00` st `2C`
(pending+confirmed+failedSinceClear). [LOG2 11:10:29]
Cluster (`7F0`, log1): `19 02 FF → 7F 19 11` (unsupported) → UI marks that ECU "no DTC function".

## 3. Status→UI mapping (ISO 14229 bits; corroborated by Active/History language in app flows) [XREF]
| bit | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| meaning | testFailed | failedThisCycle | pending | confirmed | notCompletedSinceClear | failedSinceClear | notCompletedThisCycle | warningIndicator |
UI classes: **Active** (bit0/3 set) vs **History** (bit4/6 pattern `0x50`) — matches dropdown
filter hypothesis. [INFERENCE from histogram + filter UI]

## 4. Clear workflow — fully evidenced [LOG2 11:09:10.787]
```
TX 7E0 14 FF FF FF           # clear all groups, EMS
RX 7F 14 78 → RX 54          # RCRP then positive (≈450 ms total)
TX 7E0 19 02 FF              # immediate automatic RE-SCAN (765 ms later)
```
- UI exposes **CLEAR DTC** as red top-right action; confirmation dialog before send
  (destructive-op policy) [IMG + INFERENCE for dialog copy].
- Clear is issued per-ECU (physical address), not broadcast. [LOG]
- Post-clear: automatic fresh `19 02 FF` — list reflects surviving/permanent faults. [LOG]

## 5. DTC in downstream features
- **ECU Diagnosis hub**: red badge "Faults Codes Found !" when active/history DTCs exist. [IMG 105128019]
- **VHR**: DTC presence feeds ECU "Active" section + verdict (PDF shows "Active" per ECU line). [PDF][XREF]
- **GTS**: DTC row → troubleshooting content link (GTSViewActivity). [SRC][INFERENCE path]
- **Descriptions**: app resolves code→text internally; decode dictionary not in logs
  (**UNKNOWN source — ODX/pack dependency**); UI shows text because burst list photos show
  prose rows. [IMG r5 lists]

## 6. Severity / freeze-frame linkage
Severity column/sort not observed; freeze-frame pointer absent (see 10_freeze_frame.md —
service never requested in captures). Occurrence counters not exposed (would be 19 06 — unused).

## 7. NirixX parity
Read (19 02 FF, RCRP-wait, per-ECU), clear (14 FF FF FF + auto-rescan), status-bit Active/History
classification, dedupe, faults badge, NRC dialogs — all implemented (`core/uds/UdsClient.parseDtcResponse`)
and unit-tested with the captured EMS payload (86-entry frame replayed in TestCore).
