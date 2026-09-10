# Troubleshooting

## Connection

**No devices found**
Press **Scan devices**. On Linux the user must be in the `dialout` group for
serial adapters; SocketCAN needs `ip link set can0 up type can bitrate 500000`.
The virtual VCI is always available for testing without hardware.

**"the PCANBasic library could not be loaded"**
Install the vendor driver package. The platform falls back to python-can and
then to the virtual VCI, so the application still starts.

**Vector channel cannot be opened**
Assign the channel to the application name `VehicleDiagnosticsPlatform` in the
Vector Hardware Configuration tool.

## Communication

**Every request times out**
Check the TX/RX identifiers (`7E0`/`7E8` for most passenger cars), the bitrate
and the termination. The log viewer shows whether frames leave at all.

**"no ISO-TP flow control frame received"**
The ECU did not answer a first frame: wrong RX identifier, wrong addressing
format, or the ECU is not in a session that allows the service.

**Responses arrive but are rejected as malformed**
Padding is probably wrong. Toggle *Pad frames to 8 bytes* in the connection
panel; some ECUs require unpadded frames.

## Diagnostics

| NRC | Meaning | What to do |
|-----|---------|-----------|
| `0x11` | serviceNotSupported | Check the SID and the addressing |
| `0x13` | incorrectMessageLengthOrInvalidFormat | Verify the payload length |
| `0x22` | conditionsNotCorrect | Ignition on, engine off, vehicle stationary |
| `0x31` | requestOutOfRange | The DID, routine or address is unknown |
| `0x33` | securityAccessDenied | Run SecurityAccess first |
| `0x35` | invalidKey | Wrong seed-key algorithm or level |
| `0x36` | exceededNumberOfAttempts | Power-cycle the ECU or wait for the lockout |
| `0x7F` | serviceNotSupportedInActiveSession | Switch to the extended session |

**The session falls back to default on its own**
The S3 timer expired. Enable the automatic tester present in
*Diagnostics → Tester present*.

## Flashing

**`0x72 generalProgrammingFailure`**
The erase or write failed: check the memory range, the address format and that
the correct bootloader is active.

**`0x73 wrongBlockSequenceCounter`**
A block was lost. Restart the transfer; the counter cannot be resynchronised.

**`0x92`/`0x93 voltage too high/low`**
Connect a battery support unit before flashing.

## User interface

**Text is too small or too large**
The platform follows the system DPI. Override the base size in
*Settings → Display*, or start with `--theme high_contrast` for maximum
legibility.

**The log viewer feels slow**
Enable *Hide tester present* and raise the level to `INFO`. The viewer is
tested with 500 000 entries, but formatting every keep-alive is wasted work.

## Diagnosing the platform itself

```bash
python main.py --headless --log-level DEBUG
python -m pytest -q
```

Crash reports are written to the per-user application data directory under
`crash_reports/` and contain the environment description plus the traceback.
