# Adding a VCI driver

## 1. Subclass the base driver

```python
from src.communication.vci_drivers.base_vci_driver import BaseVCIDriver
from src.core.enums.vci_enums import VCICapability, VCIType
from src.core.models.message_model import BusMessage
from src.core.models.vci_model import VCIDeviceInfo


class MyVCIDriver(BaseVCIDriver):
    """Driver for the ACME CAN interface."""

    vci_type = VCIType.CUSTOM
    capabilities = frozenset({VCICapability.CAN, VCICapability.CAN_FD})

    def _do_connect(self) -> None:
        """Open the channel described by ``self.config``."""
        self._handle = acme.open(self.config.channel, self.config.bitrate)

    def _do_disconnect(self) -> None:
        """Close the channel."""
        acme.close(self._handle)

    def _do_send(self, message: BusMessage) -> None:
        """Transmit one frame."""
        acme.write(self._handle, message.arbitration_id, message.data)

    def _do_receive(self, timeout: float) -> BusMessage | None:
        """Return the next frame or ``None`` on timeout."""
        frame = acme.read(self._handle, timeout)
        if frame is None:
            return None
        return BusMessage(data=frame.data, arbitration_id=frame.id)

    def _build_device_info(self) -> VCIDeviceInfo:
        """Describe the hardware."""
        return VCIDeviceInfo(vci_type=self.vci_type, name="ACME CAN", channel_count=2)
```

The base class already handles the state machine, statistics, events,
auto-reconnect and the `with` protocol.

## 2. Register it

From a plugin:

```python
self.register_vci_driver("ACME", MyVCIDriver)
```

Or extend `VCIFactory._create_builtin` for a first-class driver.

## 3. Add a profile

Copy `config/vci_profiles/custom_vci_template.yaml`, fill in the library names,
capabilities and channels, and the connection panel will offer it.

## 4. Make it discoverable

Extend `VCIScanner` with a `_scan_acme` method that probes for the library or
enumerates the USB devices and returns `DetectedVCI` entries.

## 5. Test it

```python
def test_driver_round_trip():
    """The driver transports a frame."""
    driver = MyVCIDriver()
    driver.connect()
    driver.send(BusMessage(data=b"\x02\x10\x03", arbitration_id=0x7E0))
    assert driver.receive(1.0) is not None
    driver.disconnect()
```

Mark hardware-dependent tests with `@pytest.mark.hardware` so they are skipped
in continuous integration.

## Guidelines

* Never block forever — always honour the timeout.
* Translate vendor error codes into `VCIError` subclasses with a readable
  message.
* Advertise only the capabilities the hardware really has; the UI disables the
  rest.
* Load the vendor library lazily so the platform still starts without it.
