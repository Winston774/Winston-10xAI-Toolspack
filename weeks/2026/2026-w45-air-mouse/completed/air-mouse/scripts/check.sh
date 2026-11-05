#!/bin/bash
# Local and CI checks; this never launches the app or changes macOS permissions.
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
APP="$ROOT/AirMouse/build/Air Mouse.app"
PLIST="$APP/Contents/Info.plist"

fail() { printf 'Check failed: %s\n' "$*" >&2; exit 1; }

for file in README.md LICENSE CHANGELOG.md CONTRIBUTING.md SECURITY.md \
  AirMouse/main.swift AirMouse/Info.plist AirMouse/build.sh \
  scripts/check.sh scripts/package.sh .github/workflows/ci.yml .github/workflows/release.yml; do
  [[ -s "$ROOT/$file" ]] || fail "Missing or empty required file: $file"
done
for script in "$ROOT/AirMouse/build.sh" "$ROOT/scripts/check.sh" "$ROOT/scripts/package.sh"; do
  /bin/bash -n "$script"
  /bin/zsh -n "$script"
done
plutil -lint "$ROOT/AirMouse/Info.plist"
/bin/bash "$ROOT/AirMouse/build.sh"
plutil -lint "$PLIST"
codesign --verify --strict "$APP"

plist_value() { /usr/libexec/PlistBuddy -c "Print :$1" "$PLIST"; }
[[ "$(plist_value CFBundleName)" == 'Air Mouse' ]] || fail 'Unexpected app name'
[[ "$(plist_value CFBundleIdentifier)" == 'local.winston.airpods-air-mouse' ]] || fail 'Bundle identifier changed'
[[ "$(plist_value CFBundleExecutable)" == 'AirPodsAirMouse' ]] || fail 'Executable name changed'
[[ "$(plist_value LSMinimumSystemVersion)" == '14.0' ]] || fail 'Expected macOS 14.0 minimum'
VERSION="$(plist_value CFBundleShortVersionString)"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'Expected a three-part release version'
BINARY="$APP/Contents/MacOS/$(plist_value CFBundleExecutable)"
[[ -x "$BINARY" ]] || fail 'App binary is not executable'
[[ "$(xcrun lipo -archs "$BINARY")" == 'arm64' ]] || fail 'Expected arm64-only binary'
BUILD_INFO="$(xcrun vtool -show-build "$BINARY")"
[[ "$(printf '%s\n' "$BUILD_INFO" | awk '$1 == "minos" { print $2 }')" == '14.0' ]] || fail 'Unexpected binary deployment target'
[[ "$(printf '%s\n' "$BUILD_INFO" | awk '$1 == "platform" { print $2 }')" == 'MACOS' ]] || fail 'Expected macOS binary'
if [[ "${AIRMOUSE_SIGN_IDENTITY:--}" == '-' ]]; then
  SIGNATURE="$(codesign --display --verbose=4 "$APP" 2>&1)"
  case "$SIGNATURE" in
    *'Signature=adhoc'*) ;;
    *) fail 'Expected ad-hoc signature' ;;
  esac
fi
printf 'Checks passed: Air Mouse %s, arm64, macOS 14.0+, verified signature.\n' "$VERSION"
