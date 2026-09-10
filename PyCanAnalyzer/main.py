"""Application Runner - System Bootstrap."""
import logging
import sys
from PyQt5.QtWidgets import QApplication
from utils.utils import ConfigLoader
from logging_system.logging_system import setup_logging
from devices.devices import DeviceManager
from pipeline.pipeline import Pipeline
from storage.storage import FrameStore
from discovery.discovery import DiscoveryEngine
from ml.ml_engine import MLEngine
from gui.gui import MainWindow


def main():
    # Load configuration
    config = ConfigLoader.load_config("configs/config.yaml")

    # Initialize logging
    setup_logging(config)

    # Initialize device manager
    device_manager = DeviceManager(config)

    # Initialize pipeline
    pipeline = Pipeline(device_manager, config)

    # Start pipeline
    # pipeline.start()  # commented out to avoid blocking

    # Initialize storage
    storage = FrameStore(config)

    # Initialize discovery engine
    discovery = DiscoveryEngine(config)

    # Load ML models
    ml_engine = MLEngine(config)

    logging.info("PyCANAnalyzer started successfully")

    # Create Qt Application
    app = QApplication(sys.argv)

    # Launch GUI
    gui = MainWindow(config, pipeline, discovery, ml_engine)
    gui.showMaximized()

    # Start event loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()