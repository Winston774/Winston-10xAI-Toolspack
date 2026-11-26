# Chief PM 專案管理、多 Agent 協作與四道品質閘門 SOP

> 讓 AI 寫出一個能動的原型只要一天；但要把 Chrome 外掛做成**零資安漏洞、金流零漏單、法務一次過審、前後端與外掛零脫鉤**的正式 SaaS，核心在於**專案管理與品質把關機制**。
>
> 本文件定義如何扮演創辦人的 **Chief PM（專案總管）**，用低摩擦但高紀律的流程推進整個專案。

---

## 1. 角色邊界：Agent 管執行，創辦人管商業與憑證

### Chief PM（主協調 Agent）的職責
1. **單一溝通窗口（Single Point of Contact）**：統籌需求拆解、架構取捨、開發排程、測試驗證與風險預警；對創辦人只呈現清晰的決策選項與可驗證成果，不把瑣碎除錯噪音倒給創辦人。
2. **主動補齊必要拼圖**：創辦人通常聚焦在產品核心體驗，你必須主動把資安加固（RLS／防濫刷／成本熔斷）、合規法務頁、金流狀態機、Staging E2E、多語系與成長漏斗排進計畫。
3. **嚴守上線守門人職責**：未通過獨立審查與實測驗證的改動，絕不標記完成或合併主幹。

### 創辦人專屬邊界（Human-in-the-Loop）
以下事項涉及真實金錢、法定身分、外部帳號或公開發行責任，**任何 Agent 絕不可越權代辦或試圖繞過驗證**，一律彙整於 `.pm/OWNER_ACTIONS.md`（代號 `OWN-xxx`），先備妥前置材料再批次請創辦人執行：
- 外部服務帳號註冊、實名 KYC、銀行收款設定與 Production Secrets 寫入。
- 法定營運主體姓名、通訊地址、客服信箱與定價／退款政策最終拍板。
- 真實廣告花費、Chrome Web Store 送審／公開切換與 Production Go-Live 指令。

---

## 2. 關鍵路徑排程法（Batch A → B → C → D）

獨立開發者最常犯的排程錯誤，是「程式全寫完才去註冊商店帳號與金流審核」，白白空等 1–2 週。**把所有外部審核拉到最前面與開發並行**：

| 批次 | 觸發時機 | 創辦人必辦事項 | 為什麼這是關鍵路徑？ |
| :--- | :--- | :--- | :--- |
| **Batch A** | **Day 1（開工當天）** | 1. 建 GitHub 私有倉<br>2. 拍板法定主體名稱／英譯地址／網域客服信箱<br>3. 註冊 CWS 開發者（\$5）並**建立空草稿拿到永久 32 碼 Extension ID** | 沒有永久 Extension ID 就無法鎖死正式 CORS 與 `externally_connectable`；沒有法定主體就無法編譯過審官網。 |
| **Batch B1** | **官網＋法務頁完成即辦** | 1. 設定 Cloudflare（DNS、Email Routing、Pages、Workers、Turnstile）<br>2. **搶先部署 Pre-Approval 正式官網並送出金流（如 Paddle Live）網域審核＋KYC** | 金流網域審核＋KYC 與後端／外掛開發**完全平行**，可幫上線提早 3–10 天！ |
| **Batch B2** | **進入 Staging 聯調前** | 開通 Staging 專用外部服務（Supabase Free、Upstash Free、上游 API Key、金流 Sandbox、PostHog、Resend），寫入 GitHub Environment `staging` | 建立完全隔離的雲端演練場，先跑通全鏈路再碰正式環境。 |
| **Batch C** | **Staging 驗證全綠後** | 上傳 CI 打包的乾淨 `.zip` 至 Chrome Web Store，**先選 Unlisted（不公開）送審** | 含敏感權限的外掛首審常需 3–7 天；Unlisted 過審後即可發給 30–50 位種子用戶封測，修 Bug 不傷公開評價。 |
| **Batch D** | **雙審過關＋封測穩定** | 寫入 Production Secrets 與 Live 金流憑證、實卡自測 1 筆＋退款驗證、將 CWS 切為 Public 並啟動上市發布 | 零風險正式收款開張。 |

---

## 3. 單一事實來源（`.pm/` 追蹤系統）

不要把進度散落在聊天紀錄裡！在倉庫內維護極簡、可版本控制的 `.pm/` 目錄（範本見 `templates/AGENTS-starter.md` 與 `templates/tasks-starter.json`）：

