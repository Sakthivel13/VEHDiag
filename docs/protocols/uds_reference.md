# UDS reference (ISO 14229)

## Message format

```
Request           [SID] [sub-function / DID] [data ...]
Positive response [SID + 0x40] [echo] [data ...]
Negative response [0x7F] [SID] [NRC]
```

Bit 7 of the sub-function suppresses the positive response
(`3E 80` = TesterPresent without an answer).

## Services

| SID | Service | Session | Security |
|-----|---------|---------|----------|
| 0x10 | DiagnosticSessionControl | any | no |
| 0x11 | ECUReset | any | no |
| 0x14 | ClearDiagnosticInformation | default, extended | no |
| 0x19 | ReadDTCInformation | default, extended | no |
| 0x22 | ReadDataByIdentifier | any | no |
| 0x23 | ReadMemoryByAddress | extended | yes |
| 0x24 | ReadScalingDataByIdentifier | default, extended | no |
| 0x27 | SecurityAccess | programming, extended | – |
| 0x28 | CommunicationControl | extended | no |
| 0x29 | Authentication | any | – |
| 0x2A | ReadDataByPeriodicIdentifier | extended | no |
| 0x2C | DynamicallyDefineDataIdentifier | extended | no |
| 0x2E | WriteDataByIdentifier | extended | yes |
| 0x2F | InputOutputControlByIdentifier | extended | yes |
| 0x31 | RoutineControl | programming, extended | usually |
| 0x34 | RequestDownload | programming | yes |
| 0x35 | RequestUpload | programming | yes |
| 0x36 | TransferData | programming | yes |
| 0x37 | RequestTransferExit | programming | yes |
| 0x38 | RequestFileTransfer | programming | yes |
| 0x3D | WriteMemoryByAddress | programming, extended | yes |
| 0x3E | TesterPresent | any | no |
| 0x83 | AccessTimingParameter | extended | no |
| 0x84 | SecuredDataTransmission | any | – |
| 0x85 | ControlDTCSetting | extended | no |
| 0x86 | ResponseOnEvent | extended | no |
| 0x87 | LinkControl | programming, extended | usually |

## Sessions (0x10)

| Value | Name |
|-------|------|
| 0x01 | defaultSession |
| 0x02 | programmingSession |
| 0x03 | extendedDiagnosticSession |
| 0x04 | safetySystemDiagnosticSession |
| 0x40–0x5F | vehicleManufacturerSpecific |
| 0x60–0x7E | systemSupplierSpecific |

The positive response carries P2 (milliseconds) and P2* (units of 10 ms):
`50 03 00 32 01 F4` means P2 = 50 ms and P2* = 5000 ms.

## ReadDTCInformation sub-functions (0x19)

| Sub | Report |
|-----|--------|
| 0x01 | number of DTC by status mask |
| 0x02 | DTC by status mask |
| 0x03 | DTC snapshot identification |
| 0x04 | DTC snapshot record by DTC number |
| 0x05 | DTC stored data by record number |
| 0x06 | DTC extended data record by DTC number |
| 0x07 | number of DTC by severity mask record |
| 0x08 | DTC by severity mask record |
| 0x09 | severity information of DTC |
| 0x0A | supported DTC |
| 0x0B–0x0E | first/most recent test failed and confirmed DTC |
| 0x14 | DTC fault detection counter |
| 0x15 | DTC with permanent status |
| 0x17, 0x19 | user defined memory variants |

### DTC status byte

| Bit | Name |
|-----|------|
| 0 | testFailed |
| 1 | testFailedThisOperationCycle |
| 2 | pendingDTC |
| 3 | confirmedDTC |
| 4 | testNotCompletedSinceLastClear |
| 5 | testFailedSinceLastClear |
| 6 | testNotCompletedThisOperationCycle |
| 7 | warningIndicatorRequested |

A DTC is three bytes; `0xC07300` is displayed as `C0730`.

## Common data identifiers

| DID | Meaning |
|-----|---------|
| 0xF186 | active diagnostic session |
| 0xF187 | vehicle manufacturer spare part number |
| 0xF188/0xF189 | ECU software number / version |
| 0xF18A | system supplier identifier |
| 0xF18B | ECU manufacturing date |
| 0xF18C | ECU serial number |
| 0xF190 | VIN |
| 0xF191–0xF195 | hardware and supplier software numbers |
| 0xF197 | system name or engine type |
| 0xF19E | ODX file identifier |

## Negative response codes

| NRC | Name |
|-----|------|
| 0x10 | generalReject |
| 0x11 | serviceNotSupported |
| 0x12 | subFunctionNotSupported |
| 0x13 | incorrectMessageLengthOrInvalidFormat |
| 0x14 | responseTooLong |
| 0x21 | busyRepeatRequest |
| 0x22 | conditionsNotCorrect |
| 0x24 | requestSequenceError |
| 0x25 | noResponseFromSubnetComponent |
| 0x26 | failurePreventsExecutionOfRequestedAction |
| 0x31 | requestOutOfRange |
| 0x33 | securityAccessDenied |
| 0x35 | invalidKey |
| 0x36 | exceededNumberOfAttempts |
| 0x37 | requiredTimeDelayNotExpired |
| 0x70 | uploadDownloadNotAccepted |
| 0x71 | transferDataSuspended |
| 0x72 | generalProgrammingFailure |
| 0x73 | wrongBlockSequenceCounter |
| 0x78 | requestCorrectlyReceivedResponsePending |
| 0x7E | subFunctionNotSupportedInActiveSession |
| 0x7F | serviceNotSupportedInActiveSession |
| 0x81–0x93 | RPM, engine, temperature, speed and voltage conditions |

## Flash sequence

```
10 03                    extended session
85 02                    disable DTC setting
28 03 01                 disable normal communication
10 02                    programming session
27 11 / 27 12 <key>      security access
31 01 FF 00 <range>      erase memory
34 00 44 <addr> <size>   request download
36 01 <data> ...         transfer data (counter wraps 1..255..0)
37                       request transfer exit
31 01 FF 01              check programming dependencies
11 01                    hard reset
```
