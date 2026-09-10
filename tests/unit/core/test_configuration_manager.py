"""Unit tests for the configuration manager."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.core.configuration_manager import ConfigurationManager


class TestAccess:
    """Reading and writing configuration values."""

    def test_defaults_are_loaded(self, config: ConfigurationManager) -> None:
        """The shipped defaults are available."""
        assert config.get("protocols.can.bitrate") == 500000
        assert config.get("ui.theme") == "dark"
        assert config.get("diagnostics.p2_client_ms") == 150

    def test_missing_key_returns_default(self, config: ConfigurationManager) -> None:
        """Unknown paths return the supplied fallback."""
        assert config.get("does.not.exist", "fallback") == "fallback"

    def test_set_and_get(self, config: ConfigurationManager) -> None:
        """Values can be written with a dotted path."""
        config.set("protocols.can.bitrate", 250000)
        assert config.get("protocols.can.bitrate") == 250000

    def test_set_creates_intermediate_levels(self, config: ConfigurationManager) -> None:
        """Missing intermediate mappings are created."""
        config.set("custom.section.value", 42)
        assert config.get("custom.section.value") == 42

    def test_section(self, config: ConfigurationManager) -> None:
        """A whole section can be read at once."""
        can = config.section("protocols.can")
        assert can["bitrate"] == 500000
        assert "tx_id" in can

    def test_update(self, config: ConfigurationManager) -> None:
        """Several values can be applied at once."""
        config.update({"ui.theme": "light", "logging.level": "DEBUG"})
        assert config.get("ui.theme") == "light"
        assert config.get("logging.level") == "DEBUG"


class TestPersistence:
    """Saving and reloading."""

    def test_save_and_reload(self, tmp_path: Path) -> None:
        """Written values survive a reload."""
        path = tmp_path / "user.yaml"
        first = ConfigurationManager(user_config=path)
        first.set("ui.theme", "light")
        first.save()
        assert ConfigurationManager(user_config=path).get("ui.theme") == "light"

    def test_reset_to_defaults(self, config: ConfigurationManager) -> None:
        """The defaults can be restored."""
        config.set("ui.theme", "light")
        config.reset_to_defaults()
        assert config.get("ui.theme") == "dark"

    def test_environment_override(self, tmp_path: Path) -> None:
        """Environment variables win over the files."""
        os.environ["VDP_THEME"] = "high_contrast"
        try:
            assert ConfigurationManager(user_config=tmp_path / "u.yaml").get("ui.theme") == "high_contrast"
        finally:
            del os.environ["VDP_THEME"]


class TestDefinitions:
    """The shipped definition tables."""

    def test_did_definitions(self, config: ConfigurationManager) -> None:
        """The DID table is keyed by integer."""
        definitions = config.did_definitions()
        assert 0xF190 in definitions
        assert definitions[0xF190]["name"] == "VIN"

    def test_nrc_definitions(self, config: ConfigurationManager) -> None:
        """The NRC table carries descriptions and recovery hints."""
        nrcs = config.nrc_definitions()
        assert nrcs[0x33]["name"] == "securityAccessDenied"
        assert "recovery" in nrcs[0x33]

    def test_protocol_definitions(self, config: ConfigurationManager) -> None:
        """The protocol table lists the supported buses."""
        protocols = config.definitions("protocol_definitions")["protocols"]
        assert "CAN" in protocols
        assert "DOIP" in protocols

    def test_vci_profiles(self, config: ConfigurationManager) -> None:
        """The shipped VCI profiles can be loaded."""
        assert "pcan_profile" in config.available_vci_profiles()
        assert config.vci_profile("pcan_profile")["vci"]["type"] == "PCAN"

    def test_session_templates(self, config: ConfigurationManager) -> None:
        """The session templates are available."""
        template = config.session_template("programming_session")
        assert template["session"]["type"] == 0x02