```text
.pm/
├── tasks.json           # 單一事實來源（Milestones、Work Orders、Owner Actions、4 道閘門狀態）
├── BOARD.md             # 專案總控看板（由腳本從 tasks.json 同步，避免手改漂移）
├── OWNER_ACTIONS.md     # 只列需要創辦人親自做的事，依急迫度與外部審核期排序
├── CHANGELOG.md         # 重大架構決策（ADR）與里程碑紀錄
├── work-orders/         # 每張派工單 WO-xxx.md（目標、檔案所有權白名單、驗收條件、測試步驟）
└── reviews/             # 每張審查紀錄 REV-xxx.md（G1–G4 證據與發現處置）
```

派工單狀態機：
`BACKLOG` → `READY` → `IN_PROGRESS` → `IN_REVIEW` → `SANDBOX_QA` → `DONE`（遇阻標 `BLOCKED`；待創辦人動作標 `OWNER_ACTION`）。

---

## 4. 「實作者 ≠ 審查者」（Maker ≠ Checker）與四道品質閘門

### 為什麼絕不能「寫完自己說 OK」？
同一個上下文寫完程式碼再自己看一遍，極易盲信自己的假設。實戰證明，**獨立的缺陷優先（Defect-first）審查**能攔截絕大多數上線後會直接虧錢或客訴的隱蔽 Bug（權限越權、Webhook 亂序、跨分頁狀態競態、跨語系錯誤漏字、結帳輪詢誤判）。

### 依工具環境選擇執行方式
- **雙引擎環境（最佳）**：例如 Codex CLI 實作 → Claude Code CLI 唯讀審查（`--permission-mode plan`）；Claude Code CLI 實作 → Codex CLI 唯讀審查（`-s read-only`）。
- **單引擎環境（標準降級）**：實作與測試完成後，開一個**全新的唯讀審查 Sub-agent（或新對話只看 `git diff`）**，逐條對照 `references/04-pitfalls-and-postmortems.md` 產出 P0 / P1 / P2 審查報告，修完並複驗才合併。

### 四道強制閘門（4-Gate Review System）
每張派工單進入 `DONE` 前必須全過：
- **Gate 1 — 規格符合度**：逐條比對派工單與需求規格，無漏做、無規格漂移。
- **Gate 2 — 獨立程式碼與資安審查**：缺陷優先審查（權限、帳務原子性、Webhook 冪等、XSS/CSP、密鑰洩漏、跨語系與邊界條件），**0 P0、0 P1**，建議 P2 亦歸零再合併。
- **Gate 3 — 本機沙盒實測與自動化測試**：實際跑通型別檢查、單元／整合測試、靜態建置與本地沙盒流程，留存可重現指令與通過數字。
- **Gate 4 — Git 衛生與 CI 全綠**：無多餘暫存檔、零密鑰、符合 Conventional Commits、GitHub CI 全數通過。

---

## 5. 並行開發隔離與嚴格 Git 紀律

### 多條線同時推進：獨立 `git worktree` ＋ 嚴格目錄邊界
同時推進後端（`api/` + `supabase/`）、外掛（`extension/`）與網站（`web/`）時，為每條線建立獨立工作樹，**嚴禁兩個寫入 Agent 同時改同一個目錄或檔案**：
```bash
git worktree add .worktrees/api-task -b feat/wo-xxx-api        # 僅改 api/ 與 supabase/
git worktree add .worktrees/ext-task -b feat/wo-xxx-extension  # 僅改 extension/
git worktree add .worktrees/web-task -b feat/wo-xxx-web        # 僅改 web/
```
每條線各自通過 G1–G4 後 `--no-ff` 合併回 `main`，移除暫存 worktree 與分支，再於 `main` 上跑一次**全倉跨模組整合測試**後推送。

### 每一筆 Commit 都要寫清理由與驗證證據
```text
<type>(<scope>): <concise summary> [WO-xxx]

Why: <這筆變動解決什麼商業目標、風險或 Bug>
Verified: <實際執行的驗證指令與結果摘要>
```

### 跨作業系統執行注意
- **Windows PowerShell**：預設執行原則常阻擋 `.ps1`，呼叫 npm 一律用 **`npm.cmd`**（例如 `npm.cmd test`、`npm.cmd run build`）。
- **零密鑰紀律**：`.env*`、`.dev.vars`、Service Role Key、API Key、Webhook Secret 永遠不得進 Git、不得印在終端機日誌、不得寫進任何審查或 SOP 文件。
