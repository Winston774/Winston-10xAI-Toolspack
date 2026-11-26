# 25 個 Chrome Extension SaaS 通用踩坑實錄與防雷清單

> **給 Agent 的強制指令**：這 25 個坑全部來自真實商業化上線過程的血淚教訓，涵蓋資安、雲端執行環境、金流計費、MV3 外掛架構與前端多語體驗——**適用於任何類型的 Chrome 外掛 SaaS**。
>
> 請在架構設計與 Gate-2 獨立審查階段，逐類掃描對照，防止學員專案重複踩雷。

---

## 一、資料庫、資安與營收防漏（Trap #01–#08）

### Trap #01：Supabase `profiles` RLS 沒鎖欄位，用戶用公開 `anon` Key 就能免費把自己改成付費方案！
- **症狀**：設定了「允許使用者更新自己的 `profiles` 列（`auth.uid() = id`）」，誤以為安全。
- **根因**：RLS 只管「列（Row）」，不管「欄（Column）」。任何人用前端公開的 `anon` key＋自己的 JWT 直打 PostgREST，就能送 `PATCH` 把自己的 `plan` 改成付費版或解除 `is_suspended`。
- **解法**：收回整表 `UPDATE` 權限，只對安全欄位授權（如 `GRANT UPDATE (display_name, preferences) ON profiles TO authenticated;`），並加 `BEFORE UPDATE` 保護觸發器禁止非 `service_role` 改動方案、餘額或停權欄。
- **防復發**：CI SQL 測試以 `authenticated` 角色實測竄改 `plan` 與 `is_suspended`，斷言一定失敗。

### Trap #02：Supabase 全新專案不再自動授權 `public` 資料表給 Data API
- **症狀**：本機或舊專案跑得動的 SQL Migrations，部署到全新 Supabase 專案後，後端連主表都讀不到而報錯。
- **解法**：撰寫獨立的顯式授權 Migration，逐表與 sequence 明確宣告 `service_role` 與 `authenticated` 權限。
- **防復發**：CI 在 PostgreSQL 17 上同時跑 **`explicit`（全新嚴格授權）** 與 **`legacy`（舊版預設授權）** 雙矩陣重播測試。

### Trap #03：計量／扣點冪等鍵（`idempotencyKey`）未綁定用戶與內容雜湊，且晚於上游呼叫才檢查 → 無限白嫖
- **症狀**：攻擊者重送同一個 `idempotencyKey` 搭配不同請求內容，能零扣點無限白嫖付費上游 API。
- **解法**：冪等鍵必須綁定 `(user_id, action, payload_hash)`，於呼叫上游 API **前**預檢；同鍵但 payload hash 不同直接回 409，完全相同才回傳已扣點的快取結果。

### Trap #04：後端用 `service_role` 直接 `upsert` 前端傳來的 UUID → 跨租戶資料劫持（IDOR）
- **症狀**：`PUT /v1/items/:id` 接受客戶端 UUID 並以 `service_role` 直接 `upsert`，攻擊者只要命中他人 ID 就能把別人的雲端資料覆寫並搶到自己名下。
- **解法**：所有 `service_role` 寫入必須顯式限定 `user_id = eq.<authenticatedUserId>`，或經由驗證擁有者的 PostgreSQL RPC 執行。

### Trap #05：免綁卡免費試用遭拋棄式信箱批次刷爆上游帳單
- **症狀**：開放免綁卡免費試用額度後，極易遭自動化腳本用臨時信箱（如 `mailinator.com`）批次註冊，一夜刷光你的上游 API 帳單。
- **解法（四層防禦）**：
  1. **Email 驗證通過後**才原子核發一次性試用額度（未驗證帳號餘額永遠為 0）；
  2. 登入、註冊與外掛綁定全程加 **Cloudflare Turnstile**；
  3. 後端維護**拋棄式信箱網域黑名單**＋IP 頻率限制；
  4. 於 Redis 建立**每日上游花費熔斷器（Spend Circuit Breaker）**，並於上游廠商後台設好月預算硬上限（Hard Cap）。

### Trap #06：15 分鐘無狀態 JWT 的「升階延遲與拒付盜刷空窗」
- **症狀**：用戶剛付費升級，卻還要等 15 分鐘 JWT 過期才解鎖新權限；或是遭 Chargeback 拒付停權的帳號，還能拿舊 JWT 繼續白用 15 分鐘。
- **解法**：在 Upstash Redis 維護極輕量的 `user_state:<userId>`（存最新 `effectivePlan`、`isSuspended`、`revokedAt`），JWT 驗簽後先查 Redis 即時覆寫；若 Redis 異常則 **Fail-Closed 回查資料庫**。

