# 自動測試與實機驗收

## 已完成的驗證

- Extension 版本：`0.6.2`
- 自動測試：66／66 通過
- JavaScript 語法檢查：9／9 通過
- 完整開發來源與 production-loaded tree：各 44 個檔案，逐檔 SHA-256 差異為 0
- 敏感資料掃描：未發現真實 API Key、Token、私鑰、`.env` 或 credential 檔
- 2026-07-22 實機驗收：專案負責人確認框選、完整可視區、第一次快捷鍵啟動，以及 `gemini-3.1-flash-lite`／`gemini-3.5-flash-lite` 都能成功使用

倉庫中的 Extension 成品由白名單複製，共 30 個檔案：23 個 runtime／README 加 7 個測試；排除內部 `AGENTS.md`、設計 QA ledger、靜態 preview、環境截圖與未被 runtime 使用的設計母檔。週次 Release ZIP 另包含本週 README、講義、metadata 與五份延伸文件，並在打包前由 validator 拒絕禁止檔、連結與常見 secret 格式。

## 執行 Extension 測試

需要 Node.js 20 以上。進入 `completed/gemini-selection-translator/` 後執行：

```powershell
node --test tests/design-system-smoke.mjs
node --test tests/theme-runtime.mjs
node --test tests/capture-utils.test.mjs
node --test tests/gemini-client.test.mjs
node --test tests/shortcut-utils.test.mjs
node --test tests/integration-contract.test.mjs
node --test tests/background-routing.test.mjs
```

語法檢查：

```powershell
node --check background.js
node --check content.js
node --check options.js
node --check popup.js
node --check sidepanel.js
node --check theme.js
node --check lib/capture-utils.js
node --check lib/gemini-client.js
node --check lib/shortcut-utils.js
```

## Chrome 實機驗收

每次換檔後先到 `chrome://extensions` 重新載入，再重新整理測試網頁：

1. 不點工具列圖示，直接按 `Alt + Shift + X`，完成框選並進入預覽。
2. 關閉 Side Panel，再按 `Alt + Shift + V`，直接進入完整可視區預覽。
3. 測試首次資料提示：預設未勾選，勾選後下次不再顯示，設定頁可以恢復。
4. 測試只轉錄與轉錄＋繁中翻譯。
5. 在 selecting、capturing、preview、running、result、error 各狀態再次按快捷鍵，最後只能留下最新工作。
6. 快速交替按 X／V，確認不會出現 screenshot 頻率錯誤。
7. 切換分頁後重新擷取，確認工作綁定新的 active tab。
8. 測試反白翻譯、單字庫、搜尋、刪除、JSON／CSV 匯出與複習沒有回歸。
9. 查看 Extension service worker 與 Side Panel DevTools，確認沒有未處理錯誤。

## Toolspack 倉庫驗證

從倉庫根目錄執行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1
git diff --check
```

正式 Release 前另執行 `scripts/build-release.ps1`，檢查 ZIP 清單與 SHA-256；合併後必須確認 `Validate Toolspack` GitHub Actions 成功，再建立 `2026-w30-v1.0.0` tag 與 Release。
