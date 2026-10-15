# W42｜影片接力 Video Bridge：從 X／Threads 到社群發文框

在 X 或 Threads 的影片上按右鍵，下載 MP4 並準備再次貼上，再到 Threads 新串文或 Facebook 一般發文框插入影片。你可以在工具列面板查看檔案大小、時長、尺寸與來源，重新複製標記、另存影片或清除暫存。

本週分享 **Chrome Manifest V3 擴充功能 v0.3.0 Preview**，包含可直接載入的完整成品與自動測試。一般使用無需 Node.js、API Key 或建置；Node.js 僅供開發練習及測試。已登入平台的整包操作仍待人工驗收，詳細範圍見 [驗證紀錄](docs/verification.md)。

## 你會學到什麼

- 以使用者右鍵位置確認目標影片，處理 blob 播放器與多影片貼文。
- 將來源定位、媒體下載、本機快取與附件插入拆成可檢查的流程。
- 理解剪貼簿識別標記、Chrome Downloads 與平台附件預覽三種不同狀態。
- 操作含防重、過期標記與發文框變更檢查的社群影片工作流。

預估 **90 分鐘**：安裝與下載練習約 30 分鐘，快取／貼上與失敗重試約 30 分鐘，閱讀架構及檢查成果約 30 分鐘。需桌面 Chrome 120+、網路及你有權使用的測試影片；接收練習需自己的 Threads 或 Facebook 帳號。

## 下載與安裝

本週以主分支與 CI 打包附件交付。可在倉庫首頁選 Code → Download ZIP；或在成功的 [GitHub Actions](https://github.com/Winston774/Winston-10xAI-Toolspack/actions/workflows/validate.yml) 執行頁下載 `toolspack-weekly-release-candidates`，取出 `2026-w42-video-bridge.zip`。Actions 附件需登入，保留 7 天。本週尚無獨立 GitHub Release。

1. 解壓後找到 `completed/video-bridge/extension/`，確認第一層有 `manifest.json`。
2. 開啟 `chrome://extensions`，啟用「開發人員模式」。
3. 點「載入未封裝項目」，選擇上述 **extension 資料夾**。
4. 確認「影片接力 Video Bridge」版本為 `0.3.0`，釘選到工具列。
5. 重新整理 X、Threads、Facebook 分頁。更新舊版時先保留舊資料夾，確認載入的新路徑後重新載入外掛與分頁；使用新資料夾安裝時避免同時啟用兩份影片接力。

## 第一次操作

1. 開啟有權使用的 X／Threads 影片，播放一下，再直接在影片畫面按右鍵。
2. 選「下載並複製影片・影片接力」，等待取得影片與交給 Chrome 下載。
3. 在 Chrome 下載項目確認檔案真正完成，再開檔檢查畫面與聲音。
4. 開啟 **Threads 新串文**或 **Facebook 一般發文視窗**，只保留一個發文視窗。
5. 在文字區按 Ctrl＋V，或點右下角「插入已複製影片至 Threads／Facebook」。
6. 確認平台附件預覽是正確影片，查看上傳／處理狀態，再自行決定是否發布。

**插入附件可能立即觸發平台上傳。** 外掛保留發布操作給使用者。只想下載時，可完成第 3 步；練習結束時自行取消發文視窗或移除附件。

X 影片上的右鍵會優先顯示 Chrome 選單；Shift＋右鍵可使用 X 原本的選單。若只需準備貼上，選「複製影片・影片接力」，不另外發起下載。

## 使用前先知道

一次快取一支、上限 **150 MiB**。剪貼簿存放 `video-bridge:<id>`，影片保存在外掛 IndexedDB；接收頁需要同一外掛的接收程式。其他平台可使用已下載 MP4 手動選檔上傳。

Threads 的貼文頁備援會帶上同站登入狀態；影片 CDN 下載及 X 公開資料請求使用 `credentials: omit`。快取留在本機，插入後則由社群平台處理附件。完整權限與資料流見 [permissions-and-privacy](docs/permissions-and-privacy.md)。

X／Threads 頁面結構與公開資料格式可能變更；無法確認目標或沒有可用 MP4 時會停止。來源與接收限制見 [limitations](docs/limitations.md)。

## 本週內容

- [操作講義、成果證據與通過標準](lesson.md)
- [來源解析與附件插入架構](docs/architecture.md)
- [權限與隱私](docs/permissions-and-privacy.md)
- [限制](docs/limitations.md)、[疑難排解](docs/troubleshooting.md)
- [來源及版本](docs/source-and-version.md)、[逐檔來源清單](docs/source-manifest.json)
- [成品與開發入口](completed/video-bridge/README.md)
