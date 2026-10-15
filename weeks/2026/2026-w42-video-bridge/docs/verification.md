# W42 驗證紀錄

日期：2026-10-15。對象：本週 `completed/video-bridge` 分發副本，manifest 版本 0.3.0。

## 本次自動驗證

在成品目錄執行 `npm.cmd run validate`：

- 六份測試共 **97 項通過、0 失敗、0 跳過**。
- `check.mjs` 通過：Manifest V3、10 個 manifest 資源、9 個 JavaScript 語法，以及 HTML／模組引用。
- 測試涵蓋目標影片、引用／多影片定位、X／Threads MP4 解析、允許網域、150 MiB 上限、完整性、下載競態與 Blob URL 清理、過期標記、分塊傳輸、既有附件、重複插入及發文框變更。
- 來源 24 檔建立 SHA-256 清單；23 檔與成品逐位元組一致，設計 README 的本機路徑調整另作確切差異比對。來源六份測試與檢查器保持一致。
- 檢查公開包的相對連結、JSON、來源／Git／ZIP 內容、敏感資訊及禁止檔案；使用倉庫驗證與每週打包工具。

測試使用合成資料、DOM／Chrome API 替身與模擬 fetch，沒有真實社群影片下載、帳號操作或上傳。原始來源檔未改動。

## 來源專案已有紀錄

來源端 2026-10-15 驗證文件描述：部分公開 X／Threads 貼文解析、產品下載函式取得帶／不帶音軌 MP4、Threads 輪播封面比對，以及模擬 Chrome API 的介面截圖。這些為來源端既有紀錄，本次未重新執行，亦未將其測試影片或私人輸出加入學員包。

## 本次待驗範圍

- Chrome 實際載入 0.3.0 後的整包右鍵、offscreen、剪貼簿與下載操作。
- 已登入平台的 X 文章／影片檢視器、Threads 串流／輪播之目前行為。
- Threads／Facebook Ctrl＋V／插入按鈕、附件預覽、上傳完成與平台改版回歸。
- 亮暗色、鍵盤及動態提示的實際瀏覽器操作體驗。

因此本週保持 **Preview**；安裝與人工驗收流程見 [lesson](../lesson.md)。下載受理、附件欄位寫入及平台上傳完成各自需要確認。

## GitHub CI 與附件

沿用現有 CI：結構驗證、completed 擴充功能語法檢查、成品 package.json 的 `validate`（執行本週 97 項測試及資源檢查），再建立所有正式週次 ZIP。可在 [Actions](https://github.com/Winston774/Winston-10xAI-Toolspack/actions/workflows/validate.yml) 查看對應提交。

合併前須確認 PR 當前提交的 CI 成功；合併後亦核對 main CI。打包附件保留 7 天。本機與 CI 的 ZIP 中繼資料可能不同，以相對清單及解壓後 SHA-256 核對內容。
