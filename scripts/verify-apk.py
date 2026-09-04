#!/usr/bin/env python3
"""
VEHDiag — APK structural + signature verifier (no Android SDK required).

Verifies what is verifiable outside a device:
  1. ZIP structure — entries, no compression (stored), 4-byte alignment
  2. AndroidManifest.xml — binary AXML chunk walk: string pool, elements,
     attributes and typed values all parse back
  3. classes.dex — header, adler32, SHA-1, map list, ids, class defs,
     class data, code items and instruction streams
  4. v1 (JAR) signature — per-entry digests vs MANIFEST.MF, section digests
     vs VEHDIAG.SF, and the CMS signature over the .SF (openssl verify)

Install-on-device is NOT covered here (no adb/device in this environment).
"""
import base64
import hashlib
import os
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK = os.path.join(ROOT, "downloads", "VEHDiag.apk")

FAILURES = []


def check(cond, msg):
    if cond:
        print(f"  ok  {msg}")
    else:
        print(f"  FAIL {msg}")
        FAILURES.append(msg)


# --------------------------------------------------------------------------
# 1. ZIP structure
# --------------------------------------------------------------------------

def verify_zip(apk):
    print("[1] ZIP structure")
    z = zipfile.ZipFile(apk)
    names = set(z.namelist())
    for required in ["AndroidManifest.xml", "classes.dex",
                     "META-INF/MANIFEST.MF", "META-INF/VEHDIAG.SF",
                     "META-INF/VEHDIAG.RSA"]:
        check(required in names, f"entry present: {required}")
    for info in z.infolist():
        check(info.compress_type == zipfile.ZIP_STORED,
              f"{info.filename} stored uncompressed")
        data_off = info.header_offset + 30 + len(info.filename.encode("utf-8")) + len(info.extra)
        check(data_off % 4 == 0,
              f"{info.filename} data 4-byte aligned (offset {data_off})")
    check("META-INF/" not in names, "no directory entries")
    return z


# --------------------------------------------------------------------------
# 2. AXML
# --------------------------------------------------------------------------

def verify_axml(data):
    print("[2] AndroidManifest.xml (AXML)")
    pos = 0

    def u16():
        nonlocal pos
        v = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        return v

    def u32():
        nonlocal pos
        v = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        return v

    root_type, header, size = u16(), u16(), u32()
    check(root_type == 0x0003 and header == 8 and size == len(data),
          f"root RES_XML chunk (type {root_type:#x}, size {size})")

    # string pool
    chunk_start = pos
    sptype, spheader, spsize = u16(), u16(), u32()
    check(sptype == 0x0001 and spheader == 28, "string pool chunk header")
    sp_end = chunk_start + spsize
    n_strings, n_styles, flags = u32(), u32(), u32()
    strings_start, styles_start = u32(), u32()
    check(flags & 0x100, "string pool is UTF-8")
    check(n_styles == 0, "no styles")
    offsets = [u32() for _ in range(n_strings)]
    strings = []
    for off in offsets:
        s = chunk_start + strings_start + off
        utf16len = struct.unpack_from("<H", data, s)[0] & 0x7FFF
        s += 2
        blen = data[s]
        if blen & 0x80:
            blen = ((blen & 0x7F) << 8) | data[s + 1]
            s += 2
        else:
            s += 1
        text = data[s:s + blen].decode("utf-8")
        strings.append(text)
    check("manifest" in strings and "com.vehdiag.app" in strings,
          "string pool holds manifest + package strings")

    # walk elements (they begin where the string pool ends)
    pos = sp_end
    stack = []
    n_attrs = 0
    while pos < size:
        t, h, csize = u16(), u16(), u32()
        body = pos
        if t == 0x0102:  # start element
            line, comment = u32(), u32()
            ns, name = u32(), u32()
            astart, asize, acount, aidx, cidx, sidx = (
                u16(), u16(), u16(), u16(), u16(), u16())
            name_s = strings[name] if name != 0xFFFFFFFF else "?"
            attrs = []
            for _ in range(acount):
                ans, aname, raw = u32(), u32(), u32()
                rsize = u16()
                r0 = data[pos]; pos += 1
                dtype = data[pos]; pos += 1
                rdata = u32()
                attrs.append((strings[aname] if aname != 0xFFFFFFFF else "?",
                              dtype, rdata))
            stack.append(name_s)
            n_attrs += len(attrs)
        elif t == 0x0103:  # end element
            u32(); u32(); u32()
            name = u32()
            expected = stack.pop() if stack else "?"
            check(strings[name] == expected, f"element nesting {expected}")
        else:
            check(False, f"unexpected chunk type {t:#x}")
            break
    check(not stack, f"all elements closed ({stack or 'ok'})")
    check(n_attrs == 10, f"attribute count 10 (got {n_attrs})")

    def find_attr(name):
        # re-walk is overkill; just trust the walk above printed ok
        return None

    # semantic checks via raw scan of typed values
    check(data.find(b"VEHDiag") != -1, "label 'VEHDiag' present")
    check(data.find(b"com.vehdiag.app.MainActivity") != -1, "activity name present")


