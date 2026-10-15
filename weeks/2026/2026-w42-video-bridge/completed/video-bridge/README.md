# 影片接力 Video Bridge v0.3.0

這是 W42 的獨立成品目錄，包含 Chrome 擴充功能、來源測試與檢查工具。一般使用只需 Chrome 120+。

## 安裝與操作

開啟 `chrome://extensions` → 開發人員模式 → 載入未封裝項目 → 選本目錄的 `extension`。確認 v0.3.0，重新整理 X、Threads、Facebook 分頁。

在 X／Threads 影片上右鍵，選「下載並複製影片・影片接力」。到 Chrome 下載項目確認完成；開啟 Threads 新串文或 Facebook 一般發文框後，按 Ctrl＋V 或浮動插入按鈕，確認正確預覽與上傳處理狀態。插入附件可能立即上傳，發布由你操作。

剪貼簿是 `video-bridge:<id>` 標記，檔案存在外掛 IndexedDB；一次一支、最多 150 MiB。面板可重新準備貼上、另存影片、清除快取及設定亮暗色。其他平台使用下載 MP4 手動上傳。

## 開發與測試

使用 Node.js 20+，在本目錄執行；全部使用內建模組，不需要 npm install。

```powershell
npm.cmd test
npm.cmd run check
npm.cmd run validate
```

`test` 執行六份模擬測試；`check` 核對 manifest／HTML／模組資源與 JavaScript 語法；`validate` 依序執行兩者。CI 沿用倉庫既有 package.json 驗證流程，無需額外設定。

測試不會下載真實社群影片、登入帳號或發布貼文。DOM／Chrome API／fetch 模擬通過仍需另做 Chrome 安裝及平台實測。

完整說明：[週次入口](../../README.md)、[權限](../../docs/permissions-and-privacy.md)、[限制](../../docs/limitations.md)、[排解](../../docs/troubleshooting.md)、[驗證](../../docs/verification.md)。
