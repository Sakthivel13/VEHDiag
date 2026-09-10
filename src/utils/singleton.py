"""Thread-safe singleton metaclass and helper."""
from __future__ import annotations

import threading
from typing import Any, ClassVar


class Singleton(type):
    """Metaclass creating at most one instance per class.

    Example:
        >>> class Registry(metaclass=Singleton):
        ...     pass
        >>> Registry() is Registry()
        True
    """

    _instances: ClassVar[dict[type, Any]] = {}
    _lock: ClassVar[threading.RLock] = threading.RLock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Return the existing instance or create it on first use."""
        if cls not in cls._instances:
            with Singleton._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

    def reset_instance(cls) -> None:
        """Forget the cached instance (used by unit tests)."""
        with Singleton._lock:
            Singleton._instances.pop(cls, None)


def reset_all_singletons() -> None:
    """Clear every cached singleton instance."""
    with Singleton._lock:
        Singleton._instances.clear()


__all__ = ["Singleton", "reset_all_singletons"]
