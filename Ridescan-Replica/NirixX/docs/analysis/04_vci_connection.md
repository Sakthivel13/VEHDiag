# 04 — VCI Connection Workflow

## 1. Hardware & transports established by evidence
| Fact | Evidence |
|---|---|
| VCI family: **TechPRO** (two generations observed: BT classic `502808`, Wi-Fi `504856`) | [VIDEO login dropdown "TechPRO_504856"][LOG headers][IMG footer session ids] |
| Transports selectable at login: **BT / WIFI / USB** | [VIDEO f01 chooser][IMG 114 same] |
| BT path = Bluetooth Classic **SPP/RFCOMM** serial | [SRC `btlibrary/SerialService,SerialSocket,BluetoothUtil,TextUtil` — the Kai-Morich serial service classes] |
| BT diagnostic capture: `[CONNECTIVITY_TYPE]: --> bluetooth` at session start | [LOG both, line 15] |
| Wi-Fi path active for VCI `504856` (status bar Wi-Fi glyph + login chooser) | [VIDEO footers] — socket/port/protocol UNKNOWN / Requires Validation |
| USB path: chooser only; never exercised in media | [VIDEO][IMG] — UNKNOWN |
| VCI firmware version reported into log header: `Firmware Version : 1.07` | [LOG both headers] (value is VCI fw; app version is separate `2.2.5 (190)`) |
| Old "0-series" VCI discontinued end of Jan-2026 → forced migration to 5-series Wi-Fi | [SRC strings: "The TechPRO VCI tool with serial number starting with 00XXXX will be fully discontinued… upgrade to the new WiFi VCI tool with serial number starting with 5XXXXX"] |
| VCI firmware auto-update with skip budget: "…skip the VCI Upgrade now. But you are only allow to skip the upgrade only 5 times" | [SRC strings] |
| Screen: `VCI_Diagnostic_Activity`, `firmware_update/tz_new_vci_firmware_update`, AddDevice | [SRC] |

## 2. Discovery / selection / pairing
1. Login screen VCI dropdown lists already-known VCIs by display name (`TechPRO_<serial>`). [VIDEO f01]
2. **ADD/PAIR VCI** opens AddDevice flow. [VIDEO][SRC AddDeviceActivity]
   - BT: standard Android pairing + SPP socket; Location permission precondition (pre-Android-12 string retained: "Location permission …"). [SRC]
   - Wi-Fi: join/select TechPRO network (INFERENCE from connectivity glyph + naming; no packet capture).
3. Selected VCI + connectivity type are remembered across launches (form pre-filled). [VIDEO]

## 3. Connection initialization sequence (observed, BT log)
```
app start session → log header written (device, app ver, dealer, session id, VCI fw, latlong)
→ [CONNECTIVITY_TYPE]: bluetooth
→ t+5.3s  TX 7E0 1001            RX 7E8 5001 0032 01F4        (default session; P2=50ms P2*=5000ms)
→ same ms TX 7E0 22F190          RX 7E8 7F2278 → RX 62 F190 <17 ASCII VIN>  (RCRP then multi-frame VIN)
→ t+3.1s  TX 7E0 3E00 … repeats every ~3.09 s while idle       (tester present keep-alive)
```
[LOG both — byte-identical on both vehicles/days]
- First-contact delay (~4–5 s after session line) = BT SPP open + VCI-side CAN attach. [INFERENCE]
- P2 timing values both sessions: `00 32 01 F4` → P2=50 ms, P2\*=5000 ms. [LOG]

## 4. Status, reconnection, failure handling
- App-bar ECU chip + **green dot** marks live ECU; persistent footer carries connectivity glyph. [IMG]
- Idle keep-alive: `3E 00` → `7E 00` at ~3.09 s cadence to every ECU the app holds an open session
  with (observed simultaneously to `7E0`, `7F0`; ABS `7E1` in log2 later window). [LOG]
- TesterPresent to an unsupported-3E ECU yields `7F 3E 11` (NRC serviceNotSupported ×45, log1,
  on the `7F0/7F8` unit) — app logs and continues rather than tearing down. [LOG]
- Socket loss / VCI off / out-of-range UI behavior, backoff & auto-reconnect policy:
  **UNKNOWN / Requires Validation** — no media of a drop event.
- Mid-flash VCI disconnect: string "Do not close the app until the flash is completed" plus
  blocked navigation implies *no graceful recovery UI* — treat as failure path (see 14_flashing.md). [SRC][INFERENCE]

## 5. Vehicle-side attach & ignition
- CAN attach precedes first `1001` [LOG]; ignition-OFF poll yields no RX → tool retries and
  surfaces communication error (no media; standard behavior INFERENCE — Requires Validation).
- On net power-cycle of vehicle (key off/on) the app re-runs `1001`+VIN chain on next action
  — no persistent DTC session assumed across ignition cycles. [INFERENCE]

## 6. VCI firmware/version detection
- VCI reports firmware `1.07` into header; app compares against policy → forced-upgrade
  dialog with 5-skip budget; "Email link for VCI Update Tool" for desktop recovery path. [LOG][SRC]

## 7. Target architecture mapping (NirixX)
`UI → DiagEngine → UdsClient (UDS/ISO-TP) → CanTransport → { BtLink(SPP) | WifiLink | UsbLink | ElmCan }`
with Kvaser/TechPro vendor SDKs behind `CanTransport` when available
(see ../../MISSING_DEPENDENCIES.md — SDK acquisition is the only blocker). NirixX already
reproduces: session-id join format parity in logs, 1001→22F190→3E00 cadence, RCRP handling,
keep-alive fan-out per ECU, NRC-continue policy. Gaps: TechPRO Wi-Fi framing (UNKNOWN),
USB framing (UNKNOWN), skip-budget VCI update UI (policy string known, mechanism to build
when vendor doc arrives).
