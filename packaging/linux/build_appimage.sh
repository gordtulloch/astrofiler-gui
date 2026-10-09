#!/usr/bin/env bash
# Wrap dist/AstroFiler into dist/AstroFiler-<version>-linux-<arch>.AppImage (x86_64 or aarch64 / Raspberry Pi 5).
# Usage: packaging/linux/build_appimage.sh <version>   (run from the repo root, after packaging/build.py)
set -euo pipefail
VERSION="${1:?version required}"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64) ;;
    aarch64|arm64) ARCH=aarch64 ;;
    *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

APPDIR="build/AstroFiler.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications"
cp -R dist/AstroFiler "$APPDIR/usr/lib/astrofiler"
cp astrofiler.png "$APPDIR/astrofiler.png"
cp "$APPDIR/astrofiler.png" "$APPDIR/.DirIcon"

cat > "$APPDIR/astrofiler.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=AstroFiler
Comment=Astronomical image management
Exec=AstroFiler
Icon=astrofiler
Categories=Science;Astronomy;Graphics;
Terminal=false
DESKTOP
cp "$APPDIR/astrofiler.desktop" "$APPDIR/usr/share/applications/"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/astrofiler/AstroFiler" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

TOOL="build/appimagetool-$ARCH.AppImage"
if [ ! -x "$TOOL" ]; then
    wget -q -O "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
    chmod +x "$TOOL"
fi

OUT="dist/AstroFiler-${VERSION}-linux-${ARCH}.AppImage"
APPIMAGE_EXTRACT_AND_RUN=1 ARCH="$ARCH" "$TOOL" "$APPDIR" "$OUT"
echo "Built $OUT"
