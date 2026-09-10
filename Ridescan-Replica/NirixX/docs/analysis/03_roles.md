# 03 — Authentication, Roles & Permission Matrix

## 1. Identity model [XREF]
- Dealer account = **Dealer ID + Branch ID + official email** (`@tvsmdealers.co.in` policy
  string; consumer emails observed accepted in practice: `neotvs@gmail.com` [PDF],
  `peethala.rajiv` w/ code `12345` [LOG], `techpro@gmail.com` OTP string [SRC]).
- Device bound at login: VCI serial + connectivity captured into session id and log header. [LOG][VIDEO]
- Credentials: **6-digit email OTP** → **4-digit PIN** for repeat logins; Forgot-PIN resets via OTP. [SRC strings][IMG keypad dialogs]
- SSO dealership login path exists (`SSOActivity`). [SRC] — trigger & flow UNKNOWN / Requires Validation.
- GPS location stamped at session start (log header `Latlong`). [LOG]
- Session expiry: no inactivity expiry observed; a session persists until logout/VCI loss.
  Exact server token TTL: UNKNOWN.

## 2. Roles observed
Two designation families are visible via the Login wizard's **Designation** step and
`UserTypeActivity` [VIDEO f01][SRC]. The UI role split implemented by prior NirixX analysis
(and matching the master brief) is:

| Role | Intent | UI differences (evidence-based) |
|---|---|---|
| **Dealer Service** | Everyday service-bay operator | Sees auto-VIN → diagnostic happy path; flashing entries hidden/disabled; write-type operations minimized. [XREF home-grid variants in IMG burst][INFERENCE for button-level gating] |
| **Dealer Engineer** | Advanced/power user | Adds flashing/campaign, write DID, manual diagnostics, logs/system tools, VCI firmware. [XREF: engineer-captured media shows flash screens; service videos do not] |

Evidence note: photographs showing flash screens originate from the BT-VCI dealer (12345);
the VHR video originates from dealer 10814. Both roles appear in the dex: no explicit
"role" class survives obfuscation, so **the exact backend role field is UNKNOWN**; the
split is corroborated by [SRC `UserTypeActivity` + designation wizard] + [IMG differing
dashboards] + master-brief description. Treat per-capability row gating as Requires
Validation wherever marked ⚠.

## 3. Role–permission matrix
Legend: ✅ allowed, ❌ hidden/blocked, ⚠ requires validation, n/a not a per-role item.

| Capability (screen) | Dealer Service | Dealer Engineer | Evidence |
|---|---|---|---|
| Dashboard (role grid) | ✅ service set | ✅ extended set | [IMG][SRC] |
| Vehicle selection / auto-VIN | ✅ | ✅ | [LOG][IMG] |
| ECU selection & discovery | ✅ | ✅ | [LOG][IMG] |
| Live Parameters | ✅ | ✅ | [LOG 22xx loops][IMG] |
| Data Watcher | ✅ | ✅ | [SRC] |
| Read DTC | ✅ | ✅ | [IMG 105007386][LOG] |
| Clear DTC | ✅ ⚠ (confirmation; post-clear rescan) | ✅ | [LOG 14 FF FF FF→54][IMG CLEAR DTC button] |
| DID Read (identifiers) | ✅ | ✅ | [LOG F1xx reads] |
| **DID Write** | ❌ ⚠ | ✅ (27 SecurityAccess) | [SRC WriteDataActivity][LOG2 27/2E-gated chain] |
| Routine Control | ⚠ subset (guided e.g. gear learning) | ✅ full | [SRC RoutineControl+GearLearning][LOG2 31 01 0211] |
| Input/Output Control | ✅ guided (VHR IO tab runs actuations) | ✅ | [VIDEO f07–f10][IMG IO toggles][LOG2 2F A800] |
| GTS view | ✅ | ✅ | [SRC GTSViewActivity] |
| Freeze Frame | n/a — not exposed in observed build (see 10_freeze_frame.md) | n/a | [LOG absence][SRC absence] |
| IUPR Primary/Secondary + History | ✅ ⚠ | ✅ | [SRC][LOG 0908/0902/0904] |
| **ECU Flashing / Campaign** | ❌ | ✅ | [IMG flash screens][JSON][SRC ecu_flashing/*] |
| Vehicle Health Report (full wizard + PDF + upload) | ✅ | ✅ | [VIDEO][PDF] |
| Battery Health Report | ✅ | ✅ | [SRC] |
| Reports / Diagnostic Report | ✅ own sessions | ✅ | [SRC] |
| Logs (viewer/files) | ⚠ | ✅ | [SRC LogViewer/FileViewer] |
| Screen Recording | ✅ (floating bubble) | ✅ | [VIDEO][SRC hbrecorder] |
| Service Manual | ✅ | ✅ | [SRC] |
| Intro Videos | ✅ | ✅ | [SRC VideoPlayer/Exo strings] |
| AI Assistant / Chatbot | ✅ | ✅ | [SRC "Welcome to RIDE Scan Chatbot!"] |
| VCI connect/status | ✅ | ✅ | [VIDEO f01][LOG] |
| VCI firmware update | ⚠ prompted w/ 5-skip | ✅ manage | [SRC strings] |
| App Update | ✅ auto-check | ✅ | [SRC Update*] |
| System Monitoring | ⚠ | ✅ | [SRC] |
| Manual Diagnostic (raw service tester) | ❌ ⚠ | ✅ | [SRC ManualDiagnosticActivity] |
| Account/Profile view | ✅ | ✅ | [SRC] |
| Notifications | ✅ | ✅ | [SRC][IMG badge] |
| Administrative (dealer creation etc.) | ❌ backend-only | ❌ backend-only | [INFERENCE: DMS-side] |

## 4. Auth states
`ANON → OTP_SENT → PIN_SET/REMEMBERED → AUTHENTICATED(role) → SESSION_ACTIVE(+VCI,+VIN) → LOCKED?`
- Account switch: "Do you want to change your account? CHANGE" → back to Login. [VIDEO f01]
- Failed OTP/PIN, network-down login behavior: UNKNOWN / Requires Validation (no media).

## 5. NirixX mapping (current v1.6.1)
NirixX implements the same two roles; navigation-level filtering (Home grid) **and**
operation-entry guards on engineer-only screens (flash, DID write, VCI firmware, manual diag),
verified by `tools/audit_links.py` area E. Gaps vs this matrix: SSO (MISSING — needs DMS),
IUPR secondary/history screens, GTS viewer. Details: 18_implementation_matrix.md.
