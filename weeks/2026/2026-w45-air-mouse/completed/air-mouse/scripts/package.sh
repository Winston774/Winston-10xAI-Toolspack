#!/bin/bash
# Create a distributable ZIP with an ad-hoc signature, regardless of local signing settings.
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DIST="$ROOT/dist"
APP="$ROOT/AirMouse/build/Air Mouse.app"
STAGE=""
cleanup() { [[ -z "$STAGE" ]] || rm -rf "$STAGE"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

AIRMOUSE_SIGN_IDENTITY=- /bin/bash "$ROOT/scripts/check.sh"
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")"
ARCHIVE_NAME="Air-Mouse-v${VERSION}-macos-arm64.zip"
mkdir -p "$DIST"
STAGE="$(mktemp -d "$DIST/.package.XXXXXX")"
PAYLOAD="$STAGE/payload"
mkdir -p "$PAYLOAD"

# Only these explicit inputs enter the archive. Local logs and build caches stay out.
ditto --norsrc --noextattr --noqtn --noacl "$APP" "$PAYLOAD/Air Mouse.app"
cp "$ROOT/LICENSE" "$PAYLOAD/LICENSE"
cat > "$PAYLOAD/README.txt" <<EOF
Air Mouse v${VERSION}

原始碼 / Source: https://github.com/Winston774/air-mouse
下載 / Downloads: https://github.com/Winston774/air-mouse/releases/latest

需求 / Requirements
Apple Silicon Mac (arm64), macOS 14 或更新版本，以及支援動態追蹤的 AirPods。
此版本為實驗性工具；不同 AirPods 與韌體的感測行為可能不同。

安裝與開啟
1. 將 Air Mouse.app 拖到「應用程式」。
2. 開啟 App。Air Mouse 會顯示在選單列。
3. 此套件使用 ad-hoc 簽章，尚未經 Apple Developer ID 簽署或公證。
   若 macOS 阻擋開啟，確認來源與下載檔案後，可依 Apple 指引前往
   「系統設定 → 隱私權與安全性 → 強制打開」，再確認開啟。
   若系統明確指出惡意內容或檔案損毀，請停止開啟並重新確認下載來源。
   Apple 指引：https://support.apple.com/en-us/102445
4. 依 App 提示允許動作感測及藍牙相關權限，並在
   「系統設定 → 隱私權與安全性 → 輔助使用」允許 Air Mouse 控制游標。
   更換或重建 App 後，可能需要重新授權。
5. 將 AirPods 連至 Mac，關閉「自動耳朵偵測」，雙耳放回充電盒內，
   並保持盒蓋開啟，再依選單列中的引導進行校正。
6. 使用 Control + Option + M（⌃⌥M）暫停或恢復控制。
   開始前請保留實體滑鼠或觸控板。
完整使用手冊：https://github.com/Winston774/air-mouse/blob/main/docs/usage.zh-TW.md

English quick start
Move Air Mouse.app to Applications and open it. The app appears in the menu bar.
This arm64 build is ad-hoc signed and is not Developer ID signed or notarized.
Follow Apple's linked guidance if Gatekeeper blocks a trusted download.
Allow the requested motion/Bluetooth permissions and enable Air Mouse in
System Settings > Privacy & Security > Accessibility. Calibrate before use.
Connect AirPods to the Mac, turn off Automatic Ear Detection, then put both
earbuds in the case and keep the lid open. Press Control + Option + M to
pause or resume control. Keep a physical mouse or trackpad available.
Full guide: https://github.com/Winston774/air-mouse/blob/main/README.en.md

授權 / License
MIT License，完整條款請見本套件內的 LICENSE。
EOF

ditto -c -k --norsrc --noextattr --noqtn --noacl "$PAYLOAD" "$STAGE/$ARCHIVE_NAME"
# Check the actual archive, including executable mode and code signature.
ditto -x -k "$STAGE/$ARCHIVE_NAME" "$STAGE/unpacked"
[[ -x "$STAGE/unpacked/Air Mouse.app/Contents/MacOS/AirPodsAirMouse" ]]
codesign --verify --strict "$STAGE/unpacked/Air Mouse.app"
(
  cd "$STAGE"
  shasum -a 256 "$ARCHIVE_NAME" > SHA256SUMS.txt
  shasum -a 256 -c SHA256SUMS.txt
)
mv "$STAGE/$ARCHIVE_NAME" "$DIST/$ARCHIVE_NAME"
mv "$STAGE/SHA256SUMS.txt" "$DIST/SHA256SUMS.txt"
printf 'Packaged: %s\nChecksum: %s\n' "$DIST/$ARCHIVE_NAME" "$DIST/SHA256SUMS.txt"
