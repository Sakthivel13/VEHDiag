"""Tests for the plugin manager metadata contract."""
from __future__ import annotations

from src.core.plugin_manager import PluginManager


class TestPluginMetadata:
    """The mapping returned by :meth:`PluginManager.describe`."""

    def test_every_plugin_reports_an_identifier(self) -> None:
        """The settings page keys its disable list on the identifier.

        A missing identifier silently broke enabling and disabling, so the
        key must always be present and never a placeholder.
        """
        manager = PluginManager()
        manager.discover_and_load()
        described = manager.describe()
        assert described, "no plugin was discovered"
        for info in described:
            assert info.get("identifier"), f"{info.get('name')} has no identifier"
            assert info["identifier"] != "?"

    def test_identifiers_are_unique(self) -> None:
        """Two plugins must never share an identifier."""
        manager = PluginManager()
        manager.discover_and_load()
        identifiers = [info["identifier"] for info in manager.describe()]
        assert len(set(identifiers)) == len(identifiers)

    def test_info_carries_the_display_fields(self) -> None:
        """Name, path and enabled state are always present."""
        manager = PluginManager()
        manager.discover_and_load()
        for info in manager.describe():
            assert info.get("name")
            assert "path" in info
            assert "enabled" in info
