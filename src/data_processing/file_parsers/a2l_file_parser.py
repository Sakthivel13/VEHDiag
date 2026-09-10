"""Minimal A2L (ASAP2) parser.

A2L files describe measurement and calibration objects of an ECU. The full
grammar is large; this parser extracts the objects the platform needs:
``MEASUREMENT``, ``CHARACTERISTIC`` and ``COMPU_METHOD`` blocks together with
their addresses and conversion coefficients.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...core.exceptions import ParseError
from ...core.models.file_transfer_model import MemorySegment
from .base_file_parser import BaseFileParser

_logger = logging.getLogger(__name__)

_BLOCK_RE = re.compile(r"/begin\s+(\w+)(.*?)/end\s+\1", re.DOTALL)
_ADDRESS_RE = re.compile(r"0x[0-9A-Fa-f]+")


@dataclass(slots=True)
class A2LObject:
    """One measurement or characteristic described by the A2L file.

    Attributes:
        kind: ``MEASUREMENT`` or ``CHARACTERISTIC``.
        name: Object name.
        description: Long identifier from the A2L file.
        data_type: ASAP2 data type such as ``UWORD``.
        address: ECU memory address of the object.
        conversion: Name of the referenced COMPU_METHOD.
        lower_limit: Lower physical limit.
        upper_limit: Upper physical limit.
    """

    kind: str
    name: str
    description: str = ""
    data_type: str = ""
    address: int = 0
    conversion: str = ""
    lower_limit: float = 0.0
    upper_limit: float = 0.0

    @property
    def size(self) -> int:
        """Return the byte width implied by :attr:`data_type`."""
        return {
            "UBYTE": 1,
            "SBYTE": 1,
            "UWORD": 2,
            "SWORD": 2,
            "ULONG": 4,
            "SLONG": 4,
            "A_UINT64": 8,
            "A_INT64": 8,
            "FLOAT32_IEEE": 4,
            "FLOAT64_IEEE": 8,
        }.get(self.data_type.upper(), 1)


@dataclass(slots=True)
class CompuMethod:
    """A linear conversion method from the A2L file."""

    name: str
    unit: str = ""
    factor: float = 1.0
    offset: float = 0.0

    def to_physical(self, raw: float) -> float:
        """Return the physical value of *raw*."""
        return raw * self.factor + self.offset


@dataclass(slots=True)
class A2LDatabase:
    """The objects extracted from one A2L file."""

    measurements: dict[str, A2LObject] = field(default_factory=dict)
    characteristics: dict[str, A2LObject] = field(default_factory=dict)
    compu_methods: dict[str, CompuMethod] = field(default_factory=dict)
    project: str = ""

    def find(self, name: str) -> A2LObject | None:
        """Return the object called *name*, whatever its kind."""
        return self.measurements.get(name) or self.characteristics.get(name)

    def conversion_for(self, obj: A2LObject) -> CompuMethod | None:
        """Return the COMPU_METHOD referenced by *obj*."""
        return self.compu_methods.get(obj.conversion)

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.measurements) + len(self.characteristics)


class A2LFileParser(BaseFileParser):
    """Extract measurements, characteristics and conversions from an A2L file."""

    format_name = "ASAP2 / A2L"
    suffixes = (".a2l", ".a2ml")

    def parse_database(self, path: str | Path) -> A2LDatabase:
        """Parse *path* into an :class:`A2LDatabase`.

        Raises:
            ParseError: The file cannot be read.
        """
        file_path = Path(path).expanduser()
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            raise ParseError(f"could not read {file_path}", {"cause": str(exc)}) from exc
        database = A2LDatabase()
        for match in _BLOCK_RE.finditer(text):
            keyword, body = match.group(1).upper(), match.group(2)
            tokens = body.split()
            if keyword == "PROJECT" and tokens:
                database.project = tokens[0]
            elif keyword in ("MEASUREMENT", "CHARACTERISTIC") and len(tokens) >= 4:
                obj = self._parse_object(keyword, tokens)
                target = (
                    database.measurements if keyword == "MEASUREMENT" else database.characteristics
                )
                target[obj.name] = obj
            elif keyword == "COMPU_METHOD" and len(tokens) >= 3:
                method = self._parse_compu_method(tokens)
                database.compu_methods[method.name] = method
        _logger.info("parsed %s with %d objects", file_path.name, len(database))
        return database

    def _parse_object(self, kind: str, tokens: list[str]) -> A2LObject:
        """Build an :class:`A2LObject` from the tokens of one block."""
        name = tokens[0]
        description = tokens[1].strip('"') if len(tokens) > 1 else ""
        data_type = ""
        conversion = ""
        address = 0
        for token in tokens[2:]:
            if token.upper() in (
                "UBYTE", "SBYTE", "UWORD", "SWORD", "ULONG", "SLONG",
                "FLOAT32_IEEE", "FLOAT64_IEEE", "A_UINT64", "A_INT64",
            ):
                data_type = token.upper()
            elif _ADDRESS_RE.fullmatch(token):
                address = int(token, 16)
            elif not conversion and token.isidentifier() and token.upper() != kind:
                conversion = token
        limits = [float(t) for t in tokens if self._is_number(t)][-2:]
        lower, upper = (limits + [0.0, 0.0])[:2] if len(limits) < 2 else limits
        return A2LObject(
            kind=kind,
            name=name,
            description=description,
            data_type=data_type,
            address=address,
            conversion=conversion,
            lower_limit=lower,
            upper_limit=upper,
        )

    def _parse_compu_method(self, tokens: list[str]) -> CompuMethod:
        """Build a :class:`CompuMethod` from the tokens of one block."""
        numbers = [float(t) for t in tokens if self._is_number(t)]
        unit = ""
        for token in tokens:
            if token.startswith('"') and token.endswith('"') and len(token) > 2:
                unit = token.strip('"')
        factor = numbers[-2] if len(numbers) >= 2 else 1.0
        offset = numbers[-1] if len(numbers) >= 1 else 0.0
        return CompuMethod(name=tokens[0], unit=unit, factor=factor or 1.0, offset=offset)

    @staticmethod
    def _is_number(token: str) -> bool:
        """Return ``True`` when *token* parses as a float."""
        try:
            float(token)
            return True
        except ValueError:
            return False

    def parse(self, path: str | Path, **options: Any) -> list[MemorySegment]:
        """A2L files describe memory but carry no data, so this returns ``[]``."""
        self.parse_database(path)
        return []

    def get_metadata(self, path: str | Path) -> dict[str, Any]:
        """Return the object counts of the A2L file."""
        database = self.parse_database(path)
        return {
            "path": str(Path(path).expanduser()),
            "format": self.format_name,
            "project": database.project,
            "measurements": len(database.measurements),
            "characteristics": len(database.characteristics),
            "compu_methods": len(database.compu_methods),
        }


__all__ = ["A2LFileParser", "A2LDatabase", "A2LObject", "CompuMethod"]
