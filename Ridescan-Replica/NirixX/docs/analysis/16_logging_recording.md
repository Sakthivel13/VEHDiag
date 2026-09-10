# 16 — Logging Architecture & Screen Recording

## A. Logging

### 1. Session & file naming [LOG][VIDEO][IMG — fully cross-decoded]
```
sessionId = <vciSerial><dd><MM><yyyy><HH><mm><ss>
log file  = <sessionId><VIN>.txt
50280823012026031513  + MD625AF99T1A25267.txt   (VCI 502808, 23-01-2026 15:15:13)   [LOG1 name+header]
50280829012026105706  + MD638AN2100000000.txt   (VCI 502808, 29-01-2026 10:57:06)   [LOG2 name+header]
footer chip 50280820012026102748                 (same VCI, 20-01-2026 10:27:48)     [IMG 105007386]
footer chip 50485617032026041703                 (VCI TechPRO_504856, 17-03-2026 04:17:03) [VIDEO every frame]
```
Rule proven by 4 independent artifacts agreeing on one format. [XREF ×4]

### 2. File header (complete field set, both logs identical schema) [LOG]
```
Device: samsung (SM-T225) | Android: 14 | Android SDK: 34
App Name: RIDE Scan 2.0 | App Version: 2.2.5 (190) | Domain: DMS
Latlong: 12.7377292,77.7871911 | Dealer Name: peethala.rajiv | Dealer Code: 12345
Session ID: 50280823012026105706 | Firmware Version: 1.07
```

### 3. Line schema
`yyyy-MM-dd HH:mm:ss.SSS <level>/<tag>: <payload>` — observed:
- `I/: [CONNECTIVITY_TYPE]: --> bluetooth` (session start marker)
- `I/: TX: --> <canId> -> <payloadHex>` / `RX: --> <canId> -> <payloadHex>` (diagnostic frames,
  ISO-TP reassembled payloads)
Level/tag taxonomy beyond `I/` (warnings, UI events, errors): **not present in captures** —
the in-field logs are comms-centric; broader event logging = Requires Validation. [LOG]

### 4. Storage / sync / export
- Local file per session; `log_viewer/LogViewerActivity`, `file_viewer/FileViewerActivity`;
  upload via `service/FileUploadWorker` + `ClientService`; retention/deletion policy UNKNOWN;
  export via system share sheet [INFERENCE from FileViewer + Android patterns]. [SRC][LOG]
- Every diagnostic op chains `user tap → TX/RX lines → UI result` inside the same file →
  post-hoc session replay is exactly what these files are for. [LOG][XREF video↔log timelines]

### 5. Sensitive-data handling
Header carries dealer identity + GPS coordinates — plain text; treat as confidential in NirixX
storage/export (we keep them in private app storage only). No VCI PINs/keys appear. [LOG][XREF]

## B. Screen recording

| Aspect | Evidence | Value |
|---|---|---|
| Library | com.hbisoft.hbrecorder in dex | [SRC] |
| On-screen affordance | floating circular RIDE-Scan bubble anchored right edge, present across screens in the video (it IS the recorded app observing itself) | [VIDEO f01–f42] |
| Strings | "Recording your screen", "Drag down to stop the recording" (notification), "Registering"(?) start | [SRC resources.txt] |
| Start/stop | manual via bubble/notification; pause/resume UNKNOWN | [VIDEO][SRC][INFERENCE] |
| Auto-start on flash? | not observed; video records VHR — either is possible | UNKNOWN / Requires Validation |
| Output | mp4 (the reference artifact is 382×850 h264) — in-app gallery vs gallery app: UNKNOWN | [VIDEO artifact] |
| Association | recordings are device-level; session association via timeline only | [INFERENCE] |

## C. NirixX parity
- Session-id format, header schema, TX/RX line format: reproduced 1:1 shape (our header swaps in
  NirixX app/identity fields) — `core/diag/DiagEngine` + FileProvider export.
- Live-data CSV recording + on-device viewer: implemented.
- Screen recording behind the same bubble affordance: NirixX uses MediaProjection directly
  (framework-only, no HBRecorder) — same interaction model; auto-start flags off by default.
- Upload of logs/PDFs: MISSING (DMS dependency) — documented.
