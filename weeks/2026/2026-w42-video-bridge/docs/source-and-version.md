# 來源、版本與封裝紀錄

來源為使用者指定的 `X_threads_video_downloader/extension`，本次盤點日期為 2026-10-15，manifest 版本 **0.3.0**。完整讀取 24 個檔案，包含九個 JavaScript、manifest、HTML、CSS、Extension Kit 說明、四個 SVG 與四個 PNG 圖示；PNG 另作實際視覺檢視。

## 分發內容

- `completed/video-bridge/extension`：可載入的擴充功能。23 個來源檔位元組保持一致；`noise-winston/README.md` 僅將開發者本機同步路徑改為相對範例，保留其設計規範。
- `completed/video-bridge/tests`：來源專案的六份 Node.js 測試，保持原始內容與相對 imports。
- `completed/video-bridge/scripts/check.mjs`：來源資源／語法檢查器，保持原始內容。
- 補上成品及 extension 安裝 README、無相依套件的開發 package.json，以及週次教材與驗證文件。
- [source-manifest.json](source-manifest.json) 記錄來源 extension 的 24 檔大小與 SHA-256；文件變更另列上述例外。

`.gitattributes` 僅針對本週 completed 設定位元組保留，讓來源與測試的換行在 Git／CI 交付時一致。原始來源目錄未修改。

未收錄來源專案的 backups、dist、research、測試影片、瀏覽器設定與原始 QA 截圖。來源端 2026-10-15 的驗證記錄描述了部分公開頁面解析與介面模擬證據；本週教材將它與本次自動測試分開記錄。

## 授權

來源目錄及專案未附 LICENSE／NOTICE；metadata 記為未指定，不額外授予來源程式的授權，也不套用倉庫根目錄 MIT。週 ZIP 不加入根目錄 LICENSE。Extension Kit 的來源註記與品牌資訊保留，外部影片及社群平台內容權利仍由使用者確認。
