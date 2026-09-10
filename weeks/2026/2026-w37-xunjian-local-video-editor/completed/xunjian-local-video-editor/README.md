# 迅剪 Local Studio v0.2 Preview｜本機影片剪輯與 Agent MCP 工作台

這是 2026-W37 的學員版。它把繁體中文本機剪輯工作台、字幕與多軌時間軸，以及供 Codex／Claude Code 使用的 stdio MCP 放在同一份可檢查的原始碼包中。

核心工作台預設只服務本機 `127.0.0.1`。建立專案、匯入素材、編輯與儲存都在你的電腦完成；核心流程不需要 API Key。

> **Preview 邊界**：這是一個可試用的 v0.2 工作台，未宣稱等同完整商用剪輯軟體。本包未附影片、聲音、模型、SQLite 專案或匯出成品；長片連續聲畫審閱、逐切點品質與每台機器的正式 MP4 匯出，仍要由你在自己的素材與環境中驗收。

## 你會得到什麼

- 本機專案、素材、時間軸、字幕與背景工作流程。
- 智能剪口播候選、提案預覽、版本防衝突與復原。
- 25 個 stdio MCP 工具，讓 UI 與 Agent 共用同一個本機專案狀態。
- 明確的證據、提案、套用、驗證與人工審閱工作鏈。

本週教學入口在上兩層的 [`README.md`](../../README.md)；來源的歷史技術說明（已去識別化路徑）保留在 [`UPSTREAM-README.md`](UPSTREAM-README.md)，本輪可採信的驗證結果以[驗證紀錄](../../docs/verification.md)為準。

## 開始前

- Windows 10/11、Python 3.11 以上。
- 若要匯入、取樣或匯出媒體，請先安裝 FFmpeg 與 FFprobe，並加入 `PATH`。
- 若要做離線中文字幕辨識，第一次需額外下載本機模型，詳見 [`scripts/setup-local-asr.ps1`](scripts/setup-local-asr.ps1)。
- 本機剪輯核心不需要 API Key。KIE Seedance、YouTube 字幕與舊 `agent-video` 是選用的舊模組，請先看[隱私與內容權利說明](../../docs/privacy-and-content-rights.md)。

## 不用 Git 的最短啟動路徑

1. 從本週 GitHub prerelease 下載 ZIP，解壓縮後開啟 `completed/xunjian-local-video-editor`。
2. 在該資料夾空白處按右鍵，選擇「在終端機中開啟」，依序執行：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\start-local-editor.ps1
```

3. 瀏覽器開啟 `http://127.0.0.1:8321`。保持 PowerShell 視窗開啟；按 `Ctrl+C` 可停止服務。
4. 在首頁按「建立新專案」，選擇畫面比例後進入工作台。第一次練習請使用你有權利處理的短片或自行製作的測試素材。

若電腦沒有 `py` 指令，請改用已安裝的 Python 3.11 執行檔，例如 `python -m venv .venv`。常見問題請看[疑難排解](../../docs/troubleshooting.md)。

## 本週主流程

```text
建立專案
  → 匯入有權處理的本機素材
  → 建立字幕或匯入 SRT/VTT
  → 產生剪輯提案
  → 檢查前後差異與證據
  → 明確套用
  → 版本化驗證與人工審閱
  → 需要時才匯出
```

不要把「已產生影格／音訊證據」當成「已完成品質審閱」。抽樣影格只代表該時間點；要確認聽感或連續畫面，請實際播放對應範圍並在成果中如實標記審閱範圍。

## 使用 Codex 或 Claude Code（選用）

先讓工作台在 `127.0.0.1:8321` 執行，再啟動 stdio MCP：

```powershell
.\.venv\Scripts\python.exe -m local_editor mcp --url http://127.0.0.1:8321
```

請手動將 [`examples/local-editor.codex.toml`](examples/local-editor.codex.toml) 或 [`examples/local-editor.mcp.json`](examples/local-editor.mcp.json) 的路徑調整為你的解壓縮位置；本包不會修改你的全域 Codex 或 Claude Code 設定。完整設定、工具責任與安全流程見 [MCP 設定](../../docs/mcp-setup.md)。

建議 Agent 工作順序：

```text
editor_get_context
  → editor_inspect_range / editor_analyze_range
  → editor_prepare_edit
  → editor_get_edit / editor_read_evidence
  → 人工確認後 editor_apply_edit
  → editor_verify_edit / editor_record_review
```

任何會改變專案的操作都要帶著目前版本並經你明確確認。版本過期時，回到讀取情境的第一步；不要沿用舊提案強行寫入。

## 驗證這份下載包

這個包沒有 Node 依賴。進入本資料夾後可直接執行：

```powershell
npm run validate
npm test
```

它們在學員電腦上只檢查本包結構、版本與必要來源，會略過你本機建立的 `.venv`、專案、媒體、模型與快取。GitHub CI 的 `validate:release` 會在乾淨 checkout 額外拒絕 `.env` 與執行期目錄；`projects/`、`outputs/` 只允許隨包的 `.gitkeep` scaffold，避免使用資料被發布。兩者都不能替代 Python、FFmpeg、MCP 宿主或真人素材驗收。這次發布的完整驗證紀錄在[verification.md](../../docs/verification.md)。

## 授權與來源

- 此包中由 Winston 創作的程式碼與學員文件依 [`LICENSE`](LICENSE) 的 MIT License 發布。
- 外部工具、Python 套件、模型、服務及參考資料保有各自的授權與使用條款；詳見 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
- 來源快照 commit 為 `3c458b19fed68f75265fb2dcddcea845f6f31090`。打包方式與差異請看[來源快照](../../docs/source-snapshot.md)。
