# Diagnostic operations

Every service has its own tab under *Diagnostics*. All of them share the same
structure: request parameters at the top, a send button, the decoded response
below and a history.

## Session control (0x10)

Choose a standard session or type a manufacturer specific sub-function. After a
positive response the panel shows the negotiated P2/P2* values and an S3
countdown; the keep-alive starts automatically for non-default sessions.

## Read DID (0x22)

* Type a DID or pick one from the predefined library (loaded from
  `config/did_definitions.yaml`).
* **Add to list** builds a batch; **Read all** reads them in one request when
  the ECU supports it and falls back to single reads otherwise.
* The response is shown as hex, ASCII and parsed value (ASCII, unsigned,
  signed, BCD or a scaled physical value with its unit).
* **Continuous read** polls at a configurable interval.
* **Analyse** sends the response to the slicer and the converter.

## Read DTC (0x19)

* All 18 sub-functions are selectable.
* The status mask is built from the eight checkboxes (TF, TFTOC, PD, CD,
  TNCSLC, TFSLC, TNCTOC, WIR).
* Results are sortable and colour coded: red confirmed, amber pending.
* Selecting a row decodes every status bit; **Read snapshot** and
  **Read extended data** fetch the freeze frame and the occurrence counters.
* Export to CSV or HTML.

## Clear DTC (0x14)

Select a group (all, powertrain, chassis, body, network) or enter a specific
three byte DTC. A confirmation dialog warns that the operation is irreversible;
afterwards a before/after table shows exactly what was cleared.

## Security access (0x27)

1. Choose the level (`0x01`, `0x03`, … or a programming level such as `0x11`).
2. Choose the algorithm source: built-in, external DLL/SO, Python script or a
   manually entered key.
3. **Auto unlock** performs the seed request, the key computation and the key
   submission in one step and visualises each stage.

The panel tracks the attempt counter and the mandatory delay after
`exceededNumberOfAttempts`.

## Routine control (0x31) and I/O control (0x2F)

Routine control offers start, stop and request-results plus the standard
routines (erase memory, check programming dependencies). I/O control supports
return-control-to-ECU, reset-to-default, freeze and short-term adjustment.

## Tester present (0x3E)

Send a single keep-alive or enable the automatic scheduler. The interval
defaults to 2 s, comfortably below the usual 5 s S3 timer, and the panel
reports how many messages were sent and how many failed.

## Raw request

Free-form hexadecimal entry with validation, service auto-completion, a history
of recent payloads and functional addressing. This is the fastest way to try an
OEM specific service.

## Negative responses

Every NRC is translated into a readable sentence plus a recovery hint, shown as
a toast and in the log. `0x21 busyRepeatRequest` and `0x78 responsePending` are
handled automatically.
