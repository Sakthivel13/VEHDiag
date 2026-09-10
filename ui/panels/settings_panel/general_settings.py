"""General application settings page.

Each settings module of this package exposes the same two things:

* a ``SETTINGS`` tuple of :class:`SettingSpec` describing every editable
  configuration path, so the page can be built, validated and documented
  without instantiating any widget,
* a ``*SettingsPage`` widget that binds those specs to real editors.

Example:
    >>> from ui.panels.settings_panel.general_settings import SETTINGS, paths
    >>> "application.developer_mode" in paths()
    True
    >>> SETTINGS[0].kind
    'bool'
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.configuration_manager import ConfigurationManager, get_config

from ...dpi_scaler import DPIScaler
from ...widgets.responsive_widget import ResponsiveWidget
from ...styles.layout_helpers import tune_form

__all__ = ["GeneralSettingsPage", "SETTINGS", "SettingSpec", "SettingsPage", "paths"]


def _as_text(value: Any) -> str:
    """Render a configuration value for a line edit.

    Lists and tuples become a comma separated string so that path lists such as
    ``plugins.directories`` round-trip through the editor.

    Example:
        >>> _as_text(["a", "b"])
        'a, b'
        >>> _as_text(None)
        ''
        >>> _as_text(3)
        '3'
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


@dataclass(frozen=True, slots=True)
class SettingSpec:
    """Declarative description of one editable setting.

    Attributes:
        path: Dotted configuration path, e.g. ``"ui.theme"``.
        label: Caption shown in the form.
        kind: One of ``bool``, ``int``, ``text`` or ``choice``.
        minimum: Lower bound of an ``int`` setting.
        maximum: Upper bound of an ``int`` setting.
        suffix: Unit suffix of an ``int`` setting.
        choices: Allowed values of a ``choice`` setting.
        tooltip: Longer explanation shown on hover.
    """

    path: str
    label: str
    kind: str = "text"
    minimum: int = 0
    maximum: int = 1_000_000
    suffix: str = ""
    choices: tuple[str, ...] = ()
    tooltip: str = ""


#: Settings shown on the general page.
SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec(
        "application.developer_mode",
        "Start in developer mode",
        "bool",
        tooltip="Open the developer panel right after startup (Ctrl+D).",
    ),
    SettingSpec(
        "application.auto_connect_last",
        "Reconnect to the last VCI at startup",
        "bool",
    ),
    SettingSpec("application.check_updates", "Check for updates", "bool"),
    SettingSpec(
        "application.confirm_destructive",
        "Confirm destructive operations",
        "bool",
        tooltip="Ask before clearing DTCs, resetting the ECU or flashing.",
    ),
    SettingSpec(
        "application.recent_files",
        "Recent file entries",
        "int",
        minimum=0,
        maximum=50,
    ),
    SettingSpec("paths.test_scripts", "Test script directory"),
    SettingSpec("paths.firmware", "Firmware directory"),
    SettingSpec("paths.exports", "Export directory"),
    SettingSpec("paths.projects", "Project directory"),
)


def paths() -> list[str]:
    """Return every configuration path edited by this page.

    Example:
        >>> len(paths()) == len(SETTINGS)
        True
    """
    return [spec.path for spec in SETTINGS]


class SettingsPage(ResponsiveWidget):
    """Base class binding a tuple of :class:`SettingSpec` to editors.

    Args:
        specs: The settings shown on the page.
        title: Caption of the surrounding group box.
        parent: Parent widget.
        scaler: Shared DPI scaler.
        config: Configuration manager backing the editors.

    Attributes:
        editors: ``{path: widget}`` for every bound setting.
    """

    #: Emitted with ``{path: value}`` whenever an editor changes.
    value_changed = Signal(dict)

    def __init__(
        self,
        specs: Iterable[SettingSpec] = (),
        title: str = "Settings",
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        config: ConfigurationManager | None = None,
    ) -> None:
        """Build one editor per spec inside a group box."""
        super().__init__(parent, scaler)
        self.config = config or get_config()
        self.specs: tuple[SettingSpec, ...] = tuple(specs)
        self.editors: dict[str, QWidget] = {}

        box = QGroupBox(title, self)
        self.form = QFormLayout(box)
        self.form.setSpacing(self.spacing(8))
        for spec in self.specs:
            self.form.addRow(spec.label, self._build_editor(spec))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(box)
        layout.addStretch(1)

    # -- editors -------------------------------------------------------------
    def _build_editor(self, spec: SettingSpec) -> QWidget:
        """Create and register the editor described by *spec*."""
        current = self.config.get(spec.path)
        widget: QWidget
        if spec.kind == "bool":
            widget = QCheckBox(self)
            widget.setChecked(bool(current))
            widget.toggled.connect(lambda _v: self._emit())
        elif spec.kind == "int":
            widget = QSpinBox(self)
            widget.setRange(spec.minimum, spec.maximum)
            widget.setValue(int(current if current is not None else spec.minimum))
            if spec.suffix:
                widget.setSuffix(spec.suffix)
            widget.valueChanged.connect(lambda _v: self._emit())
        elif spec.kind == "choice":
            widget = QComboBox(self)
            widget.addItems(list(spec.choices))
            index = widget.findText(str(current or ""))
            if index >= 0:
                widget.setCurrentIndex(index)
            widget.currentIndexChanged.connect(lambda _v: self._emit())
        else:
            widget = QLineEdit(_as_text(current), self)
            widget.textChanged.connect(lambda _v: self._emit())
        if spec.tooltip:
            widget.setToolTip(spec.tooltip)
        self.editors[spec.path] = widget
        return widget

    # -- API -----------------------------------------------------------------
    def values(self) -> dict[str, Any]:
        """Return ``{path: value}`` for every editor of the page."""
        result: dict[str, Any] = {}
        for path, widget in self.editors.items():
            if isinstance(widget, QCheckBox):
                result[path] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                result[path] = widget.value()
            elif isinstance(widget, QComboBox):
                result[path] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                result[path] = widget.text()
        return result

    def apply(self) -> dict[str, Any]:
        """Write every editor value into the configuration."""
        values = self.values()
        self.config.update(values)
        return values

    def reload(self) -> None:
        """Refresh every editor from the configuration."""
        for spec in self.specs:
            widget = self.editors[spec.path]
            value = self.config.get(spec.path)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value or spec.minimum))
            elif isinstance(widget, QComboBox):
                index = widget.findText(str(value or ""))
                if index >= 0:
                    widget.setCurrentIndex(index)
            elif isinstance(widget, QLineEdit):
                widget.setText(_as_text(value))

    def paths(self) -> list[str]:
        """Return the configuration paths bound by this page."""
        return [spec.path for spec in self.specs]

    def _emit(self) -> None:
        """Publish the current values."""
        self.value_changed.emit(self.values())


class GeneralSettingsPage(SettingsPage):
    """The general application settings page.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        config: Configuration manager backing the editors.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        config: ConfigurationManager | None = None,
    ) -> None:
        """Build the page from :data:`SETTINGS`."""
        super().__init__(SETTINGS, "Application", parent, scaler, config)
