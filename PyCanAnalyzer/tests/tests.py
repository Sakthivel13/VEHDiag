"""Testing Suite."""
from core.core import CANFrame


def test_can_frame():
    f = CANFrame(1.2345, 0x123, 8, b"\x00\x01")
    assert "CANFrame" in repr(f)


def test_device_import():
    import devices.devices as d
    assert hasattr(d, "DeviceManager")


def test_pipeline_import():
    import pipeline.pipeline as p
    assert hasattr(p, "Pipeline")


def test_discovery_import():
    import discovery.discovery as d
    assert hasattr(d, "DiscoveryEngine")


def test_ml_import():
    import ml.ml_engine as m
    assert hasattr(m, "MLEngine")


if __name__ == "__main__":
    test_can_frame()
    test_device_import()
    test_pipeline_import()
    test_discovery_import()
    test_ml_import()
    print("All tests passed!")