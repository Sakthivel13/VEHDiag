# UI alignment and VCI verification report

Date: 2026-08-26 · 761 tests passing

Two mechanical auditors were written for this pass so the result is
reproducible rather than a visual opinion:

| Tool | What it proves |
|---|---|
| `scripts/audit_ui.py` | No clipped, overlapping, overflowing, elided or collapsed widgets on any screen |
| `scripts/verify_vci.py` | Every driver's kwargs are accepted by the real python-can backend |

---

## 1. UI alignment

`audit_ui.py` walks all six workspaces and all twenty-two sections, and
checks each widget tree for:

* **clipped** – widget needs more space than it has, with no scrollbar;
* **overlap** – two siblings in a non-stacked layout intersect by >6 px;
* **overflow** – a child sticks out of its parent's rect;
* **elided** – a label is hiding its text in too little space;
* **truncated** – a table header is narrower than its own caption;
* **collapsed** – an interactive control is under 12 px.

### Result

| Resolution | dark | light | high contrast |
|---|---|---|---|
| 1280×720 (COMPACT) | clean | clean | clean |
| 1366×768 (STANDARD) | clean | clean | clean |
| 1600×900 | clean | – | – |
| 1920×1080 (WIDE) | clean | clean | clean |
| 2560×1440 (ULTRA_WIDE) | clean | – | – |
| 3840×2160 | clean | – | – |

All nine dialogs (About, Error, Progress, VCI config, Preferences, ECU
identification, Confirmation, File transfer, Report generator) audit clean.

### Defect found and fixed

**Plot canvas painted over its legend at 1280×720.** `PlotCanvas` declared a
hard `setMinimumHeight(220)`. Inside the analysis scroll area the viewport is
~306 px, so the layout could not satisfy both the canvas minimum and the
legend, and the canvas overlapped the legend text by 8 px. Two changes:

* the canvas minimum drops to 130 px and the comfortable 220 px moves into
  `sizeHint()`, which a layout may shrink below;
* the word-wrapped legend gets `QSizePolicy.Minimum` vertically, so it is
  never squeezed under its own hint.

---

## 2. VCI verification

No CAN hardware exists in this sandbox, so the goal was to verify everything
that is *not* the vendor `.so`: driver selection, argument construction,
channel formatting, the full UDS stack over a genuine python-can bus, and the
failure path.

### 2.1 Driver arguments — all 11 combinations pass

```
PCAN            CAN     -> PCANDriver              channel='PCAN_USBBUS1' bitrate=500000
PCAN_FD         CAN_FD  -> PCANFDDriver            channel='PCAN_USBBUS1' fd=True data_bitrate=2000000
VECTOR          CAN     -> VectorDriver            channel=1
VECTOR          CAN_FD  -> VectorDriver            channel=1 fd=True data_bitrate=2000000
KVASER_LEAF_V3  CAN     -> KvaserLeafV3Driver      channel=1
KVASER_LEAF_V3  CAN_FD  -> KvaserLeafV3Driver      channel=1 fd=True      (no data_bitrate: KvaserBus rejects it)
KVASER_BLACKBIRD_V2 CAN -> KvaserBlackbirdV2Driver channel=1
SOCKETCAN       CAN     -> PythonCanDriver         channel='can0'         (no bitrate: kernel owns timing)
SOCKETCAN       CAN_FD  -> PythonCanDriver         channel='can0' fd=True
INTREPIDCS      CAN     -> IntrepidCSDriver        channel='1'
VIRTUAL         CAN     -> VirtualVCIDriver
```

### 2.2 Critical bug: the channel never reached the backend correctly

The connection panel stores the channel as the combo box **text**, so an
ordinary selection arrived at the driver as `"1"`, not `1`. Every
backend-specific translation was guarded by `isinstance(channel, int)` and so
was skipped:

* **PCAN** never built its `PCAN_USBBUSx` handle — it passed the bare string
  `"1"`, which PCANBasic does not recognise;
* **Kvaser** received a string where CANlib declares `channel: int`;
* **SocketCAN** received `"0"`, and `SocketcanBus` ends up calling
  `sock.bind(("0",))` — binding to a non-existent interface.

This affected **every hardware VCI**. It was invisible in testing because the
virtual driver ignores the channel entirely, and because `VCIFactory.create`
silently falls back to the virtual driver by default.

**Fix.** Channel normalisation is now centralised and type-tolerant:

| Backend | Accepts | Produces |
|---|---|---|
| pcan | `1`, `"1"`, `"0"` | `PCAN_USBBUS1` |
| pcan | `"PCAN_PCIBUS2"` | passed through |
| socketcan | `0`, `"0"` | `can0` |
| socketcan | `"vcan0"`, `"slcan0"` | passed through |
| kvaser / vector | `"2"` | `2` (int) |

### 2.3 Channel selector is now VCI-aware

The dropdown offered `0…7` for everything, which cannot express a SocketCAN
link name. Selecting **SocketCAN** now offers `can0, can1, vcan0, vcan1,
slcan0`; every other family keeps numeric indices. The control is editable so
an operator can type `can7`, and its tooltip explains which form is expected.

### 2.4 Full UDS over a real python-can bus

A responder ECU was run on a second real `can.Bus` on the same channel, so
every frame genuinely traverses python-can — the same path a PCAN bench uses,
minus the vendor library:

```
driver: PythonCanDriver | python-can bus: VirtualBus | connected: True
  session 0x03     TX 10 03      RX 50 03 00 32 01 F4                pos=True
  read VIN (MF)    TX 22 F1 90   RX 62 F1 90 4D 44 36 32 36 ...      pos=True
  tester present   TX 3E 00      RX 7E 00                            pos=True
  unsupported DID  TX 22 DE AD   RX 7F 22 31                         pos=False
stats: req=4 pos=3 neg=1 timeouts=0
VIN: MD626EG55S1B37997
```

This exercises ISO-TP **multi-frame** transfer with first frame, flow control
and consecutive frames, plus correct negative-response handling. The VIN
matches the reference tester screenshot exactly.

### 2.5 Failure path is loud and actionable

With no hardware present each backend raises `ConnectionFailedError` carrying
the real channel and a usable hint:

| VCI | Hint |
|---|---|
| PCAN | install the PEAK driver and check the PCAN_USBBUSx index |
| Vector | assign the channel to the application name `VehicleDiagnosticsPlatform` in Vector Hardware Config |
| Kvaser | install Kvaser CANlib and check the channel index |
| SocketCAN | `bring the link up: sudo ip link set can0 up type can bitrate 500000` |
| Intrepid | install python-ics and the Intrepid drivers |

Two reporting bugs were fixed:

* the hint was buried in the collapsed *technical details* block — it now
  populates the always-visible recovery field;
* `str(VDPError)` appends the entire details mapping, which turned the dialog
  headline into a wall of text. The headline now uses `error.message`; the
  structured context stays in the details block for bug reports.

---

## 3. Remaining limitation

Vendor libraries (PCANBasic, Vector XL, Kvaser CANlib, python-ics) cannot be
installed here, and `python-can`'s Vector backend is **Windows only**. Final
confirmation still needs a bench run against real hardware, but every layer
above the vendor call is now verified, and the channel-formatting bug above
would have caused a hard failure on first connection.

Suggested bench check:

```bash
python3 scripts/verify_vci.py          # must report 0 failures
python3 main.py --vci PCAN --protocol CAN
```
