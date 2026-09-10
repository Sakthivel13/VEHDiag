# File transfer and flashing

## Supported formats

| Format | Extensions | Notes |
|--------|-----------|-------|
| Intel HEX | `.hex`, `.ihex`, `.ihx` | Record checksums validated, extended linear addressing |
| Motorola S-Record | `.mot`, `.s19`, `.s28`, `.s37`, `.srec` | S0 header, S1/S2/S3 data, S5 count, S7/S8/S9 end |
| Raw binary | `.bin`, `.raw` | Requires a base address; memory mapped above 4 MB |
| ELF | `.elf`, `.axf` | `PT_LOAD` segments, physical or virtual addresses |

## Procedure

1. Open *Diagnostics → Flash / transfer*.
2. **Add file** — the table shows the detected type, the start address and the
   size; a raw binary needs a base address.
3. Set compression, encryption, block size and the verification options.
4. Press **Start transfer**.

The sequence view tracks each step:

```
1. Extended session (0x10 0x03)        done
2. Disable DTC setting (0x85 0x02)     done
3. Disable communication (0x28 0x03)   done
4. Programming session (0x10 0x02)     done
5. Security unlock (0x27)              done
6. Request download (0x34)             done
7. Transfer data (0x36)   [######  ] 78 %
8. Transfer exit (0x37)
9. Check dependencies (0x31)
10. ECU reset (0x11 0x01)
```

Progress, speed, ETA and the block counter update live; **Pause** and **Cancel**
act between blocks.

## Safety

* Supply voltage must be stable — use a battery support unit.
* The ECU refuses the download with `0x93 voltageTooLow` when it is not.
* Never interrupt the power during step 7.
* Rejected blocks are retransmitted up to `transfer.retry_failed_blocks` times.
* After the transfer the ECU reports a checksum in the `0x37` response, which is
  compared with the CRC-32 computed locally.

## Scripted flashing

```python
from src.diagnostics.services.transfer_services.transfer_manager import (
    TransferManager, TransferOptions,
)

manager = TransferManager(
    client,
    TransferOptions(block_size=512, verify_after_transfer=True),
    on_progress=lambda p: print(f"{p.percent:.1f}% at {p.speed_bps/1024:.1f} KB/s"),
)
reports = manager.download_file("app.hex")
```

`download_files` handles a whole list, and `upload` reads memory back out of the
ECU.
