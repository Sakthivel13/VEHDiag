#!/usr/bin/env python3
"""
VEHDiag — pure-Python APK builder (no JDK / Android SDK required).

Produces a minimal, real, installable APK:
  * AndroidManifest.xml — hand-built binary AXML (RES_XML chunks)
  * classes.dex — hand-built minimal DEX: MainActivity, a WebView shell that
    loads the VEHDiag releases page (OTA-style web client; the Bluetooth
    client is the documented roadmap architecture)
  * v1 (JAR) signature — RSA key + self-signed cert via openssl, CMS SignedData
    over META-INF/VEHDIAG.SF; SHA-256 digests only (required on API 18+)

Artifacts (gitignored): downloads/VEHDiag.apk, downloads/VEHDiag.zip,
downloads/SHA256SUMS.txt. Signing keys live in keys/ (NEVER committed).

Verification: scripts/verify-apk.py re-parses the AXML, the DEX and
re-verifies every v1 signature digest + the CMS signature.
"""
import base64
import hashlib
import os
import struct
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADS = os.path.join(ROOT, "downloads")
KEYS = os.path.join(ROOT, "keys")

APP_ID = "com.vehdiag.app"
VERSION_NAME = "0.1.0"
VERSION_CODE = 1
MIN_SDK = 24
TARGET_SDK = 29
LANDING_URL = "https://github.com/Sakthivel13/VEHDiag/releases/latest"
ACTIVITY = APP_ID + ".MainActivity"
ANDROID_NS = "http://schemas.android.com/apk/res/android"

# --------------------------------------------------------------------------
# binary AXML builder
# --------------------------------------------------------------------------

RES_STRING_POOL = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_ELEMENT = 0x0102
RES_XML_END_ELEMENT = 0x0103

TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_BOOLEAN = 0x12
NONE = 0xFFFFFFFF


class StringPool:
    def __init__(self):
        self._map = {}
        self._list = []

    def idx(self, s):
        if s not in self._map:
            self._map[s] = len(self._list)
            self._list.append(s)
        return self._map[s]

    def chunks(self):
        # string offsets are relative to stringsStart
        offsets = []
        data = b""
        for s in self._list:
            offsets.append(len(data))
            utf16len = len(s.encode("utf-16-le")) // 2
            raw = s.encode("utf-8")
            entry = struct.pack("<H", utf16len)
            if len(raw) < 0x80:
                entry += bytes([len(raw)])
            else:
                entry += struct.pack("<H", 0x8000 | len(raw))
            entry += raw + b"\x00"
            data += entry
        n = len(self._list)
        header_size = 28
        strings_start = header_size + 4 * n  # offsets only; styleCount == 0
        body = struct.pack("<HHII", RES_STRING_POOL, header_size, strings_start + len(data), n) \
            + struct.pack("<IIII", 0, 0x100, strings_start, 0) \
            + b"".join(struct.pack("<I", o) for o in offsets) \
            + data
        return body


def res_value(dtype, data):
    return struct.pack("<HBB", 8, 0, dtype) + struct.pack("<I", data & 0xFFFFFFFF)


def attribute(pool, ns, name, raw, dtype, data):
    return struct.pack("<III", ns, pool.idx(name), pool.idx(raw) if raw is not None else NONE) \
        + res_value(dtype, data if dtype != TYPE_STRING else pool.idx(data))


def start_element(pool, name, attrs, line):
    n = len(attrs)
    header = struct.pack("<HHII", RES_XML_START_ELEMENT, 16, 36 + 20 * n, line) \
        + struct.pack("<I", NONE) + struct.pack("<I", NONE) \
        + struct.pack("<I", pool.idx(name)) \
        + struct.pack("<HHHHHH", 20, 20, n, 0, 0, 0)
    return header + b"".join(attrs)


def end_element(pool, name, line):
    return struct.pack("<HHII", RES_XML_END_ELEMENT, 16, 24, line) \
        + struct.pack("<I", NONE) + struct.pack("<I", NONE) \
        + struct.pack("<I", pool.idx(name))


