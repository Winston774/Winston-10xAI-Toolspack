# W40 v0.1.0 發布驗證

日期：2026-10-01。以下為本次學員副本的重新執行結果；技能內 VALIDATION.md 保留來源開發時的歷史紀錄，不能替代本次驗證。

## 本次已執行

- Windows、Python 3.11.15、FFmpeg 6.1.1、FFprobe 7.1.5。
- doctor 通過核心工具及 libx264、AAC、MJPEG、PCM16 編碼器檢查；subtitles filter 可用。測試環境未安裝選配 faster-whisper。
- 38 項 unittest 全部通過，0 失敗、0 跳過。包含 15 項計畫、5 項逐字稿／分塊、6 項 prepare 媒體整合、4 項渲染單元、8 項渲染媒體整合。
- 媒體整合實際執行 FFmpeg，涵蓋四種比例、旋轉、非方形像素、無音軌、字幕燒錄、跨切點字幕、hash 不符與失敗報告。
- 一小時合成素材：prepare → inspect → select → validate → render 成功；13 個重疊文字區塊，2 個 45／60 秒片段，4 支直橫版 MP4 與 SRT。
- 4 支合成輸出全檔解碼成功、原始合成影片 hash 未變。所有結果保持 partial，human_audiovisual_signoff=false。

重現方式：在技能資料夾設定 VH_FFMPEG 與 VH_FFPROBE 後執行 `python -m unittest discover -s tests -v`；完整流程使用 `python tests/smoke_workflow.py --out <新目錄> --ffmpeg <工具路徑> --ffprobe <工具路徑>`。測試素材與輸出放在學員包外。

## 分發檢查

對照來源 18 個檔案與 [來源清單](source-manifest.json)：17 個檔案除換行正規化外一致，SKILL.md 只增加既有範例導覽。9 支 Python 語法、技能 frontmatter、29 個本週相對文件連結、常見憑證樣式及禁止檔案檢查均通過。

週次 ZIP 由倉庫 build-release.ps1 產生，共 28 個檔案；逐檔與本週目錄一致，CRC、正斜線路徑與排除項目檢查通過。不包含根目錄 LICENSE、影片、完整字幕、模型、字型、快取或講師貼文。從 ZIP 另解壓一份技能後，38 項測試再次全部通過、0 跳過；最終文件更新後重建 ZIP 並重新核對逐檔內容。

GitHub 既有 CI 負責倉庫結構、既有工具測試及各週 ZIP 建置；沒有自動執行本週 Python 媒體測試的步驟，38 項與一小時流程的證據來自上述本機重新執行。合併結果、最新 CI 與 ZIP hash 另在 PR／交付回報核對。

## 未執行及證據界線

- 沒有下載模型或執行 faster-whisper 真實 ASR。
- 沒有重新觀看、聆聽原專案約 100 分鐘訪談或雙語合輯；歷史範例均保留其未確認事項。
- 沒有量測語意判斷準確率、漏選率、分數校準、ASR 字錯率或觀看成效。
- 合成素材使用預先指定字幕與分數，無真實訪談語音；其通過無法證明重要段落辨識品質。
- 沒有跨平台、全新帳號技能安裝、中文字形、連續聲畫同步或人類發布驗收。

上述邊界保留為 Preview，不把結構檢查與解碼成功等同內容品質認證。
