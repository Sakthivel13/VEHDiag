# Development setup

```bash
git clone <repository-url>
cd vehicle_diagnostics_platform
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
```

## Everyday commands

```bash
make run           # start the GUI
make run-headless  # start the headless self-test
make test          # run the whole suite
make cov           # coverage report
make lint          # flake8 + mypy
make format        # black + isort
```

Without `make`:

```bash
python main.py
python -m pytest
python -m pytest -m unit          # only the fast tests
python -m pytest --cov=src
python -m flake8 src ui plugins
python -m mypy src
python -m black src ui plugins tests && python -m isort src ui plugins tests
```

## Running without a display

Every test and the headless mode work without an X server. The Qt tests use
`QT_QPA_PLATFORM=offscreen`, which the root `conftest.py` sets automatically;
it also links the `libxkbcommon` copy bundled with other wheels when the system
library is missing, and skips the UI tests when Qt cannot be loaded at all.

## Layout rules

* `src/` must never import from `ui/` — the backend stays headless.
* A widget never talks to the diagnostic layer directly; a controller does.
* Blocking work belongs in a `QThread`, never in a slot.
* New hardware, protocols, parsers and loggers implement the matching interface
  in `src/core/interfaces/`.

## Adding a test

Unit tests go next to the layer they cover, integration tests use the
`connection`/`client` fixtures from `tests/conftest.py`, and UI tests use
`qtbot` plus the `main_window` fixture. Everything runs against the built-in
ECU simulator, so tests need no hardware and stay fast.
