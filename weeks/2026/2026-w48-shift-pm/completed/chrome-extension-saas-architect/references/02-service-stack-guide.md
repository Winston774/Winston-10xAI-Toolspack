# 雲端服務與部署選型指南（服務清單、推薦理由、費用與省略條件）

> 這套雲端技術棧經過真實 Chrome 外掛 SaaS 完整驗證：**Staging 開發驗證期幾乎可壓在 US\$0–\$5/月；Production 正式上線固定月費約 US\$30–\$31/月起**，可輕鬆承載數千位活躍付費用戶，無需自行管理傳統主機（VPS / Kubernetes）。
>
> **給 Agent 的使用原則**：請依 Phase 0 判定的 **Pattern 1–4** 動態裁剪以下清單，只推薦該產品真正需要的服務，並向創辦人白話說明「為什麼需要它」與「為什麼先不用別家」。

---

## 一、全套服務選型與成本對照總表

| 層級 | 推薦服務 | 解決什麼問題 | Staging 起步月費 | Production 建議月費 | 適用模式（Pattern 1–4） |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **原始碼與 CI/CD** | **GitHub + GitHub Actions** | 私有倉庫、PR 自動測試、資料庫遷移重播、`staging`/`production` 隔離部署、自動打包 CWS `.zip` | \$0 | \$0（Free 夠用） | **全模式必備** |
| **網域、DNS 與客服信箱** | **Cloudflare Registrar + DNS + Email Routing** | 網域解析、免費 HTTPS、5 分鐘建立免費 `support@yourdomain.com` 轉寄到個人信箱 | 網域年費（~\$10–\$15/年） | \$0/月 | **全模式必備** |
| **官網、法務頁與會員頁** | **Cloudflare Pages（Astro + React Islands）** | 全球 CDN、高分 SEO 靜態官網與法務頁 ＋ 互動會員控制台 | \$0 | \$0（Free 夠用） | **全模式必備** |
| **邊緣 API 閘道** | **Cloudflare Workers（Hono + TypeScript）** | 權限驗證、金流 Webhook、保護第三方 API Key、限流、定期重設配額（Cron） | \$0（或 \$5） | **\$5/月**（Workers Paid，出站流量 \$0） | **全模式推薦**（Pattern 1 可用 Free 起步） |
| **反機器人防護** | **Cloudflare Turnstile** | 註冊／登入／免費試用領取防機器人批次濫刷（無惱人九宮格） | \$0 | \$0（Free 額度極高） | 有免費額度或公開註冊**必備** |
| **資料庫與會員驗證** | **Supabase（PostgreSQL + Auth）** | 開箱即用 Google／Email 驗證、RLS 權限隔離、ACID 原子帳本與會員資料儲存 | \$0（Free 跑 Staging） | **\$25/月**（Pro：不休眠、每日備份、PITR） | **Pattern 2 / 3 / 4 必備**；Pattern 1 推薦 |
| **邊緣狀態與限流** | **Upstash Redis（Serverless REST）** | 滑動限流、即時停權／升階快取、單次授權碼、併發連線鎖、每日成本熔斷器 | \$0（Free） | \$0 起（按量極低） | **Pattern 3 / 4 必備**；Pattern 1 / 2 選配 |
| **私有物件儲存／共享快取** | **Cloudflare R2（Private Bucket）** | 儲存可跨用戶重用的公開查詢結果或大檔案（10GB 免費，**出站流量 \$0**） | \$0 | \$0 起（按量極低） | **僅 Pattern 4 需要**；Pattern 1–3 **省略** |
| **全球金流與稅務（MoR）** | **Paddle Billing v2** | 全球信用卡／PayPal 收款、**自動代收申報全球 VAT/銷售稅**、客戶自助帳務入口、匯回多國本地銀行 | \$0（Sandbox 免費） | **\$0 月費**（成交抽 `5% + \$0.50`） | **無當地 Stripe / 台灣／全球獨立創辦人首選** |
| **上游付費 API（主力＋備援）** | **高性價比主力供應商 ＋ 高可用大廠備援** | 處理核心 AI／資料／分析請求；雙供應商自動故障轉移防斷線或無預警停服 | 按量（極低） | 按量（受每日成本熔斷器保護） | **僅 Pattern 3 / 4 需要**；Pattern 1–2 **省略** |
| **隱私優先漏斗分析** | **PostHog（Server-side Capture）** | 後端追蹤安裝→註冊→首次成功使用→觸發付費牆→付費轉換漏斗（匿名 ID、不收 IP） | \$0（每月 100 萬事件免費） | \$0 起 | **全模式推薦** |
| **系統交易與留存信件** | **Resend** | 歡迎信、額度不足／試用將到期提醒、付款失敗挽留（SPF/DKIM/DMARC） | \$0（每月 3,000 封免費） | \$0 起 | **全模式推薦** |
| **外掛官方分發管道** | **Chrome Web Store Developer Console** | 合法分發外掛、Day 1 取得永久 32 碼 Extension ID、先 Unlisted 封測再 Public 上架 | **\$5 一次性** | \$0 | **全模式必備（Day 1 先辦！）** |

