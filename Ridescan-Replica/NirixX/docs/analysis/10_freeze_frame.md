# 10 — Freeze Frame Specification

## 1. Verdict from evidence
**Not exercised and not exposed in the observed build pair (2.2.5 / 2.3.0).**

| Probe | Result | Evidence |
|---|---|---|
| UDS `19 03` (DTC snapshot identification) | 0 occurrences | [LOG both, full-text scan] |
| UDS `19 04` (DTC snapshot by DTC number) | 0 occurrences | [LOG both] |
| UDS `19 06` (DTC extended data) | 0 occurrences | [LOG both] |
| OBD-II mode `02` (freeze frame PID data) | 0 occurrences (only 01/09 used) | [LOG both] |
| UI strings/classes for "freeze"/"snapshot" | none ("freeze"/"snapshot" substrings absent from resource dump) | [SRC resources.txt] |
| Any photograph/video of a freeze-frame screen | none | [IMG][VIDEO] |

## 2. Consequence for parity work
- There is **no reference behavior to copy**. Any freeze-frame feature in NirixX is NEW design,
  not parity. It must not be presented as reference-matching.
- The DTC pipe itself (`19 02 FF` + 4-byte entries) is the only fault-data channel the reference
  uses in the field; per-entry "status" byte is its entire temporal context.

## 3. Standards-based recommendation (implementation-ready when data arrives)
When the OEM definition pack lands, the natural upgrade path (and service manual flows) is:
```
19 03 FF            → list of DTCs carrying snapshots
19 04 <DTC3B> 00    → snapshot record 0 (or per stored record)
decode via per-DID mapping of the snapshot record to parameter names/units
display: expandable section under the DTC row; include in VHR/Diagnostic report if populated
```
- OBD-II lane alternative: `02 <pid>` + `02 02` DTC-that-stored-FF on emissions ECUs.
- Role: display to both roles (read-only). No destructive surface.
- Logging: same session log, service-tagged.

## 4. NirixX status
Missing (by evidence-faithful choice) — tracked in 18_implementation_matrix.md and
MISSING_DEPENDENCIES.md ("per-model ODX/CDD definition packs" includes snapshot layouts).
`UdsClient` already tolerates adding 19 03/04 without protocol work (RCRP + multi-frame paths
are proven by VIN/DTC traffic and unit tests).
