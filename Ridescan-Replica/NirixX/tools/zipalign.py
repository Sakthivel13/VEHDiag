#!/usr/bin/env python3
"""Minimal zipalign: rewite an APK so every STORED entry's data starts on a
4-byte boundary (extra-field padding), the rule Google's zipalign enforces —
strict package parsers and the resources.arsc mmap fast path depend on it.
Usage: zipalign.py in.apk out.apk"""
import struct
import sys
import zlib
import zipfile

def main(src, dst):
    zin = zipfile.ZipFile(src)
    out = bytearray()
    centrals = []
    for info in zin.infolist():
        data = zin.read(info.filename)
        name = info.filename.encode("utf-8")
        if info.compress_type == zipfile.ZIP_DEFLATED:
            co = zlib.compressobj(6, zlib.DEFLATED, -15)
            body = co.compress(data) + co.flush()
            method = 8
        else:
            body = data
            method = 0
        extra = b""
        if method == 0:
            pad = (4 - ((len(out) + 30 + len(name)) % 4)) % 4
            if pad:
                extra = struct.pack("<HH", 0xFFFF, pad) + b"\x00" * pad
        dos = info.date_time
        dostime = ((dos[3] << 11) | (dos[4] << 5) | (dos[5] >> 1)) & 0xFFFF
        dosdate = (((dos[0] - 1980) << 9) | (dos[1] << 5) | dos[2]) & 0xFFFF
        crc = zlib.crc32(data) & 0xFFFFFFFF
        local_off = len(out)
        out += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0, method,
                           dostime, dosdate, crc, len(body), len(data),
                           len(name), len(extra))
        out += name + extra + body
        centrals.append((info, name, method, dostime, dosdate, crc,
                         len(body), len(data), local_off))
    cd_off = len(out)
    for info, name, method, t, d, crc, csize, usize, loff in centrals:
        out += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0, method,
                           t, d, crc, csize, usize, len(name), 0, 0, 0, 0,
                           info.external_attr, loff)
        out += name
    n = len(centrals)
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, n, n,
                       len(out) - cd_off, cd_off, 0)
    open(dst, "wb").write(bytes(out))
    print("aligned %d entries (%d stored)" %
          (n, sum(1 for c in centrals if c[2] == 0)))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
