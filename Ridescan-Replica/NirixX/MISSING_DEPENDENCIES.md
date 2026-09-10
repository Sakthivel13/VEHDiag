# NirixX — Explicit Integration Boundaries (nothing fabricated)

Per the project rule: where a dependency genuinely doesn't exist in the
project, the integration stops at a clean interface and says so — no mocks
posed as reality.

| # | Dependency | Why required | Where used | What's already implemented | What remains | Exact action required |
|---|---|---|---|---|---|---|

**Closed since this table was first written (v1.6.0):** 12 V battery measurement is now real (ELM327 ATRV rail + SAE J1979 PID 0x42, public SoC chart — see `core/diag/BatteryAssess`). Flash binaries no longer need to ship — the operator imports the real image from storage and the true 34/36/37 pipeline runs (ECU refusals reported with their NRC). Service manuals are a real document shelf (SAF import + content-provider open). The rows below remain open.
| 1 | **Kvaser Android SDK (Canlib for Android / Kvaser Android drivers)** | Kvaser uses a proprietary binary framing, not ELM ASCII | `core/vci/` transport family | ByteLink/CanTransport interfaces; BT/WiFi/USB-CDC ELM327 transports (real) | No Kvaser channel impl — intentionally absent | Obtain Kvaser's official Android SDK/jar from Kvaser AB; drop `KvaserCan implements CanTransport` beside `ElmCan` |
| 2 | **TechPro VCI protocol spec/SDK** | Same — vendor protocol | same | same | same | Obtain TechPro protocol docs/SDK from the supplier |
| 3 | **OEM Security-Access seed-key algorithm (0x27)** | Write-DID & programming need the real key derivation | `core/uds/UdsClient.securitySeed/Key` | Full 0x27 request/response sequencing, attempt-counter/lockout NRC handling (0x35/0x36/0x37) | The algorithm itself (OEM secret — must never be reverse-engineered into the repo) | OEM-authorized key calculator (document/signed library) injected via a `SeedKeyProvider` interface |
| 4 | **Per-model diagnostic definition packs (ODX/CDD/requested DID & routine lists per ECU/variant)** | Model-accurate DID tables, min/max, routines, actuations | `db/Db` tests/ECU applicability | Supplied 33-model table + variant-string ECU applicability + captured reference DID set for the 4 documented models; generic OBD-II set tagged "Generic OBD-II" elsewhere | No invented per-model catalogs | Export the vehicle packs from the OEM diagnostic definition system into `assets/vehicles/*.json` (schema = Db tables) |
| 5 | **Campaign / flashing binaries + eligibility rules** | Real 0x34/0x36/0x37 programming needs the signed calibration file per VIN family | `FlashActivity` (engineer-gated UI), `SupplierFlash*` | Full UDS download pipeline client-side: `requestDownload/transferData/transferExit`, 4-stage progress UI, safety interlocks (battery, ignition) | No binaries, no eligibility DB | Signed flash file package + campaign table from OEM service IT |
| 6 | **DMS backend (sync endpoints, auth)** | Cloud sync of reports/logs/sessions | `configs.dms_domain`, sessions/logs tables | Local persistence of everything a DMS would store; export via file system | No network mock | Endpoint + credentials from the DMS team; implement sync worker |
| 7 | **EV battery-pack diagnostic definitions (iQube / KING E)** | Real cell/pack telemetry DIDs | `BatteryHealthActivity`, BMS ECU rows | BMS/MCU ECU entries from the supplied variant data | No invented pack metrics | Pack-level DID list from EV system engineering |
| 8 | **Per-model artwork pack** | Correct photo per model | vehicle cards | NirixX-generated artwork for Ronin/Apache/Jupiter/XL + type-matched generic art; mapping is data-driven by model | No photos claimed as real vehicles | Licensed studio/press photos mapped in `vehicles.image_res` |
| 9 | **Camera capture without AndroidX** | Physical-evaluation photos via camera intent need a FileProvider on modern Android | `VhrActivity` physical tab | Gallery/SAF upload is real and fully working today | Camera in-app capture | Add a small framework-only Camera2 capture screen OR adopt androidx.core FileProvider — decide policy |
| 10 | **AI assistant backend** | Free-form answers beyond built-in knowledge base | `SupportChatActivity` (offline expert KB is real) | Deterministic offline Q&A over flashing/DTC/VCI/reports/IUPR/VIN topics | No LLM endpoint | Endpoint + key from platform team; offline KB stays as fallback |
| 11 | **On-screen video recording (MediaProjection pipeline)** | Reference app records the screen (HBRecorder bubble) | `ScreenRecordOverlayService`, Account screen toggle | Honest session-capture **indicator** that marks the session window; UI states plainly that no video is recorded | No fake "recording" claim | Consent-flow UX on API 34 + VirtualDisplay/MediaRecorder writer + FGS `mediaProjection` type — implement when prioritized (pure framework, no dependency to procure) |

**Honesty guarantees in the build:**

- The training link (`sim/SimEcu`) only ever runs when no VCI is connected and
  is labelled in-app as "TRAINING LINK (no VCI)" — it can never mark
  `vciConnected = true`.
- Wire-level errors surface with **stage + message + NRC hint** (e.g.
  "Opening physical link — USB permission/device open failed"), never as a
  silent failure or a faked success.
- All vehicle data comes from the supplied 33-model table (plus the four
  captured reference examples); nothing else is claimable by the app.
