# Coding standards

## Style

* Line length 100, formatted with `black`, imports sorted with `isort`.
* `from __future__ import annotations` at the top of every module.
* Full type hints on every public function, method and dataclass field.
* Google style docstrings on every module, class and public function, with
  `Args`, `Returns` and `Raises` where they add information.
* Doctests for pure helpers — they double as executable documentation.

```python
def extract_bits(data: bytes, start_bit: int, bit_length: int) -> int:
    """Extract *bit_length* bits starting at *start_bit* as an integer.

    Args:
        data: Source bytes.
        start_bit: Absolute index of the first bit.
        bit_length: Number of bits to extract.

    Returns:
        The extracted bits, first bit becoming the most significant one.

    Raises:
        IndexError: The requested range exceeds *data*.

    Example:
        >>> extract_bits(b"\\xF0", 0, 4)
        15
    """
```

## Naming

| Kind | Convention | Example |
|------|-----------|---------|
| Module | `snake_case` | `isotp_handler.py` |
| Class | `PascalCase` | `TransferManager` |
| Function | `snake_case` | `read_data_by_identifier` |
| Constant | `UPPER_SNAKE` | `POSITIVE_RESPONSE_OFFSET` |
| Private | leading underscore | `_read_loop` |
| Interface | `I` prefix | `IVCIDriver` |
| Qt override | Qt naming plus `# noqa: N802` | `resizeEvent` |

## Errors

* Raise a subclass of `VDPError` with a readable message and a `details`
  mapping; the error dialog shows both.
* Never let a background thread die: catch, log and continue.
* Never swallow an error silently in a service — surface it through the event
  bus or the return value.

## Threading

* Qt widgets are touched only from the main thread.
* Long operations run in a `QThread`; results come back through signals.
* Shared state is protected by `threading.RLock`.
* Worker loops poll with a short timeout and check a stop flag, so they exit
  promptly on shutdown.

## Commits

`type(scope): summary` with `feat`, `fix`, `docs`, `test`, `refactor`, `perf`
or `chore`, for example `feat(diagnostics): add ResponseOnEvent (0x86)`.

## Definition of done

Formatted, linted, type checked, documented, covered by a test, and the whole
suite still passes.