def build_axml():
    p = StringPool()
    A = lambda name, raw, dtype, data: attribute(p, p.idx(ANDROID_NS), name, raw, dtype, data)
    line = [1]

    def ln():
        line[0] += 1
        return line[0]

    body = b""
    body += start_element(p, "manifest", [
        attribute(p, NONE, "package", APP_ID, TYPE_STRING, APP_ID),
        A("versionCode", "1", TYPE_INT_DEC, VERSION_CODE),
        A("versionName", VERSION_NAME, TYPE_STRING, VERSION_NAME),
    ], ln())
    body += start_element(p, "uses-sdk", [
        A("minSdkVersion", str(MIN_SDK), TYPE_INT_DEC, MIN_SDK),
        A("targetSdkVersion", str(TARGET_SDK), TYPE_INT_DEC, TARGET_SDK),
    ], ln())
    body += end_element(p, "uses-sdk", ln())
    body += start_element(p, "application", [
        A("label", "VEHDiag", TYPE_STRING, "VEHDiag"),
    ], ln())
    body += start_element(p, "activity", [
        A("name", ACTIVITY, TYPE_STRING, ACTIVITY),
        A("exported", "true", TYPE_INT_BOOLEAN, 0xFFFFFFFF),
    ], ln())
    body += start_element(p, "intent-filter", [], ln())
    body += start_element(p, "action", [
        A("name", "android.intent.action.MAIN", TYPE_STRING, "android.intent.action.MAIN"),
    ], ln())
    body += end_element(p, "action", ln())
    body += start_element(p, "category", [
        A("name", "android.intent.category.LAUNCHER", TYPE_STRING, "android.intent.category.LAUNCHER"),
    ], ln())
    body += end_element(p, "category", ln())
    body += end_element(p, "intent-filter", ln())
    body += end_element(p, "activity", ln())
    body += end_element(p, "application", ln())
    body += end_element(p, "manifest", ln())

    pool = p.chunks()
    size = 8 + len(pool) + len(body)
    return struct.pack("<HHI", RES_XML_TYPE, 8, size) + pool + body


# --------------------------------------------------------------------------
# minimal DEX builder
# --------------------------------------------------------------------------

