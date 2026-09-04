# VEHDiag Research — Unknowns & Non-Public Items

Date: 2026-09-01.

| Item | Classification | VEHDiag handling |
|---|---|---|
| InDiag backend implementation | NOT PUBLICLY OBSERVABLE | Independent backend (Node.js API, JSON→PostgreSQL path) |
| InDiag ECU/diagnostic databases & protocol stacks | NOT PUBLICLY OBSERVABLE | Independent OBD-II/UDS/ISO-TP/CAN implementations + seeded public-domain DTC library |
| InDiag app source code | NOT PUBLICLY OBSERVABLE | Independent Android app (VEHDiag) — own code, own signing |
| InDiag exact pricing | INFERRED (shop shows kits; prices not captured in public fetch) | VEHDiag defines own pricing tiers |
| Exact APK download URL on indiag.co | UNKNOWN (not present in public HTML; Play Store is the observed primary channel) | VEHDiag hosts own APK at /downloads/VEHDiag.apk |
| InDiag scan-engine accuracy/behavior details | NOT PUBLICLY OBSERVABLE | VEHDiag documents its own engine + simulator-based test evidence |
| EV diagnostics depth per vehicle model | OBSERVED (marketing claims) | VEHDiag ships EV ECU profile architecture + documented profiles |
