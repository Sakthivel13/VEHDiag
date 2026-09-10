"""License validation.

The platform itself is MIT licensed and fully functional without a key. This
module exists so a commercial distribution can gate optional features (extra
OEM plugins, fleet reporting) behind a signed license file without touching the
rest of the code base: when no license is present every core feature stays
available and only the flagged extras report as locked.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from ..utils.platform_utils import app_data_dir

_logger = logging.getLogger(__name__)

#: Name of the license file inside the application data directory.
LICENSE_FILE = "license.key"


class LicenseState(str, Enum):
    """Validation outcome of a license."""

    OPEN_SOURCE = "OPEN_SOURCE"
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"
    MISSING = "MISSING"

    @property
    def is_usable(self) -> bool:
        """Return ``True`` when the platform may run."""
        return self in (LicenseState.OPEN_SOURCE, LicenseState.VALID)


class Feature(str, Enum):
    """Features a license may unlock."""

    CORE = "CORE"
    OEM_PLUGINS = "OEM_PLUGINS"
    FLEET_REPORTING = "FLEET_REPORTING"
    REMOTE_DIAGNOSTICS = "REMOTE_DIAGNOSTICS"
    PRIORITY_SUPPORT = "PRIORITY_SUPPORT"


#: Features available without any license.
OPEN_SOURCE_FEATURES: frozenset[Feature] = frozenset({Feature.CORE})


@dataclass(slots=True)
class License:
    """A decoded license.

    Attributes:
        licensee: Name of the organisation the license was issued to.
        features: Features the license unlocks.
        expires_at: Expiry timestamp; ``0`` means perpetual.
        issued_at: Issue timestamp.
        seats: Number of concurrent installations allowed.
        identifier: Unique license identifier.
    """

    licensee: str = ""
    features: set[Feature] = field(default_factory=set)
    expires_at: float = 0.0
    issued_at: float = 0.0
    seats: int = 1
    identifier: str = ""

    @property
    def expired(self) -> bool:
        """Return ``True`` when the license is past its expiry date."""
        return bool(self.expires_at) and time.time() > self.expires_at

    @property
    def days_remaining(self) -> int:
        """Return the remaining days, or ``-1`` for a perpetual license."""
        if not self.expires_at:
            return -1
        return max(0, int((self.expires_at - time.time()) / 86400))

    def describe(self) -> str:
        """Return a readable summary for the about dialog."""
        if not self.licensee:
            return "Open source edition (MIT)"
        expiry = (
            "perpetual"
            if not self.expires_at
            else datetime.fromtimestamp(self.expires_at, tz=timezone.utc).strftime("%Y-%m-%d")
        )
        return f"{self.licensee} - {len(self.features)} feature(s), expires {expiry}"


class LicenseManager:
    """Loads and validates the optional license file.

    Args:
        secret: Shared secret used to verify the signature.
        path: Location of the license file.

    Example:
        >>> manager = LicenseManager()
        >>> manager.validate().is_usable
        True
        >>> manager.is_enabled(Feature.CORE)
        True
    """

    def __init__(self, secret: str = "vdp-community", path: str | Path | None = None) -> None:
        """Create the manager and locate the license file."""
        self.secret = secret.encode("utf-8")
        self.path = Path(path) if path else app_data_dir() / LICENSE_FILE
        self.license = License()
        self.state = LicenseState.OPEN_SOURCE

    # -- validation ---------------------------------------------------------
    def validate(self) -> LicenseState:
        """Load and verify the license file.

        Returns:
            The resulting :class:`LicenseState`; the absence of a file yields
            :attr:`LicenseState.OPEN_SOURCE`, never a failure.
        """
        if not self.path.is_file():
            self.state = LicenseState.OPEN_SOURCE
            self.license = License()
            return self.state
        try:
            payload = self._decode(self.path.read_text(encoding="utf-8").strip())
        except ValueError as exc:
            _logger.warning("invalid license file: %s", exc)
            self.state = LicenseState.INVALID
            return self.state
        self.license = License(
            licensee=str(payload.get("licensee", "")),
            features={Feature(f) for f in payload.get("features", []) if f in Feature.__members__},
            expires_at=float(payload.get("expires_at", 0)),
            issued_at=float(payload.get("issued_at", 0)),
            seats=int(payload.get("seats", 1)),
            identifier=str(payload.get("id", "")),
        )
        self.state = LicenseState.EXPIRED if self.license.expired else LicenseState.VALID
        _logger.info("license: %s", self.license.describe())
        return self.state

    def is_enabled(self, feature: Feature) -> bool:
        """Return ``True`` when *feature* may be used."""
        if feature in OPEN_SOURCE_FEATURES:
            return True
        if self.state is not LicenseState.VALID:
            return False
        return feature in self.license.features

    def enabled_features(self) -> set[Feature]:
        """Return every currently usable feature."""
        if self.state is LicenseState.VALID:
            return set(OPEN_SOURCE_FEATURES) | self.license.features
        return set(OPEN_SOURCE_FEATURES)

    def install(self, key: str) -> LicenseState:
        """Write a license key to disk and validate it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(key.strip(), encoding="utf-8")
        return self.validate()

    def remove(self) -> None:
        """Delete the license file and fall back to the open source edition."""
        self.path.unlink(missing_ok=True)
        self.license = License()
        self.state = LicenseState.OPEN_SOURCE

    # -- key handling ----------------------------------------------------------
    def generate(self, payload: dict[str, Any]) -> str:
        """Return a signed license key for *payload* (used by the issuer)."""
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self.secret, body, hashlib.sha256).digest()
        return (
            base64.urlsafe_b64encode(body).decode("ascii")
            + "."
            + base64.urlsafe_b64encode(signature).decode("ascii")
        )

    def _decode(self, key: str) -> dict[str, Any]:
        """Verify the signature of *key* and return its payload.

        Raises:
            ValueError: The key is malformed or the signature does not match.
        """
        if "." not in key:
            raise ValueError("the license key has no signature")
        body_text, signature_text = key.rsplit(".", 1)
        try:
            body = base64.urlsafe_b64decode(body_text.encode("ascii"))
            signature = base64.urlsafe_b64decode(signature_text.encode("ascii"))
        except Exception as exc:  # noqa: BLE001
            raise ValueError("the license key is not valid base64") from exc
        expected = hmac.new(self.secret, body, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("the license signature does not match")
        return json.loads(body.decode("utf-8"))

    def info(self) -> dict[str, Any]:
        """Return a mapping shown in the about dialog."""
        return {
            "state": self.state.value,
            "description": self.license.describe(),
            "features": sorted(feature.value for feature in self.enabled_features()),
            "days_remaining": self.license.days_remaining,
            "path": str(self.path),
        }


__all__ = ["LicenseManager", "License", "LicenseState", "Feature", "OPEN_SOURCE_FEATURES"]
