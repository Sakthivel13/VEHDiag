# 17 — Error Handling & State Machines

State machines are evidence-anchored: transitions marked [LOG]/[VIDEO]/[IMG]/[SRC] are proven;
unmarked recovery edges are standard-practice design for NirixX (clearly noted).

## E. Error taxonomy (brief §24) — Trigger → Detection → UI → Recovery → Logging
| # | Scenario | Evidence of behavior |
|---|---|---|
| E1 | VCI disconnected pre-session | Login lists remembered VCI; connect failure → stay on login w/ error [INFERENCE]; logged (header never written without attach [LOG]) |
| E2 | VCI drop mid-operation | "Do not close the app…" context strings; no recovery media — Requires Validation. NirixX: transport error → op abort dialog + session log entry |
| E3 | Vehicle/IGN off | no RX to `1001`/polls → comms error state [INFERENCE]; keep-alive resumes ECUs returning [LOG] |
| E4 | ECU doesn't answer a function | NRC 11/31 → feature marked unsupported, UI continues (cluster 19→7F1911; F191→7F2210; mode09→7F0911) [LOG] |
| E5 | RCRP delay | `7F xx 78` → wait for final response (VIN read, DTC read, clear, SA) [LOG everywhere] |
| E6 | Negative response hard fail | logged; dialog with technician text (NirixX Nrc table); reference UI copy UNKNOWN |
| E7 | Invalid VIN / blank serial | `MD638AN2100000000` proceeds in degraded mode (no model-certain features) [LOG2][INFERENCE] |
| E8 | Bad credentials/OTP | no media; Requires Validation |
| E9 | Network failure (upload/DMS) | WorkManager retry [SRC INFERENCE] |
| E10 | Flash failure | red dialog [IMG]; recovery flow UNKNOWN |
| E11 | Low battery before flash | precondition dialog w/ live voltage cards [IMG][INFERENCE] |
| E12 | App restart mid-session | new session id on relaunch; old log closed (AppCloseService flush) [SRC][LOG naming] |
| E13 | VHR checklist incomplete | red snackbar, stay on tab [VIDEO f31] |
| E14 | Unsupported service on ECU | skip + continue policy [LOG §05] |

## S. State machines (brief §25)

### S1 Authentication
`ANON --enter creds--> VALIDATING(net) --ok--> OTP_PENDING --6-digit--> PIN_CHECK --ok--> AUTHENTICATED(role,dealer,VCI?) --login wizard done--> SESSION_OPEN`
failure edges → error state w/ retry; "change account" → ANON. [VIDEO f01][SRC strings]

### S2 VCI connection
`NO_VCI --pair(AddDevice)--> KNOWN --select+type(BT/WiFi/USB)--> ATTACHING --socket open, fw hdr ok--> LINKED --GATT/SPP loss--> DROPPED --(auto?)reconnect…` last edge UNKNOWN.
LINKED proven by `[CONNECTIVITY_TYPE]` + header fw 1.07. [LOG][SRC]

### S3 Vehicle connection
`LINKED --1001 @7DF/7E0--> SESSION_DEFAULT(50 01) --22F190/0902--> IDENTIFIED(VIN) --model map--> TOPOLOGY_KNOWN --idle 3E00@3.1s--> HELD` [LOG both]
blank-VIN → IDENTIFIED_DEGRADED. [LOG2]

### S4 Diagnostic session (app-level)
`SESSION_OPEN(dealer,VCI) ↔ IDENTIFIED(VIN,ECUs) --user op--> OP_BUSY(modal) --done--> IDLE --logout/new vehicle--> CLOSE(flush log, AppCloseService)` [LOG][SRC][VIDEO busy modal]

### S5 Vehicle Health Scan
`DEALER(valid) --next--> DIAG_SCAN(auto live reads, per-ECU) --next--> IO_SEQ(each actuation: REQUESTING→OK/NOK) --next--> PHYS_EVAL(all items photo+value; else E13) --next--> SUMMARY --compute--> VERDICT --render--> PDF --auto--> UPLOADED("PDF Uploaded Successfully")` [VIDEO][PDF][SRC]

### S6 DTC workflow
`READ_ENTRY --19 02 FF--> {RCRP wait}→ LIST(All/Active/History) --CLEAR DTC (+confirm)-->14 FF FF FF→{RCRP}→54→ auto RE-READ` [LOG2][IMG]
Roles: read both; clear both⚠ w/ confirm (03_roles.md).

### S7 GTS (design note)
Viewer-only proven: `DTC_ROW --open--> GTS_VIEW(content) --back--> DTC_ROW`. Interactive stepper:
no evidence — if added later: `STEP(n,expect,measure via 22)→{pass→STEP(n+1)|fail→branch}` (09_gts.md). [SRC]

### S8 DID read/write
Read: `IDLE --22 did--> VALUE` (repeat ok). Write: `IDLE --10 03--> EXT --27 01/02--> SECURED --2E did data--> {54-like pos 6E|NRC} --> IDLE` — last hop Requires Validation (07_did.md). [LOG2]

### S9 Routine Control
`LIST --select--> CONFIRM(orange) --10 03+27--> SECURED --31 01 RID--> RUNNING(3E keep-alives) --(31 02 stop|timeout)--> DONE/FAILED` [LOG2][IMG]

### S10 IO Control
`LIST_ECUS --toggle--> CONFIRM --secured window--> 2F ioDid param state --6F echo--> RESULT_OK(recorded in VHR when from VHR)` [LOG2][VIDEO][IMG]

### S11 IUPR
`ENTRY(primary|secondary) --0908 (0902/0904 context)--> COUNTERS --save--> HISTORY --entry--> HISTORY_LIST` [SRC][LOG]

### S12 ECU Flashing (guarded)
`ENTRY(engineer) --variant bind--> PKG_SELECT --download--> PRECHECK(batt/IG/SEC) --"GET SECRET KEY"--> SECURED --PROGRAM(download 3x family)→ TRANSFER*(34/36/37 unobserved)→ VERIFY --reset(11)--> REIDENTIFY --success/fail dialog--> END` [IMG][JSON][SRC strings][LOG-partial] — starred hops Requires Validation.

### S13 Screen recording
`IDLE --bubble start--> RECORDING(notif "Recording your screen"; bubble floats) --drag notif / bubble stop--> SAVED(mp4)` [VIDEO][SRC]

### S14 Log session
`SESSION_OPEN --header write--> OPEN --each op RX/TX append--> OPEN --app close(AF_CLOSE via AppCloseService)/logout--> CLOSED --(upload DMS?)--> SYNCED` [LOG][SRC]

### S15 Application update
`CHECK(login/home) --newer--> UPDATE_AVAILABLE(UpdateDescription) --accept--> DOWNLOADING → INSTALL(package) → relaunch` ; VCI-firmware variant adds `SKIPPABLE(≤5)` counting; ECU software = flashing flow. [SRC strings]

## Global invariants (parity rules for NirixX)
1. Busy op ⇒ modal + no navigation away (esp. flash). [VIDEO][SRC]
2. Privileged ops ⇒ extended session + SecurityAccess immediately prior. [LOG2]
3. RCRP always consumable; hard NRC ⇒ log + surface + continue. [LOG]
4. Every externally visible run creates exactly one session log named by §16 rule. [LOG][IMG][VIDEO]
5. Verdicts/colors derive only from device-returned data (no synthesized values). [PDF][IMG]
