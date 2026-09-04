# VEHDiag Research — Reference Feature Inventory

Reference: https://www.indiag.co/ (homepage marketing copy, public pages). Date: 2026-09-01.

| Feature | Evidence | Classification |
|---|---|---|
| Scan vehicle / read all DTCs from ECUs | Homepage "Scan Vehicle" card, scan animation (Royal Enfield Classic 350, 68% complete, Engine (ECM) 2, ABS/Brakes scanning) | OBSERVED |
| Clear fault codes | Homepage "Clear Fault Codes" card | OBSERVED |
| Live data stream (RPM, temperature, fuel pressure, O2 sensors) | Homepage "Live Data Stream" card | OBSERVED |
| Emission test / I/M readiness | Homepage "Emission Test" card | OBSERVED |
| Read VIN | Homepage "Read VIN" card | OBSERVED |
| Freeze frame | Homepage "Freeze Frame" card | OBSERVED |
| ECU information (system IDs, HW/SW versions, calibration) | Homepage "ECU Information" card | OBSERVED |
| Read odometer | Homepage "Read Odometer" card | OBSERVED |
| Track mode (0–100 km/h) | Homepage "Track Mode" card | OBSERVED |
| OBD terminal (raw AT + OBD commands) | Homepage "OBD Terminal" card | OBSERVED |
| Multi-language reports (14 Indian languages) | Homepage language section | OBSERVED |
| Branded PDF reports (logo, colors, 3 templates, GST) | Homepage "Brand Control" section | OBSERVED |
| Cross-platform sync (phone/tablet/web), scan history | Homepage "Cross-Platform Sync" (web.indiag.co) | OBSERVED (marketing) |
| EV support (Bajaj Chetak, Hero Vida, Ather; VCU/BMS/MC/charger/DC-DC/aux) | Homepage hero + EV section | OBSERVED |
| OTA updates (new protocols, EV support) | Homepage "Evolves with every update" | OBSERVED (marketing) |
| Hardware: OBD scanner device (shop: Personal/Workshop kits, 1-yr warranty) | /shop | OBSERVED |
| Support: FAQs, chat widget, ticket system | /support | OBSERVED |
| Actual scan engine internals, ECU databases, protocol stacks | Not publicly exposed | NOT PUBLICLY OBSERVABLE |

## VEHDiag implementation decisions

- Equivalent capability scope, independent implementation: OBD-II modes 01/02/03/04/07/09/0A, UDS core services, ELM327/BT/USB/CAN/Simulation adapters, EV ECU profile architecture (BMS/VCU/MCU/OBC/DC-DC).
- Branded PDF reports: VEHDiag implements PDF (print-to-PDF), JSON, CSV export.
- Languages: VEHDiag starts with English (+i18n-ready strings) — no claim of parity with 14 languages.