def uleb(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


class DexBuilder:
    def __init__(self):
        self.strings = {}   # string -> idx
        self.string_items = []  # idx -> bytes (data item, without alignment)

    def s(self, text):
        if text not in self.strings:
            self.strings[text] = len(self.string_items)
            utf16len = len(text.encode("utf-16-le")) // 2
            raw = text.encode("utf-8")
            item = uleb(utf16len) + raw + b"\x00"
            self.string_items.append(item)
        return self.strings[text]

    def build(self):
        # --- string ids (sorted by content, as required) ---
        order = sorted(self.string_items, key=lambda item: item.split(b"\x00", 1)[0])
        self._string_off = {}
        for sidx, item in enumerate(order):
            self._string_off[sidx] = item  # placeholder; offsets computed later
        # rebuild: assign string idx from sorted contents
        new_map = {}
        for i, item in enumerate(order):
            # find original index of this item
            orig = self.string_items.index(item)
            new_map[orig] = i
        # content -> new idx
        content_idx = {}
        for text, orig in self.strings.items():
            content_idx[text] = new_map[orig]
        self.strings = content_idx
        self.string_items = order

        s = self.strings
        # type_ids sorted by descriptor string index (DEX requirement).
        # Sorted descriptors: Landroid/app/Activity; Landroid/content/Context;
        # Landroid/os/Bundle; Landroid/webkit/WebSettings; Landroid/webkit/WebView;
        # Lcom/vehdiag/app/MainActivity; Ljava/lang/String; V Z
        TYPE_DESC = [s["Landroid/app/Activity;"], s["Landroid/content/Context;"],
                     s["Landroid/os/Bundle;"], s["Landroid/webkit/WebSettings;"],
                     s["Landroid/webkit/WebView;"], s["Lcom/vehdiag/app/MainActivity;"],
                     s["Ljava/lang/String;"], s["V"], s["Z"]]
        # proto_ids sorted by return type index, then argument list
        PROTO = [
            (s["()Landroid/webkit/WebSettings;"], s["Landroid/webkit/WebSettings;"], None),
            (s["()V"], s["V"], None),
            (s["(Landroid/content/Context;)V"], s["V"], [s["Landroid/content/Context;"]]),
            (s["(Landroid/os/Bundle;)V"], s["V"], [s["Landroid/os/Bundle;"]]),
            (s["(Landroid/webkit/WebView;)V"], s["V"], [s["Landroid/webkit/WebView;"]]),
            (s["(Ljava/lang/String;)V"], s["V"], [s["Ljava/lang/String;"]]),
            (s["(Z)V"], s["V"], [s["Z"]]),
        ]
        # (class, proto, name) sorted by (class_idx, name_idx, proto_idx).
        # Indices: 0 Activity.<init>, 1 Activity.setContentView,
        # 2 WebView.<init>, 3 WebView.getSettings, 4 WebView.setJavaScriptEnabled,
        # 5 WebView.loadUrl, 6 MainActivity.<init>, 7 MainActivity.onCreate
        METHOD = [
            (0, 1, s["<init>"]),                          # 0 Activity.<init>
            (0, 4, s["setContentView"]),                  # 1 Activity.setContentView
            (4, 2, s["<init>"]),                          # 2 WebView.<init>
            (4, 0, s["getSettings"]),                     # 3 WebView.getSettings
            (4, 6, s["setJavaScriptEnabled"]),            # 4 WebView.setJavaScriptEnabled
            (4, 5, s["loadUrl"]),                         # 5 WebView.loadUrl
            (5, 1, s["<init>"]),                          # 6 MainActivity.<init>
            (5, 3, s["onCreate"]),                        # 7 MainActivity.onCreate
        ]
        T_Activity = 0
        T_Context = 1
        T_Bundle = 2
        T_WebSettings = 3
        T_WebView = 4
        T_Main = 5
        T_String = 6

        # instructions -----------------------------------------------------
        # <init>: invoke-direct {v0}, Activity.<init> ; return-void
        init_units = [
            0x1070, 0x0000, 0x0000,   # invoke-direct {v0} method@0
            0x000E,                   # return-void
        ]
        # onCreate(Bundle): new WebView, getSettings, setJavaScriptEnabled(true),
        # loadUrl, setContentView
        create_units = [
            0x0122, 0x0004,           # new-instance v1, WebView (type@4)
            0x2070, 0x0002, 0x0001,   # invoke-direct {v1,v0}, WebView.<init> (method@2)
            0x106E, 0x0003, 0x0001,   # invoke-virtual {v1}, WebView.getSettings (method@3)
            0x020C,                   # move-result-object v2
            0x1312,                   # const/4 v3, #1
            0x206E, 0x0004, 0x0023,   # invoke-virtual {v2,v3}, setJavaScriptEnabled (method@4)
            0x041A, self.strings[LANDING_URL],  # const-string v4, url
            0x206E, 0x0005, 0x0014,   # invoke-virtual {v1,v4}, WebView.loadUrl (method@5)
            0x206E, 0x0001, 0x0001,   # invoke-virtual {v0,v1}, Activity.setContentView (method@1)
            0x000E,                   # return-void
        ]

        def code_item(regs, ins, outs, units):
            insns = b"".join(struct.pack("<H", u) for u in units)
            if len(insns) % 4:
                insns += b"\x00\x00"
            return struct.pack("<HHHHI", regs, ins, outs, 0, 0) \
                + struct.pack("<I", len(units)) + insns

        init_code = code_item(1, 1, 1, init_units)
        create_code = code_item(5, 2, 2, create_units)

        # ------------------------------------------------------------------
        # assemble sections with offsets
        header_size = 0x70
        n_strings = len(self.string_items)
        n_types = len(TYPE_DESC)
        n_protos = len(PROTO)
        n_methods = len(METHOD)
        n_classes = 1
        n_fields = 0

        string_ids_off = header_size
        type_ids_off = string_ids_off + 4 * n_strings
        proto_ids_off = type_ids_off + 4 * n_types
        field_ids_off = 0
        method_ids_off = proto_ids_off + 12 * n_protos
        class_defs_off = method_ids_off + 8 * n_methods
        data_off = class_defs_off + 32 * n_classes

        out = bytearray()

        def place(data, align=1):
            while len(out) % align:
                out.append(0)
            off = data_off + len(out)
            out.extend(data)
            return off

        # data section: type lists first (4-aligned), then string items,
        # class_data, code items
        type_lists = []
        for (_shorty, _ret, params) in PROTO:
            if params is None:
                type_lists.append(None)
            else:
                blob = struct.pack("<I", len(params)) + b"".join(struct.pack("<H", t) for t in params)
                if len(blob) % 4:
                    blob += b"\x00" * (4 - len(blob) % 4)
                type_lists.append(blob)
        type_list_offs = []
        for blob in type_lists:
            type_list_offs.append(place(blob, 4) if blob else 0)

        string_offs = []
        for item in self.string_items:
            string_offs.append(place(item, 1))

        init_code_off = place(init_code, 4)
        create_code_off = place(create_code, 4)

        # class data: no static/instance fields; 1 direct + 1 virtual method
        # (each encoded method = method_idx_diff, access_flags, code_off)
        class_data = uleb(0) + uleb(0) + uleb(1) + uleb(1)
        class_data += uleb(6) + uleb(0x10001) + uleb(init_code_off)    # MainActivity.<init> (idx 6)
        class_data += uleb(1) + uleb(0x1) + uleb(create_code_off)      # MainActivity.onCreate (idx 7)
        class_data_off = place(class_data, 1)

        # map list (sorted by offset) — built after map_off is known
        map_entries = []
        map_entries.append((0x0000, 1, 0))
        map_entries.append((0x0001, n_strings, string_ids_off))
        map_entries.append((0x0002, n_types, type_ids_off))
        map_entries.append((0x0003, n_protos, proto_ids_off))
        map_entries.append((0x0005, n_methods, method_ids_off))
        map_entries.append((0x0006, n_classes, class_defs_off))
        tl_offs = [o for o in type_list_offs if o]
        map_entries.append((0x1001, len(type_lists), min(tl_offs) if tl_offs else 0))
        map_entries.append((0x2000, 1, class_data_off))
        map_entries.append((0x2001, 2, init_code_off))
        for o in string_offs:
            map_entries.append((0x2002, 1, o))
        map_entries.sort(key=lambda e: e[2])

        data_size = len(out)          # from data_off to map_off
        map_off = data_off + data_size
        map_entries.append((0x1000, 1, map_off))
        map_entries.sort(key=lambda e: e[2])
        map_size = 4 + 12 * len(map_entries)
        file_size = map_off + map_size

        # header
        header = struct.pack("<8s", b"dex\n035\x00")
        header += b"\x00" * 4                       # checksum placeholder
        header += b"\x00" * 20                      # signature placeholder
        header += struct.pack("<I", file_size)
        header += struct.pack("<I", header_size)
        header += struct.pack("<I", 0x12345678)
        header += struct.pack("<II", 0, 0)          # link
        header += struct.pack("<I", map_off)
        header += struct.pack("<II", n_strings, string_ids_off)
        header += struct.pack("<II", n_types, type_ids_off)
        header += struct.pack("<II", n_protos, proto_ids_off)
        header += struct.pack("<II", n_fields, field_ids_off)
        header += struct.pack("<II", n_methods, method_ids_off)
        header += struct.pack("<II", n_classes, class_defs_off)
        header += struct.pack("<II", data_size, data_off)
        assert len(header) == 0x70

        tables = bytearray()
        tables += b"".join(struct.pack("<I", o) for o in string_offs)
        tables += b"".join(struct.pack("<I", t) for t in TYPE_DESC)
        for (shorty, ret, _params) in PROTO:
            tables += struct.pack("<III", shorty, ret, 0)
        # fill proto parameter offsets (protos start after string+type tables)
        proto_base_in_tables = 4 * n_strings + 4 * n_types
        for i, (shorty, ret, params) in enumerate(PROTO):
            poff = type_list_offs[i] if params else 0
            off = proto_base_in_tables + 12 * i + 8
            tables[off:off + 4] = struct.pack("<I", poff)
        tables += b"".join(struct.pack("<HHI", c, proto, name) for (c, proto, name) in METHOD)
        class_def = struct.pack("<IIIII", T_Main, 0x1, T_Activity, 0, self.strings["MainActivity.java"])
        class_def += struct.pack("<III", 0, class_data_off, 0)
        tables += class_def

        assert len(tables) == data_off - header_size

        # map
        map_body = struct.pack("<I", len(map_entries))
        for (t, size, off) in map_entries:
            map_body += struct.pack("<HHI", t, 0, size) + struct.pack("<I", off)

        file_body = bytes(tables) + bytes(out) + map_body
        assert len(file_body) == file_size - 0x70

        # checksum + signature (header[8:12] and header[12:32] are placeholders)
        tail = header[32:] + file_body
        signature = hashlib.sha1(tail).digest()
        checksum = __import__("zlib").adler32(signature + tail) & 0xFFFFFFFF
        return header[:8] + struct.pack("<I", checksum) + signature + tail


# --------------------------------------------------------------------------
# v1 (JAR) signing
# --------------------------------------------------------------------------

def ensure_keypair():
    os.makedirs(KEYS, exist_ok=True)
    key = os.path.join(KEYS, "vehdiag-dev-key.pem")
    cert = os.path.join(KEYS, "vehdiag-dev-cert.pem")
    if not (os.path.exists(key) and os.path.exists(cert)):
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key, "-out", cert,
            "-days", "3650", "-nodes",
            "-subj", "/C=IN/O=VEHDiag/CN=VEHDiag APK (development)",
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return key, cert


def sign_v1(entries):
    """entries: {name: raw_bytes}. Returns {name: bytes} of META-INF files."""
    def b64(data):
        return base64.b64encode(data).decode("ascii")

    created_by = "Created-By: VEHDiag build (github.com/Sakthivel13/VEHDiag)\r\n"

    # MANIFEST.MF
    mf = "Manifest-Version: 1.0\r\n" + created_by + "\r\n"
    for name in sorted(entries):
        if name.startswith("META-INF/"):
            continue
        mf += f"Name: {name}\r\n"
        mf += f"SHA-256-Digest: {b64(hashlib.sha256(entries[name]).digest())}\r\n\r\n"
    mf_bytes = mf.encode("utf-8")

    # VEHDIAG.SF
    sf = "Signature-Version: 1.0\r\n" + created_by
    sf += f"SHA-256-Digest-Manifest: {b64(hashlib.sha256(mf_bytes).digest())}\r\n\r\n"
    manifest_sections = {}
    pos = 0
    lines = mf.split("\r\n")
    i = 0
    while i < len(lines):
        if lines[i].startswith("Name: "):
            name = lines[i][6:]
            j = i
            # a section ends at the blank line following its attributes
            while j < len(lines) and lines[j] != "":
                j += 1
            section = "\r\n".join(lines[i:j + 2]).encode("utf-8")  # include trailing blank line
            manifest_sections[name] = section
            i = j + 1
        else:
            i += 1
    for name in sorted(manifest_sections):
        sf += f"Name: {name}\r\n"
        sf += f"SHA-256-Digest: {b64(hashlib.sha256(manifest_sections[name]).digest())}\r\n\r\n"
    sf_bytes = sf.encode("utf-8")

    # VEHDIAG.RSA — CMS SignedData over the .SF
    key, cert = ensure_keypair()
    tmp_dir = os.path.join(KEYS, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    sf_path = os.path.join(tmp_dir, "VEHDIAG.SF")
    rsa_path = os.path.join(tmp_dir, "VEHDIAG.RSA")
    with open(sf_path, "wb") as f:
        f.write(sf_bytes)
    subprocess.run([
        "openssl", "cms", "-sign", "-binary", "-nodetach",
        "-in", sf_path, "-signer", cert, "-inkey", key,
        "-outform", "DER", "-out", rsa_path,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(rsa_path, "rb") as f:
        rsa_bytes = f.read()

    return {
        "META-INF/MANIFEST.MF": mf_bytes,
        "META-INF/VEHDIAG.SF": sf_bytes,
        "META-INF/VEHDIAG.RSA": rsa_bytes,
    }


def assemble_apk(path, entries):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            zf.writestr(info, data)
    # 4-byte align stored payloads via zip extra fields (zipalign equivalent
    # for uncompressed entries)
    aligned = os.path.join(os.path.dirname(path), "aligned.tmp")
    with zipfile.ZipFile(path, "r") as zin:
        with open(aligned, "wb") as fout, zipfile.ZipFile(fout, "w", zipfile.ZIP_STORED) as zout:
            # pass 1: compute pads
            pads = {}
            pos = 0
            for info in zin.infolist():
                # local header: 30 + name + extra; extra may change
                extra = b""
                base = 30 + len(info.filename.encode("utf-8")) + len(extra)
                data_pos = pos + base
                pad = (-data_pos) % 4
                if pad:
                    extra = struct.pack("<HH", 0x0000, pad) + b"\x00" * pad
                    data_pos = pos + 30 + len(info.filename.encode("utf-8")) + len(extra)
                pads[info.filename] = extra
                pos = data_pos + info.file_size
            # pass 2: write
            for info in zin.infolist():
                data = zin.read(info.filename)
                new = zipfile.ZipInfo(info.filename)
                new.compress_type = zipfile.ZIP_STORED
                new.create_system = 3
                new.extra = pads[info.filename]
                zout.writestr(new, data)
    os.replace(aligned, path)


def main():
    os.makedirs(DOWNLOADS, exist_ok=True)

    print("building AndroidManifest.xml (AXML)…")
    axml = build_axml()
    print("building classes.dex…")
    dex = DexBuilder()
    # prime all strings so indices are final
    for t in ["Lcom/vehdiag/app/MainActivity;", "Landroid/app/Activity;",
              "Landroid/os/Bundle;", "Landroid/webkit/WebView;",
              "Landroid/webkit/WebSettings;", "Ljava/lang/String;",
              "Landroid/content/Context;", "V", "Z",
              "()Landroid/webkit/WebSettings;", "()V",
              "(Landroid/os/Bundle;)V", "(Landroid/content/Context;)V",
              "(Ljava/lang/String;)V", "(Landroid/webkit/WebView;)V", "(Z)V",
              "<init>", "onCreate", "getSettings", "setJavaScriptEnabled",
              "loadUrl", "setContentView", "MainActivity.java", LANDING_URL]:
        dex.s(t)
    dex_bytes = dex.build()

    entries = {
        "AndroidManifest.xml": axml,
        "classes.dex": dex_bytes,
    }
    entries.update(sign_v1(entries))

    apk_path = os.path.join(DOWNLOADS, "VEHDiag.apk")
    assemble_apk(apk_path, entries)
    print(f"  {apk_path} ({os.path.getsize(apk_path)} bytes)")

    # release bundle: apk + checksums + install instructions
    readme = (
        "VEHDiag 0.1.0 (development build)\n"
        "=================================\n\n"
        "This APK is a minimal OTA-style client: MainActivity hosts a WebView\n"
        "that loads the VEHDiag release page. The Bluetooth diagnostic client\n"
        "is the documented roadmap architecture (see docs/).\n\n"
        "Signed with the v1 (JAR) signature scheme (SHA-256 digests).\n"
        "targetSdkVersion 29, minSdkVersion 24.\n\n"
        "Verify before installing:\n"
        "  sha256sum -c SHA256SUMS.txt\n"
        "  apksigner verify --print-certs VEHDiag.apk   (requires Android SDK)\n"
        "Install (requires USB debugging):\n"
        "  adb install VEHDiag.apk\n"
    ).encode("utf-8")

    sha_apk = hashlib.sha256(open(apk_path, "rb").read()).hexdigest()
    sums_path = os.path.join(DOWNLOADS, "SHA256SUMS.txt")
    with open(sums_path, "w") as f:
        f.write(f"{sha_apk}  VEHDiag.apk\n")

    zip_path = os.path.join(DOWNLOADS, "VEHDiag.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(apk_path, "VEHDiag.apk")
        zf.write(sums_path, "SHA256SUMS.txt")
        zf.writestr("README.txt", readme)
    sha_zip = hashlib.sha256(open(zip_path, "rb").read()).hexdigest()
    with open(sums_path, "a") as f:
        f.write(f"{sha_zip}  VEHDiag.zip\n")

    print(f"  {zip_path} ({os.path.getsize(zip_path)} bytes)")
    print(f"  {sums_path}")
    print("\nSHA-256 (VEHDiag.apk):", sha_apk)
    return 0


if __name__ == "__main__":
    sys.exit(main())
