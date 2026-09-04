# VEHDiag

**VEHDiag** is an open, independently implemented automotive diagnostics
platform: marketing website, web diagnostic application, REST + WebSocket
backend, OBD-II/CAN/ISO-TP/UDS diagnostic engine, vehicle simulator, Android
client architecture, and PostgreSQL persistence — built without any access to
proprietary code.

> **Provenance note.** The feature landscape was researched from *publicly
> observable* behaviour of comparable products (see `research/`, including the
> `NOT PUBLICLY OBSERVABLE` table). All implementation here is original.
> VEHDiag has its own brand identity: purple-centered palette, original logo,
> icons and copy.

---

## Quickstart

```bash
npm install
VEHDIAG_SECRET=dev-secret PORT=8080 node services/api/server.js
```

One process serves everything:

| Endpoint | What |
|---|---|
| `http://localhost:8080/` | Marketing website |
| `http://localhost:8080/app/` | Web diagnostic app (**Try the demo — no signup**) |
| `http://localhost:8080/api/v1` | REST API (OpenAPI: `/openapi.json`, `docs/openapi.json`) |
| `ws://localhost:8080/ws` | WebSocket realtime (live data, scan progress, notifications) |
| `tcp://localhost:35000` | ELM327-over-TCP simulator (`ATZ`, `010C`, …) |
| `http://localhost:8080/downloads/` | `VEHDiag.apk`, `VEHDiag.zip`, `SHA256SUMS.txt` |

Default storage is a zero-dependency JSON file (`data/db.json`). Set
`DATABASE_URL` to use **PostgreSQL** instead (see below).

## Demo

Open `/app/` and press **“⚡ Try the demo — no signup”**. It signs you into a
provisioned demo account (`demo@vehdiag.app` / `demo1234`, overridable via
`VEHDIAG_DEMO_EMAIL` / `VEHDIAG_DEMO_PASSWORD`). Everything is real: sessions,
scans, DTCs, live data and reports are produced by the simulator, not mocked.

Create a session (e.g. *Sedan · Petrol 1.5L*), run a full scan — you will see
`P0130` (stored, with freeze frame) and `P0351` (pending), the VIN
`MA3JF31S6MK441207`, protocol `A6` and ECU info. Then open **Live Data** or
type `010C` in the OBD terminal.

## Diagnostics engine (`diagnostics/`)

| Module | Scope |
|---|---|
| `obd/` | SAE J1979 codec: PID decode/encode formulas, DTC packing, mode 09 |
| `can/` | `CanFrame` + `CanInterface` (adapter contract: SocketCAN/PCAN/Kvaser/Vector/Simulation) |
| `isotp/` | ISO-TP (ISO 15765-2) sender/receiver, flow control, sequence + timeout errors |
| `uds/` | UDS (ISO 14229-1): sessions, security access, DIDs, 0x78 polling, NRCs |
| `dtc/` | DTC validation/decode/severity + bundled library (~110 codes) |
| `ecu/` | ECU registry: ICE (ECM/TCM/ABS) and EV (BMS/VCU/MCU/OBC) with CAN addressing + DIDs |
| `simulator/` | 4 vehicle profiles (ICE sedan, EV scooter, motorcycle, diesel truck); real ELM327 AT-command surface **and** UDS-over-ISO-TP-over-CAN; fault injection (`no_response`, `nrc78`, …) |

**UDS security policy** (never bypassed): `0x27` requires a legitimate
`keyFromSeed` provider (wrong keys → NRC `0x35`); `0x2E` requires prior `0x27`
success (else NRC `0x33`); `0x34` flashing is not authorized. The simulator
uses its own documented demo algorithm only.

## Backend (`services/api/`)

Clean layers: routes → `lib/runtime.js` (DiagnosticRuntime) → diagnostics
engine. Auth: scrypt password hashing (never plaintext), HMAC-signed tokens,
RBAC (`USER`, `TECHNICIAN`, `WORKSHOP_ADMIN`, `ADMIN`, `SUPER_ADMIN`).
Security: rate limiting, security headers, CORS allowlist, per-request audit
logging, ownership checks on every resource.

The 8-stage scan orchestrator drives real ELM/UDS traffic
(`ATZ → ATDPN → 0100 → 0902 → 03/07 → 0202 → ECU info`) and streams progress
over WebSocket; live data streams every 500 ms.

## PostgreSQL

```bash
DATABASE_URL=postgres://user:pass@host:5432/vehdiag node scripts/migrate.js   # apply migrations
DATABASE_URL=postgres://… node services/api/server.js                        # run on PG
```

`database/migrations/0001_init.sql` defines the full schema (users, vehicles,
sessions, reports, devices, subscriptions, notifications, audit). The
`PostgresStore` adapter implements the same interface as the JSON store
(read-through, write-behind). Integration test:
`VEHDIAG_TEST_PG_URL=… node --test tests/e2e/postgres.integration.test.js`.

## Android app

`downloads/VEHDiag.apk` is built **without a JDK or Android SDK** by
`scripts/build-apk.py`: binary `AndroidManifest.xml` (AXML chunks), a minimal
`classes.dex` (WebView shell loading the releases page — OTA-style client),
and a v1 (JAR) signature via openssl CMS (SHA-256 digests; minSdk 24,
targetSdk 29). `scripts/verify-apk.py` re-parses the AXML, the DEX and
re-verifies every signature digest. The Bluetooth diagnostic client is the
documented roadmap architecture; install-on-device is not covered in CI (no
device) — verify with `apksigner verify` before sideloading.

Signing keys are generated into `keys/` (gitignored — **keys are never
committed**); release builds use a CI secret.

## Tests

```bash
node --test tests/engine/   # 30: OBD/CAN/ISO-TP/UDS/DTC/ECU + simulator ELM+UDS
node --test tests/unit/     # config + PostgresStore (fake client)
node --test tests/e2e/      # REST smoke + WebSocket flow (needs a running server)
```

All suites are green in this workspace (`tests/` also records the e2e
contracts: auth envelope `{data:{token,user}}`, WS message types, scan
stage percentages, session isolation).

## Layout

```
apps/{web,dashboard}      marketing site + web diagnostic SPA
services/{api,simulator}  single-process app server + TCP ELM simulator
packages/config           shared validated configuration
diagnostics/*             engine (obd, can, isotp, uds, dtc, ecu, simulator)
database/migrations/      PostgreSQL migrations (scripts/migrate.js)
scripts/                  APK builder + verifier, migration runner
tests/{engine,unit,e2e}
research/  design-system/  branding/  docs/
```

## Roadmap

- Android Bluetooth client (ELM327 SPP) with OTA update flow — architecture
  documented in `docs/`
- CAN hardware adapters (SocketCAN/PCAN/Kvaser/Vector) behind `CanInterface`
- Workshop multi-user workspaces + report sharing
- Play Store listing (placeholder `com.vehdiag.app`)

## License

MIT — see `LICENSE`.
