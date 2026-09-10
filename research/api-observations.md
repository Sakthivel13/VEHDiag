# VEHDiag Research — Public API Observations

Reference: https://www.indiag.co/ + web.indiag.co (public surface only). Date: 2026-09-01.

## Observations
- No public API documentation, OpenAPI spec, or developer console linked from the public site — OBSERVED (absent).
- Homepage JS is a bundled SPA artifact; no stable public REST endpoints are documented — NOT PUBLICLY OBSERVABLE by design (we do not reverse-engineer private endpoints).
- robots.txt disallows /dashboard, /account, /checkout, /login, /signup, /delete-account — OBSERVED.
- Support contact channels: phone +91 81699 33168, hello@indiag.co, WhatsApp — OBSERVED (public).

## VEHDiag decisions
- Design our own public REST API: `/api/v1/{auth,users,vehicles,diagnostics,dtc,ecus,live-data,reports,devices,subscriptions}` with OpenAPI spec (docs/api.md + openapi.yaml), typed envelopes, pagination, validation, rate limiting.
- WebSocket channel `/ws` for live data, scan progress, notifications.
