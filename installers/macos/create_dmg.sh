#!/usr/bin/env bash
# Build a macOS disk image from the PyInstaller application bundle.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="0.1.0"
NAME="VehicleDiagnosticsPlatform"
APP="${ROOT}/dist/${NAME}.app"
STAGE="${ROOT}/build/dmg"
OUTPUT="${ROOT}/dist/installer/${NAME}-${VERSION}.dmg"

if [ ! -d "${APP}" ]; then
    echo "run 'python scripts/build_macos.py' first" >&2
    exit 1
fi

rm -rf "${STAGE}" "${OUTPUT}"
mkdir -p "${STAGE}" "${ROOT}/dist/installer"
cp -R "${APP}" "${STAGE}/"
cp "${ROOT}/README.md" "${ROOT}/LICENSE" "${STAGE}/"
ln -s /Applications "${STAGE}/Applications"

# Optional code signing when a certificate is configured.
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
    codesign --deep --force --options runtime \
             --sign "${CODESIGN_IDENTITY}" "${STAGE}/${NAME}.app"
    echo "signed with ${CODESIGN_IDENTITY}"
fi

hdiutil create -volname "${NAME} ${VERSION}" \
               -srcfolder "${STAGE}" \
               -ov -format UDZO \
               "${OUTPUT}"

echo "created ${OUTPUT}"
echo "note: the bundle requests USB and network permissions on first launch"
