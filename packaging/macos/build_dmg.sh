#!/usr/bin/env bash
# Wrap dist/AstroFiler.app into dist/AstroFiler-<version>-macos-<arch>.dmg.
# Usage: packaging/macos/build_dmg.sh <version>   (run from the repo root, after packaging/build.py)
# Signing/notarization run only when APPLE_SIGN_IDENTITY (and APPLE_ID/APPLE_TEAM_ID/APPLE_APP_PASSWORD) are set.
set -euo pipefail
VERSION="${1:?version required}"
ARCH="$(uname -m)"; [ "$ARCH" = "arm64" ] || ARCH="x86_64"
APP="dist/AstroFiler.app"
DMG="dist/AstroFiler-${VERSION}-macos-${ARCH}.dmg"

if [ -n "${APPLE_SIGN_IDENTITY:-}" ]; then
    codesign --force --deep --options runtime --timestamp --sign "$APPLE_SIGN_IDENTITY" "$APP"
else
    echo "APPLE_SIGN_IDENTITY not set: ad-hoc signing only (users must right-click > Open)"
    codesign --force --deep --sign - "$APP"
fi

STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname "AstroFiler" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

if [ -n "${APPLE_SIGN_IDENTITY:-}" ] && [ -n "${APPLE_ID:-}" ]; then
    codesign --force --timestamp --sign "$APPLE_SIGN_IDENTITY" "$DMG"
    xcrun notarytool submit "$DMG" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" \
        --password "$APPLE_APP_PASSWORD" --wait
    xcrun stapler staple "$DMG"
fi
echo "Built $DMG"
