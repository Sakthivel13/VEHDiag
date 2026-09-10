# 05 — Vehicle Identification, Communication & Diagnostics Architecture

## 1. On-bus topology (observed)
All diagnostic traffic is **11-bit CAN, ISO 15765-2 (ISO-TP) carrying ISO 14229 UDS**;
SAE J1979 OBD-II modes 01/09 run on the functional broadcast channel in parallel. [LOG both]

| CAN id pair (req→res) | Offset | Role | Evidence |
|---|---|---|---|
| `0x7DF → any` | — | Functional broadcast (OBD-II modes 01/09, init probe, `19 02 FF` sweep) | [LOG both] |
| `0x7E0 → 0x7E8` | +8 | **EMS / engine ECU** (both vehicles) | [LOG both: full UDS incl. SecurityAccess] |
| `0x7E1 → 0x7E9` | +8 | **ABS** on `MD638AN21…` (answers `50 01`; DTCs `C1200-00`, `U2932-00` st.2C) | [LOG2 11:10:29] |
| `0x7E5 → 0x7ED` | +8 | Secondary node on `MD625AF99…` (tester-present only, 6×; likely ABS/ICU variant) | [LOG1] function UNKNOWN |
| `0x7F0 → 0x7F1` | **+1** | **ICU/cluster on MD638…** — massive live DID space `22E0xx/22E1xx/22F19x/22F2xx`, 1 609 reads | [LOG2] |
| `0x7F0 → 0x7F8` | **+8** | Cluster/other node on MD625… (VIN `22F190` unsupported → `7F2211`; no 3E support → `7F3E11`) | [LOG1] |

**Topology is model-dependent**: address sets differ between the two captured vehicles → the app
carries a per-model ECU table (binding after VIN decode). Same-family ECUs answer differently
(cluster response offset +1 vs +8). [XREF both logs]

## 2. Vehicle identification chain [LOG both, identical byte sequences both days]
```
TX 7E0 10 01                 RX 7E8 50 01 00 32 01 F4          # default session, P2=50ms P2*=5000ms
TX 7E0 22 F1 90              RX 7E8 7F 22 78                   # RCRP pending
                             RX 7E8 62 F1 90 <17B ASCII VIN>   # ISO-TP multi-frame reassembled by stack
TX 7DF 09 02                 RX 7E8 49 02 01 <17B ASCII VIN>   # OBD-II cross-read of VIN
TX 7DF 09 04                 RX 7E8 49 04 01 "N597IBS6B1A3a120"  # CALID  (log2)
```
- VIN `22 F1 90` read is retried/RCRP-tolerant; ASCII payload begins `MD6…` (LM1 WMI family). [LOG]
- CALID prefix `N597…` matches the decompiled `n597_cluster_flashing` supplier family name — the
  app maps CALID/SW-part families to flash flows. [XREF SRC]
- Model resolution examples encoded by UI: `MD638DS16…`→"TVS APACHE RR310 Refresh";
  `MD637AN11…`→"TVS Ronin"; `MD625AF99…`→(vehicle of log1, NTorq-class); VIN banner shows
  model + image immediately after read. [IMG][PDF][VIDEO]

## 3. UDS service usage (evidence histogram)
TX counts per service over both logs (⊕ = positive response seen; ✖ = NRC seen):

| SID | Service | Where | Observed | Response/NRC evidence |
|---|---|---|---|---|
| 0x10 | DiagnosticSessionControl | 7E0/7E1/7F0/7DF | 01 default (log1 ×24; log2 ×6), **03 extended before secured ops** (log2) | `50 01/50 03 00 32 01 F4` ⊕; `7F1078` pending once |
| 0x19 | ReadDTCInformation | all ECUs | **only subfunc 0x02, mask 0xFF** (×34/×8) | `59 02 FF + entries` ⊕; `7F1978` then payload; `7F1911` on cluster(log1) |
| 0x14 | ClearDiagnosticInformation | 7E0 | `14 FF FF FF` | `7F1478` → `54` ⊕ (log2 11:09:10) |
| 0x22 | ReadDataByIdentifier | every ECU | 3 394× on 7E0 + 723× (log2) + 1 609× on 7F0(log2) | `62 <did> <data>` ⊕; NRCs `7F2210/31/78`, `7F2211` |
| 0x27 | SecurityAccess | 7E0 | `27 01` → 8-byte seed; `27 02` + 8-byte key (log2 ×3 pairs) | `67 01 <seed>` ⊕; `7F2778` → `67 02` ⊕ |
| 0x2F | InputOutputControlByIdentifier | 7E0 | `2F A8 00 03 01` (log2 11:06:57) | `6F A8 00 03 00` ⊕ |
| 0x31 | RoutineControl | 7E0 | `31 01 02 11` (log2 ×2) | `71 01 02 11 01` ⊕ (statusRecord 01=running→?) |
| 0x3E | TesterPresent | 7E0/7F0/7E5 | `3E 00` at ~3.09 s | `7E 00` ⊕; `7F3E11`/`7F3E13` on cluster(log1) |
| 0x01 | OBD-II mode 01 | 7DF | PIDs **0B MAP, 0F IAT** (only two observed) ⊕ | `41 0B/0F …` |
| 0x09 | OBD-II mode 09 | 7DF/7E0 | 02 VIN ⊕, 04 CALID ⊕(7DF), 06 CVN, 08 IPT (IUPR) — 09 08 seen ×9 | `49 …` ⊕; `7F0911` on ECUs lacking mode 09 |

