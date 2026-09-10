# Codex／Claude Code MCP 設定與安全操作

## 先啟動同一個本機工作台

在 `completed/xunjian-local-video-editor` 建好 `.venv` 後，先執行：

```powershell
.\start-local-editor.ps1
```

它會啟動 `http://127.0.0.1:8321`。MCP 程序只是一個 stdio 橋接器，必須連到這個已執行的工作台，才能讀取同一個專案、版本、背景工作與媒體證據。

## 手動設定

本包提供兩個範例：

- [`examples/local-editor.codex.toml`](../completed/xunjian-local-video-editor/examples/local-editor.codex.toml)
- [`examples/local-editor.mcp.json`](../completed/xunjian-local-video-editor/examples/local-editor.mcp.json)

先複製符合你使用工具的範例，再把其中的 placeholder Python 路徑：

```text
C:\path\to\xunjian-local-video-editor\.venv\Scripts\python.exe
```

改成你自己解壓縮後的完整路徑，例如：

```text
C:\Users\你的帳號\Downloads\2026-w37-xunjian-local-video-editor\completed\xunjian-local-video-editor\.venv\Scripts\python.exe
```

參數保留為：

```text
-m local_editor mcp --url http://127.0.0.1:8321
```

本課程只提供範例，不會直接修改你的全域 MCP 設定。修改後請重新啟動對應宿主，並以該宿主的工具清單確認 `local-editor` 是否出現。

## 第一次 Agent 對話範本

```text
請先呼叫 editor_get_context，列出目前專案、版本、剪輯方向與未知資訊。
不要改動專案。若要建議剪輯，先針對明確區間建立提案，顯示差異與副作用，等待我確認後才套用。
```

寫入前，要求 Agent 回報：

- `project_id` 與目前版本。
- 要處理的精確時間範圍。
- 提案影響的片段、字幕與可能副作用。
- 仍未看過／未聽過的範圍。

## 寫入與審閱邊界

`editor_prepare_edit` 只建立提案，`editor_apply_edit` 才會改變專案。任何人或 Agent 在提案後又改變時間軸，都可能讓提案過期；遇到版本不相符時，重新從 `editor_get_context` 開始。

`editor_verify_edit` 能回報結構、字幕與已登錄證據的狀態。它不會把抽樣影格自動升級成完整聲畫簽核。要宣稱一段影片已審閱，請實際播放並用 `editor_record_review` 記下有限、明確的範圍。

## Token 控制

- 先讀 `editor_get_context`，避免一次列出所有專案與媒體。
- 以 `editor_inspect_range`／`editor_analyze_range` 縮小到最多 30 秒的重要片段。
- 長工作先取得 `job_id`，再低頻查詢 `editor_job_status`。
- 只要求 Agent 回報可驗證的摘要、提案與差異，無需記錄或要求私人推理。
