# Air Mouse

**Use an open AirPods charging case as an air mouse for your Mac.**

Keep both earbuds in the case with the lid open. Turn the case to move the pointer, pause your movement and tap once for a left click, or tap twice for a double click. Air Mouse is a native Swift menu bar app with local motion processing.

[繁體中文](README.md) · [Download](https://github.com/Winston774/air-mouse/releases/latest)

> **v0.1.0 is an experimental open-lid release.** First-generation AirPods Pro have been tested with the lid open. Other models, long sessions and reliable recovery across repeated disconnects need further validation. Keep the lid open and disable Automatic Ear Detection.

## Features and requirements

- Relative pointer movement from case rotation, with three speed settings and optional vertical inversion.
- Left click and double click from taps, with a guided sensitivity test.
- Separate, persistent direction calibration for each earbud.
- A global `Control + Option + M` shortcut to pause or resume pointer control.
- Stops pointer movement when fresh motion data is unavailable; optional Bluetooth reconnection.
- Local connection statistics and JSONL diagnostic logs.

Right click, scrolling and a dedicated drag gesture are not provided. The app interface is in Traditional Chinese.

The release targets **Apple Silicon (arm64), macOS 14 or later**. macOS 14 is the deployment target; hardware testing was performed on **macOS 27.0.1**. Earlier supported OS versions and Intel Macs have not been validated.

The tested device was **AirPods Pro (1st generation), model A2084, earbud firmware 6F21, case firmware 1.4.1**. Compatibility with every AirPods model is not established. The earbuds must supply motion data through `CMHeadphoneMotionManager` while connected to the Mac, inside the open case, with Automatic Ear Detection disabled.

## Install and set up

1. Download `Air-Mouse-v0.1.0-macos-arm64.zip` from [GitHub Releases](https://github.com/Winston774/air-mouse/releases/latest), extract it and move `Air Mouse.app` into Applications.
2. Launch the app. The public build is **ad-hoc signed and not notarized**. If macOS blocks it because the developer cannot be verified, confirm the download source, then use **System Settings → Privacy & Security → Open Anyway**. See [Apple's instructions](https://support.apple.com/en-gb/102445).
3. Allow **Motion & Fitness** and **Bluetooth** when prompted. Enable Air Mouse under **System Settings → Privacy & Security → Accessibility** so it can move the pointer and click.
4. Connect the AirPods to your Mac, disable **Automatic Ear Detection**, and keep both earbuds in the case with the lid open.
5. When the calibration window appears, point the front of the case toward the screen. Hold it still for about 1.5 seconds, then tilt the front upward about 30° and stop. The other earbud needs its own calibration when it becomes the motion source.
6. Open **點按校正測試…** in the menu bar menu to calibrate taps. Follow the green dot: hold still for 8 seconds, tap once on each of 10 prompts, double-tap on each of 5 prompts, then move normally without tapping for 15 seconds. Keep motion data flowing throughout the test; repeat it after any interruption, even if a suggestion appears. Press the apply button to save the suggested threshold. Results describe detector output for that recording and do not establish successful double clicks in macOS apps.

The app runs in the menu bar without a Dock icon. Reopening the app shows direction calibration. Use `Control + Option + M` to pause control, and **結束** to quit.

Pausing stops pointer control and prevents new automatic Bluetooth reconnection attempts. Motion collection and local logging continue while paused; quit the app to stop them.

## Everyday controls

| Menu / action | Meaning |
| --- | --- |
| Turn the case left/right | Move the pointer left/right |
| Tilt the front up/down | Move the pointer up/down |
| Tap after holding still | Left click |
| Two quick taps | Double click |
| 控制游標 | Enable pointer control |
| 校正方向… | Direction calibration |
| 游標速度 | Pointer speed: slow / medium / fast |
| 點按靈敏度 | Tap sensitivity; a lower `g` threshold detects lighter taps |
| 上下反轉 | Invert vertical movement |
| 斷線時自動重新連線 | Automatic Bluetooth reconnection |
| 打開紀錄資料夾 | Open the log folder |

If you want to use the AirPods with an iPhone, pause control or disable automatic reconnection first. The app may otherwise try to connect them back to the Mac. Reconnection success depends on the device and Bluetooth state. Automatic reconnection searches paired devices whose names contain `AirPods`; renaming the device may prevent discovery. With multiple candidates, it prefers the saved address, then the most recently accessed device.

Direction calibration is stored per left/right source, without a separate profile for each physical pair of earbuds. Recalibrate both sources when switching to another pair.

## Build and package

Install Xcode Command Line Tools or Xcode, including the macOS SDK and Swift compiler. There are no third-party package dependencies.

```sh
git clone https://github.com/Winston774/air-mouse.git
cd air-mouse
zsh AirMouse/build.sh
open "AirMouse/build/Air Mouse.app"
```

The build defaults to arm64, macOS 14+ and ad-hoc signing. To use a local signing identity:

```sh
AIRMOUSE_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" zsh AirMouse/build.sh
```

Signing does not perform notarization. Rebuilding or changing the signature may require renewed Accessibility permission.

```sh
zsh scripts/check.sh
zsh scripts/package.sh
```

Packaging produces `dist/Air-Mouse-v0.1.0-macos-arm64.zip` and `dist/SHA256SUMS.txt`. Download both release assets to the same folder and run `shasum -a 256 -c SHA256SUMS.txt` there to verify the archive checksum.

For a custom log folder or detailed motion logging, quit the app first, then run:

```sh
open "AirMouse/build/Air Mouse.app" --args "$PWD/logs" --raw
```

Use `--tap-test` to open the guided tap test, including when another instance is already running:

```sh
open -n "AirMouse/build/Air Mouse.app" --args --tap-test
```

## Privacy and limitations

The source contains no external network requests, telemetry uploads or microphone access. It writes local JSONL logs by default to `~/Library/Logs/AirPodsAirMouse`; `--raw` adds per-sample motion details. Preferences include calibration, sensitivity and a preferred Bluetooth address for reconnection. Logs are not automatically rotated or deleted. Review them before sharing.

Closed-lid operation is outside this release's supported workflow. Earlier research observed one approximately 91-second closed-lid stream, but subsequent attempts did not establish repeatable startup or sustained operation. This release makes no universal claim about whether closed-lid operation is possible.

Calls or other use of the AirPods audio connection can interrupt motion data. Long-term reliability, other AirPods models, Intel support, broad multi-display behavior and third-party app compatibility remain incompletely tested. Build checks do not establish hardware reliability; see [verification](docs/verification.md).

If no motion arrives, check the lid, Automatic Ear Detection, pairing and permissions. If data arrives but the pointer does not move, check Accessibility permission, direction calibration and the pause shortcut. Quit other apps that consume headphone motion data. For false clicks, increase the threshold or disable tap clicking while moving.

## Documentation and contributing

- [Detailed usage and troubleshooting](docs/usage.zh-TW.md) (Traditional Chinese)
- [Compatibility](docs/compatibility.md) · [Architecture](docs/architecture.md) · [Privacy](docs/privacy.md)
- [Verification](docs/verification.md) · [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md) · [Security reporting](SECURITY.md)

Created by **Winston**. Released under the [MIT License](LICENSE).

[YouTube @NoiseWinston](https://www.youtube.com/@NoiseWinston) · [Facebook](https://www.facebook.com/huang.hao.543) · [Skool ai10x](https://www.skool.com/ai10x)

AirPods, Mac and macOS are trademarks of Apple. This is an independent community project with no affiliation with Apple.
