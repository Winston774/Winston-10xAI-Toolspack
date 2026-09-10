# 2026-W37：迅剪 Local Studio — 本機影片剪輯與 Agent MCP 工作台

> 把剪輯的「讀取情境、提案、套用、驗證與人工審閱」整理成 Agent 可以遵守、你可以檢查的本機工作流。

## 本週成果

本週提供 `迅剪 Local Studio v0.2 Preview`。你會在 Windows 本機啟動繁體中文剪輯工作台，建立一個專案、匯入你有權處理的短素材，並用版本化提案完成一次小範圍剪輯。若你已使用 Codex 或 Claude Code，也可以讓 Agent 透過 stdio MCP 讀取同一個專案、產生提案、等待人工確認後套用，再登錄可追溯的驗證與審閱結果。

成品位置：[`completed/xunjian-local-video-editor/`](completed/xunjian-local-video-editor/)

延伸文件：

- [教學講義與 Agent Workflow](lesson.md)
- [MCP 設定與安全操作](docs/mcp-setup.md)
- [驗證紀錄與證據邊界](docs/verification.md)
- [已知限制與升級條件](docs/known-limitations.md)
- [隱私、內容權利與外部傳輸](docs/privacy-and-content-rights.md)
- [來源快照與打包差異](docs/source-snapshot.md)
- [疑難排解](docs/troubleshooting.md)

## 基本資料

- 類型：Local AI Tool／本機影片剪輯工作台／stdio MCP
- 難度：進階
- 預估時間：安裝與首個專案約 60 分鐘；完成版本化剪輯與 Agent 練習約 120 分鐘
- 支援平台：Windows 10/11；服務僅綁定 localhost
- 需求：Python 3.11 以上；FFmpeg／FFprobe；選用的本機 ASR、Codex 或 Claude Code
- 版本：`0.2.0 Preview`
- 核心 API Key：不需要
- 來源快照：commit `3c458b19fed68f75265fb2dcddcea845f6f31090`

## 安裝與開始

1. 從本週 GitHub prerelease 下載 `2026-w37-xunjian-local-video-editor.zip`，解壓縮。
2. 進入 `completed/xunjian-local-video-editor`。
3. 建立 Python 環境並安裝本機來源：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

4. 安裝 FFmpeg 與 FFprobe，確認兩者可在 PowerShell 執行。接著啟動：

```powershell
.\start-local-editor.ps1
```

5. 開啟 `http://127.0.0.1:8321`，按「建立新專案」，先使用你有權處理的短素材完成最小流程。

`start-local-editor.ps1` 會優先使用這個資料夾的 `.venv`。第一次使用離線語音辨識才需要執行 `scripts/setup-local-asr.ps1`；它會下載模型，請先確認網路、磁碟空間與模型權利。

## 最小使用示範

1. 建立 `W37-我的剪輯練習`，選擇橫式、直式或方形畫布。
2. 匯入 15–30 秒、你有權處理的本機素材。
3. 將素材加入主影片軌，建立或匯入字幕。
4. 用「智能剪口播」或「Agent」先建立提案；先看差異與證據，再選取候選內容套用。
5. 用復原／重做確認版本化操作可回復。
6. 若要輸出，請自行播放檢查實際聲畫後再匯出；輸出成功不等於品質已被自動判定合格。

## Agent Workflow

工作台與 stdio MCP 共用一個本機服務與專案狀態。建議固定遵守以下順序：

```text
讀取目前情境與版本
  → 只取需要的區間證據
  → 形成版本綁定的剪輯提案
  → 檢查前後差異、未知與副作用
  → 人工確認後套用
  → 驗證結構與實際審閱範圍
```

對應 MCP 呼叫可採：

```text
editor_get_context
  → editor_inspect_range / editor_analyze_range
  → editor_prepare_edit
  → editor_get_edit / editor_read_evidence
  → editor_apply_edit
  → editor_verify_edit / editor_record_review
```

工具清單共 25 個；實際能力與版本仍以你連線中的本機服務 `tools/list` 為準。設定方式見 [MCP 設定](docs/mcp-setup.md)。

## 本週任務

1. 啟動 localhost 工作台，建立一個無私人資料的練習專案。
2. 完成一次素材加入時間軸、字幕建立或匯入、以及一個可復原的編輯。
3. 建立一份提案，寫出它預期刪除／保留什麼以及原因。
4. 確認提案基於目前版本；若版本已變更，重新讀取，不直接套用舊提案。
5. 使用結構驗證，再對實際播放過的聲畫範圍做人工審閱紀錄。
6. 寫下「已看過／已聽過的範圍」與「尚未確認的範圍」，不要以抽樣結果代替全片品質聲明。

## 成果證據

- localhost 首頁或工作台截圖，不含私人檔案路徑、人物、字幕或 API Key。
- 專案名稱、畫布比例與時間軸上的一個可辨識編輯。
- 一次提案的前後差異或版本驗證結果。
- 至少一項人工審閱範圍與一項仍待確認的限制。
- 若使用 MCP：`editor_get_context → prepare → apply → verify` 的精簡紀錄，包含同一個專案版本。

## 通過標準

- [ ] `npm run validate` 與 `npm test` 成功。
- [ ] localhost 首頁可建立並進入一個空白專案。
- [ ] 能使用自己的授權素材完成一個可復原的最小剪輯。
- [ ] Agent 或手動流程都能清楚辨識目前專案版本與提案副作用。
- [ ] 只有在人類明確確認後才套用會改變專案的提案。
- [ ] 成果說明區分結構檢查、抽樣證據與真正已播放審閱的範圍。
- [ ] 截圖、Issue、分享文字及 GitHub 上傳內容沒有私人媒體、SQLite、模型、Token、Cookie 或 API Key。

## Preview 邊界

- 此版沒有桌面安裝包、依賴鎖檔或跨平台保證。
- 本輪只完成空白專案的隔離瀏覽器流程；沒有以學員真人長片完成連續聲畫審閱、逐切點黑閃檢查或正式 MP4 匯出驗收。
- 工具的結構性驗證、抽樣影格與音訊傳輸，不能證明畫面語意、口條自然度或整部影片品質。
- 舊 `agent-video`、KIE Seedance、YouTube 相關入口保留在來源快照中，並非本週必修。外部傳輸、費用與內容權利需由使用者明確觸發並自行確認。

完整限制與未來 Stable gate 見[已知限制](docs/known-limitations.md)。

## 失敗時的最短路徑

1. Python 找不到：確認 Python 3.11，重新建立 `.venv`，再執行 editable install。
2. FFmpeg／FFprobe 找不到：安裝後重新開啟 PowerShell，確認兩個指令在 `PATH`。
3. localhost 無法開啟：確認啟動視窗仍在執行，改用未被占用的連接埠，見[疑難排解](docs/troubleshooting.md)。
4. MCP 連不上：先開工作台，再確認 MCP 設定中的 Python 路徑與 URL 都指向同一份解壓縮資料夾。
5. ASR 或模型設定失敗：不要上傳私人音訊求助；先保存套件版本、第一個錯誤和環境資訊，再依[疑難排解](docs/troubleshooting.md)處理。
6. 仍失敗：以不含私人內容的最小素材、最短操作步驟與第一個錯誤建立 Issue。

## 版本紀錄

- `v0.2.0 Preview`：發布本機剪輯工作台、25 個 stdio MCP 工具、版本綁定提案與驗證流程的可審核學員包；完整證據與未驗收範圍已公開記錄。
