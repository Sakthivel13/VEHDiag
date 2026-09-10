"""FlexRay specific configuration for the connection panel."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.communication.protocols.flexray.flexray_cluster import FlexRayCluster
from src.communication.protocols.flexray.flexray_fibex_parser import parse_fibex

#: Channel combinations offered in the UI.
CHANNELS: tuple[str, ...] = ("A", "B", "AB")


def load_cluster(path: str | Path) -> FlexRayCluster:
   """Parse a FIBEX file and return the described cluster."""
   return parse_fibex(path)


def build_options(config_file: str = "", channels: str = "AB", **extra: Any) -> dict[str, Any]:
   """Return the FlexRay options for the connection profile.

   Example:
       >>> build_options()["channels"]
       'AB'
   """
   return {"config_file": config_file, "channels": channels, **extra}
