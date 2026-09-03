# 疑難排解

## `npm ci` 拒絕 Node 版本

先執行 `node --version`。本專案要求 Node.js `22.13.0` 以上；建議使用 Node 24 LTS 相容環境。更新後重新開啟終端再執行 `npm ci`。

## 顯示 `WebMCP unavailable in this browser`

代表目前分頁沒有 `document.modelContext.registerTool`。請切換到支援 WebMCP 的 ChatGPT／瀏覽器執行環境，並完整重新載入頁面。工具只在頁面載入時註冊；一般 Chromium 仍可人工下棋與檢查畫面。

## Agent 回傳 `STALE_BOARD_VERSION`

棋盤在讀取後已改變。重新呼叫 `get_board_state`，丟棄舊 `decisionId`，再呼叫 `publish_agent_decision` 與 `place_stone`。

## Agent 回傳 `DECISION_REQUIRED` 或 `DECISION_MOVE_MISMATCH`

依序確認：

1. 已先呼叫 `publish_agent_decision`。
2. 使用它回傳的 `decisionId`。
3. player、row、col 與公開摘要完全相同。
4. boardVersion 尚未改變。

## 新棋局核准卡片仍在畫面上

先核准或拒絕，再繼續落子。Preview 目前有 stale approval 限制，詳見[已知限制](known-limitations.md)。

## `npm run build` 出現 route classification warning

Vinext 可能顯示 `/` route classification 警告；若命令 exit code 為 0 且 build 完成，記錄警告即可。首頁使用 server redirect 導向 `/gomoku.html`。

## `npm run lint` 失敗

本版已知有 19 項未使用 scaffold 診斷。它不會被 `npm run validate` 隱藏；驗證文件分開記錄 build/typecheck 通過與 lint 失敗。要升級 Stable，需修正或有依據地縮小 lint 範圍。

## 部署指向原專案

停止部署，依[部署文件](deployment-and-licenses.md)建立自己的專案綁定。`project_id` 不是 token，但也不代表你有原專案寫入權限。