UDS services from the master list **not observed** in any capture: 0x11 ECUReset (exercised
only inside flashing boundary per strings "ECU Reset"), 0x23 ReadMemoryByAddress, 0x28,
0x2E WriteDataByIdentifier (**expected** for WriteDataActivity but not captured on wire — the
secured chain stops after 27 in log2 at 11:06; Requires Validation), 0x34/36/37 transfer
(flashing media shows dialogs/progress but no CAN capture), 0x83–0x87. NirixX implements the
full set behind flags and marks unobserved ones from flash UI flow logic. [XREF]

## 4. NRC vocabulary (observed, both logs)
| `7F ss nn` | n | Meaning used as |
|---|---|---|
| 22 78 | 209 | RCRP — **pending**, app waits for real response (always followed by final PR) |
| 22 31 | 245 | requestOutOfRange — DID not present on that ECU (polled-off params) |
| 22 10 | 91+74 | generalReject — e.g. `22 F1 91` on EMS |
| 22 11 | 5 | serviceNotSupported — VIN DID on 7F0/7F8 cluster |
| 3E 11/13 | 45/2+1 | testerPresent unsupported / bad length (cluster log1) |
| 09 11 | 31 | mode-09 unsupported (older EMS, log1) |
| 01 11 | 20 | mode-01 unsupported (non-emissions nodes) |
| 19 11 | 5 | 19 unsupported (cluster log1) |
| 27 78/14 78/10 78 | 3/1/1 | pending on SecurityAccess / ClearDTC / SessionControl |
| 7E 01 | 1 | anomaly: NRC 01 against SID 0x7E echo — logged, treated as transient [INFERENCE] |

**Policy proven by logs**: send → on `7F xx 78` keep waiting (P2* 5 000 ms window) → on
hard NRC, log it, mark parameter/function unsupported, continue without tearing the session.

## 5. Timing & concurrency
- Live polling is **sequential request→response cycling** across the ECU's DID list, one DID per
  request, typical gap 31–100 ms; never pipelined. [LOG deltas]
- Tester-present interleaves with live reads on the same ECU address. [LOG]
- Functional `7DF` used for OBD-II sweeps alongside physical sessions. [LOG]

## 6. Session/model binding & persistence
- Session binds: dealer, VCI(+fw), connectivity, VIN, ECU set, gps, app version — header of log. [LOG]
- Per-ECU capabilities shown after discovery (grid cards filtered — ICU example lists 5). [IMG]
- Address/ECU map per model = app data table [XREF: two vehicles show different maps].

## 7. Diagnostics kernel (error taxonomy exercised)
timeout (no RX within P2/P2*), hard NRC (table above), RCRP wait-chain, unsupported ECU skip,
VIN mismatch/blank serial (`…2100000000`). Recovery = continue/rescan; full teardown never
observed on NRC. [LOG][XREF]

## 8. NirixX parity note
`core/uds/UdsClient` implements exactly: RCRP wait, +8/+1 response-id tables (`TransportSettings`),
sequential DID cycling, 3E fan-out, broadcast OBD-II lane, NRC taxonomy with technician text.
`core/vin/VinRules` reproduces the 33-model prefix table (which includes MD637/MD638/MD625
families seen here). Tests in `tests/jvm/TestCore.java` replay captured frames from these two logs.
