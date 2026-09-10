# Vehicle Diagnostics Platform

A professional, cross-platform vehicle diagnostics tool written in Python 3.10+
with a PySide6 (Qt 6) user interface. It implements the full UDS (ISO 14229)
service set over every major automotive bus, ships a built-in ECU simulator so
it is fully usable without hardware, and includes a scripted developer mode for
end-of-line and regression testing.

![Diagnostics workspace](docs/screenshot_diagnostics.png)

---

## Highlights

| Area | What is implemented |
|------|--------------------|
| **Protocols** | CAN, CAN FD, ISO-TP (ISO 15765-2), K-Line (ISO 9141-2 / ISO 14230 KWP2000), LIN, FlexRay (ISO 10681 + FIBEX), DoIP (ISO 13400), SAE J1939 (TP.CM/TP.DT, address claim, DM1/DM2/DM3/DM11) |
| **Diagnostics** | 27 UDS services with request building, response parsing, NRC interpretation, `0x78` pending handling, suppress-positive-response and automatic retries |
| **Hardware** | PEAK PCAN, Vector XL, Kvaser CANlib (BlackBird V2, Leaf v3), IntrepidCS neoVI, Linux SocketCAN, serial K-Line/LIN adapters and a virtual VCI |
| **Simulation** | Configurable ECU simulator: sessions, DIDs, DTCs with snapshots, seed-key security, flash download, pending responses and error injection |
| **Developer mode** | Drag-and-drop test sequences, Python test scripts with a sandboxed API, single/batch execution, cancellation and HTML/CSV/JSON reports |
| **Data analysis** | Response slicer (byte and bit level), multi-format converter, live DID monitor, custom formulas and physical scaling |
| **Files** | Intel HEX, Motorola S-Record, raw binary, ELF and A2L parsing, merging, gap filling and CRC/MD5/SHA-256 validation |
| **Logging** | Microsecond timestamps, SQLite storage, virtual-scrolling viewer for 500 000+ entries, filtering, search and CSV/JSON/XML/HTML/ASC/BLF/PCAP export |
| **UI** | DPI-aware from 1280x720 to 4K at 100-200 % scaling, responsive breakpoints, dark/light/high-contrast themes, two-level top tab navigation |

---

## Quick start

```bash
git clone <repository-url>
cd vehicle_diagnostics_platform
python -m pip install -r requirements.txt

python main.py              # graphical application (virtual VCI by default)
python main.py --headless   # self-test against the built-in ECU simulator
```

The headless mode needs no hardware and no display:

```
Vehicle Diagnostics Platform 0.1.0 (headless)
session change : positive response (6 bytes) in 3.2 ms
VIN            : WBAZZZ0GM12345678
DTCs           : 3
statistics     : {'requests': 3, 'positive': 3, 'negative': 0, ...}
```

### Command line options

| Option | Meaning |
|--------|---------|
| `--headless` | Run the self-test without a user interface |
| `--vci TYPE` | `PCAN`, `VECTOR`, `KVASER_LEAF_V3`, `SOCKETCAN`, `VIRTUAL`, ... |
| `--protocol NAME` | `CAN`, `CAN_FD`, `KLINE`, `LIN`, `DOIP`, `J1939`, `FLEXRAY` |
| `--theme NAME` | `dark`, `light`, `high_contrast` |
| `--config PATH` | Alternative user configuration file |
| `--log-level LEVEL` | `TRACE` … `CRITICAL` |
| `--no-splash` | Skip the splash screen |

---

## Using the API

```python
from src.core.application import Application
from src.communication.connection_manager import ConnectionProfile
from src.diagnostics.services.dtc_services.read_dtc_information import ReadDTCInformation
from src.diagnostics.services.session_control.diagnostic_session_control import (
    DiagnosticSessionControl,
)

with Application(headless=True) as app:          # initialises and starts
    app.connect(ConnectionProfile())             # virtual VCI + ECU simulator
    client = app.create_client()

    DiagnosticSessionControl(client).enter_extended()
    for dtc in ReadDTCInformation(client).read_by_status_mask():
        print(dtc)                               # C0730 (0xC07300) status=0x2F [...]
```

Flashing an ECU is equally short:

```python
from src.diagnostics.services.security.security_access import SecurityAccess
from src.diagnostics.services.transfer_services.transfer_manager import TransferManager

DiagnosticSessionControl(client).enter_programming()
SecurityAccess(client, "add_constant").execute(0x11)

manager = TransferManager(client, on_progress=lambda p: print(f"{p.percent:.0f}%"))
report = manager.download_file("firmware.hex")   # HEX, S-Record, BIN or ELF
```

---

## Project layout

```
vehicle_diagnostics_platform/
├── main.py                     entry point (GUI and headless)
├── config/                     YAML configuration, VCI profiles, session templates, themes
├── src/
│   ├── core/                   application, event bus, configuration, models, enums, interfaces
│   ├── communication/          transport, ISO-TP, protocol handlers, VCI drivers
│   ├── diagnostics/            UDS client, dispatcher and every service
│   ├── data_processing/        converters, response slicer, firmware file parsers
│   ├── test_execution/         test runner, script loader, sequences, scheduler
│   ├── logging_system/         log manager, SQLite storage, filters, exporters
│   └── utils/                  bytes, checksums, threading, timers, validation
├── ui/                         PySide6 widgets, panels, dialogs and controllers
├── plugins/                    plugin base plus OEM and custom examples
├── tests/                      unit, integration, simulation and UI tests
├── docs/                       user guide, developer guide, protocol references
├── scripts/                    build and packaging helpers
└── sample_test_scripts/        ready-made developer mode scripts
```

---

## Navigation

The window uses **two rows of tabs at the top and nothing else** - there is no
side tree and there are no dock widgets, so a command lives in exactly one
place:

