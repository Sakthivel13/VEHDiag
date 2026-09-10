#!/usr/bin/env python3
"""Vehicle Diagnostics Platform - application entry point.

Usage::

    python main.py                 # start the graphical application
    python main.py --headless      # run the headless self-test
    python main.py --virtual       # force the virtual VCI (default)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Make the project importable when started from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.core.application import VERSION, Application  # noqa: E402
from src.core.configuration_manager import ConfigurationManager  # noqa: E402


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line arguments.

    Example:
        >>> parse_arguments(["--headless"]).headless
        True
    """
    parser = argparse.ArgumentParser(
        prog="vdp", description="Vehicle Diagnostics Platform"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--headless", action="store_true", help="run without a user interface")
    parser.add_argument("--config", type=str, default="", help="path to a configuration file")
    parser.add_argument("--vci", type=str, default="", help="VCI type to use (default: VIRTUAL)")
    parser.add_argument("--protocol", type=str, default="", help="protocol to use")
    parser.add_argument("--theme", type=str, default="", help="theme (dark, light, high_contrast)")
    parser.add_argument("--log-level", type=str, default="", help="log level")
    parser.add_argument("--no-splash", action="store_true", help="skip the splash screen")
    return parser.parse_args(argv)


def build_configuration(arguments: argparse.Namespace) -> ConfigurationManager:
    """Create the configuration manager honouring the command line overrides."""
    config = ConfigurationManager(user_config=arguments.config or None)
    if arguments.vci:
        config.set("connection.vci_type", arguments.vci.upper(), publish=False)
    if arguments.protocol:
        config.set("connection.protocol", arguments.protocol.upper(), publish=False)
    if arguments.theme:
        config.set("ui.theme", arguments.theme.lower(), publish=False)
    if arguments.log_level:
        config.set("logging.level", arguments.log_level.upper(), publish=False)
    if arguments.no_splash:
        config.set("ui.show_splash", False, publish=False)
    return config


def run_headless(config: ConfigurationManager) -> int:
    """Run a self-test against the built-in ECU simulator."""
    from src.communication.connection_manager import ConnectionProfile

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")
    application = Application(config, headless=True)
    application.initialize()
    application.install_exception_handler()
    application.start()

    print(f"Vehicle Diagnostics Platform {VERSION} (headless)")
    print(f"detected interfaces: {[d.label for d in application.detected_devices]}")

    application.connect(ConnectionProfile.from_config(config))
    client = application.create_client()
    print(f"session change : {client.change_session(0x03).summary()}")
    response = client.read_data_by_identifier(0xF190)
    print(f"VIN            : {response.raw[3:].decode('ascii', 'replace')}")
    report = application.dispatcher.execute(0x19, 0x02, 0xFF) if application.dispatcher else None
    print(f"DTCs           : {len(report) if report else 0}")
    print(f"statistics     : {client.get_info()['statistics']}")
    application.shutdown()
    return 0


def run_gui(config: ConfigurationManager, arguments: argparse.Namespace) -> int:
    """Start the graphical application."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from ui.app_startup import ApplicationStartup
    from ui.controllers.main_controller import MainController
    from ui.main_window import MainWindow

    qt_application = QApplication(sys.argv)
    qt_application.setApplicationName(str(config.get("application.name", "VDP")))
    qt_application.setApplicationVersion(VERSION)
    qt_application.setOrganizationName("Vehicle Diagnostics Platform")

    startup = ApplicationStartup(qt_application, config, not arguments.no_splash)
    problems = startup.check_environment()
    for problem in problems:
        print(f"environment problem: {problem}", file=sys.stderr)

    application = Application(config)
    startup.report("Loading configuration", 10)
    context = application.initialize()
    application.install_exception_handler()

    startup.report("Building the user interface", 95)
    window = MainWindow(config, application.bus, context.registry)
    controller = MainController(window, config, application.logs, context.registry, application.bus)
    window.controller = controller  # type: ignore[attr-defined]
    application.add_shutdown_hook(controller.shutdown)

    window.apply_theme()
    # ``_apply_geometry`` has already set the maximised window state, so a
    # plain show() honours it; showMaximized() is used as a belt-and-braces
    # fallback for platforms that drop the pre-show state.
    if window.isMaximized() or bool(config.get("ui.start_maximized", True)):
        window.showMaximized()
    else:
        window.show()
    startup.finish(window)
    application.start()
    controller.start()

    exit_code = qt_application.exec()
    application.shutdown()
    return int(exit_code)


def main(argv: list[str] | None = None) -> int:
    """Program entry point."""
    arguments = parse_arguments(argv)
    config = build_configuration(arguments)
    if arguments.headless:
        return run_headless(config)
    try:
        return run_gui(config, arguments)
    except ImportError as exc:
        print(f"the graphical interface is unavailable ({exc});", file=sys.stderr)
        print("falling back to the headless self-test", file=sys.stderr)
        return run_headless(config)


if __name__ == "__main__":
    raise SystemExit(main())
