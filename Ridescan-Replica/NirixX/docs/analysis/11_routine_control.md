# 11 — Routine Control (0x31) Specification

## 1. Observed wire sequence [LOG2 2026-01-29 11:06:02 & 11:06:36, twice]
```
TX 7E0 10 03            RX 7E8 50 03 00 32 01 F4     # extended session
TX 7E0 27 01            RX 7E8 67 01 <8B seed>       # SecurityAccess REQUIRED first
TX 7E0 27 02 <8B key>   RX 7E8 7F 27 78 → 67 02      # key accepted
TX 7E0 31 01 02 11      RX 7E8 71 01 02 11 01        # startRoutine, RID 0x0211
# …over following ~3 s: periodic 3E 00 keep-alives, no stop/result-request frames
```
- Only RID **0x0211** observed, twice consecutively (~34 s apart), with `01` = start,
  response statusByte `01`. [LOG2]
- RID catalogue, per-RID parameter records, stop (31 02) / result (31 03) usage:
  **UNKNOWN / Requires Validation** (ODX dependency).
- Semantic mapping hypothesis: RID 0211 executed right after SecurityAccess inside the same
  secured window that later issues `2F A8 00` IO control (11:06:57) — consistent with a
  service-bay actuation/test enable group. [INFERENCE]

## 2. UI evidence
- `RoutineControlActivity` (with 1 inner class → simple list+confirm) and
  **`gear_learning_procedure/GearLearningActivity`** — a named, guided routine flow
  (gear learning) with its own screen. [SRC]
- Burst row-5 photos show a "CONTINUE??"-class confirm dialog before a routine (orange header). [IMG r4 t8]
- Routine list is ECU-scoped (from ECU Diagnosis grid). [IMG 105128019 tile]

## 3. Behavioral contract (evidence-grounded)
| Step | Rule | Evidence |
|---|---|---|
| Select routine | list from per-ECU catalogue | [SRC][IMG] |
| Configure | optional params (not observed) | UNKNOWN |
| Preconditions | extended session + SecurityAccess (27) immediately before start | [LOG2] |
| Start | `31 01 <RID2B> [params]` → expect `71 01 <RID> <status>` | [LOG2] |
| Monitor | tester-present keep-alive; NO progress polling observed | [LOG2] |
| Stop/result | `31 02/31 03` defined but never seen | UNKNOWN |
| Role | Engineer (guided subset for Service via GearLearning) ⚠ | [03_roles.md] |
| Failure | NRC 31 (RID unknown), 24 (sequence), 22 (conditions), 33 (security) — standard; observed none | [INFERENCE] |

## 4. NirixX parity
Implemented: `RoutineControlActivity` with secured start (10 03 + 27 chain via UdsClient),
RID catalogue hook behind definition pack, GearLearning edge. Open: OEM RID catalogue +
param/result layouts (MISSING_DEPENDENCIES.md).
