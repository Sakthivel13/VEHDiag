# 06 — Live Parameter Specification

## 1. Data path (proven)
```
ECU DID raw bytes  --(22<did> → 62<did><bytes>)-->  app decode table
  → engineering value + unit → UI card/row (green=in-range, red=out-of-range on bounded views)
```
Acquisition = **one `22` request per DID, sequential round-robin**; no multi-DID reads
(`22 <did1><did2>`) and no periodic-scheduler services (0x2A) appear anywhere in 13.5k log
lines. [LOG both]

## 2. Observed polling cadence [LOG1 15:17–15:26 window]
- Per-request gap typically **31–100 ms** (BT SPP + CAN); a full list sweep repeats continuously.
- TesterPresent `3E00` interleaves every ~3.09 s on each held ECU without pausing polling.
- OBD-II mode 01 (`7DF 01 0B/01 0F` — MAP & IAT) polled on the side at lower frequency (60× total). [LOG1]

## 3. DID evidence tables

### 3.1 EMS (7E0) — top live DIDs, log1 (3 394 reads total)
| DID | Reads | Payload len | Sample response | Note |
|---|---|---|---|---|
| F1F4 | 125 | 4 B binary | `62F1F4 13564526` | not ASCII → boot/app id or timer [INFERENCE] |
| F182 | 114 | 16 B ASCII | `62F182 "N360GBS6B1A3b300"` | ECU SW part-number family |
| A808 | 113 | 2 B | `62A808 0000` | TVS-specific measured [UNKNOWN name] |
| A809 | 113 | 2 B | `62A809 0000` | TVS-specific measured [UNKNOWN name] |
| 0105 | 99 | 1 B | `620105 00` | engine temp family [INFERENCE] |
| 0106 | 96 | 2 B | — | |
| 0101 | 94 | 2 B | `620101 0000` | |
| 010A | 75 | — | | |
| 0111/0100/0103 | 68/68/65 | — | | |
| 1009/100A | 56/56 | 2 B | `62100A 00AA` | |
| 0149/0109/0177/0163/0162/0154/0178 | 56–52 | — | | voltage/angle family [INFERENCE] |
| F190 | 44 | 17 B ASCII | VIN | |
| F191 | 39 | — | `7F2210` generalReject | not supported on this EMS |
| A803/A802 | 43/43 | 2 B | | TVS-specific |
| 0116/010B/0114/011A/102F… | ~30–44 | — | | |

Addressed full DID population on EMS (log1): `0100–011F` block, `0149`, `0154`, `0162/63/77/78`,
`1009–102F` block, `A802/03/08/09`, identity `F190/F182/F1F4` → **~100 distinct DIDs/round**.
[LOG1 histogram]

### 3.2 ICU/cluster (7F0→7F1), log2 (1 609 reads)
Blocks `E065/E117/E11B/E127/E12B/E142/E1B3/E1C9/E1D3`, `F19A–F1A7`, `F1A0–F1A2`, `F206/F208/FF56`;
e.g. `22 E1 17 → 62 E1 17 00` (1 B). Cluster DIDs are 1-byte flag/counter style. [LOG2]

### 3.3 Identity & OBD-II
- `09 02`→VIN, `09 04`→CALID `"N597IBS6B1A3a120"` (log2 EMS), `09 06`→CVN, `09 08`→IPT (IUPR, ×9). [LOG]
- Mode 01 PIDs used: **0B (MAP), 0F (IAT)**. [LOG both]

## 4. Naming, units, scaling
Displayed live/VHR parameters (bounded set with min/max!) [VIDEO f34][IMG 20260317 set][PDF]:
| Display name | Unit | Min–Max (Ronin run) | Value seen | Source channel [INFERENCE except noted] |
|---|---|---|---|---|
| Battery Voltage | V | 10.5–14.5 | 13.8 | EMS DID (battery-family 01xx) — OBD 42 not observed in logs |
| Engine Temperature | °C | −30…120 (later run 65–110) | 65.66 / 55.96… | EMS DID 0105-family |
| Throttle Position Sensor (Sensor 1 / 2) | V | 0.5–4.5 | 0.69 / 4.32 | dual-sensor DIDs |
| Intake/Manifold Air Pressure | kpa / hPa | 3–115 kPa (alt 100–1150 hPa) | 3.4 / 993.75 hPa | EMS + **OBD-II 01 0B** [LOG] |
| Intake Air Temperature | °C | −40–130 | 43.6 | **OBD-II 01 0F** [LOG] + EMS |
| Engine Speed | rpm | 1000–2500 (idle-test band) / 1400–2000 | 1643 / 1989 | EMS DID |
| Quick shift sensor voltage | V | 2.2–2.8 | **4.99 → RED** | model-specific DID (Ronin run) [IMG] |

Scaling/decoding **formulas are not recoverable from logs** (bytes are model-DID-specific and
values small): each parameter's raw→engineering transform follows the standard UDS DID
definition pack for that ECU. **[UNKNOWN — requires the OEM DID definition pack; see
MISSING_DEPENDENCIES.md]**. What IS proven: 1–2 B payloads, ms-resolution values (e.g.
65.66 °C, 3.4 kpa), unit-suffixed display, min/max card on bounded views.

## 5. UI & update behavior [IMG][VIDEO]
- Grid/list cards: name left, live value + unit right; on bounded views (VHR diagnostic tab,
  summary) a `Min: x  Max: y` line and green/red colorization; ~2–4 Hz visual refresh.
- `DataWatcherActivity` = focused watch of user-selected params (with capture). [SRC]
- `LiveDataRecordingActivity` records param streams to CSV for later FileViewer use. [SRC]
- Freeze/threshold events: out-of-range → red immediately (Quick-shift 4.99 V example). [IMG]

## 6. NirixX status
Implemented: sequential DID polling engine, per-model DID sets, bounded VHR table with
green/red colorization, CSV recording, "definition pending" row when the decode table lacks an
entry (no fabricated values). Open: OEM DID decode pack population (per model/ECU) — the one
hard dependency for full name/unit/scale parity.