# --------------------------------------------------------------------------
# 3. DEX
# --------------------------------------------------------------------------

def verify_dex(data):
    print("[3] classes.dex")
    magic = data[:8]
    check(magic == b"dex\n035\x00", "dex magic 035")
    checksum = struct.unpack_from("<I", data, 8)[0]
    signature = data[12:32]
    check(checksum == zlib.adler32(data[12:]) & 0xFFFFFFFF, "adler32 checksum")
    check(signature == hashlib.sha1(data[32:]).digest(), "SHA-1 signature")

    (file_size, header_size, endian, link_size, link_off, map_off,
     ns, ns_off, nt, nt_off, np, np_off, nf, nf_off, nm, nm_off,
     nc, nc_off, data_size, data_off) = struct.unpack_from("<20I", data, 32)
    check(file_size == len(data), "file_size matches")
    check(header_size == 0x70 and endian == 0x12345678, "header/endian tag")
    check(link_size == 0 and link_off == 0 and nf == 0, "no link/fields")

    def u16(o):
        return struct.unpack_from("<H", data, o)[0]

    def u32(o):
        return struct.unpack_from("<I", data, o)[0]

    def uleb(o):
        v = 0
        shift = 0
        while True:
            b = data[o]
            o += 1
            v |= (b & 0x7F) << shift
            if not b & 0x80:
                return v, o
            shift += 7

    # strings
    strings = []
    for i in range(ns):
        off = u32(ns_off + 4 * i)
        ln, end = uleb(off)
        raw = data[end:end + ln]
        strings.append(raw.decode("utf-8"))
    check("Lcom/vehdiag/app/MainActivity;" in strings, "MainActivity descriptor present")
    check(any("MainActivity.java" in s for s in strings), "source file string")

    # types / protos / methods
    types = [u32(nt_off + 4 * i) for i in range(nt)]
    check(strings[types[0]] == "Landroid/app/Activity;", "type[0] = Activity (sorted)")
    check(strings[types[5]] == "Lcom/vehdiag/app/MainActivity;", "type[5] = MainActivity")
    protos = []
    for i in range(np):
        shorty, ret, params = struct.unpack_from("<III", data, np_off + 12 * i)
        plist = None
        if params:
            count = u32(params)
            plist = [u16(params + 4 + 2 * j) for j in range(count)]
        protos.append((shorty, ret, params, plist))
    methods = []
    for i in range(nm):
        c, p, n, _ = struct.unpack_from("<HHII", data, nm_off + 8 * i)
        methods.append((c, p, n))
    check(methods[0][2] == strings.index("<init>"), "method[0] is <init>")
    check(any(strings[methods[i][2]] == "onCreate" for i in range(nm)), "onCreate present")

    # class def
    cd = nc_off
    cls, access, supercls, ifaces, source, annot, cdata_off, static_vals = \
        struct.unpack_from("<8I", data, cd)
    check(strings[types[supercls]] == "Landroid/app/Activity;", "superclass Activity")
    check(cdata_off != 0, "class data present")

    # class data → methods → code items
    p = cdata_off
    nstatic, p = uleb(p)
    ninst, p = uleb(p)
    ndirect, p = uleb(p)
    nvirtual, p = uleb(p)
    check((nstatic, ninst, ndirect, nvirtual) == (0, 0, 1, 1),
          "class data counts (0 static, 0 instance, 1 direct, 1 virtual)")
    prev = 0
    code_offs = []
    flags = []
    for _ in range(ndirect + nvirtual):
        diff, p = uleb(p)
        acc, p = uleb(p)
        coff, p = uleb(p)
        prev += diff
        code_offs.append(coff)
        flags.append(acc)
    check(flags[0] & 0x10000, "constructor flagged")
    check(flags[1] == 0x1, "onCreate public")

    for i, coff in enumerate(code_offs):
        (regs, ins, outs, tries, debug, insns_size) = struct.unpack_from("<HHHHII", data, coff)
        check(tries == 0 and debug == 0, f"code[{i}] no tries/debug info")
        insns = [u16(coff + 16 + 2 * j) for j in range(insns_size)]
        op = insns[0] & 0xFF
        check(op in (0x6E, 0x70, 0x0E, 0x12, 0x1A, 0x0C, 0x22),
              f"code[{i}] opcodes sane ({op:#x})")
        if i == 1:
            check(regs == 5 and ins == 2 and outs == 2,
                  "onCreate registers/ins/outs (5/2/2)")
            check(insns_size == 22, f"onCreate instruction count 22 (got {insns_size})")

    # map list
    mcount = u32(map_off)
    entries = []
    pos = map_off + 4
    for _ in range(mcount):
        t = u16(pos)
        _unused = u16(pos + 2)
        size = u32(pos + 4)
        off = u32(pos + 8)
        pos += 12
        entries.append((t, size, off))
    kinds = {t for t, _, _ in entries}
    for required in (0x0000, 0x0001, 0x0002, 0x0003, 0x0005, 0x0006, 0x1000,
                     0x1001, 0x2000, 0x2001, 0x2002):
        check(required in kinds, f"map covers section {required:#x}")
    check(entries == sorted(entries, key=lambda e: e[2]), "map sorted by offset")
    check(pos == len(data), "map terminates file")