### Trap #07：客戶端預設設定指向「付費專屬功能」，上線首日 100% 免費用戶直接報錯
- **症狀**：開發者在測試期習慣把預設選項開在最高級付費模式，上線忘了改回免費可用模式，導致所有新用戶一點就吃 `403 TIER_LOCKED`。
- **解法**：外掛、控制台、資料庫三端預設值一律為 Free 可用設定；若用戶降階，前端自動安全降級至可用模式並顯示升級引導。

### Trap #08：外掛套件殘留 API Key、本機路徑或違規測試碼 → 商店退件或直接封號
- **症狀**：從原型演化來的外掛目錄常遺留上游 API Key、本機硬碟路徑（`C:/`、`D:/`）、舊專案名或針對敏感站點的測試程式碼。
- **解法**：寫一支靜態檢查腳本（如 `check-extension --strict`）納入每次 PR CI，強制掃描並阻斷任何上游金鑰、未授權網域、本機路徑與商店違規關鍵字。

---

## 二、Cloudflare Workers 與雲端環境地雷（Trap #09–#13）

### Trap #09：Cloudflare Workers `workerd` 拒吃 `fetch(..., { redirect: 'error' })`！
- **症狀**：本機 Node.js 測試全過，部署上 Cloudflare Workers 後，**金流結帳回 503、遙測事件全漏、信件寄不出去**！
- **根因**：Node.js 支援 `redirect: 'error'`，但 Cloudflare Workers 的 `workerd` 執行時期會直接對它拋 `TypeError`，請求根本沒送出。
- **解法**：Workers 內所有對外 `fetch` 一律使用 **`redirect: 'manual'`**，收到 `3xx` 狀態碼時於程式內直接拒絕跟隨（兼顧不洩漏 Authorization 標頭的資安要求）。
- **防復發**：測試套件明確斷言 API 程式碼中禁止出現 `redirect: 'error'`，並在 CI 執行本機 Workers 煙霧測試。

### Trap #10：在 Workers 背景任務內「巢狀呼叫 `ctx.waitUntil()`」
- **症狀**：背景寄信、紀錄或遙測偶發遺失或報錯。
- **解法**：所有背景工作一律只回傳標準 `Promise`，統一只在 HTTP Route Handler 最外層呼叫一次 `ctx.waitUntil(Promise.allSettled([...]))`，嚴禁巢狀 `waitUntil`。

### Trap #11：Cloudflare Scrape Shield 自動遮蔽客服信箱，害金流審核看不到你的信箱！
- **症狀**：本機法務頁明明印了 `support@yourdomain.com`，一上 Cloudflare Pages，線上 HTML 就被改寫成 `/cdn-cgi/l/email-protection`，金流審核員或自動化檢查可能因此退件。
- **解法**：在 Footer 與法務頁用 Cloudflare 官方排除標記 `<!--email_off-->...<!--/email_off-->` 包住信箱；若使用 **Astro**（預設會剝除一般 HTML 註解），必須用 **`<Fragment set:html={'<!--email_off-->'} />`** 與 **`<Fragment set:html={'<!--/email_off-->'} />`** 才能保留在編譯結果中，並以自動化測試把關。

### Trap #12：第三方上游 API 無預警淘汰端點或權限不符
- **症狀**：帳號與金鑰都開通、`GET /accounts` 也回 200，結果實際送出真實業務請求才發現該模型／端點已被廠商公告淘汰或權限不足。
- **解法**：任何外部服務接入前，一律用**最小合成真實 payload** 跑端對端探測；為關鍵上游設計 Provider 抽象與備援切換；並確保 `/privacy` 只列「已驗證實際上線」的供應商，絕不寫未獲書面確認的零留存（ZDR）宣稱。

### Trap #13：Staging 環境變數誤混入 Production 建置
- **症狀**：在 Production 建置環境不小心殘留 Staging 專用覆寫變數（如測試網域或測試外掛 ID），導致正式官網按鈕全部指向測試站。
- **解法**：`staging` 與 `production` 使用獨立 GitHub Environment，Production 部署流程嚴格檢核不得存在任何 Staging 變數，並於部署後以唯讀腳本掃描所有正式 HTML 斷言零測試網址與零測試 ID。

---

## 三、金流（Paddle / MoR）與計費狀態機地雷（Trap #14–#20）

### Trap #14：Webhook 亂序 — `subscription.created` 比 `transaction.completed` 早到，付費用戶月配額竟為 0！
- **症狀**：用戶剛刷卡訂閱成功，控制台方案已變成付費版，但該月可用配額卻顯示 `0`、無重設日，後續扣點全被轉扣到永不過期的加購包！
- **根因**：金流 Webhook **不保證到達順序**。訂閱建立事件常比交易完成事件早幾百毫秒抵達並先寫入週期時間，若後端的過期防護寫太死，就會把晚到的同週期 `transaction.completed` 誤判為過期事件而跳過入帳。
- **解法**：
  1. 後端同週期付款判定須容許合理時間差（如 ±10 分鐘）並核對帳本是否已對該週期發放過月配額，保留較新訂閱中繼資料的同時完整核發額度。
  2. 前端結帳後的輪詢不可只看到「方案名稱變了」就停，必須確認**新配額已入帳或重設日已更新**才宣告完成。

