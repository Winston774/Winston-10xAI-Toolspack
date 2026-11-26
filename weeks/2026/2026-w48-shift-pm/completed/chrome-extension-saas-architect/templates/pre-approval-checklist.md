# 上線送審前總自檢表（金流審核 ＋ Chrome Web Store ＋ 資安與體驗）

> 在送出 **金流正式審核（如 Paddle Live）**、**Chrome Web Store 送審** 或執行 **Production Go-Live** 前，由 Agent 逐項核對並附上實測證據。

---

## A. 法務與金流（MoR / Payment）過審自檢

- [ ] `STRICT_LEGAL=true` 正式建置通過，全站零 `TODO`、`TBD` 或占位符文字。
- [ ] 首頁、`/pricing`、`/terms`、`/privacy`、`/refund`、`/help`（及多語版）全數回傳 HTTP 200。
- [ ] Footer 與法務頁清楚顯示**真實營運主體姓名／公司名**、**英文羅馬拼音地址**與**已實測可收信的網域客服信箱**（無未設定轉寄的失效別名）。
- [ ] 檢視線上實際 HTML 確認客服信箱未被 Cloudflare Scrape Shield 遮蔽（已加 `<!--email_off-->`）。
- [ ] `/pricing` 價格、幣別、週期、自動續約與隨時取消聲明，與金流後台目錄 100% 一致。
- [ ] `/refund` 寫明符合 MoR 規定的退款申請窗口與規則，且 Chargeback 停權／恢復流程與後端程式碼完全一致。
- [ ] `/privacy` 誠實揭露所有實際使用中的第三方子處理商與資料流（無已淘汰供應商、無未獲書面核准之 ZDR 宣稱）。
- [ ] 全站與外掛零高風險違規宣稱（無破解 DRM、繞過付費牆或未授權存取私人資料）。
- [ ] 正式官網與會員網域零任何 Staging 網域或 Staging Extension ID 洩漏。

---

## B. 資安、邊緣後端與金流狀態機自檢

- [ ] `profiles` RLS 已收斂欄位權限（實測前端角色無法修改 `plan` 或 `is_suspended`）。
- [ ] 資料庫 migrations 於全新嚴格授權（`explicit`）與舊版授權（`legacy`）兩組 PostgreSQL 環境皆重播通過。
- [ ] 免費試用／體驗額度須通過 Email 驗證＋Turnstile＋拋棄式信箱黑名單才核發；若呼叫付費上游 API，已啟用每日成本熔斷器與供應商硬上限。
- [ ] Cloudflare Workers 程式碼中**零 `redirect: 'error'`**（全為 `redirect: 'manual'`）、無巢狀 `ctx.waitUntil()`、所有外部請求具 `AbortSignal.timeout()`。
- [ ] Webhook 驗簽使用 Raw Body、採狀態機防重試漏單、通過「訂閱建立早於交易完成」亂序測試、退款僅在 `approved` 精準回沖；若採雙桶額度，有回歸測試證明月配額優先於加購包扣抵。
- [ ] 會員控制台支援直接付款連結（如 `?_ptxn=`）載入時自動初始化結帳。

---

## C. Chrome Extension MV3、多語系與 UX 自檢

- [ ] 靜態掃描通過：零上游金鑰、零系統核心 Prompt 外洩、零本機硬碟路徑、零違規測試網域。
- [ ] 所有認證與 API 呼叫集中於 Service Worker 並具單飛 Refresh 互斥鎖；Offscreen 用完即關。
- [ ] 免費用戶預設選項不會觸發 `403 TIER_LOCKED`。
- [ ] 全站（含控制台、登入／外掛綁定頁、歡迎頁）支援所有目標語系並記住使用者語系偏好；不覆寫顯式語系網址、不破壞 OAuth 回呼與錯誤訊息；API／Auth 錯誤碼全在地化。
- [ ] 若為計量型產品，控制台與外掛 Popup 全面統一顯示「剩餘」額度，帳本清楚呈現扣抵來源。
- [ ] 全站導覽列清楚顯示登入狀態；控制台頂部即時顯示外掛連線狀態並支援一鍵連線。
- [ ] CWS `.zip` 排除開發／測試檔並具 SHA-256；備妥單一用途聲明、逐項權限正當性、Data Usage 揭露、5 張 `1280×800` 截圖與示範影片（先送 **Unlisted**）。

---

## D. 隱私遙測與系統信件自檢

- [ ] 漏斗分析僅由後端發送去識別化匿名事件（如 `anon_<32hex>`）；分析後台開啟 `Discard client IP data` 且停用 GeoIP；實查事件零 `$ip` / `$geoip_*`。
- [ ] 寄信網域 SPF / DKIM / DMARC 全數生效；真實新帳號實測收到歡迎信；測試網域自動抑制寄出。
