"""Core application services: models, enums, interfaces and infrastructure.

This package is deliberately free of Qt and hardware imports so that it can be
used from head-less scripts, unit tests and the CLI entry point.

Example:
    >>> from src.core import get_event_bus, get_config
    >>> bus = get_event_bus()
    >>> config = get_config()
    >>> config.get("application.name") is not None
    True
"""
from __future__ import annotations

from .configuration_manager import ConfigurationManager, get_config, set_config
from .event_bus import Event, EventBus, EventCategory, EventType, get_event_bus

__all__ = [
    "ConfigurationManager",
    "Event",
    "EventBus",
    "EventCategory",
    "EventType",
    "get_config",
    "get_event_bus",
    "set_config",
]