### Trap #15：先寫 `webhook_events` 去重表再跑帳本邏輯 → 暫時性錯誤造成付費永久漏單
- **症狀**：先 `INSERT` 事件 ID 才更新帳本，若更新中途遇網路抖動回 500，金流重試時查到事件 ID 已存在就直接回 `200 duplicate`，付費客戶從此拿不到商品。
- **解法**：事件表必須採**狀態機**（`processing` → 成功改 `processed`／失敗改 `failed` 並回 500 觸發重試），僅將 `processed` 視為完成，搭配搶佔鎖防併發重入。

### Trap #16：把「退款」與「取消訂閱」混淆，或忽略兩階段退款
- **症狀**：金流退款常見兩階段（先 `pending_approval` 再 `approved`）。若在待審階段就扣點，退款被拒會誤損用戶權益；若沒比對原購買商品，退一次性加購包時可能錯扣月配額。
- **解法**：僅在 `status === 'approved'` 時依原交易精準回沖對應桶別，並用「調整單＋桶別」穩定冪等鍵避免重複扣回；取消訂閱走獨立事件（停續約但不做退款回沖）；確認 Chargeback 拒付時立即停權並撤銷全部裝置 Refresh Token（且 `/refund` 條款文案須與程式碼一致）。

### Trap #17：忘記支援直接付款連結（`?_ptxn=...`）與審核前／後循環死鎖
- **症狀**：金流提供的發票或直接付款連結（如 Paddle Default Payment Link）會帶 `?_ptxn=txn_...` 回到 `/dashboard` 並要求頁面一載入就自動彈出結帳；若頁面只在按購買鍵時才載入結帳 SDK，這條路會斷掉。此外，還沒通過金流審核時你拿不到 Live Token，若正式建置強依賴 Live Token 就會陷入死鎖。
- **解法**：`/dashboard` 載入時主動偵測合法 `_ptxn` 並自動初始化結帳 SDK（強制 `allowLogout: false` 防串帳）；同時將正式部署拆成 **Pre-Approval（安全停用結帳按鈕、先讓官網＋法務上線送審）** 與 **Go-Live（寫入 Live Token 啟用真實結帳）** 兩階段。

### Trap #18：Sandbox 刷真實信用卡必拒付，且 API 探測須對齊最小權限
- **症狀**：測試環境輸入自己真實信用卡被銀行拒付；或健康檢查腳本去打 API Key 沒開權限的端點而誤報紅燈。
- **解法**：Sandbox 一律使用金流官方測試卡（例如 Paddle 測試 Visa `4242 4242 4242 4242`）；API Key 嚴守最小權限原則，自動化探測僅打該 Key 實際授權的端點。

### Trap #19：小額商品被固定手續費吃光毛利
- **症狀**：MoR 常見費率 `5% + \$0.50`。賣 \$5 商品，單筆手續費就高達 \$0.75（**佔比 15%**！）；賣 \$69 年繳方案，手續費佔比驟降至 **5.7%**。
- **解法**：定價頁預設選中**年繳方案**，一次性加購包設定合理最低面額並將較高面額標為「最划算推薦」。

### Trap #20：金流與商店審核常見退件雷區
- **五大必踩退件原因**：(1) 法務頁留有 Placeholder 或缺真實賣家／英文地址；(2) 印出沒設定轉寄的無效信箱別名；(3) `/privacy` 隱瞞實際使用的第三方 API 或亂寫未驗證的零留存承諾；(4) 產品文案或程式碼觸碰平台紅線（破解 DRM、繞過付費牆、未授權抓取私人受保護資料）；(5) 退款與拒付條款跟系統實際行為不一致。
- **解法**：上線前用自動化自檢腳本（參考 `templates/pre-approval-checklist.md`）全項跑綠再按送審。

---

## 四、Chrome Extension MV3 與 Web 雙向連線地雷（Trap #21–#23）

### Trap #21：MV3 多執行環境各自刷新 Token → 觸發重放偵測強制登出用戶
- **症狀**：Service Worker 與 Popup／Offscreen／Content Script 同時發現 Access Token 過期，各自拿同一把 Refresh Token 去換新 Token，後端偵測到 Token 重用直接把整個帳號撤銷登出。
- **解法**：**所有認證狀態、Token 儲存與 API 呼叫一律集中在 MV3 Service Worker**，並實作**單飛刷新互斥鎖（Single-flight Refresh Mutex）**確保併發 401 只觸發一次 Refresh；若使用 Offscreen Document，工作結束立即呼叫 `chrome.offscreen.closeDocument()` 釋放資源。

