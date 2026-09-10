# DoIP reference (ISO 13400)

## Header

Every message starts with the same eight bytes:

```
[version] [~version] [payload type (2)] [payload length (4)] [payload ...]
```

The protocol version is `0x02` for ISO 13400-2:2012 and later; the second byte
is its bitwise complement.

## Payload types

| Type | Meaning |
|------|---------|
| 0x0000 | generic negative acknowledge |
| 0x0001–0x0003 | vehicle identification request (plain, by EID, by VIN) |
| 0x0004 | vehicle announcement / identification response |
| 0x0005 / 0x0006 | routing activation request / response |
| 0x0007 / 0x0008 | alive check request / response |
| 0x4001 / 0x4002 | entity status request / response |
| 0x4003 / 0x4004 | diagnostic power mode request / response |
| 0x8001 | diagnostic message |
| 0x8002 / 0x8003 | diagnostic message positive / negative acknowledge |

## Ports

| Port | Use |
|------|-----|
| 13400/UDP | vehicle discovery |
| 13400/TCP | diagnostic messages |
| 3496/TCP | DoIP over TLS |

## Connection sequence

```
1. UDP broadcast  vehicle identification request  (0x0001)
2. UDP response   vehicle announcement            (0x0004) - VIN, logical address, EID, GID
3. TCP connect    to port 13400
4. TCP send       routing activation request      (0x0005) - source address 0x0E00
5. TCP receive    routing activation response     (0x0006) - code 0x10 = success
6. TCP send       diagnostic message              (0x8001) - source, target, UDS payload
7. TCP receive    acknowledge (0x8002) and the diagnostic response (0x8001)
```

## Routing activation response codes

| Code | Meaning |
|------|---------|
| 0x00 | unknown source address |
| 0x01 | all sockets registered |
| 0x02 | source address mismatch |
| 0x03 | source address already in use |
| 0x04 | socket already activated |
| 0x05 | missing authentication |
| 0x06 | rejected confirmation |
| 0x07 | unsupported activation type |
| 0x10 | success |
| 0x11 | success, confirmation pending |

## Addressing

| Address | Meaning |
|---------|---------|
| 0x0E00–0x0EFF | external test equipment |
| 0x1000–0x1FFF | ECUs |
| 0xE400–0xE7FF | functional group addresses |

## Keep-alive

The entity closes an idle socket. Send an alive check (0x0007) every two
seconds, or answer the entity's own alive check request with 0x0008; the
platform does both automatically.

## Usage

```python
from src.communication.protocols.ethernet.doip_protocol import DoIPProtocol

for vehicle in DoIPProtocol.discover(timeout=2.0):
    print(vehicle)     # VIN @ 192.168.0.10 (0x1000)

protocol = DoIPProtocol(config={"host": "192.168.0.10", "source_address": 0x0E00})
protocol.initialize()
response = protocol.request(bytes.fromhex("22F190"))
```
