# `<YOUR_PRODUCT_NAME>` (`<yourdomain.com>`) — Chief PM 治理憲章範本

> **使用方式**：將本檔複製為專案根目錄的 `AGENTS.md`，替換所有 `<...>` 佔位符，並依 Phase 0 診斷的 **Pattern 1–4** 保留對應紅線。

---

## 1. 專案定位與單一溝通窗口

- **產品定位**：`<一句話說明你的 Chrome 外掛替誰解決什麼問題>`
- **架構模式**：`<Pattern 1 純本地 / Pattern 2 雲端同步 / Pattern 3 API 計量 / Pattern 4 高流量快取>`
- **收費模式**：`<一次買斷 / 功能分級訂閱 / 訂閱配額＋永不過期加購包>`
- **目標網域**：`<yourdomain.com>`（官網與法務）／`<app.yourdomain.com>`（會員控制台與結帳）／`<api.yourdomain.com>`（API）
- **單一窗口**：由 **Chief PM（主協調 Agent）** 統籌規劃、派工、審查與風險回報，創辦人只需對 Chief PM 做商業決策。

### 創辦人專屬邊界（Human-in-the-Loop）
以下事項涉及真實金錢、法定身分、外部憑證或公開釋出，**任何 Agent 皆不得越權代辦**，一律登記於 `.pm/OWNER_ACTIONS.md`：
- 外部服務帳號註冊、實名 KYC、銀行收款設定與 Production Secrets 寫入。
- 法定營運主體姓名、英文地址、客服信箱（`support@<yourdomain.com>`）與定價／退款政策核定。
- 真實廣告預算、Chrome Web Store 送審／公開切換與 Production Go-Live。

---

## 2. 不可妥協的架構紅線（Non-Negotiable Invariants）

1. **零前端密鑰與商店衛生**：`extension/` 嚴禁殘留上游付費 API Key、核心商業 Prompt／演算法、本機路徑或違反平台政策之程式碼；每次 PR 須通過靜態掃描。
2. **零信任權限與原子帳務**：`profiles` RLS 嚴鎖欄位不可讓前端修改 `plan` 或 `is_suspended`；所有額度／權限變動一律由後端 PostgreSQL `SECURITY DEFINER` 原子 RPC＋冪等鍵處理，絕不信任客戶端回報的用量或方案。
3. **邊緣執行時期安全慣例（Cloudflare Workers）**：所有對外 `fetch` 一律用 `redirect: 'manual'`（禁用 `redirect: 'error'`）、禁止巢狀 `ctx.waitUntil()`、所有外部請求設 `AbortSignal.timeout()`。
4. **金流 Webhook 狀態機與亂序防禦**：驗簽讀取 Raw Body；事件表採 `processing`→`processed`/`failed` 狀態機；正確處理訂閱建立早於交易完成之同週期亂序；退款僅於 `approved` 依原交易桶別回沖。
5. **隱私、法務與多語一致性**：`/privacy` 子處理商與資料流須與實際程式碼 100% 同步；法務頁客服信箱加 `<!--email_off-->`；全站含控制台完整支援所選多語系並記住使用者語系偏好。

---

## 3. 品質閘門與 Git 紀律

### 實作者 ≠ 審查者（Maker ≠ Checker）
- 雙引擎環境（如 Codex CLI ↔ Claude Code CLI）：由另一引擎執行唯讀缺陷優先審查。
- 單引擎環境：另開全新唯讀審查 Session／Sub-agent 逐條比對避坑清單稽核。

### 四道審核閘門（進入 `DONE` 前必全過）
- **G1 規格符合度**：逐條核對派工單驗收條件。
- **G2 獨立程式碼與資安審查**：0 P0、0 P1、P2 清零。
- **G3 本機沙盒與自動化測試**：實跑 typecheck、測試、建置與本機驗證，留存輸出證據。
- **G4 Git 衛生與 CI 全綠**：零密鑰與暫存檔、Conventional Commits（含 `Why:` 與 `Verified:`）、GitHub CI 全綠。

### 並行開發與跨平台慣例
- 多條線並行開發使用獨立 `git worktree` 與不重疊目錄邊界（`api/`、`extension/`、`web/`）。
- Windows PowerShell 呼叫 npm 一律使用 `npm.cmd`。
