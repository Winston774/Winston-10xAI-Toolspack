# 打包來源識別與可稽核範圍

## 來源識別

本週包從使用者提供的本機 Git 專案建立。以下 commit 是製作者使用的來源識別，不是可供學員公開 clone 或 fetch 的 remote；ZIP 也不含 `.git`。學員可公開取得並驗證的是本週 Toolspack 包本身。

```text
commit：3c458b19fed68f75265fb2dcddcea845f6f31090
分支：codex/brand-ui-colors
追蹤檔案：114
```

打包採 `git archive HEAD` 的 Git 追蹤檔案 allowlist。此方式排除了來源工作區中大量被忽略的本機內容，例如 `.env`、`.venv`、`.local-editor`、`.editor-test-data`、實際 `projects/` 素材、模型、SQLite、驗證產物與匯出媒體。

## 這個學員包額外加入的檔案

為了讓來源可公開學習與由 Toolspack CI 驗證，包內新增或調整：

- 學員版 `README.md`；`UPSTREAM-README.md` 保留來源技術說明，但把作者機器路徑改為 generic placeholder，並在檔首標示它是歷史快照而非本輪驗收證據。
- `LICENSE`：Winston 創作程式碼與學員文件採 MIT License。
- `THIRD_PARTY_NOTICES.md`：外部工具、模型、服務與參考內容的權利邊界。
- `package.json` 與 `scripts/validate-package.mjs`：零 Node 依賴的 release 結構檢查。
- W37 的教學、MCP、隱私、驗證、限制與疑難排解文件。
- `.env.example`、MCP 範例與文件中的作者機器路徑改為 placeholder；`scripts/prune.ps1`／`scripts/prune.sh` 加入專案根目錄與 reparse point 保護。

上述變動不改寫剪輯核心、MCP 契約或媒體處理行為。來源 Python 專案仍由 `pyproject.toml`、`local_editor/`、`agent_video_editor/`、`seedance/` 和既有文件組成。

## 範圍取捨

本次保留 114 個 Git 追蹤檔案作為公開包基底，以避免隱性遺漏來源專案模組。為了公開隱私、設定可移植性與刪除安全，以下來源檔在包內有刻意差異：

- `.env.example`、`examples/local-editor.codex.toml`、`examples/local-editor.mcp.json`、`docs/local-editor-mcp.md`、`DESIGN.md`：作者機器路徑改為 generic placeholder。
- `README.md`、`docs/agent-understanding-v02.md`、`docs/local-editor-acceptance.md`：加入歷史證據與未附產物的醒目註記；根 `README.md` 的學員起步內容改由新的 `README.md` 提供。
- `local_editor/web/app.js`：UI 下載的 MCP 範例改用 `local-editor` 名稱與可攜 Python path placeholder，不再輸出作者工作目錄。
- `agent_video_editor/media.py`：移除另一個工作區的硬編碼工具搜尋路徑，只保留 PATH 與使用者明確設定的搜尋方式。
- `scripts/prune.ps1`、`scripts/prune.sh`：新增 Job 格式、專案根目錄與 symlink／reparse point 防護。
- `seedance/__init__.py`、`seedance/cli.py`、`seedance/client.py`：只移除檔尾多餘空白行，以符合 Toolspack 的 Git whitespace 檢查；程式行為未改。

這些公開化變動涵蓋 15 個來源檔；其餘 99 個來源檔維持可對應來源 Git blob。課程主線只聚焦 `local_editor/` 與其 MCP；`agent_video_editor/`、`seedance/`、舊 skills 與 KIE 設定屬於額外來源，必須由使用者自行決定是否啟用。

任何新增的使用者素材、模型、API Key、Cookie、輸出影片、資料庫或快取，都不應視為這份公開來源快照的一部分。
