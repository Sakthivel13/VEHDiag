#!/usr/bin/env bash
# Build an AppImage from the PyInstaller output.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="0.1.0"
APPDIR="${ROOT}/build/AppDir"
NAME="VehicleDiagnosticsPlatform"

if [ ! -d "${ROOT}/dist/vehicle-diagnostics-platform" ]; then
    echo "run 'python scripts/build_linux.py' first" >&2
    exit 1
fi

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" \
         "${APPDIR}/usr/share/icons/hicolor/scalable/apps"

cp -r "${ROOT}/dist/vehicle-diagnostics-platform/." "${APPDIR}/usr/bin/"
cp -r "${ROOT}/config" "${ROOT}/sample_test_scripts" "${APPDIR}/usr/bin/"
cp "${ROOT}/ui/resources/icons/app_icon.svg" \
   "${APPDIR}/usr/share/icons/hicolor/scalable/apps/${NAME}.svg"
cp "${ROOT}/ui/resources/icons/app_icon.svg" "${APPDIR}/${NAME}.svg"

cat > "${APPDIR}/${NAME}.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Vehicle Diagnostics Platform
Comment=UDS diagnostics for CAN, DoIP, K-Line, LIN, FlexRay and J1939
Exec=vehicle-diagnostics-platform
Icon=${NAME}
Terminal=false
Categories=Development;Engineering;
DESKTOP
cp "${APPDIR}/${NAME}.desktop" "${APPDIR}/usr/share/applications/"

cat > "${APPDIR}/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH:-}"
exec "${HERE}/usr/bin/vehicle-diagnostics-platform" "$@"
APPRUN
chmod +x "${APPDIR}/AppRun"

TOOL="$(command -v appimagetool || true)"
if [ -z "${TOOL}" ]; then
    echo "appimagetool was not found; the AppDir is ready at ${APPDIR}"
    echo "download it from https://github.com/AppImage/AppImageKit/releases"
    exit 0
fi

mkdir -p "${ROOT}/dist/installer"
"${TOOL}" "${APPDIR}" "${ROOT}/dist/installer/${NAME}-${VERSION}-x86_64.AppImage"
echo "created dist/installer/${NAME}-${VERSION}-x86_64.AppImage"
