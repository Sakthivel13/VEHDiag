# Data analysis

## Response slicer

Load a response by pressing **Analyse** on any diagnostic panel, by pasting hex
or by pressing **Load last response**.

The byte map shows every byte with its index; slices are defined by name, start
and length (or start bit and bit length) and each one gets its own conversion:

| Format | Example result |
|--------|----------------|
| HEX | `F1 90` |
| ASCII | `WBAZZZ0GM12345678` |
| DEC unsigned / signed | `61840` / `-3696` |
| BIN | `11110001 10010000` |
| BCD | `20240115` |
| FLOAT32 / FLOAT64 | `3.14159` |
| PHYSICAL | `13.200 V` (factor, offset and unit) |

**Auto detect** creates a sensible SID/DID/data split for UDS responses. Slice
sets are saved as YAML profiles and reloaded for the next measurement.

## Data converter

Enter data in any format and every other representation appears at once: hex
with and without prefix, ASCII, per-byte decimals, 16/32-bit values in both byte
orders, binary, BCD and IEEE-754 floats, plus a physical value computed with
`raw x factor + offset`. Each row has a copy button.

## Data monitor

Add DIDs, choose a polling interval and press **Start**. The table shows the raw
bytes, the converted value, the unit and the running minimum and maximum. This
is the quickest way to watch a sensor while moving an actuator.

## Formulas

The physical converter accepts an arbitrary expression with `raw` as the
variable, evaluated in a restricted namespace that only exposes arithmetic and
a few maths functions:

```
raw * 0.1 - 40          temperature in degrees Celsius
raw * 0.00390625        percentage from a byte
sqrt(raw) * 2.5         non-linear sensor
```
