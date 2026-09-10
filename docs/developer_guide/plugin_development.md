# Plugin development

Plugins live under `plugins/` and are discovered automatically at startup. They
can add data identifiers, seed-key algorithms, VCI drivers and event handlers.

## Minimal plugin

```python
from plugins.plugin_base import PluginBase


class MyPlugin(PluginBase):
    """Register the data identifiers of my OEM."""

    plugin_id = "oem.mycompany"
    name = "My company"
    version = "1.0.0"
    description = "OEM specific identifiers and seed-key algorithm"

    def on_initialize(self, context):
        self.register_dids({0xF1F0: {"name": "Calibration id", "format": "ASCII"}})
        self.log("ready")

    def on_shutdown(self):
        self.log("stopped")
```

Drop the file into `plugins/oem_specific/` — nothing else is required.

## What the context offers

| Attribute | Purpose |
|-----------|---------|
| `context.config` | Read and write configuration values |
| `context.bus` | Subscribe to and publish events |
| `context.logs` | Write to the platform log |
| `context.connections` | Inspect the active connection |
| `context.registry` | The DID definition registry |

## Registration helpers

```python
self.register_dids({0xF1F0: {"name": "...", "format": "ASCII", "unit": "V"}})
self.register_seed_key("my_algorithm", my_callable)
self.register_vci_driver("MY_VCI", MyDriverFactory)
self.subscribe(EventType.DIAG_SESSION_CHANGED, self.on_session)
```

A seed-key algorithm is any callable `(seed: bytes, params: dict) -> bytes`:

```python
def my_algorithm(seed, params=None):
    """Return the key for *seed*."""
    constant = int((params or {}).get("constant", 0x5A))
    return bytes(((b << 1) & 0xFF) ^ constant for b in seed)
```

It then appears in the security access panel next to the built-in algorithms.

## Bundled examples

* `plugins/oem_specific/template_oem_plugin.py` — the starting point
* `plugins/oem_specific/volkswagen_plugin.py` — VAG identifiers and routines
* `plugins/oem_specific/bmw_plugin.py` — BMW identifiers
* `plugins/custom/example_plugin.py` — event subscription

## Rules

* A failing plugin never stops the application; it is recorded as broken and
  shown in *Settings → Plugins*.
* `on_shutdown` must release every resource it acquired.
* Disable a plugin by adding its identifier to `plugins.disabled`.
