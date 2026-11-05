# Air Mouse

**把打開蓋子的 AirPods 充電盒，變成 Mac 的空中滑鼠。**

兩耳留在盒內，左右轉動盒子移動游標，停住後輕敲一下左鍵、快速兩下雙擊。Air Mouse 是原生 Swift 選單列 App，所有動作處理都在 Mac 本機完成。

[English](README.en.md) · [下載最新版](https://github.com/Winston774/air-mouse/releases/latest) · [完整使用指南](docs/usage.zh-TW.md)

> **v0.1.0 是開蓋實驗版。** 已有 AirPods Pro 第一代的開蓋實測；其他型號、長時間使用與每次斷線恢復尚未完成廣泛驗證。使用時請保持盒蓋打開，並關閉 AirPods 的「自動耳朵偵測」。

## 功能

| 操作 | 效果 |
| --- | --- |
| 左右轉動盒子 | 游標左右移動 |
| 盒子前端上下抬 | 游標上下移動 |
| 停穩後輕敲盒子一下 | 左鍵點擊，修正點按造成的游標晃動 |
| 快速輕敲兩下 | 雙擊 |
| `Control + Option + M`（`⌃⌥M`） | 暫停／恢復游標控制 |

- 左右耳分別校正方向，校正結果與個人偏好保存在本機。
- 三段游標速度、上下反轉、點按靈敏度與個人點按校正測試。
- 停止收到動作資料時停止游標移動，並提供可關閉的藍牙自動重連。
- 選單顯示資料頻率與工作階段統計，本機 JSONL 記錄方便排查問題。

目前未提供右鍵、捲動或獨立拖放手勢。App 介面以繁體中文呈現。

## 使用條件

- **Apple Silicon Mac（arm64）、macOS 14 以上。** 最低版本是建置設定；目前實機環境為 macOS 27.0.1，較早版本尚待實測。
- 可向 `CMHeadphoneMotionManager` 提供動作資料的 AirPods。已測組合為 **AirPods Pro 第一代，型號 A2084、耳機韌體 6F21、充電殼韌體 1.4.1**。
- AirPods 已與 Mac 配對、連線，兩耳留在充電盒內、盒蓋打開，「自動耳朵偵測」關閉。
- 允許「動作與健身」、「藍牙」及「輔助使用」權限。

其他型號的相容性、合蓋研究結論與已知限制，見[相容性說明](docs/compatibility.md)。

## 下載與開始使用

1. 從 [GitHub Releases](https://github.com/Winston774/air-mouse/releases/latest) 下載 `Air-Mouse-v0.1.0-macos-arm64.zip`，解壓縮後把 `Air Mouse.app` 移到「應用程式」。
2. 開啟 App。公開版本使用 **ad-hoc 簽章，尚未經 Apple 公證（notarization）**。若 macOS 因開發者無法驗證而阻擋，請先確認下載來源，再到「系統設定 → 隱私權與安全性 → 安全性」選擇「仍要打開」。可參考 [Apple 的開啟 App 說明](https://support.apple.com/en-gb/102445)。
3. 依系統提示授權；到「系統設定 → 隱私權與安全性 → 輔助使用」啟用 Air Mouse。
4. 連接 AirPods，關閉「自動耳朵偵測」，讓兩耳留在打開的充電盒內。
5. 收到資料後，依校正視窗指示：盒子前端朝螢幕，拿穩約 1.5 秒，再把前端向上抬約 30° 並停住。資料來源切換到未校正的另一耳時，會再提示校正。
6. 從選單執行「點按校正測試…」，找出適合自己的力道。隨時按 `⌃⌥M` 暫停游標控制。

App 只顯示在選單列，沒有 Dock 圖示。暫停期間仍會讀取動作與寫入本機記錄；選單「結束」才會停止整個 App。詳細操作與排錯見[使用指南](docs/usage.zh-TW.md)。

## 從原始碼建置

需要 macOS、Xcode Command Line Tools（或 Xcode），以及可用的 macOS SDK 與 Swift 編譯器。沒有第三方套件依賴。

```sh
git clone https://github.com/Winston774/air-mouse.git
cd air-mouse
zsh AirMouse/build.sh
open "AirMouse/build/Air Mouse.app"
```

腳本預設為 arm64、macOS 14+，使用 ad-hoc 簽章。若本機有合適的簽章憑證，可指定：

```sh
AIRMOUSE_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" zsh AirMouse/build.sh
```

指定憑證只負責簽章；公證須另行處理。重新建置或更換簽章後，macOS 可能要求重新授權輔助使用。

```sh
# 檔案、建置與簽章檢查
zsh scripts/check.sh

# 產生發佈壓縮檔與 SHA-256 清單
zsh scripts/package.sh
```

封裝輸出：

- `dist/Air-Mouse-v0.1.0-macos-arm64.zip`
- `dist/SHA256SUMS.txt`

建置檢查與實機驗證範圍分別記在[驗證說明](docs/verification.md)。

## 隱私與記錄

Air Mouse 原碼沒有外部網路請求、帳號、遙測上傳或麥克風存取。預設在 `~/Library/Logs/AirPodsAirMouse` 寫入連線、點按與統計記錄；加上 `--raw` 才會增加逐筆感測資料。設定會保存優先重連的藍牙位址。記錄不會自動清除，分享前請先檢查內容。詳見[隱私說明](docs/privacy.md)。

## 文件與參與

- [使用指南與排錯](docs/usage.zh-TW.md)
- [相容性與研究邊界](docs/compatibility.md)
- [程式架構](docs/architecture.md)
- [隱私與資料保存](docs/privacy.md)
- [驗證說明](docs/verification.md) · [更新紀錄](CHANGELOG.md)
- [貢獻指南](CONTRIBUTING.md) · [安全問題回報](SECURITY.md)

## 作者與授權

由 **Winston** 製作，使用 [MIT License](LICENSE)。

[YouTube @NoiseWinston](https://www.youtube.com/@NoiseWinston) · [Facebook](https://www.facebook.com/huang.hao.543) · [Skool ai10x](https://www.skool.com/ai10x)

AirPods、Mac 與 macOS 為 Apple 的商標。本專案由社群獨立開發，與 Apple 無隸屬關係。
