# SAE J1939 reference

## Identifier

J1939 always uses the 29-bit identifier:

```
| priority (3) | reserved (1) | data page (1) | PDU format (8) | PDU specific (8) | source address (8) |
```

* PDU format < 240 (PDU1): destination specific, PDU specific is the target.
* PDU format >= 240 (PDU2): broadcast, PDU specific is part of the PGN.

`0x18FECA00` = priority 6, PGN 0xFECA (DM1), source address 0x00.

## Common PGNs

| PGN | Name |
|-----|------|
| 0x00E800 | acknowledgement |
| 0x00EA00 | request |
| 0x00EB00 | TP.DT transport protocol data transfer |
| 0x00EC00 | TP.CM transport protocol connection management |
| 0x00EE00 | address claimed |
| 0x00EF00 | proprietary A |
| 0x00FECA | DM1 active diagnostic trouble codes |
| 0x00FECB | DM2 previously active DTCs |
| 0x00FECC | DM3 diagnostic data clear |
| 0x00FED3 | DM11 clear active DTCs |
| 0x00F004 | electronic engine controller 1 |

## Transport protocol

Messages above eight bytes are segmented:

* **BAM** (broadcast): TP.CM with control byte 0x20, then TP.DT packets.
* **RTS/CTS** (destination specific): 0x10 request to send, 0x11 clear to send,
  0x13 end of message acknowledge, 0xFF abort.

Each TP.DT packet carries a sequence number plus seven data bytes, so the
maximum payload is 255 × 7 = 1785 bytes.

## Address claiming

A node broadcasts PGN 0xEE00 with its 64-bit NAME. On a conflict the lower NAME
wins; the loser either claims another address (when arbitrary address capable)
or goes silent with the null address 0xFE. Address 0xFF is the global address,
and 128–247 is the range for diagnostic tools (0xF9 by convention).

## Diagnostic messages

DM1 and DM2 carry two lamp status bytes followed by four byte DTC records:

```
| SPN low (8) | SPN mid (8) | SPN high (3) + FMI (5) | CM (1) + occurrence (7) |
```

Failure mode identifiers 0–31 describe the fault: 0 above normal (severe),
1 below normal (severe), 3 voltage high, 4 voltage low, 5 open circuit,
31 condition exists.

## Usage

```python
from src.communication.protocols.j1939 import J1939Id, J1939Protocol, parse_dm

identifier = J1939Id.from_can_id(0x18FECA00)
identifier.pgn, identifier.source_address, identifier.name

protocol = J1939Protocol(driver, {"source_address": 0xF9})
protocol.initialize()
message = protocol.read_active_dtcs()
for dtc in message.dtcs:
    print(dtc)                  # SPN 238 FMI 4 (voltage below normal) x1
protocol.clear_active_dtcs()
```
