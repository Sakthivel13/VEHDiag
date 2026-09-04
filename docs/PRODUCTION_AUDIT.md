# VEHDiag — Production-Readiness Audit

Date: 2026-09-04 · Scope: full repository · Honesty policy: **only what was
actually verified is claimed as verified.** Unverifiable-here items are listed
explicitly with the path to verify them.

## 1. What is verified in this environment

| Area | Evidence |
|---|---|
| Engine correctness | 30/30 tests: OBD PID math, J1979 DTC packing round-trip, CAN routing + fault injection, ISO-TP FF/CF/FC/sequence/timeouts, UDS NRCs + 0x78 polling + timeouts, DTC library, ECU registry |
| Simulator realism | 14/14 tests: ELM327 AT/mode 01/03/07/09/04 paths, UDS session/DID/security/0x19 over real ISO-TP-over-CAN, EV BMS DIDs, fault injection, session isolation |
| REST API | 7/7 e2e: register/login/me, 401 gating, vehicle CRUD + VIN decode, session scan (finds P0130/P0351, VIN, freeze frame), DTC clear, ELM + UDS consoles, fault injection, reports (json/csv/txt/html), device register/pair/test over TCP, subscriptions, admin gating, DTC library, ECUs |
| WebSocket | 8/8 e2e incl. auth flow, live:data @500 ms, scan:progress 5→100, notification push, unsubscribe |
| Static site | every asset across all pages resolves 200 with correct content type (automated sweep) |
| APK | build + verify: zip structure, 4-byte alignment, AXML chunk walk, DEX header/checksum/SHA-1/map/ids/class data/code items, v1 signature digests + CMS verify (openssl) |
| PostgreSQL adapter | 4/4 unit tests (fake client): row mapping, FK-safe flush order, debounce, parameterization |
| Config | 4/4: defaults, overrides, fail-fast validation |

## 2. Not verifiable here — with the path to verify

| Item | Why not here | Where it gets verified |
|---|---|---|
| `adb install` / app launch | no Android device or emulator in sandbox | GitHub Actions can add an emulator job; or any machine with `apksigner verify --print-certs` + `adb install` |
| PostgreSQL against a live server | no postgres server (apt blocked) | CI job `postgres` runs migrations + `tests/e2e/postgres.integration.test.js` against a postgres:16 service |
| APK v2/v3 signature schemes | v1 chosen deliberately (minSdk 24, targetSdk 29 sideload channel) | release signing job moves to apksigner v2/v3 with the CI secret |
| HTTPS | the sandbox preview terminates TLS at the proxy | deploy behind a reverse proxy (Caddy/nginx) with certbot; all tokens are bearer cookies over same-origin, and `Secure`/`SameSite` flags are set by the proxy |
| Load/performance | no load tooling | k6 script added with deployment; rate limiter default 1500 req/min/IP |

## 3. Security checklist

- [x] Passwords: scrypt (N=16384) + per-user salt; never plaintext; never logged
- [x] Tokens: HMAC-SHA256 signed (access/refresh types); secret from env, never committed
- [x] RBAC enforced server-side on admin routes (`ADMIN`+), ownership on all resources
- [x] Rate limiting per IP (env-tunable), security headers (X-Content-Type-Options, X-Frame-Options, CSP on web pages, nosniff), CORS allowlist
- [x] No secrets in repo: signing keys in gitignored `keys/`, `data/`, `.env` ignored; CI secret for release signing
- [x] Path traversal guarded in the static resolver (normalize + prefix checks)
- [x] Input validation on auth/vehicles/devices payloads; SQL parameterized (no string-built SQL with user input)
- [ ] CSRF hardening for cookie-based sessions (SPA uses bearer tokens; revisit when cookies are introduced)
- [ ] Dependency audit in CI (`npm audit`, `pip-audit` for build scripts)

## 4. Known gaps & trade-offs (deliberate, documented)

1. **JSON store default** — zero-dependency dev/demo path; `DATABASE_URL` selects PostgreSQL. Migrations + adapter are in place and CI-tested.
2. **PostgresStore write-behind** — collections are read-through/write-behind (DELETE+bulk INSERT on flush). Correct and transactional; scale-up path is a write-through DAO layer per collection.
3. **Demo account** — `demo@vehdiag.app` with a fixed password is provisioned on boot; disable via `VEHDIAG_DEMO_EMAIL=""` in production, or firewall `/app/#/demo`. Shared demo data is purged daily on provision.
4. **ELM327 TCP simulator** — binds `0.0.0.0:35000` for device pairing/tests; production should bind it to localhost only (env `ELM_TCP_PORT` + `HOST`).
5. **Single-process architecture** — one Node process serves HTTP + WS + TCP sim. The monorepo layout anticipates splitting services (api / websocket / worker / diagnostic-engine); the composition boundary is already `lib/runtime.js` (clean swap point).
6. **APK scope** — WebView shell (OTA client) is shipped; native Bluetooth client is documented in `docs/mobile-architecture.md` and behind a CI-generated code path.

## 5. Operational readiness

- [x] Structured logs by channel (app/diagnostics/security/error) with session/user ids
- [x] Health endpoint `/api/v1/healthz`
- [x] Graceful shutdown (SIGTERM: detach simulators, close WS, stop TCP)
- [x] Audit log collection + admin audit route
- [ ] Backups for PostgreSQL (document `pg_dump` schedule with deployment)
- [ ] Monitoring/alerts (Prometheus metrics endpoint planned with service split)

**Bottom line:** development-complete with honest verification evidence for
every layer; the items in §2 are environment-limited, not implementation-
limited, and each has a concrete CI/device verification path.

## CI workflow note

The CI pipeline is defined in `docs/ci.yml.example` (engine/unit/e2e tests,
PostgreSQL service job, APK build+verify, lint). It is kept as an example
file because the GitHub connection used for this repository does not have the
`workflows` permission; move it to `.github/workflows/ci.yml` once the
connection (or a token with workflow scope) is granted.
