# Connection setup

## Choosing the interface

Press **Scan devices** in the *Connection* tab. The platform enumerates
python-can backends, PCANBasic, Kvaser CANlib, the Vector XL library and the
serial ports, and always offers the virtual VCI as a fallback.

| VCI | Requirement |
|-----|-------------|
| PEAK PCAN | PCANBasic driver package |
| Vector | XL Driver Library, channel assigned to `VehicleDiagnosticsPlatform` |
| Kvaser BlackBird V2 / Leaf v3 | Kvaser drivers and CANlib |
| IntrepidCS neoVI | ICS driver package plus `python-ics` |
| SocketCAN | Linux, `ip link set can0 up type can bitrate 500000` |
| Serial | Any K-Line or LIN adapter exposed as a COM port or `/dev/tty*` |
| Virtual | Nothing — the built-in ECU simulator |

## Protocol parameters

### CAN and CAN FD

| Field | Typical value |
|-------|---------------|
| Bitrate | 500 kbit/s |
| FD data bitrate | 2 Mbit/s |
| TX identifier | `7E0` (physical request) |
| RX identifier | `7E8` (physical response) |
| Functional identifier | `7DF` |
| 29-bit identifiers | off for passenger cars, on for J1939 |
| Padding | on, `0x00` |

ISO-TP block size, STmin and the N_Bs/N_Cr timeouts live in
*Settings → Protocols*.

### DoIP

| Field | Typical value |
|-------|---------------|
| Host | IP of the gateway, for example `192.168.0.10` |
| Port | 13400 (3496 with TLS) |
| Source address | `0E00` (tester) |
| Target address | `1000` (ECU) |
| Activation type | `0x00` default, `0x01` WWH-OBD |

Vehicle discovery is available programmatically through
`DoIPProtocol.discover()`.

### K-Line

| Field | Typical value |
|-------|---------------|
| Port | `COM3` or `/dev/ttyUSB0` |
| Baudrate | 10400 |
| Initialisation | Fast init (ISO 14230) or 5 baud (ISO 9141) |

### LIN, FlexRay, J1939

LIN needs the port, the baudrate and the NAD. FlexRay needs a FIBEX cluster
description. J1939 needs the bitrate and the tester source address (`0xF9`).

## Connection profiles

**Save profile** stores the whole configuration; the ten most recent profiles
are offered again in the panel. Profiles are plain YAML and can be committed to
a project repository.

## Automatic reconnection

`connection.auto_reconnect` (default on) reconnects up to
`connection.reconnect_attempts` times with an increasing delay. A health check
runs every `connection.health_check_interval_ms` and raises `COMM_ERROR` when
the interface disappears.
