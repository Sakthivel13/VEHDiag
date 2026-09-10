"""ODX and PDX file parsing.

ODX (ASAM MCD-2 D, ISO 22901) describes the diagnostic capabilities of an ECU
in XML. A PDX file is a ZIP container holding one or more ODX documents. This
parser extracts the parts the platform can act on: the ECU variants, the
diagnostic services with their request and response structure, the data object
properties and the computation methods.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from ...core.exceptions import ParseError

_logger = logging.getLogger(__name__)

#: Suffixes recognised as ODX documents.
ODX_SUFFIXES: tuple[str, ...] = (".odx", ".odx-d", ".odx-c", ".odx-f", ".xml")

#: Suffix of the ZIP container.
PDX_SUFFIX = ".pdx"


@dataclass(slots=True)
class ComputeMethod:
    """A linear or textual conversion from a raw to a physical value."""

    category: str = "IDENTICAL"
    factor: float = 1.0
    offset: float = 0.0
    unit: str = ""
    texts: dict[int, str] = field(default_factory=dict)

    def to_physical(self, raw: float) -> Any:
        """Convert a raw value into its physical representation."""
        if self.category == "TEXTTABLE":
            return self.texts.get(int(raw), raw)
        return raw * self.factor + self.offset


@dataclass(slots=True)
class DataObjectProperty:
    """An ODX data object property (DOP): how one parameter is encoded."""

    short_name: str
    long_name: str = ""
    bit_length: int = 8
    base_type: str = "A_UINT32"
    compute: ComputeMethod = field(default_factory=ComputeMethod)

    @property
    def byte_length(self) -> int:
        """Return the width in whole bytes."""
        return max(1, (self.bit_length + 7) // 8)


@dataclass(slots=True)
class DiagService:
    """One diagnostic service described by the ODX document."""

    short_name: str
    long_name: str = ""
    semantic: str = ""
    service_id: int = 0
    request_bytes: bytes = b""
    parameters: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        """Return the text shown in a service list."""
        return self.long_name or self.short_name

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"{self.label} (0x{self.service_id:02X})"


@dataclass(slots=True)
class ECUVariant:
    """One ECU variant with its services and data object properties."""

    short_name: str
    long_name: str = ""
    services: dict[str, DiagService] = field(default_factory=dict)
    dops: dict[str, DataObjectProperty] = field(default_factory=dict)

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.services)


class ODXParser:
    """Extract the usable parts of an ODX or PDX file.

    Example:
        >>> parser = ODXParser()
        >>> parser.suffixes[0]
        '.odx'
    """

    #: Suffixes this parser handles.
    suffixes = ODX_SUFFIXES + (PDX_SUFFIX,)

    def parse(self, path: str | Path) -> list[ECUVariant]:
        """Parse *path* and return every ECU variant it describes.

        Raises:
            ParseError: The file cannot be read or is not valid XML.
        """
        file_path = Path(path).expanduser()
        if file_path.suffix.lower() == PDX_SUFFIX:
            return self._parse_container(file_path)
        return self._parse_document(file_path.read_bytes(), file_path.name)

    def _parse_container(self, path: Path) -> list[ECUVariant]:
        """Parse every ODX document inside a PDX container."""
        variants: list[ECUVariant] = []
        try:
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if Path(name).suffix.lower() in ODX_SUFFIXES:
                        variants.extend(self._parse_document(archive.read(name), name))
        except zipfile.BadZipFile as exc:
            raise ParseError(f"{path} is not a valid PDX container") from exc
        return variants

    def _parse_document(self, payload: bytes, name: str) -> list[ECUVariant]:
        """Parse one ODX XML document.

        Raises:
            ParseError: The document is not valid XML.
        """
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise ParseError(f"could not parse the ODX document {name}", {"cause": str(exc)}) from exc

        variants: list[ECUVariant] = []
        for element in self._iter_local(root, "ECU-VARIANT", "BASE-VARIANT"):
            variant = ECUVariant(
                short_name=self._child_text(element, "SHORT-NAME") or name,
                long_name=self._child_text(element, "LONG-NAME"),
            )
            for dop_element in self._iter_local(element, "DATA-OBJECT-PROP"):
                dop = self._parse_dop(dop_element)
                variant.dops[dop.short_name] = dop
            for service_element in self._iter_local(element, "DIAG-SERVICE"):
                service = self._parse_service(service_element)
                variant.services[service.short_name] = service
            variants.append(variant)

        if not variants:  # flat document without an explicit variant
            variant = ECUVariant(short_name=Path(name).stem)
            for service_element in self._iter_local(root, "DIAG-SERVICE"):
                service = self._parse_service(service_element)
                variant.services[service.short_name] = service
            for dop_element in self._iter_local(root, "DATA-OBJECT-PROP"):
                dop = self._parse_dop(dop_element)
                variant.dops[dop.short_name] = dop
            if variant.services or variant.dops:
                variants.append(variant)
        _logger.info("parsed %s: %d variant(s)", name, len(variants))
        return variants

    def _parse_service(self, element: ET.Element) -> DiagService:
        """Build a :class:`DiagService` from a ``DIAG-SERVICE`` element."""
        service = DiagService(
            short_name=self._child_text(element, "SHORT-NAME"),
            long_name=self._child_text(element, "LONG-NAME"),
            semantic=element.get("SEMANTIC", ""),
        )
        for coded in self._iter_local(element, "CODED-VALUE"):
            text = (coded.text or "").strip()
            if text.isdigit():
                service.service_id = int(text)
                service.request_bytes = bytes([service.service_id & 0xFF])
                break
        service.parameters = [
            self._child_text(param, "SHORT-NAME")
            for param in self._iter_local(element, "PARAM")
        ]
        return service

    def _parse_dop(self, element: ET.Element) -> DataObjectProperty:
        """Build a :class:`DataObjectProperty` from a ``DATA-OBJECT-PROP``."""
        dop = DataObjectProperty(
            short_name=self._child_text(element, "SHORT-NAME"),
            long_name=self._child_text(element, "LONG-NAME"),
        )
        bit_length = self._child_text(element, "BIT-LENGTH")
        if bit_length.isdigit():
            dop.bit_length = int(bit_length)
        base_type = self._child_text(element, "BASE-DATA-TYPE")
        if base_type:
            dop.base_type = base_type
        dop.compute = self._parse_compu(element)
        return dop

    def _parse_compu(self, element: ET.Element) -> ComputeMethod:
        """Extract the computation method of a DOP."""
        method = ComputeMethod()
        category = self._child_text(element, "CATEGORY")
        if category:
            method.category = category
        coefficients = [
            float(text)
            for coefficient in self._iter_local(element, "V")
            if (text := (coefficient.text or "").strip()) and self._is_number(text)
        ]
        if len(coefficients) >= 2:
            method.offset, method.factor = coefficients[0], coefficients[1]
        method.unit = self._child_text(element, "DISPLAY-NAME")
        for scale in self._iter_local(element, "COMPU-SCALE"):
            lower = self._child_text(scale, "LOWER-LIMIT")
            text = self._child_text(scale, "VT")
            if lower.isdigit() and text:
                method.texts[int(lower)] = text
        return method

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _local(tag: str) -> str:
        """Return the tag without its XML namespace."""
        return tag.rsplit("}", 1)[-1].upper()

    def _iter_local(self, root: ET.Element, *names: str) -> Iterator[ET.Element]:
        """Yield every descendant whose local name matches one of *names*."""
        wanted = {name.upper() for name in names}
        for element in root.iter():
            if self._local(element.tag) in wanted:
                yield element

    def _child_text(self, element: ET.Element, name: str) -> str:
        """Return the text of the first descendant called *name*."""
        for child in element.iter():
            if self._local(child.tag) == name.upper():
                return (child.text or "").strip()
        return ""

    @staticmethod
    def _is_number(text: str) -> bool:
        """Return ``True`` when *text* parses as a float."""
        try:
            float(text)
            return True
        except ValueError:
            return False


def parse_odx(path: str | Path) -> list[ECUVariant]:
    """Convenience wrapper around :class:`ODXParser`."""
    return ODXParser().parse(path)


__all__ = [
    "ODXParser",
    "ECUVariant",
    "DiagService",
    "DataObjectProperty",
    "ComputeMethod",
    "parse_odx",
    "ODX_SUFFIXES",
    "PDX_SUFFIX",
]
