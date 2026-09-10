.PHONY: help install install-dev run test cov lint format clean build

PY ?= python3

help:
	@echo "install      install runtime dependencies"
	@echo "install-dev  install development dependencies"
	@echo "run          launch the GUI application"
	@echo "run-headless run the headless demo (no Qt required)"
	@echo "test         run the test suite"
	@echo "cov          run tests with coverage report"
	@echo "lint         flake8 + mypy"
	@echo "format       black + isort"
	@echo "build        build a distributable with PyInstaller"

install:
	$(PY) -m pip install -r requirements.txt

install-dev:
	$(PY) -m pip install -r requirements-dev.txt

run:
	$(PY) main.py

run-headless:
	$(PY) demo_headless.py

test:
	$(PY) -m pytest

cov:
	$(PY) -m pytest --cov=src --cov=ui --cov-report=term-missing

lint:
	$(PY) -m flake8 src ui plugins
	$(PY) -m mypy src

format:
	$(PY) -m black src ui plugins tests
	$(PY) -m isort src ui plugins tests

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache
	find . -name __pycache__ -type d -exec rm -rf {} +

build:
	$(PY) scripts/build_linux.py
