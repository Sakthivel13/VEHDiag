# Adding a protocol

## 1. Subclass the base protocol

```python
from src.communication.protocols.base_protocol import BaseProtocol
from src.core.enums.protocol_enums import ConnectionState, ProtocolType


class MyProtocol(BaseProtocol):
    """Diagnostics over the ACME bus."""

    @property
    def protocol_type(self) -> ProtocolType:
        """Return the protocol identifier."""
        return ProtocolType.CUSTOM

    def initialize(self) -> None:
        """Perform the handshake and start the receive thread."""
        self._set_state(ConnectionState.CONNECTING)
        ...
        self._set_state(ConnectionState.CONNECTED)

    def shutdown(self) -> None:
        """Stop the receive thread."""
        ...
        super().shutdown()

    def send_message(self, payload: bytes, functional: bool = False) -> None:
        """Send an assembled diagnostic payload."""

    def receive_message(self, timeout: float = 1.0) -> bytes | None:
        """Return the next assembled payload or ``None``."""
```

The base class provides the state machine, the event notifications and the
timing storage.

## 2. Add the enumeration value

Extend `ProtocolType` in `src/core/enums/protocol_enums.py` with the value and
its display name.

## 3. Wire it into the connection manager

Add a branch to `ConnectionManager._build_protocol` that instantiates the
handler with the options from the connection profile.

## 4. Give it a configuration page

Add a page to `ConnectionPanel` (see `_build_can_page` for the pattern) and map
the protocol to its index in `_on_protocol_changed`.

## 5. Document the parameters

Add the protocol to `config/protocol_definitions.yaml` with its standard,
bitrates, payload limits and any protocol specific constants.

## Segmentation

If the protocol needs segmentation, reuse `IsoTpHandler` — it is transport
agnostic and only needs a send and a receive callable:

```python
self.isotp = IsoTpHandler(self._send_raw_frame, self._next_raw_frame, config)
```

`FlexRayProtocol` shows how to implement a different segmentation scheme
(ISO 10681) when the ISO-TP rules do not apply.

## Tests

Add a unit test for the framing and a round trip test using two handlers
connected through in-memory queues, as `tests/unit/communication/test_isotp_handler.py`
does.
