# CAN and ISO-TP reference

## Frame format

| Property | Classic CAN | CAN FD |
|----------|-------------|--------|
| Identifier | 11 or 29 bit | 11 or 29 bit |
| Payload | 0–8 bytes | 0–64 bytes |
| Bitrate | up to 1 Mbit/s | arbitration up to 1 Mbit/s, data up to 8 Mbit/s |
| DLC 9–15 | invalid | 12, 16, 20, 24, 32, 48, 64 bytes |

## Diagnostic identifiers

| Identifier | Meaning |
|------------|---------|
| 0x7DF | functional request to every ECU |
| 0x7E0–0x7E7 | physical request to ECU 0–7 |
| 0x7E8–0x7EF | physical response from ECU 0–7 |

## ISO-TP (ISO 15765-2)

| Frame | First byte | Purpose |
|-------|-----------|---------|
| Single | `0x0L` | payload of L bytes (L ≤ 7) |
| First | `0x1L LL` | start of a message of `LLL` bytes |
| Consecutive | `0x2N` | continuation with sequence number N (1..15, wraps to 0) |
| Flow control | `0x3S BS ST` | S = status, BS = block size, ST = STmin |

Flow status: `0` continue to send, `1` wait, `2` overflow.

STmin encoding: `0x00`–`0x7F` are milliseconds, `0xF1`–`0xF9` are 100–900
microseconds.

CAN FD uses a two byte PCI (`0x00 LL`) for single frames above seven bytes and
an escape sequence in the first frame for messages above 4095 bytes.

### Exchange

```
Tester  --> 10 14 62 F1 90 57 42 41    first frame, 20 bytes announced
ECU     --> 30 08 00                   flow control: send 8, no delay
Tester  --> 21 5A 5A 5A 30 47 4D 31    consecutive 1
Tester  --> 22 32 33 34 35 36 37 38    consecutive 2
```

## Bit timing

The nominal bit time is divided into synchronisation segment, propagation
segment and two phase segments. The sample point should sit at 75–87.5 %.

```python
from src.communication.protocols.can.can_timing import calculate_bit_timing

timing = calculate_bit_timing(500_000, clock_hz=80_000_000, sample_point=0.875)
timing.brp, timing.tseg1, timing.tseg2, timing.sample_point
```

## Timing parameters

| Parameter | Meaning | Typical |
|-----------|---------|---------|
| N_As / N_Ar | frame transmission | 25 ms |
| N_Bs | waiting for flow control | 75 ms |
| N_Cr | waiting for a consecutive frame | 150 ms |
| P2 client | waiting for the first response | 150 ms |
| P2* client | waiting after `0x78` | 5000 ms |
| S3 client | keep-alive interval | 2000 ms |

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| No response at all | wrong identifiers, wrong bitrate, missing termination |
| Only the first frame arrives | the tester did not send flow control |
| `wrongBlockSequenceCounter` | a consecutive frame was lost |
| Random frame loss | bitrate mismatch or a bus load above 80 % |
