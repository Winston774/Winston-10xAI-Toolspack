# Changelog

所有正式週次與重要倉庫變更都記錄於此。

## Unreleased

- 尚無。

## 2026-W38 v0.1.1 Preview — 2026-09-17

- 依使用者更正的 video-understanding2.rar 更新同一個 W38，12 個功能／設定檔與原始文字一致，驗證紀錄另依本次結果重寫。
- 重新編寫學員入口、講義、限制、疑難排解、分享、來源與驗證說明，統一新版本下載入口。
- 移除前版額外加入的 Hypit 研究文件、安全附加流程與合成示例；保留 LICENSE 並更新 NOTICE 交代補件來源。
- 排除 RAR 的 4 個 Python 快取，完整執行 30 項測試（含 7 項合成媒體整合），0 項跳過。

## 2026-W38 v0.1.0 Preview — 2026-09-17（已由 v0.1.1 取代）

- 新增 2026-W38「Video Understanding：附時間證據的短影音理解與生成交接」Preview。
- 將使用者提供 ZIP 的 10 個技能檔案轉成可公開的學員包，補齊 LICENSE、NOTICE、Hypit 研究參考、30 項可重跑測試、合成 partial 範例與安裝文件。
- 新增本機優先、逐檔外部傳輸確認、內容權利、未信任影片衍生文字與公開分享排除規則。
- 將真實影片、畫格、WAV、逐字稿、metadata、私有測試產物與上游快取排除在公開 Release 外；維持 Preview，因跨平台與完整 FFmpeg 整合驗證仍待補足。

## 2026-W37 v0.2.0 Preview — 2026-09-10

- 發布迅剪 Local Studio：本機影片剪輯與 Agent MCP 工作台 Preview。
- 加入本機專案、時間軸、字幕、提案、版本防衝突、復原與 25 個 stdio MCP 工具的學員文件。
- 以 Git 追蹤來源 allowlist 打包，排除 `.env`、模型、媒體、SQLite、快取、驗證產物與私人專案資料。
- 加入 MIT、第三方通知、外部傳輸、內容權利、MCP 操作、驗證證據與 Preview 限制；把長片連續聲畫、正式 MP4 與真實 MCP 宿主驗收保留為 Stable gate。

## 2026-W36 v0.1.0 Preview — 2026-09-03

- 發布 Gomoku Lab WebMCP 人機五子棋 Preview。
- 加入 8 個頁面工具、棋盤版本檢查、公開決策摘要、可見分析標記與 Audit Log。
- 加入桌面／手機操作、TypeScript、production build 與靜態契約驗證紀錄。
- 公開記錄尚待處理的核准版本競態與 19 項未使用 UI scaffold lint 診斷，完成修正與原生 WebMCP 驗收後再升級 Stable。

## 2026-W35 v1.0.0 — 2026-08-28

- 正式發布 Mastery Loop：可驗證的點擊式精熟學習系統。
- 加入 version 3 批次 Assessment、證據連結 Learning Map、新情境 Review 與 delayed review。
- 加入點擊優先介面、答案防洩漏、不可變 response、idempotent retry、phase lock 與 crash recovery。
- 加入 90 項自動測試、完整安裝教學、資料隱私、安全邊界、驗證方式與疑難排解。

## 2026-W34 v1.0.0 — 2026-08-20

- 正式發布 Kinetic Character Reveal：13-Cut 動態角色登場提示詞系統。
- 加入 EXTRACT、FAITHFUL、SERIES、REMIX、AUDIT 五種工作模式。
- 加入 Style DNA、約束矩陣、13-Cut Blueprint、Prompt 資產、範例與觸發評估資料。
- 加入零依賴 Prompt Validator、安裝教學、素材權利、疑難排解與自動／人工驗收邊界。

## 2026-W33 v1.0.0 — 2026-08-13

- 正式發布 Index Studio：IndexTTS 2.5 本機語音實驗工作台。
- 加入臺灣正體中文、五語言、四種情緒模式、語速／發音／採樣控制與 WAV／JSON 實驗證據。
- 加入聲音權利、衍生作品授權、學員任務、疑難排解與自動／人工驗收邊界。
- 擴充 Toolspack local AI tool 驗證，支援 Python 專案搭配零依賴 Node release checks。

## 2026-W32 v1.0.0 — 2026-08-06

- 正式發布 2026-W32「Goal Me — AI Agent 目標任務書」。
- 加入執行型、探索型、混合型與經授權的多 Agent 任務書流程。
- 加入權限邊界、防取巧驗收、三道止損、斷點續跑與獨立驗收設計。
- 加入完整安裝教學、練習、成果證據、重試路徑與驗證文件。

## 2026-W31 v1.0.0 — 2026-07-30

- 加入 Stylebase 設計靈感資料庫與 `Local AI Tool` 週次類型。
- 加入本地圖片索引、SHA-256 去重、SQLite／FTS5 搜尋與人工來源欄位。
- 加入明確觸發的 Codex 圖片分析、單工佇列、JSON Schema、Visual DNA 與 Prompt Kit。
- 加入完整教學、架構、資料隱私、圖片權利、疑難排解與驗證文件。
- 擴充 Repository Validator 與 GitHub Actions，驗證 completed Node.js 工具。

## 2026-W30 v1.0.0 — 2026-07-27

- 建立 Winston 10xAI Toolspack 基礎結構。
- 加入 AI Skill、Chrome Extension 與每週教學模板。
- 加入本機與 GitHub Actions 驗證流程。
- 加入 2026-W30「Gemini 畫面文字 OCR」Chrome Extension v0.6.2、教學講義、API 設定、架構、權限與疑難排解文件。
- 加入框選與完整可視區快捷鍵、圖片 OCR、繁中翻譯、反白翻譯、單字庫與可重現測試。
- 採用 MIT License，並將倉庫與 `2026-w30-v1.0.0` Release 公開發布。
