# Winston 10xAI Toolspack

每週一個可以直接使用、拆解、練習與分享的 AI Skill、Chrome Extension 或 Local AI Tool。

## 從這裡開始

1. 前往 [CATALOG.md](CATALOG.md) 選擇一週內容。
2. 打開該週的 `README.md`，先確認需要準備的工具。
3. 不熟悉 Git 也沒關係：可直接從 [GitHub Releases](https://github.com/Winston774/Winston-10xAI-Toolspack/releases) 下載 ZIP。
4. 完成任務後，依照該週的「成果證據」與「通過標準」自我檢查。
5. 到 GitHub Discussions 分享成果；安裝或程式問題請建立 Issue。

## 內容類型

- **AI Skill**：可重複使用的指令、參考資料、腳本與範例。
- **Chrome Extension**：可在 Chrome 載入、操作與修改的擴充功能。
- **Local AI Tool**：在自己的電腦執行、保留本地資料並可選擇串接 AI 的完整工具。

## 倉庫結構

```text
weeks/       每週正式內容
templates/   建立新週次時使用的模板
shared/      共用品牌、圖片與學習指南
scripts/     驗證與打包工具
.github/     GitHub Actions 與回報模板
```

## 每週內容的完成定義

每個正式週次都必須包含：

- 明確的學習成果與預估時間
- 可以操作的成品或 starter
- 成果證據
- 可判定的通過標準
- 失敗時的重試路徑
- 版本與更新紀錄

## 最新內容

- [2026-W36：Gomoku Lab — 用 WebMCP 與 ChatGPT 下五子棋](weeks/2026/2026-w36-gomoku-lab-webmcp/README.md)（`0.1.0 Preview`）— 以頁面工具、棋盤版本、公開決策摘要與人工核准，建立可稽核的人機對弈 Workflow。
- [2026-W35：Mastery Loop — 可驗證的點擊式精熟學習系統](weeks/2026/2026-w35-mastery-loop/README.md)（`1.0.0 Stable`）— 以批次評估、證據連結學習地圖與新情境複習建立可續跑的學習循環。
- [2026-W34：Kinetic Character Reveal — 13-Cut 動態角色登場提示詞系統](weeks/2026/2026-w34-kinetic-character-reveal/README.md)（`1.0.0 Stable`）— 抽取 Style DNA、鎖定角色與視覺規則，產生並驗證 15 秒動態角色登場 Prompt。
- [2026-W33：Index Studio — IndexTTS 2.5 本機語音實驗工作台](weeks/2026/2026-w33-index-studio-indextts-2-5/README.md)（`1.0.0 Stable`）— 在 Windows 本機控制五語言、情緒、語速與發音，保存 WAV／JSON 做可重現 A/B。
- [2026-W32：Goal Me — AI Agent 目標任務書](weeks/2026/2026-w32-goal-me-agent-task-brief/README.md)（`1.0.0 Stable`）— 將一句模糊想法轉成可獨立執行、續跑與驗收的 Agent 工作規格。
- [2026-W31：Stylebase 設計靈感資料庫](weeks/2026/2026-w31-stylebase-design-inspiration-library/README.md)（`1.0.0 Stable`）— 將設計截圖建立本地索引，並以 Codex 輔助分析成 Visual DNA 與 Prompt Kit。
- [2026-W30：Gemini 畫面文字 OCR](weeks/2026/2026-w30-gemini-screen-text-ocr/README.md)（`1.0.0 Stable`）— 用快捷鍵框選圖片、影片或 Canvas 的文字，交給 Gemini 轉錄並翻譯。
- 其他內容請查看 [完整目錄](CATALOG.md)。

## 給維護者

建立新週次前，請閱讀 [CONTRIBUTING.md](CONTRIBUTING.md)。正式發布流程為：建立週次、驗證、Pull Request、合併、建立 GitHub Release，再分享到 Skool。

## 授權

本倉庫自行創作的程式碼、教材與隨附素材依 [MIT License](LICENSE) 授權。個別週次若含第三方或衍生專案，以該週 `metadata.yml` 與 completed 內授權檔為準；根目錄 MIT 不會覆蓋第三方授權。
