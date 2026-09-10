"""Minimal FIBEX (ASAM MCD-2 NET) parser for FlexRay clusters.

Only the subset needed to configure a controller is extracted: cluster timing,
channels, ECUs and their key slots.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ....core.exceptions import ParseError
from .flexray_cluster import FlexRayCluster, FlexRayNode
from .flexray_frame import FlexRayChannel
from .flexray_timing import FlexRayTiming

_logger = logging.getLogger(__name__)

#: XML namespaces commonly used in FIBEX documents.
NAMESPACES: dict[str, str] = {
    "fx": "http://www.asam.net/xml/fbx",
    "flexray": "http://www.asam.net/xml/fbx/flexray",
    "ho": "http://www.asam.net/xml",
}


class FibexParser:
    """Extract FlexRay cluster information from a FIBEX file."""

    def parse(self, path: str | Path) -> FlexRayCluster:
        """Parse *path* and return the described cluster.

        Raises:
            ParseError: The file is not valid XML or contains no cluster.
        """
        file_path = Path(path).expanduser()
        try:
            tree = ET.parse(file_path)
        except (ET.ParseError, OSError) as exc:
            raise ParseError(f"could not parse the FIBEX file {file_path}", {"cause": str(exc)}) from exc
        root = tree.getroot()
        cluster = FlexRayCluster(name=file_path.stem)
        cluster.timing = self._parse_timing(root)
        cluster.nodes = self._parse_nodes(root)
        if not cluster.nodes:
            _logger.warning("no ECUs found in %s", file_path)
        return cluster

    def _parse_timing(self, root: ET.Element) -> FlexRayTiming:
        """Extract the cluster timing parameters."""
        timing = FlexRayTiming()
        values = self._collect_values(root)
        timing.macro_per_cycle = int(values.get("MACRO-PER-CYCLE", timing.macro_per_cycle))
        timing.static_slots = int(values.get("NUMBER-OF-STATIC-SLOTS", timing.static_slots))
        timing.static_slot_macroticks = int(
            values.get("STATIC-SLOT", timing.static_slot_macroticks)
        )
        timing.minislots = int(values.get("NUMBER-OF-MINISLOTS", timing.minislots))
        timing.minislot_macroticks = int(values.get("MINISLOT", timing.minislot_macroticks))
        timing.network_idle_macroticks = int(
            values.get("NETWORK-IDLE-TIME", timing.network_idle_macroticks)
        )
        timing.bitrate = int(values.get("BIT-RATE", timing.bitrate))
        return timing

    def _parse_nodes(self, root: ET.Element) -> list[FlexRayNode]:
        """Extract the ECUs and their key slots."""
        nodes: list[FlexRayNode] = []
        for element in root.iter():
            tag = self._local_name(element.tag)
            if tag not in ("ECU", "CONTROLLER"):
                continue
            name = self._child_text(element, "SHORT-NAME") or element.get("ID", "node")
            key_slot = int(self._child_text(element, "KEY-SLOT-ID") or 0)
            nodes.append(
                FlexRayNode(
                    name=name,
                    key_slot=key_slot,
                    channels=FlexRayChannel.AB,
                    is_sync_node=bool(key_slot),
                    is_startup_node=bool(key_slot),
                )
            )
        return nodes

    def _collect_values(self, root: ET.Element) -> dict[str, Any]:
        """Return a flat mapping of every leaf element with numeric text."""
        values: dict[str, Any] = {}
        for element in root.iter():
            text = (element.text or "").strip()
            if not text:
                continue
            try:
                values[self._local_name(element.tag)] = int(float(text))
            except ValueError:
                continue
        return values

    @staticmethod
    def _local_name(tag: str) -> str:
        """Strip the XML namespace from *tag*."""
        return tag.rsplit("}", 1)[-1].upper()

    def _child_text(self, element: ET.Element, name: str) -> str:
        """Return the text of the first descendant whose local name matches."""
        for child in element.iter():
            if self._local_name(child.tag) == name.upper():
                return (child.text or "").strip()
        return ""


def parse_fibex(path: str | Path) -> FlexRayCluster:
    """Convenience wrapper around :class:`FibexParser`."""
    return FibexParser().parse(path)


__all__ = ["FibexParser", "parse_fibex", "NAMESPACES"]
