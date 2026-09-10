# 09 — GTS (Guided Troubleshooting Steps)

## 1. What the evidence proves
- A dedicated **`gtsviews/GTSViewActivity`** ships in the application. [SRC]
- It is a **single lightweight Activity (one class, no inner flows)** — a *viewer*, not an
  interactive wizard engine: no step/decision classes, no measurement-capture classes, no
  Bluetooth chatter attributable to it in logs. [SRC][LOG]
- The name family ("views") + read-only class shape indicate: DTC-linked **troubleshooting
  content pages** (inspection steps, wiring hints, specs), opened from DTC context. [INFERENCE]

## 2. What is NOT evidenced (do not over-implement)
- No step-state machine, no branching decisions driven by live measurements, no pass/fail
  capture, no "evidence attachment", no structured final-diagnosis record.
- No GTS traffic on CAN (no service correlates). [LOG]
- No media shows a GTS screen open (137 photos + video + contacts). [IMG][VIDEO]
⇒ Treat interactive/decision-tree GTS in the reference build as **UNKNOWN / Requires
Validation**; the shippable, defensible core is the **viewer bound to DTC codes**.

## 3. Trigger & relationship to DTC
- Probable link: ReadDTCs row (or DTC detail) opens GTSView for that fault code. [INFERENCE]
- Content storage: static app bundle vs DMS download — **UNKNOWN** (no network capture;
  DMS domain exists [LOG header]).

## 4. Observable UX contract to reproduce (minimal, safe)
- Opened per-DTC; title carries the fault code; scrollable structured content; back returns to
  DTC list; no write/actuation capability inside GTS. [INFERENCE — matches class shape]
- Role: available to both roles (read-only content). [INFERENCE]

## 5. Decision-tree/state machine (if OEM content later demands interactivity)
`GTS_CLOSED → OPEN(dtc) → STEP_1 … STEP_n {measure? → read via 22 → compare → branch} →
CONCLUSION {repair-ok | escalate}` — design only, **no evidence in reference build**; flagged
here so NirixX does not block on it. See 17_state_machines.md §7.

## 6. NirixX status
- Now: GTS not exposed (parity-safe absence; DTC detail carries code + description + NRC text).
- Planned (cheap, evidence-aligned): `GTSViewerActivity` bound to DTC rows, content from the
  per-model definition pack when it arrives; marked in MISSING_DEPENDENCIES.md.
