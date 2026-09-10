# Developer mode

Developer mode turns the platform into a test bench: each UDS service gets a
card, cards can be reordered by dragging, and each one can execute a raw
payload, a Python script, or both.

Open it with the toolbar button or `Ctrl+D`.

## The service card

```
+----------------------------------------------------------+
| :: 1  Session Control (0x10)      * Idle  [x] Enabled  v x|
|   Test file : /path/to/session_test.py        [Browse][x] |
|   Payload   : 10 03                          Script       |
|                                    45.2 ms   [ Run > ]    |
+----------------------------------------------------------+
```

* **Drag handle** — reorder; the sequence numbers update automatically.
* **Enabled** — disabled cards are skipped by *Run all*.
* **Test file** — any `.py` file exposing a `TestScript` class.
* **Payload** — validated hexadecimal, pre-filled with the service identifier.
* **Status LED** — grey idle, blue running, green pass, red fail, amber skipped.

## Execution modes

| Mode | Behaviour |
|------|-----------|
| Payload | Send the bytes, pass on a positive response (or on the expected NRC) |
| Script | Import the mapped file and run `setup`, `execute`, `teardown` |
| Combined | Run the script first, then verify with the payload |

## Running

* **Run** on a card executes only that step.
* **Run all** executes every enabled card top to bottom.
* **Stop on failure** aborts and marks the rest as skipped.
* **Cancel** stops within 500 ms and marks the remainder as cancelled.

The status panel shows the running step, the progress, the elapsed times and a
live TX/RX stream. The results table records the request, the response, the
duration and the message, and exports to HTML, CSV or JSON.

## Writing a test script

```python
class TestScript:
    """Verify the VIN and its length."""

    name = "VIN check"

    def __init__(self, api):
        self.api = api

    def setup(self):
        self.api.change_session(0x03)

    def execute(self):
        vin = self.api.read_did(0xF190).decode("ascii")
        self.api.log(f"VIN: {vin}")
        self.api.assert_equal(len(vin), 17, "a VIN must be 17 characters")
        return "PASS"

    def teardown(self):
        self.api.change_session(0x01)
```

### The script API

| Group | Methods |
|-------|---------|
| Raw | `send_request`, `send_hex`, `send_raw`, `get_last_response` |
| Services | `change_session`, `read_did`, `write_did`, `read_dtcs`, `clear_dtcs`, `security_unlock`, `routine`, `ecu_reset`, `tester_present` |
| Assertions | `assert_positive_response`, `assert_nrc`, `assert_equal`, `assert_data`, `assert_true` |
| Utilities | `wait`, `log`, `set_variable`, `get_variable`, `session`, `is_unlocked` |

Returning `"PASS"`, `"FAIL"`, a boolean or `None` (which counts as pass) sets
the result; raising an exception marks the step as an error.

### Safety

Scripts are parsed before execution and rejected when they import `os`,
`subprocess`, `socket`, `ctypes`, or call `eval`, `exec` or `open`. They run in
a worker thread, so a hanging script never freezes the application.

## Bundled samples

`sample_test_scripts/` contains ready-to-use scripts: `read_all_dids.py`,
`read_all_dtcs.py`, `clear_all_dtcs.py`, `security_unlock.py`, `flash_ecu.py`,
`eol_test_sequence.py` and `custom_test_template.py`.

## Sequences

**Save** and **Load** persist the whole sequence — order, mapped files,
payloads and the enabled flags — as YAML:

```yaml
name: End of line
stop_on_failure: true
test_sequence:
  - {service: "0x10", name: Session Control, payload: "10 03", order: 1, enabled: true}
  - {service: "0x22", name: Read VIN, payload: "22 F1 90", order: 2, enabled: true}
```
