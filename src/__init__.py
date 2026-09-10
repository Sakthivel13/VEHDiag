"""Vehicle Diagnostics Platform source root.

The :mod:`src` package holds every non-UI layer of the platform:

``src.core``
    Enumerations, data models, interfaces, the event bus and the
    configuration manager shared by all other layers.
``src.communication``
    VCI drivers, transport protocols (CAN, CAN FD, K-Line, LIN, FlexRay,
    DoIP, J1939) and the ISO 15765-2 transport layer.
``src.diagnostics``
    The UDS (ISO 14229) client and one module per diagnostic service.
``src.data_processing``
    Response slicing, data conversion and firmware file parsing.
``src.logging_system``
    The SQLite backed communication log, filters, formatters and exporters.
``src.test_execution``
    The developer-mode test runner and the scripting API.
``src.controllers``
    Qt-aware glue binding the UI panels to the layers above.
``src.utils``
    Small dependency-free helpers.

Example:
    >>> from src import __version__
    >>> isinstance(__version__, str)
    True
"""
from __future__ import annotations

#: Semantic version of the platform.
__version__ = "0.1.0"

#: Human readable application name.
__app_name__ = "Vehicle Diagnostics Platform"

__all__ = ["__version__", "__app_name__"]
