"""User interface exception hierarchy."""
from __future__ import annotations

from .communication_exceptions import VDPError


class UIError(VDPError):
    """Base class for user interface failures."""


class WidgetInitializationError(UIError):
    """Raised when a widget cannot be constructed (missing resource, bad state)."""


class ThemeLoadError(UIError):
    """Raised when a QSS theme file is missing or invalid."""


class ResourceNotFoundError(UIError):
    """Raised when an icon, font or image resource is missing."""


class InvalidUserInputError(UIError):
    """Raised when user supplied input fails validation."""


__all__ = [
    "UIError",
    "WidgetInitializationError",
    "ThemeLoadError",
    "ResourceNotFoundError",
    "InvalidUserInputError",
]
