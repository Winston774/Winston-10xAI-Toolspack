# v0.1.0 發布驗證

驗證日期：2026-11-05（Asia/Taipei）。本頁區分發布產物檢查與實體耳機使用測試。

## 本機建置環境

| 項目 | 內容 |
| --- | --- |
| 主機 | Apple Silicon / arm64 |
| 系統 | macOS 27.0.1（26A434） |
| 編譯器 | Apple Swift 6.3.3，Swift 5 語言模式 |
| macOS SDK | 26.5，由 `xcrun --sdk macosx` 選取 |
| 輸出 | Air Mouse 0.1.0，arm64，最低 macOS 14.0 |
| 簽章 | ad-hoc；沒有 Developer ID、公證或 Team Identifier |

## 已完成的發布檢查

- 執行 `zsh scripts/package.sh`，內含完整 `scripts/check.sh`：必要檔案、bash／zsh 語法、Swift 編譯、plist、bundle identifier、執行檔權限、架構、最低系統版本與簽章均通過。
- 以 `file`、`xcrun vtool -show-build` 與 `codesign` 獨立確認實際產物為 arm64、`minos 14.0`，且簽章完整。
- 封裝後重新解壓縮，確認 App 執行檔仍可執行，並再次通過嚴格簽章檢查。
- `shasum -a 256 -c SHA256SUMS.txt` 通過。校驗碼隨 Release 提供，對應實際上傳的 ZIP。
- 以暫存複本故意造成 Swift 編譯失敗，確認舊 App 保留且暫存建置目錄會清除。
- GitHub workflow 與 Issue 範本通過 YAML 解析；workflow 的 shell 區段通過語法檢查。
- 公開檔案以明確清單整理；未帶入私人原始記錄、實驗工具、簽章憑證或舊的研究 Git 歷史。對文字檔的常見密鑰、私人路徑與藍牙位址樣式檢查沒有發現符合項；這項檢查不等同完整安全稽核。

ZIP 的使用者內容為 `Air Mouse.app`、`README.txt` 與 `LICENSE`；原始碼由 GitHub 的版本標籤提供。

## 自動檢查

[Build and check](https://github.com/Winston774/air-mouse/actions/workflows/ci.yml) 在 push 與 Pull Request 時，使用 GitHub 的 `macos-15` runner 重新建置與檢查。各次雲端結果以 Actions 頁面為準。

發布 workflow 僅能手動啟動，會核對既有標籤、plist 版本與 checkout commit，並拒絕覆寫既有 Release。一般建置與 PR 工作使用唯讀權限；發布工作才具有寫入 Release 所需權限。官方 Actions 固定使用已核對的 commit SHA。

## 本次沒有重跑的項目

此次整理保留了第一版的核心動作、點按與重連程式，僅修正一行過時註解，並更新品牌名稱、版本、建置及發布文件。

本次沒有啟動 App 控制游標，也沒有進行新的實體 AirPods 端到端測試。方向、左鍵／雙擊、權限引導、睡眠恢復、斷線恢復、其他耳機型號、多螢幕與長時間穩定性，均不能由編譯或封裝通過推定。未在另一台 Mac 上完成下載、Gatekeeper、權限與首次操作的完整測試。

## 歷史硬體證據

公開前研究使用 AirPods Pro 第一代（A2084、6F21、充電殼 1.4.1）與 macOS 27.0.1。關閉自動耳朵偵測並保持開蓋時，兩次 20 秒窗口得到約 50 Hz 的動作資料。這項觀察來自診斷工具，尚不足以驗證最新 App 的完整操作與長期穩定性。

合蓋曾短暫取得約 91 秒串流，後續未建立穩定重現流程，因此本版以開蓋操作為範圍。歷史資料的詳細邊界見[相容性說明](compatibility.md)。
