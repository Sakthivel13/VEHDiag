"""Configuration of the seed-key algorithm source.

The key can come from four places, mirroring
:class:`~src.diagnostics.services.security.security_dll_loader.AlgorithmSource`:

* a built-in algorithm from
  :mod:`~src.diagnostics.services.security.security_algorithms`,
* a native shared library exposing a ``GenerateKeyEx`` style entry point,
* a Python script defining ``compute_key(seed, level)``,
* a key typed by hand.

Example:
    >>> from ui.panels.diagnostic_panel.security_access_panel.security_dll_config import (
    ...     library_filter, needs_path, source_for_label, SOURCE_LABELS)
    >>> source_for_label("Python script").value
    'PYTHON_SCRIPT'
    >>> needs_path(source_for_label("Built-in"))
    False
    >>> needs_path(source_for_label("External library"))
    True
    >>> "*.so" in library_filter()
    True
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from src.core.exceptions import DriverNotFoundError, VDPError
from src.diagnostics.services.security.security_algorithms import available_algorithms
from src.diagnostics.services.security.security_dll_loader import (
    AlgorithmSource,
    LoadedAlgorithm,
    SecurityDLLLoader,
)

from ....dpi_scaler import DPIScaler
from ....widgets.file_browser_widget import FileBrowserWidget
from ....widgets.hex_input_field import HexInputField
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....styles.layout_helpers import tune_form

__all__ = [
    "SOURCE_LABELS",
    "SecurityDLLConfig",
    "library_filter",
    "needs_path",
    "script_filter",
    "source_for_label",
]

#: Drop-down label of each algorithm source.
SOURCE_LABELS: dict[AlgorithmSource, str] = {
    AlgorithmSource.BUILTIN: "Built-in",
    AlgorithmSource.SHARED_LIBRARY: "External library",
    AlgorithmSource.PYTHON_SCRIPT: "Python script",
    AlgorithmSource.MANUAL: "Manual key",
}


def source_for_label(label: str) -> AlgorithmSource:
    """Return the :class:`AlgorithmSource` matching *label*.

    Args:
        label: One of the values of :data:`SOURCE_LABELS`.

    Returns:
        The matching source; :attr:`AlgorithmSource.BUILTIN` when unknown.

    Example:
        >>> source_for_label("nope") is AlgorithmSource.BUILTIN
        True
    """
    for source, text in SOURCE_LABELS.items():
        if text == label:
            return source
    return AlgorithmSource.BUILTIN


def needs_path(source: AlgorithmSource) -> bool:
    """Return ``True`` when *source* requires a file to be selected.

    Example:
        >>> needs_path(AlgorithmSource.MANUAL)
        False
    """
    return source in (AlgorithmSource.SHARED_LIBRARY, AlgorithmSource.PYTHON_SCRIPT)


def library_filter() -> str:
    """Return the Qt file dialog filter for native libraries.

    Example:
        >>> library_filter().startswith("Shared libraries")
        True
    """
    return "Shared libraries (*.dll *.so *.dylib);;All files (*)"


def script_filter() -> str:
    """Return the Qt file dialog filter for Python scripts."""
    return "Python scripts (*.py);;All files (*)"


class SecurityDLLConfig(ResponsiveWidget):
    """Chooses where the seed-key algorithm comes from and loads it.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        loader: Loader used for the library and script sources.

    Attributes:
        loaded: The algorithm that was loaded last, if any.
    """

    #: Emitted with the loaded algorithm after a successful load.
    algorithm_loaded = Signal(object)
    #: Emitted with the error message when loading fails.
    load_failed = Signal(str)
    #: Emitted with the new source whenever the selection changes.
    source_changed = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        loader: SecurityDLLLoader | None = None,
    ) -> None:
        """Build the source selector and the source specific editors."""
        super().__init__(parent, scaler)
        self.loader = loader or SecurityDLLLoader()
        self.loaded: LoadedAlgorithm | None = None

        self.source_box = QComboBox(self)
        for source, label in SOURCE_LABELS.items():
            self.source_box.addItem(label, source.value)
        self.source_box.currentIndexChanged.connect(self._on_source_changed)

        self.builtin_box = QComboBox(self)
        self.builtin_box.addItems(available_algorithms())

        self.file_browser = FileBrowserWidget(
            self, self.scaler, caption="Select the seed-key implementation",
            name_filter=library_filter(),
        )
        self.entry_point_box = QComboBox(self)
        self.entry_point_box.setEditable(True)
        self.entry_point_box.addItems(["", "GenerateKeyEx", "GenerateKeyExOpt", "compute_key"])

        self.manual_field = HexInputField(
            self, self.scaler, min_bytes=1, placeholder="e.g. 11 22 33 44"
        )

        self.load_button = ScalableButton("Load", "folder_open", self, self.scaler)
        self.load_button.clicked.connect(self.load)
        self.status_label = QLabel("built-in algorithm selected", self)
        self.status_label.setProperty("role", "secondary")
        self.status_label.setWordWrap(True)

        box = QGroupBox("Seed-key algorithm", self)
        self._form = QFormLayout(box)
        self._form.setSpacing(self.spacing(6))
        self._form.addRow("Source:", self.source_box)
        self._form.addRow("Built-in:", self.builtin_box)
        self._form.addRow("File:", self.file_browser)
        self._form.addRow("Entry point:", self.entry_point_box)
        self._form.addRow("Manual key:", self.manual_field)
        self._form.addRow("", self.load_button)
        self._form.addRow("Status:", self.status_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(box)

        self._on_source_changed(0)

    # -- API -----------------------------------------------------------------
    def source(self) -> AlgorithmSource:
        """Return the currently selected algorithm source."""
        return AlgorithmSource(str(self.source_box.currentData()))

    def set_source(self, source: AlgorithmSource) -> None:
        """Select *source* in the drop-down."""
        index = self.source_box.findData(source.value)
        if index >= 0:
            self.source_box.setCurrentIndex(index)

    def algorithm_name(self) -> str:
        """Return the name of the built-in algorithm that is selected."""
        return self.builtin_box.currentText()

    def manual_key(self) -> bytes:
        """Return the key typed by hand."""
        return self.manual_field.value()

    def is_ready(self) -> bool:
        """Return ``True`` when the current configuration can produce a key."""
        source = self.source()
        if source is AlgorithmSource.BUILTIN:
            return bool(self.algorithm_name())
        if source is AlgorithmSource.MANUAL:
            return bool(self.manual_key())
        return self.file_browser.is_valid()

    def load(self) -> LoadedAlgorithm | None:
        """Load the configured algorithm.

        Returns:
            The loaded algorithm, or ``None`` when the source needs no loading
            (built-in and manual) or when loading failed.
        """
        source = self.source()
        try:
            if source is AlgorithmSource.SHARED_LIBRARY:
                self.loaded = self.loader.load_library(
                    self.file_browser.path(), self.entry_point_box.currentText() or None
                )
            elif source is AlgorithmSource.PYTHON_SCRIPT:
                self.loaded = self.loader.load_script(self.file_browser.path())
            else:
                self.loaded = None
                self.status_label.setText(
                    f"using the built-in algorithm '{self.algorithm_name()}'"
                    if source is AlgorithmSource.BUILTIN
                    else "the key will be taken from the manual field"
                )
                return None
        except (VDPError, DriverNotFoundError, OSError) as exc:  # pragma: no cover - IO paths
            message = str(exc)
            self.status_label.setText(f"load failed: {message}")
            self.status_label.setProperty("state", "error")
            self.load_failed.emit(message)
            return None
        self.status_label.setText(f"loaded {self.loaded.name} from {self.loaded.path}")
        self.status_label.setProperty("state", "success")
        self.algorithm_loaded.emit(self.loaded)
        return self.loaded

    def configuration(self) -> dict[str, Any]:
        """Return the configuration as a serialisable mapping.

        Example:
            >>> # config.configuration()["source"]
            >>> None
        """
        return {
            "source": self.source().value,
            "algorithm": self.algorithm_name(),
            "path": self.file_browser.path(),
            "entry_point": self.entry_point_box.currentText(),
            "manual_key": self.manual_key().hex().upper(),
        }

    # -- internals ------------------------------------------------------------
    def _on_source_changed(self, _index: int) -> None:
        """Show only the editors relevant for the selected source."""
        source = self.source()
        self._set_row_visible(self.builtin_box, source is AlgorithmSource.BUILTIN)
        self._set_row_visible(self.file_browser, needs_path(source))
        self._set_row_visible(
            self.entry_point_box, source is AlgorithmSource.SHARED_LIBRARY
        )
        self._set_row_visible(self.manual_field, source is AlgorithmSource.MANUAL)
        self.load_button.setVisible(needs_path(source))
        self.file_browser.name_filter = (
            library_filter() if source is AlgorithmSource.SHARED_LIBRARY else script_filter()
        )
        self.source_changed.emit(source)

    def _set_row_visible(self, widget: QWidget, visible: bool) -> None:
        """Show or hide *widget* together with its form label."""
        widget.setVisible(visible)
        label = self._form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)
