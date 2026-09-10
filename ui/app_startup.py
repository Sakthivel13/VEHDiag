"""Splash screen and application startup sequence."""
from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from src.core.configuration_manager import ConfigurationManager, get_config

from .dpi_scaler import DPIScaler
from .styles.style_constants import DARK_PALETTE

_logger = logging.getLogger(__name__)

#: Steps announced on the splash screen, with their relative weight.
STARTUP_STEPS: tuple[tuple[str, int], ...] = (
    ("Loading configuration", 10),
    ("Starting the event bus", 20),
    ("Initialising the log manager", 35),
    ("Loading plugins", 50),
    ("Scanning for VCI hardware", 65),
    ("Preparing the diagnostic services", 80),
    ("Building the user interface", 95),
    ("Ready", 100),
)


class SplashScreen(QSplashScreen):
    """A generated splash screen showing the startup progress.

    Args:
        scaler: Shared DPI scaler.
        version: Version string shown under the title.
    """

    def __init__(self, scaler: DPIScaler | None = None, version: str = "0.1.0") -> None:
        """Render the splash pixmap and show it."""
        self.scaler = scaler or DPIScaler()
        self.version = version
        super().__init__(self._render(), Qt.WindowType.WindowStaysOnTopHint)
        self.setEnabled(False)

    def _render(self) -> QPixmap:
        """Draw the splash background."""
        width, height = self.scaler.px(520), self.scaler.px(300)
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(DARK_PALETTE.background))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setPen(QColor(DARK_PALETTE.primary))
        painter.setBrush(QColor(DARK_PALETTE.surface))
        painter.drawRoundedRect(
            self.scaler.px(2), self.scaler.px(2), width - self.scaler.px(4),
            height - self.scaler.px(4), self.scaler.px(10), self.scaler.px(10)
        )

        title_font = QFont("Roboto", self.scaler.font(22))
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor(DARK_PALETTE.text_primary))
        painter.drawText(
            self.scaler.px(36), self.scaler.px(110), "Vehicle Diagnostics"
        )
        painter.drawText(self.scaler.px(36), self.scaler.px(150), "Platform")

        painter.setFont(QFont("Roboto", self.scaler.font(11)))
        painter.setPen(QColor(DARK_PALETTE.text_secondary))
        painter.drawText(self.scaler.px(38), self.scaler.px(180), f"Version {self.version}")
        painter.drawText(
            self.scaler.px(38),
            self.scaler.px(205),
            "UDS - CAN - CAN FD - K-Line - LIN - FlexRay - DoIP - J1939",
        )
        painter.setPen(QColor(DARK_PALETTE.primary))
        painter.drawLine(
            self.scaler.px(36), self.scaler.px(70), self.scaler.px(200), self.scaler.px(70)
        )
        painter.end()
        return pixmap

    def report(self, message: str, percent: int = 0) -> None:
        """Show a progress message on the splash screen."""
        text = f"{message}...  {percent}%" if percent else message
        self.showMessage(
            text,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
            QColor(DARK_PALETTE.text_secondary),
        )
        QCoreApplication.processEvents()


class ApplicationStartup:
    """Runs the startup steps and reports them on the splash screen.

    Args:
        application: The Qt application instance.
        config: Application configuration.
        show_splash: Display the splash screen.
    """

    def __init__(
        self,
        application: QApplication,
        config: ConfigurationManager | None = None,
        show_splash: bool = True,
    ) -> None:
        """Create the startup helper."""
        self.application = application
        self.config = config or get_config()
        self.scaler = DPIScaler.from_screen()
        self.splash: SplashScreen | None = None
        if show_splash and bool(self.config.get("ui.show_splash", True)):
            self.splash = SplashScreen(self.scaler, str(self.config.get("application.version", "0.1.0")))
            self.splash.show()
            QCoreApplication.processEvents()

    def report(self, message: str, percent: int = 0) -> None:
        """Report one startup step."""
        _logger.info("startup: %s", message)
        if self.splash is not None:
            self.splash.report(message, percent)

    def run_steps(self, handlers: dict[str, Callable[[], Any]]) -> dict[str, Any]:
        """Execute the startup steps, reporting each one.

        Args:
            handlers: Mapping of step name to callable; unknown steps are just
                reported without doing anything.

        Returns:
            Mapping of step name to the value the handler returned.
        """
        results: dict[str, Any] = {}
        for name, percent in STARTUP_STEPS:
            self.report(name, percent)
            handler = handlers.get(name)
            if handler is not None:
                results[name] = handler()
        return results

    def finish(self, window: Any) -> None:
        """Close the splash screen once *window* is visible."""
        if self.splash is not None:
            self.splash.finish(window)
            self.splash = None

    @staticmethod
    def check_environment() -> list[str]:
        """Return a list of environment problems (empty when everything is fine).

        Example:
            >>> isinstance(ApplicationStartup.check_environment(), list)
            True
        """
        import sys

        problems: list[str] = []
        if sys.version_info < (3, 10):
            problems.append(f"Python 3.10+ is required, found {sys.version.split()[0]}")
        for module, purpose in (
            ("yaml", "configuration files"),
            ("PySide6", "the user interface"),
        ):
            try:
                __import__(module)
            except ImportError:
                problems.append(f"the {module} package is required for {purpose}")
        return problems


__all__ = ["ApplicationStartup", "SplashScreen", "STARTUP_STEPS"]
