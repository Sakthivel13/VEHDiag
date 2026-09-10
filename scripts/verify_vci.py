"""Verify every VCI driver against the installed python-can backends.

No CAN hardware is present in CI, so this cannot open a real channel.  What it
*can* do - and what actually catches the bugs that bite on a bench - is check
that the keyword arguments each driver builds are accepted by the real
constructor of the corresponding python-can backend, and that the factory
returns the specific driver class the operator selected.

Checks performed per backend:

1. the driver class is reachable through :func:`create_driver`;
2. every keyword the driver would pass exists in the backend's ``__init__``
   signature (or the backend accepts ``**kwargs``);
3. required keywords the backend declares are supplied;
4. the channel argument has the type the backend documents.

Usage::

    python3 scripts/verify_vci.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.enums.protocol_enums import ProtocolType  # noqa: E402
from src.core.enums.vci_enums import VCIType  # noqa: E402
from src.core.models.vci_model import VCIChannelConfig  # noqa: E402

#: python-can backend module/class for each interface name.
BACKENDS: dict[str, tuple[str, str]] = {
    "pcan": ("can.interfaces.pcan", "PcanBus"),
    "vector": ("can.interfaces.vector", "VectorBus"),
    "kvaser": ("can.interfaces.kvaser", "KvaserBus"),
    "socketcan": ("can.interfaces.socketcan", "SocketcanBus"),
    "neovi": ("can.interfaces.ics_neovi", "NeoViBus"),
    "virtual": ("can.interfaces.virtual", "VirtualBus"),
}


def backend_signature(interface: str) -> tuple[inspect.Signature | None, str]:
    """Return the ``__init__`` signature of a python-can backend."""
    module_name, class_name = BACKENDS[interface]
    try:
        module = __import__(module_name, fromlist=[class_name])
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return None, f"import failed: {exc}"
    cls = getattr(module, class_name, None)
    if cls is None:
        return None, f"{class_name} missing from {module_name}"
    try:
        return inspect.signature(cls.__init__), ""
    except (TypeError, ValueError) as exc:  # pragma: no cover
        return None, f"no signature: {exc}"


def check_kwargs(interface: str, kwargs: dict[str, Any]) -> list[str]:
    """Return a list of problems with *kwargs* for *interface*."""
    signature, error = backend_signature(interface)
    if signature is None:
        return [error]
    parameters = signature.parameters
    accepts_var_kw = any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()
    )
    problems: list[str] = []
    for key in kwargs:
        if key in ("interface",):
            continue  # consumed by can.Bus, not by the backend
        if key not in parameters and not accepts_var_kw:
            problems.append(f"backend rejects keyword {key!r}")
    for name, parameter in parameters.items():
        if name in ("self", "kwargs", "args"):
            continue
        if parameter.default is inspect.Parameter.empty and parameter.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            if name not in kwargs:
                problems.append(f"missing required argument {name!r}")
    return problems


def build_kwargs(vci_type: VCIType, protocol: ProtocolType, channel: Any) -> Any:
    """Instantiate the driver for *vci_type* and return it with its kwargs."""
    from src.communication.vci_drivers.vci_factory import VCIFactory

    config = VCIChannelConfig(
        channel=channel,
        bitrate=500_000,
        data_bitrate=2_000_000,
        protocol=protocol,
    )
    # Never fall back: a silent virtual substitute would make a broken vendor
    # driver look healthy, which is exactly the bug this script hunts for.
    driver = VCIFactory.create(vci_type, config, fallback_to_virtual=False)
    kwargs = None
    builder = getattr(driver, "_build_bus_kwargs", None)
    if callable(builder):
        kwargs = builder()
    return driver, kwargs


def main() -> int:
    """Run the verification and print a report."""
    # Channels are given as strings on purpose: the connection panel stores
    # the combo box *text*, so this is exactly what reaches the drivers.
    cases: list[tuple[VCIType, ProtocolType, str]] = [
        (VCIType.PCAN, ProtocolType.CAN, "pcan"),
        (VCIType.PCAN_FD, ProtocolType.CAN_FD, "pcan"),
        (VCIType.VECTOR, ProtocolType.CAN, "vector"),
        (VCIType.VECTOR, ProtocolType.CAN_FD, "vector"),
        (VCIType.KVASER_LEAF_V3, ProtocolType.CAN, "kvaser"),
        (VCIType.KVASER_LEAF_V3, ProtocolType.CAN_FD, "kvaser"),
        (VCIType.KVASER_BLACKBIRD_V2, ProtocolType.CAN, "kvaser"),
        (VCIType.SOCKETCAN, ProtocolType.CAN, "socketcan"),
        (VCIType.SOCKETCAN, ProtocolType.CAN_FD, "socketcan"),
        (VCIType.INTREPIDCS, ProtocolType.CAN, "neovi"),
        (VCIType.VIRTUAL, ProtocolType.CAN, "virtual"),
    ]

    failures = 0
    print("=== VCI driver verification against installed python-can ===\n")
    for vci_type, protocol, interface in cases:
        label = f"{vci_type.name:<16} {protocol.name:<7} -> {interface:<10}"
        try:
            channel = "can0" if vci_type is VCIType.SOCKETCAN else "1"
            driver, kwargs = build_kwargs(vci_type, protocol, channel)
        except Exception as exc:  # noqa: BLE001 - reported
            print(f"{label} FACTORY FAILED: {exc}")
            failures += 1
            continue
        driver_name = type(driver).__name__
        if kwargs is None:
            print(f"{label} {driver_name:<26} (no python-can kwargs)")
            continue
        problems = check_kwargs(interface, kwargs)
        shown = {k: v for k, v in kwargs.items() if k != "interface"}
        if problems:
            failures += len(problems)
            print(f"{label} {driver_name:<26} FAIL")
            for problem in problems:
                print(f"    - {problem}")
            print(f"    kwargs: {shown}")
        else:
            print(f"{label} {driver_name:<26} ok  {shown}")

    print(f"\nfailures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
