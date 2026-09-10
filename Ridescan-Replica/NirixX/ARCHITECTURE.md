# NirixX — Architecture Map (v1.6.0)

## 1. Audit verdict (what was found on inspection)

| Area | State before 1.5.0 | Verdict |
|---|---|---|
| UI / screens | 49 activities, reference-styled | **reusable** — kept |
| VIN flow | SimEcu-generated frames only | **replaced** — real engine added, sim kept as labelled "training link" |
| VCI connect page | Simulated "connected" flag on tap | **replaced** — real ByteLink open + ELM327 init + UDS session + VIN read |
| UDS / ISO-TP | None (string tricks) | **new real implementation** (core/uds) |
| Transports | None | **new real**: BT-SPP, Wi-Fi TCP, USB-CDC (core/vci) |
| Vehicle DB | 4 curated models | **extended** — full supplied 33-model TVS table + VIN rules |
| Roles | Display-only spinner | **enforced RBAC** (core/role) — navigation guard + operation guards |
| Reports/VHR | Tabs + PDF replica | **kept** — physical-eval photos now real (SAF pick → file → PDF asset) |
| Logs | Real .txt session logs + DB mirror | **kept** (matches captured log byte format) |
| Flashing UI | Reference-styled simulation page | **kept, gated** to Dealer Engineer; real programming path = missing dependency (see MISSING_DEPENDENCIES.md) |
| DMS backend sync | None | **missing dependency** (documented) |

## 2. Module structure

```
com.nirixx.app
├── core/
│   ├── uds/   IsoTp (SF/FF/CF/FC, BS, STmin, timeouts)      [pure Java]
│   │          UdsClient (0x10/0x11/0x14/0x19/0x22/0x23/0x27/0x28/0x2E/0x2F/0x31/
│   │                    0x34/0x36/0x37/0x3E/0x85, NRC 0x78 wait-out)    [pure Java]
│   │          Nrc (ISO 14229 code → technician text)        [pure Java]
│   │          Obd (SAE J1979 Mode 01/09 PIDs + formulas)    [pure Java]
│   ├── vin/   VinRules (validity, prefix rules, systems)    [pure Java]
│   ├── vci/   CanTransport · ByteLink (interfaces)
│   │          ElmCan  (ELM327 dialect: ATZ/E0/L0/H1/SP6/SH/CRA + ATRV/ATI
│   │                  sync queries + frame counters)
│   │          BtLink  (RFCOMM SPP 00001101)
│   │          WifiLink(TCP 192.168.0.10:35000, configurable)
│   │          UsbLink (android.hardware.usb host, CDC-ACM claim, bulk EPs)
│   ├── diag/  DiagEngine (owning chain, bring-up, results)
│   │          DiagOps (single-executor ops surface: DTC/io/routine/DID/
│   │                  PID/Mode09/ATRV, real-traced, NRC-mapped)
│   │          FlashRunner (real 34/36/37 transfer engine)
│   │          TestAddr (tests.addr grammar)                 [pure Java]
│   │          BatteryAssess (12 V SoC bands)                [pure Java]
│   │          TransportSettings (configs persistence)
│   └── role/  Roles (RBAC modules, screen map, role checks)
├── db/        Db — SQLite v3: 33 supplied vehicles + VIN rules, ECU
│              applicability from variant strings, tests.addr bus addresses,
│              users/roles/sessions/logs/streams/inputs/iupr/vhr/configs +
│              manuals/flash_bins (real imports)
├── sim/       SimEcu + UdsLog — TRAINING link only (clearly labelled;
│              never presented as a live link)
├── DocsProvider — framework-only content provider (imported manuals,
│              binaries, reports opened by external viewers)
└── *Activity  reference-styled screens (Ui kit + BaseActivity shell)
```

## 3. Data flow — the real path

```
LoginActivity ─ dealer code/role from users table
   │
HomeActivity ─ tiles filtered by Roles.can(role, module)
   │ VCI Connect
AddDeviceActivity ─ BT (live discovery/bonded) | WIFI (live scan + endpoint) | USB (live enumeration + permission)
   │              pick LIVE device  →  ByteLink subclass
DiagEngine.connectAndIdentify(ctx, link, tx, rx)
   │ open link → ATZ/E0/L0/H1/SP6/SH/CRA ("Opening physical link")
   │ IsoTp(7E0/7E8) → UdsClient.sessionControl(0x01 or 0x03)
   │ UdsClient.readDid(0xF190)  →  VIN (ISO3779-validated by VinRules)
   │ Db.vehicleByVin(vin): exact captured sample → longest VIN-rule prefix
   ├─ matched   → Session.selectVehicle/ecus → Diagnostic Section
   ├─ unmatched → Vehicle List (manual selection) → Diagnostic Section
   └─ error     → stage + NRC + hint surfaced, RETRY offered (never silent)

Diagnostics (per screen)  →  UdsClient calls inside workers;
   ECU refusal (0x7F xx) → Nrc.of(code) technician text + remediation hint;
   ISO-TP handles multi-frame both directions with real FC behaviour.

Training link (no VCI): SimEcu emits the SAME service sequence with an
explicit "TRAINING LINK (simulated UDS)" banner — used for UI training only.
```

## 4. RBAC matrix (enforced in BaseActivity.go + operation entry guards)

| Module | Dealer Service | Dealer Engineer | Technician/Advisor | Manager/Admin |
|---|---|---|---|---|
| VIN diagnostics / vehicle grid / VCI | ✅ | ✅ | ✅ | ✅ |
| Diagnostic section (live/DTC/IO/routine/IUPR) | ✅ | ✅ | ✅ | ✅ |
| Write DID / Flashing / VIN-flash / Campaign | ❌ | ✅ | ❌ | ✅ |
| Health report / Reports / Battery / Recording / Logs | ➖ | ✅ | ✅ | ✅ |
| Service manual / AI / System check / App update / VCI fw | ❌ | ✅ | ❌ | ✅ |

## 5. Threading

- All VCI/UDS work on dedicated worker threads (`vci-connect`, `vin-read`,
  link reader threads); UI only via Handler posts.
- IsoTp blocking waits use N_Bs=1 s, P2 default 2.5–4 s, P2* (NRC 78) up to
  40 × 5 s — per ISO 14229 timing.

## 6. Testing

- `tests/run_tests.sh` — off-device JVM suite (ecj-compiled):
  VIN validity/rules/systems parsing, ISO-TP FF/CF/FC + FC emission,
  UDS session→VIN with NRC-0x78 wait-out (frames from the captured logs),
  DTC record decoding, negative-response surfacing, NRC table coverage.
- `tools/verify_apk.py` — 21 APK checks (signature, dex, layouts, nav,
  Android-12+ compatibility).

## 7. What is intentionally NOT here (see MISSING_DEPENDENCIES.md)

Kvaser/TechPro vendor SDK transport, OEM seed-key algorithm, per-model
diagnostic definition packs (ODX/CDD), campaign/flashing binaries, DMS
backend credentials, per-model battery-pack definitions for EV models.
None of these are simulated; the boundaries are explicit in code and UI.