> **起步決策速記**：
> - **Pattern 1（純本地工具）**：幾乎 **US\$0/月**（僅網域年費＋CWS \$5 一次性）就能先上線收款；有穩定月營收後再視需求升 Supabase Pro / Workers Paid。
> - **Pattern 2–4（完整 SaaS）**：Staging 驗證期 **US\$0–\$5/月**；正式上線固定底薪約 **US\$30–\$31/月**，其餘全為隨營收成長的變動成本。

---

## 二、每個服務的推薦原因、取捨與替代方案

### 1. Cloudflare 全家桶（DNS / Email Routing / Pages / Workers / Turnstile / R2）
- **為什麼選它**：
  - **免出站流量費（\$0 Egress）**：傳統雲（AWS / GCP）出站流量帳單常成為中小 SaaS 隱形殺手；Cloudflare Workers 與 R2 零出站費，對外掛高頻呼叫極度友善。
  - **免費自訂網域客服信箱（Email Routing）**：金流與商店審核非常在意是否具備網域官方信箱（如 `support@yourdomain.com`），免花 Google Workspace 月費就能 5 分鐘設好轉寄。
  - **低延遲無冷啟動**：Hono + TypeScript 跑在邊緣節點，全球用戶開啟外掛都秒回。
  - **單一自動化部署憑證**：GitHub Actions 一組 Token 就能同時管網站與 API 部署。
- **替代方案**：Vercel（靜態頁與 Serverless 體驗佳，但免費層商業使用限制較嚴且出站流量較貴）、Fly.io / Railway（適合需要長連線或 Python/重型容器的後端）。

### 2. Supabase（PostgreSQL + Auth）
- **為什麼選它**：
  - **交易一致性的硬剛需**：凡涉及「付費方案狀態、點數餘額、退款回沖、配額扣抵」，絕不能用弱一致性資料庫。PostgreSQL 的 `SECURITY DEFINER` 原子預存函數（RPC）能把「檢餘額→扣點→記明細→冪等防重」鎖在同一個 ACID 交易內。
  - **省下兩週 Auth 開發與資安風險**：內建 Google OAuth、Email 驗證、密碼重設與 Turnstile 整合。
  - **Staging／Production 完美隔離**：Staging 用 Free 專案（注意閒置可能休眠，僅供測試）；Production 切獨立 Pro 專案（\$25/月），取得不休眠、每日備份與時間點還原（PITR）。
- **替代方案**：Neon + Clerk（分拆組合，彈性高但整合與帳單分散）、Firebase（NoSQL 對複雜帳本對帳較吃力）。

### 3. Upstash Redis（Serverless HTTP Redis）
- **為什麼選它**：
  - Cloudflare Workers 是無狀態邊緣環境，不適合開傳統長駐 TCP Redis 連線池；Upstash 提供原生 **HTTP REST API**，毫秒級存取且免費層就夠跑完整 Staging 與初期 Production。
  - 解決五大高頻需求：**滑動視窗限流、即時停權／方案覆寫快取（彌補 JWT 15 分鐘延遲）、單次 PKCE 授權碼、併發連線鎖（ZSET）與每日上游 API 成本熔斷器**。