### Trap #22：開發期未封裝外掛每次載入 ID 都會變，導致 CORS 與網頁橋接永遠壞掉
- **症狀**：在 `chrome://extensions` 載入 unpacked 資料夾，換路徑或換電腦 Extension ID 就變了，後端白名單與 `externally_connectable` 全數失靈。
- **解法**：用一組 Staging 專用固定公鑰（SPKI `key`）由腳本寫入 Staging 產出物的 `manifest.json`，永遠鎖定同一個 Staging Extension ID，並於腳本內斷言產出物零正式站網域。

### Trap #23：網頁與外掛完全割裂 — 用戶已登入卻還看到「免費試用」，也不知道外掛有沒有連上
- **症狀**：登入完網頁回到官網右上角仍顯示未登入 CTA；進控制台也不知道目前瀏覽器裡的 Chrome 外掛是否連到同一個帳號。
- **解法**：
  1. 外掛 `manifest.json` 的 `externally_connectable.matches` 放行 `app.yourdomain.com/*` 與 `yourdomain.com/*`；
  2. 外掛實作 `EXT_PING`（嚴格回傳 `{ ok: true, installed: true, version, signedIn, matchesUser }`）與 `EXT_START_AUTH`（僅限 `app.yourdomain.com`，啟動全新 PKCE）；
  3. 網頁全站導覽列顯示帳號狀態（行銷頁不載入肥大 Auth SDK，改以不帶個資的布林提示 Cookie ＋ ping 外掛判斷，且於視窗 `focus`／`visibilitychange` 即時重驗，並用序號防範切換帳號時的慢回覆覆蓋）；
  4. 控制台頂部顯示「帳號與外掛連線狀態列」，未連線時提供 **「一鍵連線外掛」** 按鈕直接走完 PKCE 綁定。

---

## 五、全站多語系（i18n）、錢包 UX 與隱私遙測地雷（Trap #24–#25）

### Trap #24：多語系只做半套、切語言掉參數、或把 OAuth 弄壞
- **六個必防細節**：
  1. **別漏掉控制台與登入頁**：`/dashboard`、`/ext-auth`、`/welcome` 都要跟官網一樣完整多語系，並以 TypeScript `Record<Locale, Strings>` 在編譯期鎖死所有鍵值。
  2. **別用瀏覽器語言覆蓋顯式語系網址**：用戶點擊繁中連結打開 `/zh-hant/dashboard` 時，即使瀏覽器是 `en-US` 且未存偏好，也絕不可強行把人家跳回英文！只有在「預設無前綴網址」且「無已存偏好」時才自動偵測 `navigator.languages`。
  3. **保留 `?query#hash`**：在帶參數頁面（如結帳預選、PKCE 綁定）切換語系務必保留參數；未翻譯頁面 fallback 回首頁時則不可亂帶原參數。
  4. **不破壞 OAuth 回呼白名單與錯誤顯示**：OAuth `redirectTo` 永遠維持無語系前綴的規範路徑，發起 OAuth 前記住當前語系偏好，等 Auth 回呼完成且「沒有要顯示的錯誤訊息」才導回偏好語系。
  5. **精確限制跨子網域 Cookie 主機**：`Domain=.yourdomain.com` 只限精確的正式主機清單（`yourdomain.com`、`www.yourdomain.com`、`app.yourdomain.com`），絕不用寬鬆萬用子域，避免測試子域污染正式站。
  6. **錯誤碼全在地化＋編碼細節**：將後端與 Auth 錯誤碼全部對應到當前語系，避免繁中頁跳出英文原文；另外注意 Astro 會把屬性中的 `"` 編成 `&#34;`，寫 HTML 靜態測試時記得解碼。

### Trap #25：額度計數語意混亂，以及第三方遙測精靈自動開 PR 偷塞隱私地雷
- **額度計數鐵律**：
  - 網頁控制台與外掛 Popup 全面統一以 **「剩餘（Remaining）」** 呈現，絕不混用「剩餘」與「已使用」，也不要用無標尺的實心色條誤導用戶。
  - 免費試用額度若與加購包共用欄位，不要顯示 `Monthly quota: 0` 造成恐慌，也不要在明細把免費試用標成「加購」；有月配額時清楚標示消耗順序（優先扣月配額、再用加購）與每筆明細的扣抵來源。
- **拒絕自動追蹤精靈 PR**：
  - 許多第三方分析工具的安裝精靈會自動開 PR 在前端塞入全功能追蹤 SDK（預設啟用 Cookie、IP 蒐集、錄影），瞬間打破無追蹤 Cookie 的隱私承諾。**直接關閉不合併**，改由後端發送匿名事件（`anon_<32hex>`）並於後台開啟 `Discard client IP data`＋暫停 GeoIP。
