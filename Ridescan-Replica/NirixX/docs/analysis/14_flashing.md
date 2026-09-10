# 14 — ECU Flashing / Campaign Workflow

> Safety-critical. This document separates **Observed behavior** from **Requires Validation**
> and **Implementation recommendation**, per the master brief. No flashing step below was
> invented; where the wire protocol is unobserved it says so.

## 1. Surface area (evidence)
- 15 supplier-specific flash flows in the binary:
  `kems_flash` (Keihin KEMS), `keihin_flash_sport`, `conti_flash`, `conti2_flash` (Continental),
  `mikuni_can_flash`, `sedemac_ems_flashing` (+ `u558`, `sedemac_xl_100_obd2b_flash`),
  `pricol_flash/u400/tpms`, `n597_cluster_flashing`, `u732_{tft,rlcd}_cluster_flash`,
  `u577_{premium,basic}_cluster_flash`, `u796_cluster_flashing`, `abs_flashing_conti`,
  `babs2_flashing`, `keyless_ecu_flashing`, `new_ecu_flashing`, plus
  `vin_based_flashing/VINBasedFlashingActivity`. [SRC]
- Flash catalogue: `flash_variant.json` — **22 variants → 60 packages**, each with `value`
  (package key), `ecu` (`EMS | EMS-OBDII | KEMS | ICU | SEMS-OBDII-B`), `norm` (`BSVI`),
  human `description` (hardware-differentiator notes: "White Ignition Coil Coupler",
  "GPS Coupler Colour- Black/White", "Pulse make vs Bremi make Ignition coil (before/after
  31.07.2022)", SIDESTAND / KILL SWITCH / AHO / digital-cluster options…). [JSON]
- Strings lifecycle: "Downloading HEX file", "Do not close the app until the flash is completed",
  "ECU Flashing" / "ECU Flashing completed", "ECU Reset", "ECU Security Authentication",
  "Transfer Data for %1$s", "Request". [SRC]
- Screens in burst photos: model/variant selection ("Please select FL VIN"-class), package list
  rows (`TVS FLASH_…`), "Select a File System (Proprietary)" chooser dialog, "GET SECRET KEY"-style
  input dialogs (several), progress dialogs, orange "Continue??" confirm, red failure header,
  green success header. [IMG burst r3–r7]
- **Per-ECU restriction example**: ICU ECU-diagnosis footer "Please contact TVS for ECU related
  flashing" — flashing can be policy-disabled per ECU even for engineers. [IMG 105128019]

## 2. Observed/derivable workflow
```
Entry: Home → Flashing (engineer) → pick Model/Variant (or VIN-Based Flashing → auto variant)
  1. Variant screen binds model (VIN or manual)                       [IMG][SRC]
  2. Package selection from model_list (description disambiguates
     hardware batches, couplers, side-stand/kill-switch options)      [JSON][IMG]
  3. Download HEX package ("Downloading HEX file")                    [SRC strings]
  4. Preconditions UI: battery/voltage & caution dialogs observed
     ("Actuate Starter Relay…" family battery cards, 12.3 V readout)  [IMG][INFERENCE]
  5. "GET SECRET KEY"-class dialog → ECU Security Authentication      [IMG][SRC]
       (UDS 10 03 → 27 01/27 02 chain is the proven secured-entry
        mechanism for all privileged ops — flashing follows it)       [LOG2][XREF]
  6. Transfer ("Transfer Data for <ecu>"), progress dialog,
     app-exit locked ("Do not close the app until the flash …")       [SRC strings][IMG]
  7. Verification + ECU Reset ("ECU Reset")                           [SRC strings]
  8. Result: green success / red failure dialog; entry logged         [IMG]
```
**Wire-level detail (0x34 RequestDownload, 0x36 TransferData, 0x37 TransferExit, 11 ECUReset):
NOT captured in any evidence.** Bootloader session type (0x02 programming vs 0x03 extended),
memory addresses, block sizes, checksum scheme → **Requires Validation**; do not ship against
assumptions. NirixX's `FlashRunner` implements the textbook 34/36/37 inside its own documented
boundaries and clearly flags it as non-validated-against-reference (`MISSING_DEPENDENCIES.md`).

## 3. Safety-critical checkpoints (parity contract)
| # | Checkpoint | Evidence | NirixX enforcement |
|---|---|---|---|
| 1 | Role = Engineer | [XREF] | entry guard (`Roles`) |
| 2 | Variant/package binding explicit (VIN or chosen) | [JSON][IMG] | SupplierFlash flow |
| 3 | Battery/tablet charge precondition surfaced before start | [IMG][INFERENCE] | implemented (transport/device charge probe + dialog) |
| 4 | SecurityAccess seed-key precedes programming | [LOG2 pattern][IMG dialogs] | implemented abstractly; OEM algorithm missing (key entered via dialog when provided) |
| 5 | UI lock during transfer; no navigation away | [SRC strings][IMG] | implemented (modal) |
| 6 | Per-ECU flash permission ("Please contact TVS…") | [IMG] | policy flag per ECU row |
| 7 | Result + re-identify after reset; failure explicit | [IMG][SRC strings] | implemented dialog + session log |
| 8 | Everything logged | [LOG format][SRC] | implemented |

## 4. Recovery / failure
- Observed artifacts: red failure dialog; "Download failed" string; no evidence of a
  bootloader-recovery flow in app (recovery likely vendor-tool side — "Email link for VCI Update
  Tool" exists for VCI; ECU-side unknown). [SRC] **Recovery semantics = UNKNOWN / Requires Validation.**
- Interruption of flash (VCI drop / app kill) has no graceful path by design ("Do not close…"). [SRC]

## 5. Campaign vs local package
- `new_ecu_flashing` + "Downloading HEX file" ⇒ server-hosted packages chosen by
  variant (campaign semantics), while "Select a File System (Proprietary)" dialog suggests a
  local-file channel too. Exact eligibility checks (DMS round-trip) UNKNOWN. [SRC][IMG][INFERENCE]

## 6. NirixX gaps (tracked)
- True supplier bootloader flows per family (need vendor docs/binaries).
- Campaign eligibility backend (DMS API).
- CALID↔package-family validation automation (N597 ↔ n597_cluster_flashing mapping is visible:
  [XREF LOG2 CALID] vs [SRC]) — implementable now as a config table.