- **何時可省略**：Pattern 1 純本地買斷外掛、無上游變動成本且無高頻 API 時可先省略，待轉訂閱／計量型再加。

### 4. Paddle Billing v2（Merchant of Record, MoR）
- **為什麼選它**：
  - **幫獨立創辦人扛掉全球稅務**：只要客戶來自歐盟、英國、日本、美國各州，自行申報跨境數位稅務成本高到不切實際。Paddle 身為名義賣家（MoR）全自動代收申報全球 VAT/GST 並開合規發票。
  - **對台灣與非 Stripe 國家創辦人極度友善**：支援個人或公司主體，完成線上身分驗證（KYC）即可直收全球信用卡／PayPal 並匯回本地銀行。
  - **內建完整商業閉環**：Overlay 結帳視窗、訂閱升降階、客戶自助管理入口（換卡、取消、下載發票）與完整 Webhook 事件。
- **替代方案**：
  - **Stripe Billing + Stripe Tax**：若你已有美國／新加坡／日本等 Stripe 支援主體、客單價極高且有會計師支援，可選 Stripe。
  - **Lemon Squeezy / Polar**：同為 MoR 路線，可依當下地區支援度與手續費比較選用。

### 5. 前端架構：Astro SSG ＋ React Islands（單倉雙網域）
- **為什麼選它**：
  - **行銷頁極速 SEO**：Astro 編譯純靜態 HTML，Core Web Vitals 輕鬆 95–100，**完全不把肥大的 Auth SDK 或結帳腳本打包進首頁、定價頁與 SEO 著陸頁**。
  - **會員控制台高度互動**：只在 `/dashboard`、`/ext-auth`、`/welcome` 掛載 React 互動島（Islands），共用設計 Token 與雙語字典。
  - **單專案雙網域部署**：同一份 Cloudflare Pages 專案掛載 `yourdomain.com`（SEO 行銷與法務）與 `app.yourdomain.com`（會員控制台與結帳，強制 `noindex, nofollow`）。
- **替代方案**：Next.js / Nuxt（團隊若已非常熟悉亦可採用，但仍須嚴格落實行銷頁輕量化與 App 路由 `noindex` 隔離）。

### 6. 雙上游供應商主力＋備援（適用 Pattern 3 / 4）
- **為什麼選雙供應商**：
  - **成本與穩定兼得**：主力挑速度快、單價低的供應商把毛利率推高；備援挑高可用大廠，當主力回傳 429/503 或逾時即自動切換。
  - **防範廠商突發淘汰**：第三方 AI / API 廠商常在短時間內調整定價或下架舊端點，抽象一層 Provider Interface 讓你 10 分鐘就能切換供應商而不影響前端外掛。

### 7. PostHog（Server-side）＋ Resend
- **PostHog（後端匿名漏斗）**：在 API 後端直接上報關鍵商業轉換事件（註冊、首次成功體驗、額度提醒、觸發付費牆、首次付費、刪帳），搭配不可逆雜湊 `distinct_id`（`anon_<32hex>`）並於後台開啟 `Discard client IP data` 與停用 GeoIP——拿得到完整商業漏斗，又完全不碰惱人的前端追蹤 Cookie 與個資法規風險。
- **Resend（交易與生命週期信件）**：免費層 3,000 封/月、REST API 極簡、搭配 Cloudflare DNS 驗證 SPF/DKIM/DMARC，讓歡迎信、額度不足提醒與付款失敗挽留信穩定進收件匣。

### 8. GitHub Actions（雙環境隔離 CI/CD）
- 建立獨立的 **`staging`** 與 **`production`** GitHub Environments，分別管理測試與正式密鑰。
- 每次 PR 自動執行品質門禁（型別、測試、外掛零密鑰掃描、資料庫雙授權重播、嚴格法務 Web 建置），確保沒有任何壞程式或測試金鑰能溜進正式環境。
