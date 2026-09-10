# Component diagram

## Modules and their dependencies

```
                          +-------------+
                          |   ui/       |
                          +------+------+
                                 |
              +------------------+------------------+
              |                  |                  |
     +--------v-------+  +-------v--------+  +------v-------+
     | test_execution |  |  diagnostics   |  | data_process |
     +--------+-------+  +-------+--------+  +------+-------+
              |                  |                  |
              +------------------+------------------+
                                 |
                        +--------v---------+
                        |  communication   |
                        +--------+---------+
                                 |
                        +--------v---------+
                        |      core        |
                        +--------+---------+
                                 |
                +----------------+----------------+
                |                                 |
       +--------v--------+              +---------v--------+
       | logging_system  |              |      utils       |
       +-----------------+              +------------------+
```

Nothing below `ui/` imports Qt, which is why the whole backend runs headless.

## Key classes

| Component | Class | Responsibility |
|-----------|-------|----------------|
| Application | `Application` | Lifecycle, services, crash reports |
| Configuration | `ConfigurationManager` | Merges defaults, files and environment |
| Events | `EventBus` | Thread-safe publish/subscribe |
| Connection | `ConnectionManager` | Builds VCI + protocol + transport |
| Transport | `TransportLayer` | Request/response serialisation, timing |
| Segmentation | `IsoTpHandler` | ISO 15765-2 |
| Diagnostics | `UDSClient` | Pending, retries, suppression, validation |
| Routing | `ServiceDispatcher` | Maps a SID to its service object |
| Testing | `TestRunner` | Payload, script and combined execution |
| Logging | `LogManager` | Console, file, SQLite and UI fan-out |
| Presentation | `MainWindow` + `MainController` | Wires the panels to the backend |

## Data flow of a DTC read

```
ReadDTCView --read_requested(sub_function, mask)--> DiagnosticController
DiagnosticController --QThread--> ReadDTCInformation.execute()
ReadDTCInformation --> UDSClient --> TransportLayer --> CANProtocol --> driver
driver --> simulator/ECU --> ... --> DTCReport
DiagnosticController --Qt signal--> ReadDTCView.show_report()
EventBus --DIAG_DTC_READ--> LogManager --> LogViewerPanel
```
