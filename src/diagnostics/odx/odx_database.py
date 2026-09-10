"""In-memory database of the parsed ODX content."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .odx_parser import DataObjectProperty, DiagService, ECUVariant, ODXParser

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ODXDatabase:
    """Holds every ECU variant loaded from ODX or PDX files.

    Example:
        >>> database = ODXDatabase()
        >>> len(database)
        0
    """

    variants: dict[str, ECUVariant] = field(default_factory=dict)
    sources: list[Path] = field(default_factory=list)

    # -- loading -------------------------------------------------------------
    def load(self, path: str | Path) -> int:
        """Parse *path* and merge its variants into the database.

        Returns:
            The number of variants that were added.
        """
        source = Path(path).expanduser()
        variants = ODXParser().parse(source)
        for variant in variants:
            self.variants[variant.short_name] = variant
        self.sources.append(source)
        _logger.info("loaded %d ECU variant(s) from %s", len(variants), source.name)
        return len(variants)

    def clear(self) -> None:
        """Remove every loaded variant."""
        self.variants.clear()
        self.sources.clear()

    # -- queries --------------------------------------------------------------
    def variant(self, name: str) -> ECUVariant | None:
        """Return the variant called *name*."""
        return self.variants.get(name)

    def variant_names(self) -> list[str]:
        """Return the names of every loaded variant."""
        return sorted(self.variants)

    def services(self, variant: str | None = None) -> list[DiagService]:
        """Return the services of one variant, or of every variant."""
        if variant is not None:
            found = self.variants.get(variant)
            return sorted(found.services.values(), key=lambda s: s.short_name) if found else []
        result: list[DiagService] = []
        for entry in self.variants.values():
            result.extend(entry.services.values())
        return sorted(result, key=lambda s: s.short_name)

    def find_service(self, name: str) -> DiagService | None:
        """Return the first service whose short or long name matches *name*."""
        needle = name.strip().lower()
        for service in self.services():
            if needle in (service.short_name.lower(), service.long_name.lower()):
                return service
        return None

    def services_for_sid(self, service_id: int) -> list[DiagService]:
        """Return every service using the given service identifier."""
        return [service for service in self.services() if service.service_id == service_id]

    def dop(self, name: str, variant: str | None = None) -> DataObjectProperty | None:
        """Return a data object property by name."""
        candidates = (
            [self.variants[variant]] if variant and variant in self.variants
            else list(self.variants.values())
        )
        for entry in candidates:
            if name in entry.dops:
                return entry.dops[name]
        return None

    def search(self, text: str) -> list[DiagService]:
        """Return every service whose name contains *text*."""
        needle = text.strip().lower()
        return [
            service
            for service in self.services()
            if needle in service.short_name.lower() or needle in service.long_name.lower()
        ]

    def statistics(self) -> dict[str, Any]:
        """Return counters describing the loaded content."""
        return {
            "sources": [path.name for path in self.sources],
            "variants": len(self.variants),
            "services": len(self.services()),
            "dops": sum(len(variant.dops) for variant in self.variants.values()),
        }

    def __iter__(self) -> Iterator[ECUVariant]:  # noqa: D105 - trivial
        return iter(self.variants.values())

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.variants)


__all__ = ["ODXDatabase"]