```
| Connection | Diagnostics | Developer mode | Data analysis | Logs | Settings |   <- workspaces
| Session | Read DID | Read DTC | Clear DTC | Security | ... | Raw request  |   <- sections
  Diagnostics > Read DTC                                                        <- breadcrumb
```

* **Row 1 - workspace.** Solid raised bar, `Ctrl+1` ... `Ctrl+6`.
* **Row 2 - section.** Pill shaped bar owned by the active workspace; the
  eleven UDS services, the four analysis tools, the two log views and the
  settings pages are all sections.
* **Breadcrumb.** Spells the active path out, plus the connected VCI on the
  right, so the state is readable without scanning two tab bars.

Everything routes through one entry point:

```python
window.navigate("Diagnostics", "Read DTC")   # workspace, then section
window.navigate("Trace viewer")              # historical names still resolve
```

Below 1366 px the section tabs collapse to icons with tooltips rather than
scrolling out of sight, so no service ever becomes unreachable.

## Developer mode

The developer panel maps a Python script and/or a raw payload to each UDS
service, lets the operator reorder them by dragging the cards and runs them
individually or as a batch.

![Developer mode](docs/screenshot_developer.png)

A test script is a plain class:

```python
class TestScript:
    """Verify the VIN can be read."""

    def __init__(self, api):
        self.api = api

    def setup(self):
        self.api.change_session(0x03)

    def execute(self):
        self.api.send_hex("22 F1 90")
        self.api.assert_positive_response()
        self.api.log(f"VIN: {self.api.get_last_response().raw[3:].decode()}")
        return "PASS"

    def teardown(self):
        self.api.change_session(0x01)
```

Scripts are statically validated (no `os`, `subprocess`, `eval`, ...) and run in
a background thread that can be cancelled in under 500 ms.

---

## Data analysis

The workspace puts the two tools that belong together side by side, with the
live trace pinned underneath:

```
| Slicer | Monitor | Plot |
+---------------------------+---------------------------+
|  Data slicer              |  Sliced data converter    |
|  byte map + slice table   |  the selected field, in    |
|                           |  every representation      |
+---------------------------+---------------------------+
|  Live trace - TX/RX, colour coded, always visible      |
```

* **Data slicer** - define named byte or bit ranges over a response, pick a
  conversion per slice and save the set as a reusable profile.
* **Sliced data converter** - selecting a row in the slicer sends *that field
  alone* to the converter, together with its factor/offset/unit, so the
  physical value is right without retyping the scaling.
* **Live trace** - every request and response as it happens, colour coded by
  outcome (amber `NRC 0x78` pending, red negative, green positive) with the
  round-trip time. Double click a frame to load it back into the slicer.

![Data analysis](docs/analysis_live_from_ecu.png)

---

## Testing

```bash
python -m pytest                       # 761 tests
python -m pytest -m unit               # fast unit tests only
python -m pytest -m ui                 # PySide6 widget tests only
python -m pytest --cov=src --cov=ui    # coverage report
```

The suite runs entirely against the built-in simulator, so no hardware and no
display are required; the Qt tests fall back to the offscreen platform and skip
themselves when PySide6 cannot be loaded.

| Layer | Tests | What is covered |
| --- | --- | --- |
| `tests/unit` | 380 | Byte helpers, ISO-TP, the UDS client and every service, the converters and file parsers, the event bus, the configuration manager and the logging system. |
| `tests/integration` | 30 | The diagnostic flow and the developer-mode flow from the transport up to the controllers. |
| `tests/simulation` | 10 | End-to-end exchanges against the built-in ECU simulator, including the full flash path. |
| `tests/ui_tests` | 332 | Responsive layout, the 24 custom widgets, the main window, and every diagnostic, developer, log, settings and dialog panel. |

Coverage is 66% overall; the implemented core sits between 80% and 100%
(`isotp_handler` 87%, `transport_layer` 83%, `event_bus` 81%,
`configuration_manager` 89%, `exceptions` 100%).

---

## Verification tooling

Two auditors ship with the project so a regression is caught mechanically
rather than by eye:

```bash
# Walks every workspace/section and reports clipped, overlapping,
# overflowing, elided or collapsed widgets. Exit code 1 on any defect.
QT_QPA_PLATFORM=offscreen python3 scripts/audit_ui.py --width 1920 --height 1080
QT_QPA_PLATFORM=offscreen python3 scripts/audit_ui.py --width 1280 --height 720 --theme light

# Checks the kwargs each VCI driver builds against the real python-can
# backend signatures, with the virtual fallback disabled.
python3 scripts/verify_vci.py
```

`audit_ui.py` is clean at 1280x720, 1366x768, 1600x900, 1920x1080, 2560x1440
and 3840x2160 in all three themes. `verify_vci.py` passes for all eleven
VCI/protocol combinations.

---

## Requirements

* Python 3.10 or newer
* PySide6 6.5+ (graphical application only)
* python-can, cantools, pyserial, intelhex, bincopy, PyYAML, SQLAlchemy, cryptography, loguru, natsort, Pillow

Vendor libraries (PCANBasic, Vector XL, Kvaser CANlib, ICS neoVI) are optional;
the platform detects what is installed and falls back to the virtual VCI.

## Documentation

* [Getting started](docs/user_guide/getting_started.md)
* [Connection setup](docs/user_guide/connection_setup.md)
* [Diagnostic operations](docs/user_guide/diagnostic_operations.md)
* [Developer mode](docs/user_guide/developer_mode.md)
* [System architecture](docs/architecture/system_architecture.md)
* [Plugin development](docs/developer_guide/plugin_development.md)
* [UDS reference](docs/protocols/uds_reference.md)

## License

MIT — see [LICENSE](LICENSE).
