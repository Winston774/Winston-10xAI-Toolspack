# 已知限制與 Stable 門檻

## P1：待核准期間棋盤改變，舊核准仍可清盤

目前 `showNewGameApproval()` 會保存 `createdVersion`，`approveRequest()` 尚未比較它與最新 `state.version`。

已重現序列：

1. 在 BOARD v1 提出新棋局請求。
2. 等待核准期間落一子，棋盤進入 v2。
3. 按下舊核准。
4. 棋盤被清空並進入 v3。

建議修正：

- 已有 pending approval 時拒絕第二個請求。
- 核准前要求 `pendingApproval.createdVersion === state.version`。
- stale 時清除或拒絕請求，不改變棋盤，並寫入 Audit Log。
- 加入「等待核准期間人類落子」與「重複請求」回歸測試。

臨時操作邊界：核准卡片出現後，先核准或拒絕，再繼續落子。

## Lint 邊界

`npm run lint` 目前回報 19 項診斷，集中在未被首頁匯入的 `components/ui/*` 與 `hooks/use-mobile.ts` scaffold，包括可及性規則、Effect 內同步 setState 與 template expression。實際首頁導向 `public/gomoku.html`，這些檔案仍屬發佈來源，故保留失敗紀錄。

## 尚未完成的原生環境證據

本次已在一般 Chromium 驗證棋盤、按鈕、響應式畫面與公開 helper 的工具契約。該環境沒有 `document.modelContext`，因此原生 ChatGPT WebMCP 註冊與完整實機對局標記為 `NOT RUN`。

## 升級 Stable 的必要條件

- 修正 P1 並加入自動回歸測試。
- `npm run lint` 零錯誤，或明確縮小 lint 範圍且說明排除理由。
- 在支援 WebMCP 的 ChatGPT 環境完成 8 工具註冊、讀盤、公布、落子、stale 拒絕與人工核准驗收。
- 重新建置 Release，保存 PR CI 與全新下載驗證證據。
