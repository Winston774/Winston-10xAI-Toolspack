#!/bin/bash
# Build an Apple Silicon app from any working directory.
set -euo pipefail

SOURCE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BUILD_DIR="$SOURCE_DIR/build"
APP="$BUILD_DIR/Air Mouse.app"
SIGN_IDENTITY="${AIRMOUSE_SIGN_IDENTITY:--}"
STAGE=""
CACHE=""

cleanup() {
  if [[ -n "$STAGE" && -d "$STAGE/previous.app" && ! -e "$APP" ]]; then
    if ! mv "$STAGE/previous.app" "$APP"; then
      printf 'Previous app preserved at: %s\n' "$STAGE/previous.app" >&2
      [[ -z "$CACHE" ]] || rm -rf "$CACHE"
      return
    fi
  fi
  [[ -z "$STAGE" ]] || rm -rf "$STAGE"
  [[ -z "$CACHE" ]] || rm -rf "$CACHE"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "$BUILD_DIR"
STAGE="$(mktemp -d "$BUILD_DIR/.stage.XXXXXX")"
CACHE="$(mktemp -d "${TMPDIR:-/tmp}/air-mouse-module-cache.XXXXXX")"
STAGED_APP="$STAGE/Air Mouse.app"
EXECUTABLE="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$SOURCE_DIR/Info.plist")"
SDK_PATH="$(xcrun --sdk macosx --show-sdk-path)"

mkdir -p "$STAGED_APP/Contents/MacOS"
cp "$SOURCE_DIR/Info.plist" "$STAGED_APP/Contents/Info.plist"
plutil -lint "$STAGED_APP/Contents/Info.plist"
xcrun --sdk macosx swiftc -swift-version 5 -O \
  -sdk "$SDK_PATH" -module-cache-path "$CACHE" -target arm64-apple-macosx14.0 \
  -framework AppKit -framework CoreMotion -framework IOBluetooth \
  -framework Carbon -framework ApplicationServices \
  "$SOURCE_DIR/main.swift" -o "$STAGED_APP/Contents/MacOS/$EXECUTABLE"

# Signing is explicit. Never search the user's keychain for a certificate.
codesign --force --timestamp=none --sign "$SIGN_IDENTITY" "$STAGED_APP"
codesign --verify --strict "$STAGED_APP"

# Retain the previous app until the new build and signature have passed.
if [[ -e "$APP" ]]; then
  mv "$APP" "$STAGE/previous.app"
fi
mv "$STAGED_APP" "$APP"
printf 'Built: %s\n' "$APP"
