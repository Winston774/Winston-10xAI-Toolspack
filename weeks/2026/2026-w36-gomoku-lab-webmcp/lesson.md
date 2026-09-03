# 教學講義：把網頁互動拆成 Agent 可驗證的工具契約

## 學習目標

完成本週練習後，你會理解：

1. 如何把 Canvas UI 狀態包成有 JSON Schema 的頁面工具。
2. 如何以 `boardVersion` 阻擋讀盤後已過期的動作。
3. 如何強制 Agent 先公開可審核摘要，再取得寫入能力。
4. 如何區分讀取、草稿、追蹤、寫入、核准等工具責任。
5. 如何用頁面畫面與 Audit Log 形成使用者可檢查的證據鏈。

## 架構

```text
ChatGPT / WebMCP Host
  ↓ document.modelContext.registerTool
8 個頁面工具
  ↓
Authoritative in-memory state
  ├─ board / turn / version / history
  ├─ highlights / variation
  ├─ pendingDecision / pendingApproval
  └─ audit
  ↓
Canvas 棋盤 + 決策 / Tools / Audit 可視介面
```

`public/gomoku.html` 同時包含狀態、繪圖、工具契約與可視 UI。這種單檔結構適合教學與快速稽核；要擴充多人連線或長期保存時，再拆成 state core、tool adapter、renderer 與 persistence。

## 工具分層

| 類型 | 工具 | 是否改變棋盤 |
|---|---|---|
| Read | `get_board_state`, `get_audit_log` | 否 |
| Draft | `highlight_cells`, `draw_variation`, `clear_analysis` | 否，只改可視分析 |
| Trace | `publish_agent_decision` | 否，建立公開決策 |
| Write | `place_stone` | 是，需決策與版本一致 |
| Approval | `request_new_game` | 提出時不改，核准後清盤 |

Agent 每次先讀取最新狀態。分析工具可以失敗或重跑，寫入工具則必須檢查時間與內容是否仍有效。

## 寫入前的兩道鎖

第一道鎖是棋盤版本：

```text
expectedVersion === state.version
```

第二道鎖是公開決策：

```text
decisionId、player、row、col 全部與 pendingDecision 相同
```

只要人類在 Agent 分析期間落了一子，版本就改變；舊決策無法落盤。這使「先讀、再想、再寫」成為可驗證的協定。

## 公開摘要與私人推理

`publish_agent_decision` 要求：

- `summary`：一句可審核的策略結論。
- `evidence`：1–4 個棋盤事實。
- `alternatives`：最多 3 個候選方案。
- `confidence`：0–1 的信心。

頁面保留決策依據與取捨，沒有要求或保存模型私人思維過程。實務上應追蹤可驗證的輸入、輸出、工具呼叫與規則，不依賴不可稽核的內部推理文字。

## 核准需要版本語意

核准工具也屬於延遲寫入。完整設計應保存 `createdVersion`，並在使用者按下核准時再次比較目前版本。若版本已改變，清除或拒絕舊核准，要求 Agent 根據新狀態重新提出。

本版已保存 `createdVersion`，核准函式尚未執行第二次比較，因此列為 Preview。這個缺口很適合做本週延伸練習。

## Agent Workflow 範本

```text
1. 呼叫 get_board_state(includeHistory=true)。
2. 根據 boardVersion 分析當前威脅。
3. 視需要呼叫 highlight_cells 或 draw_variation。
4. 呼叫 publish_agent_decision，公開摘要與證據。
5. 以回傳 decisionId 及同一 boardVersion 呼叫 place_stone。
6. 再讀棋盤與 Audit Log，確認版本增加且座標一致。
7. 任一步驟回傳 stale 時，回到第 1 步。
```

## Token 成本優化

- 先讀 compact board rows；只有需要追溯時才加入 history。
- `evidence` 保留最關鍵的 1–4 點，避免把整盤重新敘述一次。
- variation 限制 8 手、highlights 限制 12 格，讓視覺與 JSON 都保持可控。
- stale 時不要辯解或沿用舊分析，直接重新讀取。
- Audit 查詢先用小 `limit`，除錯時再擴大。

## 延伸實作 TODO Tree

```text
Stable gate
├─ Approval safety
│  ├─ 拒絕第二個 pending request
│  ├─ approve 前比較 createdVersion
│  └─ stale 時不改盤並寫入 audit
├─ Code quality
│  └─ 清理或排除未使用 shadcn scaffold 的 19 項 lint 診斷
├─ Native runtime QA
│  ├─ 真實 ChatGPT WebMCP 註冊 8 工具
│  ├─ 完成一局讀盤／公布／落子流程
│  └─ 驗證人工拒絕與 stale approval
└─ Regression tests
   ├─ 重複 request
   ├─ 核准等待期間的人類落子
   └─ decisionId / version / move mismatch
```
