# 07 — DID Read & Write Specification

## 1. Read DID (ReadDataByIdentifier, 0x22) — fully evidenced
- Entry paths: Live parameters grid (implicit), ECU identity (F1xx), VHR diagnostic tab implicit
  reads, IUPR/battery/readiness flows. [LOG][IMG][VIDEO]
- Wire shape: `TX <ecu> 22 <did2B>` → `RX 62 <did> <payload>`; RCRP (`7F2278`) wait applies;
  hard NRCs logged: `10/11/31`. [LOG both]
- Identity DIDs proven: `F190` VIN (17 B ASCII, multi-frame), `F182` SW part (16 B ASCII
  "N360GBS6B1A3b300"), `F1F4` 4 B binary; `F191` **rejected** (`7F2210`) on EMS log1. [LOG]
- Raw payload sizes observed: 1 B (flags), 2 B (measurements), 4 B (F1F4), 16–17 B (identity ASCII).
- Access control: reads work in **default session** (`10 01`), no security. [LOG]
- UI: value + unit formatting per decode table; raw view in DataWatcher/manual screens
  [INFERENCE — no raw-view media].

## 2. Write DID (WriteDataByIdentifier, 0x2E) — UI evidenced, wire UNKNOWN
Evidence chain [LOG2 11:06:02–11:06:36]:
```
TX 7E0 10 03        RX 7E8 50 03 00 32 01 F4        # extended session REQUIRED
TX 7E0 27 01        RX 7E8 67 01 <8B seed>          # SecurityAccess level 01, seed 8 bytes
TX 7E0 27 02 <8B>   RX 7E8 7F 27 78 → 67 02         # app-computed key accepted
   (then 31 01 02 11 / 2F A8 00 03 01 — see routine/IO docs)
```
- The **secret-key dialogs** photographed on flash screens ("GET SECRET KEY"-style header + input
  + Submit, 4 variants in burst) corroborate a seed-key UI for secured operations. [IMG r6]
- **The actual `2E` frame never appears in either log** — writes require SecurityAccess and are
  exercised rarely in the field; write-DID list, byte ordering & allowed ranges are
  **UNKNOWN / Requires Validation** (ODX pack dependency).
- `WriteDataActivity` is the write UI; role-gated (engineer). [SRC][03_roles.md]
- Confirmation requirements: extended session + SecurityAccess are the de-facto gating;
  additional UI confirmation for writes: [INFERENCE: confirm dialog per destructive-op UX policy].
- Failure surface: NRCs `22 78`(wait), `13`(length), `31`(range), `33`(security access denied),
  `35/36`(bad key/attempts), `72`(general programming failure) — 35/36/33 not observed, standard
  taxonomy assumed. [INFERENCE]

## 3. Read vs Write — operational contrast
| Aspect | Read (0x22) | Write (0x2E) |
|---|---|---|
| Session | default | **extended (10 03)** [LOG2] |
| Security | none | **27 01/02 seed-key, 8-byte** [LOG2] |
| Role | both | Engineer (⚠ table 03) |
| Repetition | continuous poll | single-shot |
| Fail NRCs | 10/11/31 | 13/31/33/35/36/72 |
| Audit | logged | logged + (recommend) explicit confirm |

## 4. Logging
Every request/response line logged with ms timestamps; writes (when performed) land in the same
session log between the `27` pair — none present in captures. [LOG]
