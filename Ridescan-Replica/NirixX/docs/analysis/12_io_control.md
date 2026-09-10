# 12 — Input/Output Control (0x2F) Specification

## 1. Observed wire sequence [LOG2 2026-01-29 11:06:57.010]
```
TX 7E0 2F A8 00 03 01        RX 7E8 6F A8 00 03 00
```
Format: `2F <ioDid2B> <controlParam1B> <controlState1B>` → response echoes DID + param, with
**last byte 00** (request had `01`) — the ECU returns resulting state; EMS DID **A8 00** with
controlParam **03** is the single observed actuation group (inside the same secured window as
RID 0211, i.e. SecurityAccess precedes). [LOG2][XREF]

## 2. UI evidence — two surfaces
1. **ECU Diagnosis → IOControlActivity**: per-ECU actuation list with **toggle switches**;
   EMS visible set: *MIL Lamp, Fuel Pump Relay, Actuate Starter Relay, Upstream Lambda Heater*;
   `#BABS` set: *Start Wheel Speed Test*. [IMG 20260317 IO tab][PDF §I/§II mirror list]
2. **VHR IO CONTROL tab**: same actuations run as a **guided auto-sequence** — orange
   "Requesting… <actuation name>" modal with progress + note "Don't close the application,
   While complete the diagnostics." per step (MIL Lamp → … → Upstream Lambda Heater). [VIDEO f07–f10]

## 3. Safety & anti-accident design observed
- One actuation executes at a time inside VHR (sequenced modal); user cannot stack requests. [VIDEO]
- Per-action toggle + explicit switch UI (no free-form). [IMG]
- SecurityAccess gate before actuation group. [LOG2]
- App-blocking busy modal prevents navigation mid-actuation. [VIDEO][SRC strings]
- Timeout/recovery: on missing response the modal pattern implies abort + dialog; no drop media
  — **UNKNOWN / Requires Validation**.

## 4. Result recording
- VHR records per-actuation result "Ok" into the report (PDF "Input/Output Control Result"
  lines: MIL Lamp Ok / Fuel Pump Relay Ok / Actuate Starter Relay Ok / Upstream Lambda Heater Ok;
  ABS "Start Wheel Speed Test Ok"). [PDF]
- In standalone IOControlActivity, toggle state + success/failure echoed; result persistence
  there = session log only. [LOG][INFERENCE]

## 5. Payload dictionary status
IO-DID catalog (A800 shown = an EMS output bank), per-DID control params (03), and the
actuation↔DID mapping live in the OEM definition pack → **MISSING_DEPENDENCIES.md**.
What IS known per surface: actuation display names (above), sequencing, result capture. [IMG][PDF]

## 6. NirixX parity
Implemented: secured 0x2F issuer in `DiagOps`, VHR IO tab auto-sequence with per-step modal +
Ok capture into report, standalone IO control list with pending-definition chips when the pack
lacks the entry. Open: per-model IO catalogue population.
