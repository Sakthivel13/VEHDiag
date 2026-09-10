# 19 — Test Strategy (brief §31)

Three test rings. Rings 1–2 run in CI/sandbox today; ring 3 needs a bench harness (vehicle/VCU
simulator or real bike + VCI).

## Ring 1 — JVM unit tests (present: `tests/jvm/TestCore.java`, 8 suites PASS)
Replay + logic tests derived from captured evidence:
| Suite | Anchored to |
|---|---|
| VIN rules (33-model decode) | [IMG/PDF VINs] |
| ISO-TP segmentation/reassembly (SF/FF/CF/FC, BS, STmin, timeouts) | simulator + VIN multi-frame shape [LOG] |
| UDS conversation replay (log-derived script: 1001→22F190→3E loop) | [LOG1 head] |
| Negative response handling (RCRP 78 → wait; hard NRC surfaces) | [LOG 7F2278 chains] |
| NRC table completeness (10/11/13/22/24/31/33/35-37/72/78…) | [LOG NRC histogram §05] |
| OBD-II decode (mode 01 0B/0F; mode 09 02/04/08) | [LOG 49 02/49 04 samples] |
| TestAddr grammar (did:/rid:/io:/pid:/m09: tokens) | per-model capability maps |
| Battery assessment bands (12 V) | [PDF 10.5–14.5 kPa… V band] |
Additions queued from this analysis: DTC payload replay of the 86-entry EMS frame (already
parsed in code — formalize), ABS 5902 2F pair, RCRP-then-clear chain.

## Ring 2 — Static gates (present, run every build)
- `tools/verify_apk.py` — 21 checks: manifest sanity, Android 12+ exported flags, nav
  reachability (49/49), intent-edge/contract audit, services/provider presence.
- `tools/audit_links.py` — back-wiring, extras contract, REQ_* pairing, RBAC coverage,
  service/provider wiring, vehicle-image resolution → 0 errors policy.

## Ring 3 — Functional / device tests (bench, when hardware available)
Organized per master-brief §31:

### Functional (F#)
- F01 Login OTP/PIN, wrong-OTP lockout, change-account (S1).
- F02 Role matrix: Service vs Engineer tile sets; engineer-only entries guarded even via
  deep link (matrix 03). Automate with adb am start + UI dump asserts.
- F03 VCI connect per transport: BT pair known/unknown VCI, Wi-Fi join, USB attach;
  `[CONNECTIVITY_TYPE]` line + header written (S2) — compare with [LOG].
- F04 Auto-VIN: on-bench ECU answers 22F190; expect VIN banner + model image + topology select.
- F05 ECU discovery: partial answer set (EMS+ABS silent cluster) ⇒ grid shows only live ECUs.
- F06 Live parameters: poll cadence, green/red coloring vs min-max table (06).
- F07 DID read identity set; F08 DID write under security (write a safe DID on bench).
- F09 Read DTC: 19 02 FF replay vs canned ECU: 86-entry EMS payload renders, dup handling,
  All/Active/History counts match status bytes.
- F10 Clear DTC: 14 FF FF FF → 54 → **list auto-refreshes**; surviving permanent codes remain.
- F11 IO control: VHR auto-sequence modals order = MIL→FuelPump→Starter→Lambda; results marked.
- F12 Routine control: RID 0211 start on bench; stop/result when documented.
- F13 IUPR primary/secondary render + history entry written.
- F14 VHR end-to-end: 5 tabs, photo-mandatory validation (fails like video f31 when empty),
  PDF content equality vs expected template, verdict math with one out-of-range param (Quick
  shift case ⇒ not Passed).
- F15 Flash bench (supplier bench only): prechecks, progress, success dialog, fail-injection
  (transfer abort → red dialog), post-reset re-identify.
- F16 Report/log files: name pattern `<sessionId><VIN>.txt`; viewer opens; share/export works.
- F17 Screen recording: start/stop, indicator, file saved+playable.
- F18 Notifications: list/unread/nav.
- F19 Updates: app-update description screen; VCI fw skip counter (when channel exists).

### Negative (N#)
- N01 VCI unplug during live poll, DTC read, flash transfer → op aborts, dialog, session log
  records E2; app alive.
- N02 Ignition off before connect / mid-poll → E3/E4 behaviors; recovery on IGN on.
- N03 ECU NRC storms (7F 22 31 loop) → no crash; param marked unsupported; UI continues.
- N04 RCRP beyond P2* (delay injection) → timeout path, technician-facing message.
- N05 Bad VIN (blank serial) → degraded mode, no model-certain features.
- N06 Permission denials (Camera during VHR photo) → graceful fallback to import.
- N07 Storage full during log/PDF/record write → error surfaced, no silent truncation.
- N08 App kill mid-VHR / mid-flash → AppCloseService flush; relaunch = clean login; locked
  resources released.
- N09 Network loss during upload → queued, retried; indicator honest.

### Role-matrix (R#) — every row of 03_roles.md matrix executed for both roles (≥46 checks).

### State-transition (S#) — the 15 machines in 17_state_machines.md: each documented edge gets
a trigger test; recovery edges verified by injection (drop/NRC/timeout/kill).

### Compliance gate per release
Ring 1 100% PASS · Ring 2 zero errors/warnings · Ring 3 bench subset F03–F14 + N01–N08 signed
off with attached session logs (which double as regression evidence for test updates).
