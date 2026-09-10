# System architecture

## Layer model

The platform is a strict layer stack. Every layer only knows the abstract
interface of the one below it, so a protocol, a piece of hardware or the whole
user interface can be replaced without touching the rest.

```
+---------------------------------------------------------------+
|  ui/            panels, widgets, dialogs, controllers (Qt)     |
+---------------------------------------------------------------+
|  src/test_execution/    test runner, script loader, sequences  |
+---------------------------------------------------------------+
|  src/diagnostics/       UDS client, dispatcher, 27 services    |
+---------------------------------------------------------------+
|  src/communication/     transport, ISO-TP, protocols, VCI      |
+---------------------------------------------------------------+
|  src/core/    event bus, configuration, models, interfaces     |
+---------------------------------------------------------------+
     src/data_processing/   src/logging_system/   src/utils/
```

## Request path

A single `ReadDataByIdentifier` travels through the whole stack:

```
ReadDIDView (Qt widget)
   |  read_requested(list[int])
DiagnosticController          -> runs on a QThread, never blocks the UI
   |
ReadDataByIdentifier          -> builds "22 F1 90", parses the response
   |
UDSClient                     -> suppression bit, 0x78 pending, retries
   |
TransportLayer                -> P2 timing, statistics, priority queue
   |
CANProtocol + IsoTpHandler    -> segmentation, flow control, padding
   |
VirtualVCIDriver / PCANDriver -> raw frames on the bus
```

Each hop publishes on the event bus, which is how the log viewer, the status
bar and the trace viewer stay in sync without any direct coupling.

## Core patterns

| Pattern | Where | Why |
|---------|-------|-----|
| Abstract interfaces | `src/core/interfaces/` | Hardware, protocols, parsers and loggers are pluggable |
| Event bus | `src/core/event_bus.py` | Decouples producers from the UI; thread-safe pub/sub |
| Template method | `BaseVCIDriver`, `BaseProtocol`, `BaseService` | Subclasses implement only the vendor or service specific hooks |
| Factory | `VCIFactory` | Chooses the driver and falls back to the virtual VCI |
| Model-View-Controller | `ui/controllers/` | Views never touch the diagnostic layer directly |
| Dependency injection | Everywhere | Configuration, event bus and scaler are passed in, which is what makes the tests fast |

## Threading

* The Qt main thread only paints; it never performs I/O.
* Every diagnostic operation runs in a `QThread` (`DiagnosticWorker`) and
  reports back through signals.
* Each protocol handler owns one receive thread that pushes frames into a
  bounded queue; the loop exits as soon as the driver closes.
* Keep-alive (`TesterPresent`), the connection health check and the LIN
  schedule use `PeriodicTimer` daemon threads.
* The log manager batches entries and flushes them every 100 ms so a burst of
  bus traffic cannot stall the UI.

## Event catalogue

| Category | Examples | Consumers |
|----------|----------|-----------|
| `COMM_*` | connected, disconnected, message TX/RX, bus error | status bar, log viewer, trace viewer |
| `DIAG_*` | session changed, NRC received, transfer progress | panels, toasts, diagnostic logger |
| `TEST_*` | step started/completed, sequence complete | developer panel, results table |
| `LOG_*` | entry added, exported, cleared | log viewer |
| `UI_*` | theme changed, DPI changed, breakpoint changed | every widget |
| `SYSTEM_*` | startup, ready, config changed, plugin loaded, shutdown | application controller |

## Application lifecycle

```
INITIALIZING -> CONFIGURED -> STARTING -> RUNNING -> SHUTTING_DOWN -> STOPPED
```

Startup order: configuration, event bus, log manager, DID registry, plugins,
connection manager, VCI scan, user interface. Shutdown runs in reverse and is
idempotent: cancel operations, disconnect, unload plugins, flush logs, save the
configuration.

## Extension points

* **VCI driver** — subclass `BaseVCIDriver`, register with `register_driver`.
* **Protocol** — subclass `BaseProtocol`, extend `ConnectionManager._build_protocol`.
* **Diagnostic service** — subclass `BaseService`, register with `ServiceDispatcher.register`.
* **Seed-key algorithm** — `register_algorithm(name, callable)` or load a DLL/SO.
* **Plugin** — subclass `PluginBase` under `plugins/`; discovered automatically.
