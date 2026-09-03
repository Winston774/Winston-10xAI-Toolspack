# 2026-W36：Gomoku Lab — 用 WebMCP 與 ChatGPT 下五子棋

> 把五子棋頁面變成 Agent 可讀、可分析、可公布決策、可受控落子的 8 個工具。

## 本週成果

本週提供 `Gomoku Lab v0.1.0 Preview`。你會在本機啟動 15×15 五子棋，觀察 ChatGPT 依序讀取棋盤、公布可審核的決策摘要，再用相同棋盤版本落子。頁面保留人類落子、分析標記、變化圖、Tools 狀態與 Audit Log。

主要能力：

- `get_board_state` 讀取唯一可信的即時棋盤。
- `highlight_cells`、`draw_variation` 顯示風險與候選路線，不改變棋子。
- `publish_agent_decision` 先公開策略、證據、替代方案與信心。
- `place_stone` 僅接受相同 `decisionId`、棋步與 `boardVersion`。
- `request_new_game` 將清盤保留給人類核准。
- `get_audit_log` 保存工具呼叫、拒絕與核准紀錄。
- 頁面內沒有模型、API Key、後端推論或遙測。

成品位置：[`completed/gomoku-lab-webmcp/`](completed/gomoku-lab-webmcp/)

延伸文件：

- [完整教學講義](lesson.md)
- [驗證方式與證據邊界](docs/verification.md)
- [已知限制與 Stable 門檻](docs/known-limitations.md)
- [資料、隱私與內容權利](docs/privacy-and-content-rights.md)
- [部署與專案綁定](docs/deployment-and-licenses.md)
- [疑難排解](docs/troubleshooting.md)

## 基本資料

- 類型：Local AI Tool／WebMCP 示範
- 難度：中級
- 預估時間：安裝 15 分鐘；理解工具契約與完成練習約 90–120 分鐘
- 需求：Node.js `22.13.0` 以上、npm、支援 `document.modelContext.registerTool` 的瀏覽器／ChatGPT 執行環境
- 版本：`0.1.0 Preview`
- API Key：不需要
- 來源快照：`D:\Codex\WebMCP_Gomoku` commit `7541bf1d09d85c5f34f095cb070ea277d748cf7d`

## 安裝與開始

1. 從本週 GitHub prerelease 下載 `2026-w36-gomoku-lab-webmcp.zip` 並解壓縮。
2. 進入 `completed/gomoku-lab-webmcp`。
3. 執行：

```powershell
npm ci
npm run validate
npm run dev
```

4. 打開終端顯示的 localhost 網址。首頁會導向 `/gomoku.html`。
5. 先以人類身分落一子，再請 Agent 依以下契約操作：

```text
請讀取目前棋局，分析風險，公布決策摘要後替白棋落子。
```

若頁面顯示 `WebMCP unavailable in this browser`，棋盤仍可人工操作；請改用支援 WebMCP 的環境並重新載入頁面，原生工具才會註冊。

## 核心 Workflow

```text
get_board_state
  → highlight_cells / draw_variation（選用）
  → publish_agent_decision
  → place_stone
  → get_board_state / get_audit_log 驗證
```

每一個寫入動作都帶著 `boardVersion`。版本或棋步不一致時，頁面拒絕落子；Agent 必須重新讀取棋盤並重新公布決策。

## 本週任務

1. 啟動本機頁面，確認桌面或手機版棋盤可點擊。
2. 由人類先下黑棋。
3. 要求 Agent 讀取棋盤，標示至少一個危險點與一個候選點。
4. 要求 Agent 公布白棋決策摘要，再呼叫 `place_stone`。
5. 檢查決策分頁與 Audit Log 是否能對上同一個版本、座標與玩家。
6. 刻意使用舊 `boardVersion` 呼叫工具，確認動作被拒絕。
7. 記錄一項你會如何改進核准、版本控制或可觀測性。

## 成果證據

- 啟動終端與 localhost 頁面的截圖。
- 一次 `get_board_state → publish_agent_decision → place_stone` 的成功紀錄。
- 決策摘要、棋盤落點與 Audit Log 的對照截圖。
- 一次 `STALE_BOARD_VERSION` 或同等拒絕紀錄。
- 一段 100–200 字說明：頁面工具如何降低 Agent 未讀盤、跳步或偷偷改盤的風險。

## 通過標準

- [ ] `npm ci`、`npm test`、`npm run typecheck`、`npm run build` 全部成功。
- [ ] 棋盤可用滑鼠或觸控落子，Tools 與 Audit 分頁可開啟。
- [ ] 頁面成功註冊 8 個工具，或明確記錄目前環境不支援原生 WebMCP。
- [ ] Agent 落子前有公開摘要，落子與摘要的玩家、座標及版本一致。
- [ ] 舊版本或不匹配的 `decisionId` 無法改變棋盤。
- [ ] 分享的截圖、Issue 與報告不含帳號、私人對話或部署憑證。
- [ ] 沒有把 `npm run lint` 描述成通過；Preview 目前仍有 19 項 scaffold 診斷。

## Preview 邊界

目前新棋局核准沒有再次比較「提出請求時的棋盤版本」與「按下核准時的棋盤版本」。若核准等待期間已有新棋步，舊核准仍可能清空新棋局狀態。課程示範前請避免在待核准期間繼續落子，詳細重現與修正條件見[已知限制](docs/known-limitations.md)。

## 失敗時的最短路徑

1. 版本不符：升級至 Node.js `22.13.0` 以上後重新 `npm ci`。
2. WebMCP 未出現：換到支援的執行環境並完整重新載入頁面。
3. Agent 無法落子：重新呼叫 `get_board_state`，再公布新的決策摘要。
4. 啟動或建置失敗：刪除自己產生的 `node_modules` 與建置目錄後重新 `npm ci`；不要刪除學員產物或來源檔。
5. 部署綁到原專案：先依[部署文件](docs/deployment-and-licenses.md)建立自己的專案綁定。
6. 仍失敗：保存 Node/npm 版本、完整指令、第一個錯誤與 Audit Log，再依[疑難排解](docs/troubleshooting.md)縮小問題。

## 版本紀錄

- `v0.1.0 Preview`：8 個 WebMCP 工具、15×15 棋盤、可見決策、版本式寫入保護、人工新局核准與 Audit Log。
