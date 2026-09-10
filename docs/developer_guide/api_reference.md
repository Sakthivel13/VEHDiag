# API reference

The authoritative reference is the docstrings; this page lists the entry points.

## Application

```python
from src.core.application import Application

app = Application(headless=True)
context = app.initialize()      # configuration, logs, plugins, registry
app.start()                     # scan hardware, announce readiness
transport = app.connect(profile)
client = app.create_client()
app.shutdown()
```

## Connection

```python
from src.communication.connection_manager import ConnectionManager, ConnectionProfile

manager = ConnectionManager()
transport = manager.connect(ConnectionProfile(vci_type=VCIType.PCAN, protocol=ProtocolType.CAN))
manager.get_info()
manager.disconnect()
```

## Diagnostics

```python
from src.diagnostics.uds_client import UDSClient, UDSClientConfig

client = UDSClient(transport, UDSClientConfig(p2_client_ms=150))
client.change_session(0x03)
client.read_data_by_identifier(0xF190, 0xF18C)
client.security_access(0x01)
client.clear_diagnostic_information()
client.send_request(bytes.fromhex("2F F1 A0 03 01"))
```

Every response is a `DiagnosticResponse` with `is_positive()`, `is_negative`,
`nrc`, `nrc_text`, `data`, `elapsed_ms` and `summary()`.

### Services

| SID | Class |
|-----|-------|
| 0x10 | `DiagnosticSessionControl` |
| 0x11 | `ECUReset` |
| 0x14 | `ClearDiagnosticInformation` |
| 0x19 | `ReadDTCInformation`, `DTCSnapshotReader`, `DTCExtendedReader` |
| 0x22 / 0x2E | `ReadDataByIdentifier` / `WriteDataByIdentifier` |
| 0x23 / 0x3D | `ReadMemoryByAddress` / `WriteMemoryByAddress` |
| 0x24 | `ReadScalingDataByIdentifier` |
| 0x27 / 0x29 | `SecurityAccess` / `Authentication` |
| 0x28 / 0x87 | `CommunicationControl` / `LinkControl` |
| 0x2A / 0x2C | `ReadDataByPeriodicIdentifier` / `DynamicallyDefineDataIdentifier` |
| 0x2F / 0x31 | `InputOutputControlByIdentifier` / `RoutineControl` |
| 0x34–0x38 | `RequestDownload`, `RequestUpload`, `TransferData`, `RequestTransferExit`, `RequestFileTransfer`, `TransferManager` |
| 0x3E / 0x83 | `TesterPresent`, `TesterPresentScheduler` / `AccessTimingParameter` |
| 0x84 / 0x85 / 0x86 | `SecuredDataTransmission` / `ControlDTCSetting` / `ResponseOnEvent` |

Or route by identifier:

```python
from src.diagnostics.service_dispatcher import ServiceDispatcher

dispatcher = ServiceDispatcher(client)
dispatcher.execute(0x22, 0xF190)
dispatcher.describe_services()
```

## Data processing

```python
from src.data_processing.data_converter import DataConverter
from src.data_processing.response_slicer import ResponseSlicer, SliceDefinition, SliceProfile

DataConverter().convert_all(b"ABCD")
profile = SliceProfile("VIN"); profile.add(SliceDefinition("data", 3, 17))
ResponseSlicer().apply_dict(response.raw, profile)
```

## Files

```python
from src.data_processing.file_parsers import parse_firmware_file, FileMerger, FileValidator

segments = parse_firmware_file("app.hex")
memory, report = FileMerger().merge_files(["boot.hex", "app.mot"])
FileValidator().validate_bytes(data, expected={"CRC32": 0x1234ABCD})
```

## Test execution

```python
from src.test_execution import TestRunner, TestSequenceManager

sequence = TestSequenceManager().create_default()
runner = TestRunner(client)
runner.load_sequence(sequence)
results = runner.execute_all()
runner.summary().as_text()
```

## Logging

```python
from src.logging_system import LogManager, ExportFormat

logs = LogManager()
logs.info("connected", category=LogCategory.COMM)
logs.export("session.html", "HTML")
```

## Events

```python
from src.core.event_bus import EventType, get_event_bus

bus = get_event_bus()
bus.subscribe(EventType.DIAG_NRC_RECEIVED, lambda event: print(event.get("info")))
```