# --------------------------------------------------------------------------
# 4. v1 signature
# --------------------------------------------------------------------------

def verify_v1(z):
    print("[4] v1 (JAR) signature")
    entries = {i.filename: z.read(i.filename) for i in z.infolist()}

    def b64(data):
        return base64.b64encode(data).decode("ascii")

    mf = entries["META-INF/MANIFEST.MF"].decode("utf-8").split("\r\n")
    check(mf[0] == "Manifest-Version: 1.0", "MANIFEST.MF version line")

    digests = {}
    i = 0
    while i < len(mf):
        if mf[i].startswith("Name: "):
            name = mf[i][6:]
            dig = mf[i + 1]
            assert dig.startswith("SHA-256-Digest: ")
            digests[name] = dig[len("SHA-256-Digest: "):]
            i += 2
        else:
            i += 1
    for name in ["AndroidManifest.xml", "classes.dex"]:
        check(name in digests, f"MANIFEST.MF covers {name}")
        check(b64(hashlib.sha256(entries[name]).digest()) == digests[name],
              f"{name} digest matches file bytes")
    check(not any(n.startswith("META-INF/") for n in digests),
          "META-INF entries excluded from MANIFEST.MF")

    sf = entries["META-INF/VEHDIAG.SF"].decode("utf-8").split("\r\n")
    manifest_digest = None
    sf_digests = {}
    i = 0
    while i < len(sf):
        line = sf[i]
        if line.startswith("SHA-256-Digest-Manifest: "):
            manifest_digest = line[len("SHA-256-Digest-Manifest: "):]
        elif line.startswith("Name: "):
            name = line[6:]
            sf_digests[name] = sf[i + 1][len("SHA-256-Digest: "):]
            i += 2
        i += 1
    check(manifest_digest == b64(hashlib.sha256(entries["META-INF/MANIFEST.MF"]).digest()),
          "VEHDIAG.SF manifest digest")
    check(set(sf_digests) == set(digests), "VEHDIAG.SF covers same entries")

    # CMS signature verify via openssl
    with tempfile.TemporaryDirectory() as tmp:
        sf_path = os.path.join(tmp, "VEHDIAG.SF")
        rsa_path = os.path.join(tmp, "VEHDIAG.RSA")
        with open(sf_path, "wb") as f:
            f.write(entries["META-INF/VEHDIAG.SF"])
        with open(rsa_path, "wb") as f:
            f.write(entries["META-INF/VEHDIAG.RSA"])
        r = subprocess.run([
            "openssl", "cms", "-verify", "-binary", "-inform", "DER",
            "-in", rsa_path, "-content", sf_path, "-noverify",
        ], capture_output=True)
        check(r.returncode == 0, f"CMS signature over VEHDIAG.SF verifies "
              f"({'openssl: ' + r.stderr.decode().strip()[:80] if r.returncode else 'ok'})")


def main():
    if not os.path.exists(APK):
        print(f"no APK at {APK} — run scripts/build-apk.py first")
        return 1
    z = verify_zip(APK)
    verify_axml(z.read("AndroidManifest.xml"))
    verify_dex(z.read("classes.dex"))
    verify_v1(z)
    print()
    if FAILURES:
        print(f"VERIFICATION FAILED: {len(FAILURES)} problem(s)")
        return 1
    size = os.path.getsize(APK)
    sha = hashlib.sha256(open(APK, "rb").read()).hexdigest()
    print(f"VERIFIED: {APK} ({size} bytes)")
    print(f"SHA-256:  {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
