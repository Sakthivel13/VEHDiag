#!/usr/bin/env bash
# Build a .deb package from the PyInstaller output.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="0.1.0"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
PACKAGE="vehicle-diagnostics-platform"
STAGE="${ROOT}/build/deb/${PACKAGE}_${VERSION}_${ARCH}"

if [ ! -d "${ROOT}/dist/vehicle-diagnostics-platform" ]; then
    echo "run 'python scripts/build_linux.py' first" >&2
    exit 1
fi

rm -rf "${STAGE}"
mkdir -p "${STAGE}/DEBIAN" \
         "${STAGE}/opt/${PACKAGE}" \
         "${STAGE}/usr/bin" \
         "${STAGE}/usr/share/applications" \
         "${STAGE}/usr/share/doc/${PACKAGE}" \
         "${STAGE}/usr/share/man/man1"

cp -r "${ROOT}/dist/vehicle-diagnostics-platform/." "${STAGE}/opt/${PACKAGE}/"
cp -r "${ROOT}/config" "${ROOT}/sample_test_scripts" "${STAGE}/opt/${PACKAGE}/"
cp "${ROOT}/LICENSE" "${ROOT}/README.md" "${STAGE}/usr/share/doc/${PACKAGE}/"

cat > "${STAGE}/DEBIAN/control" <<CONTROL
Package: ${PACKAGE}
Version: ${VERSION}
Section: electronics
Priority: optional
Architecture: ${ARCH}
Depends: libxkbcommon0, libgl1, libegl1, libfontconfig1, libdbus-1-3
Recommends: can-utils
Maintainer: Vehicle Diagnostics Platform Team <team@example.com>
Description: Professional vehicle diagnostics platform
 Cross-platform UDS (ISO 14229) diagnostics tool supporting CAN, CAN FD,
 K-Line, LIN, FlexRay, DoIP and J1939, with a scripted developer mode,
 flash programming and a built-in ECU simulator.
CONTROL

cat > "${STAGE}/usr/bin/${PACKAGE}" <<LAUNCHER
#!/bin/sh
exec /opt/${PACKAGE}/vehicle-diagnostics-platform "\$@"
LAUNCHER
chmod 755 "${STAGE}/usr/bin/${PACKAGE}"

cat > "${STAGE}/usr/share/applications/${PACKAGE}.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Vehicle Diagnostics Platform
Comment=UDS diagnostics for CAN, DoIP, K-Line, LIN, FlexRay and J1939
Exec=${PACKAGE}
Icon=${PACKAGE}
Terminal=false
Categories=Development;Engineering;
DESKTOP

gzip -9 -c > "${STAGE}/usr/share/man/man1/${PACKAGE}.1.gz" <<MAN
.TH VEHICLE-DIAGNOSTICS-PLATFORM 1 "2026" "${VERSION}" "User Commands"
.SH NAME
vehicle-diagnostics-platform \- professional vehicle diagnostics
.SH SYNOPSIS
.B vehicle-diagnostics-platform
[\fB--headless\fR] [\fB--vci\fR \fITYPE\fR] [\fB--protocol\fR \fINAME\fR]
.SH DESCRIPTION
Cross-platform UDS (ISO 14229) diagnostics tool with support for CAN, CAN FD,
K-Line, LIN, FlexRay, DoIP and J1939, a scripted developer mode and flash
programming.
.SH OPTIONS
.TP
.B --headless
Run the self-test without a user interface.
.TP
.B --vci TYPE
Select the interface: PCAN, VECTOR, KVASER_LEAF_V3, SOCKETCAN, VIRTUAL.
.TP
.B --protocol NAME
Select the protocol: CAN, CAN_FD, KLINE, LIN, DOIP, J1939, FLEXRAY.
MAN

dpkg-deb --build --root-owner-group "${STAGE}"
mkdir -p "${ROOT}/dist/installer"
mv "${STAGE}.deb" "${ROOT}/dist/installer/"
echo "created dist/installer/$(basename "${STAGE}").deb"
