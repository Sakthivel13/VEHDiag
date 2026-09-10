# Getting started

## Installation

```bash
python -m pip install -r requirements.txt
python main.py
```

The application starts with the **virtual VCI** and a built-in ECU simulator, so
everything can be explored before any hardware is attached.

## The main window

```
+------------------------------------------------------------------+
|  File  Edit  View  Diagnostics  Tools  Help                       |
+------------------------------------------------------------------+
| Connect | Disconnect | Session v | Run | Run all | Cancel | ...    |
+---------+---------------------------------------+----------------+
|         |                                       |                |
|  Nav    |   Connection / Diagnostics /          |  Data          |
|  tree   |   Developer mode / Analysis / ...     |  converter     |
|         |                                       |                |
+---------+---------------------------------------+----------------+
|  Log viewer (filter, search, export)                              |
+------------------------------------------------------------------+
|  Breakpoint | Session | Security | TX/RX | Connection state       |
+------------------------------------------------------------------+
```

## First session

1. **Connect** — open the *Connection* tab, keep `Virtual VCI` and `CAN`,
   press **Connect**. The status bar turns green.
2. **Change the session** — go to *Diagnostics → Session*, choose
   `0x03 extendedDiagnosticSession` and press **Send request**. The P2/P2*
   values and the S3 countdown appear.
3. **Read the VIN** — *Diagnostics → Read DID*, pick `F190 - VIN` from the
   predefined list and press **Read**. The response is shown as hex, ASCII and
   parsed value.
4. **Read the fault memory** — *Diagnostics → Read DTC*, press **Read DTCs**.
   Confirmed codes are red, pending codes amber. Select a row to see the
   individual status bits.
5. **Clear it** — *Diagnostics → Clear DTC*, confirm the warning dialog. The
   before/after table shows what disappeared.

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+C` / `Ctrl+Shift+D` | Connect / disconnect |
| `F5` / `F6` / `Esc` | Run step / run all / cancel |
| `Ctrl+D` | Toggle developer mode |
| `Ctrl+L` | Toggle the log panel |
| `Ctrl+1` / `Ctrl+2` | Toggle the navigation / analysis panel |
| `Ctrl+T` | Toggle the theme |
| `Ctrl+E` | Export the log |
| `F11` | Full screen |
| `F1` | Documentation |

## Next steps

* [Connection setup](connection_setup.md) — real hardware and every protocol
* [Diagnostic operations](diagnostic_operations.md) — all services in detail
* [Developer mode](developer_mode.md) — scripted test sequences
* [Data analysis](data_analysis.md) — slicing and conversion
* [File transfer](file_transfer.md) — flashing an ECU
* [Troubleshooting](troubleshooting.md) — when something does not work
