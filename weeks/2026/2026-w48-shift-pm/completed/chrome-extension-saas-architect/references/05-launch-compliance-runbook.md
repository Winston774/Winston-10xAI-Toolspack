# 上線合規、雙平台送審與 Staging → Production 切網 SOP

> 這份手冊將 **Staging 全鏈路演練 → 金流快速一次過審 → Chrome Web Store 先 Unlisted 再 Public → Zero-Leak 正式切網** 標準化，適用於任何類型要上線收費的 Chrome 外掛 SaaS。

---

## 一、Staging 雲端全鏈路驗證（未全綠，絕不切正式）

在動任何正式環境前，先部署一套**完全獨立的 Staging 環境**（Staging 網站 ＋ Staging API ＋ Staging 資料庫 ＋ Staging Redis ＋ 金流 Sandbox ＋ 固定 ID 的未封裝 Staging 外掛），逐項驗收 6 條鏈路：

1. **Smoke 與 CORS 嚴格隔離**：
   - API `/health` 回 200，具安全標頭（`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`、`Cache-Control: no-store`）。
   - CORS 僅放行 Staging 網域與 Staging Extension ID，明確拒絕正式網域、陌生網域與未註冊外掛。
   - 無效金流 Webhook 簽章與錯誤管理員 Token 均回 HTTP 403。
2. **註冊驗證、防濫刷與歡迎信**：
   - 未驗證 Email 帳號不核發免費試用額度；點擊驗證信後冪等核發一次（重送不重複加發）。
   - 拋棄式信箱網域與無效 Turnstile 皆遭 HTTP 403 攔截。
   - 用全新真實信箱註冊，確認收到 Resend 歡迎信（自動化測試使用的 `@example.com` 網域則由 RFC 2606 規則抑制寄出，保護網域寄信信譽）。
3. **外掛實機操作與雙向連線**：
   - 載入本機建置的 Staging 未封裝外掛，完成 Popup 登入 → `/ext-auth` PKCE 綁定 → 回控制台看到「Chrome 外掛已連線」綠燈，並測試「一鍵連線外掛」與核心功能扣點／權限解鎖。
4. **金流 Sandbox 6 大情境＋測試卡實刷**：
   - 於瀏覽器使用官方測試卡（如 Paddle Sandbox `4242 4242 4242 4242`）跑通：
     1. 訂閱購買（月繳／年繳）→ 確認權限與配額正確入帳（特別驗證 `subscription.created` 早於 `transaction.completed` 不掉單）；
     2. 一次性加購包／單次商品購買（若適用）→ 確認正確入帳；
     3. 同時擁有月配額與加購包時使用功能 → 確認明細清楚顯示**優先扣抵月配額**，用盡才扣加購包；
     4. 方案升階 → 確認差額與新權限免重登即時生效；
     5. 取消訂閱 → 停止續約但保留既有永不過期餘額；
     6. 兩階段退款（`pending_approval` 不動帳本 → `approved` 單次精準回沖）與 Chargeback 拒付即時停權並撤銷全裝置 Token。
5. **隱私遙測複驗**：
   - 至分析後台實查收錄事件，確認 `distinct_id` 皆為去識別化格式（如 `anon_<32hex>`），零 `$ip` 與零 `$geoip_*` 欄位。
6. **GDPR 自助刪帳**：
   - 尚有有效訂閱時阻擋刪帳（HTTP 409，引導先至客戶入口取消訂閱）；
   - 無有效訂閱時成功硬刪（清除資料表、撤銷 Token、刪除 Auth 用戶且原 JWT 立刻失效）。

---

## 二、金流（Paddle / MoR）快速一次過審 8 大硬門檻

金流審核的核心標準非常單純：**你是真實合法賣家、產品與定價透明一致、法務頁與實際行為吻合、零違規業務**。照以下清單準備，可大幅壓縮審核時間（實戰最快 41 分鐘通過雙網域審核）：

1. **真實營運主體（零 Placeholder）**：
   - `/terms`、`/privacy`、`/refund` 與 Footer 完整揭露真實個人或公司中英文名稱、**英文羅馬拼音通訊地址**與準據法。
   - 在建置腳本加入 `STRICT_LEGAL=true` 強制門禁：只要還有任何 `TODO` / `TBD` / 占位符就直接讓正式建置失敗。
2. **真實可收信的網域客服信箱＋`<!--email_off-->`**：
   - 實測寄信給 `support@yourdomain.com` 確認成功轉寄到你信箱；絕不印出未設定轉寄的失效別名。
   - 若掛在 Cloudflare 下，務必以 `<!--email_off-->...<!--/email_off-->` 包覆信箱（Astro 用 `<Fragment set:html={'<!--email_off-->'} />`），防止 Cloudflare Scrape Shield 把信箱變成亂碼。
3. **公開定價頁與金流目錄分毫不差**：
   - `/pricing` 清楚列出所有方案、幣別（USD）、週期、內含權益／額度，以及**自動續約與隨時可取消**聲明，每一分錢都與金流後台完全一致。
4. **合規退款政策（`/refund`）**：
   - 依所選 MoR 規定載明退款申請窗口（如 Paddle 14 天申請窗口，依 Buyer Terms 個案審核、不影響法定消費者權益）、連結官方買家條款、說明核准退款會收回對應權益，並明確區分「取消續約」與「申請退款」。
   - Chargeback 停權與恢復說明須與後端程式邏輯完全一致。
5. **誠實且與程式碼同步的隱私權政策（`/privacy`）**：
   - 逐項列出實際使用中的第三方子處理商、處理哪些資料、是否留存及留存多久、如何撤銷同意或刪除帳號。
   - 絕不列出已停用的供應商，也絕不亂寫未獲書面核准的「零資料留存（ZDR）」宣稱。
6. **零高風險違規宣稱**：
   - 全站與外掛絕不宣稱破解 DRM、繞過付費牆、未授權抓取受保護私人資料或侵權下載；若涉及跨方通訊／錄製／協作情境，應加上合規告知提醒。
7. **Pre-Approval 雙網域送審不卡關**：
   - 先部署 Pre-Approval 正式版（`https://yourdomain.com` ＋ `https://app.yourdomain.com`，Live 結帳按鈕安全停用等待審核通過）。
   - 用唯讀自動化腳本檢查所有公開頁與法務頁全為 HTTP 200、含明文客服信箱與法定主體、零 Staging 洩漏後，立刻送出金流網域審核＋線上 KYC＋收款銀行設定。
8. **過審後（Post-Approval）收尾**：
   - 建立正式 Live 商品價格、設定正式 Default Payment Link 指向 `https://app.yourdomain.com/dashboard`、設定正式 Webhook 端點、將 `live_` Client Token 與 Live Secrets 寫入 Production 環境。

---

## 三、Chrome Web Store（CWS）MV3 送審與「先 Unlisted 再 Public」策略

### 為什麼強烈建議先送 Unlisted？
- 權限較多的 MV3 外掛首次審核常需 **3–7 個工作天**。
- 先選 **Unlisted（不公開，憑連結安裝）** 送審：
  1. 過審後立刻獲得正式商店安裝連結，邀請 30–50 位種子封測用戶實戰測試；
  2. 封測期發現任何相容性或體驗問題都能快速靜默更新，**不會在公開第一天就吃低星負評**；
  3. 收集完首批真實推薦語與五星評價後，一鍵切換為 **Public** 正式上市，免再苦等首次長審。

### CWS 一次過審備料清單
- **CI 自動打包乾淨 `.zip`**：自動排除 `.git`、`tests/`、`node_modules`、`*.test.*` 與開發檔，通過靜態零密鑰掃描並產出 SHA-256。
- **Single Purpose（單一用途聲明）**：1–2 句精準聚焦核心用途，絕不寫成大雜燴工具箱。
- **權限最小化與逐條正當性說明**：砍掉所有非必要權限，剩餘每一項 `permission` 與 `host_permissions` 都明確對應到使用者可見的具體功能。
- **Data Usage 揭露**：與 `/privacy` 100% 同步，明確勾選收集類別與用途，承諾絕不販售個資。
- **高轉化商店素材**：5 張 `1280 × 800` 清晰截圖（第 1 張直擊 Before/After 痛點解決）、小宣傳圖 `440 × 280`，以及 1 段 30–60 秒無剪接操作示範影片供審核員快速驗收。

---

## 四、Staging → Production 正式切網檢核（Zero-Leak Cutover）

取得創辦人正式 Go-Live 核准後依序執行：
1. **全新獨立正式基礎設施**：建立與 Staging 完全分離的 Production 資料庫（套用全數 Migrations、開啟每日備份與 PITR）、獨立 Redis、獨立儲存桶（若適用）與全新獨立 32-byte 隨機內部密鑰。
2. **隔離紅線驗證**：
   - 確認 Production 環境變數內**完全沒有**任何 Staging 專用變數；
   - Production API 鎖定 `DEV_MODE=false`、正式金流模式與正式 32 碼 Extension ID；
   - 上游付費 API 廠商後台設定月費消費硬上限（Hard Spend Cap）。
3. **執行自動化正式驗收腳本（`--mode go-live`）**：驗證全部公開頁、法務頁、API `/health`、CORS 白名單、Webhook 驗簽與管理端點全數 PASS。
4. **真實卡片 1 筆閉環自測＋退款**：創辦人以真實卡片購買 1 筆最低額方案，驗證入帳、外掛解鎖、發票與退款回沖全部正常。
5. **上市後 72 小時值班監控**：開啟 `/health` 每分鐘 Uptime 監控、盯緊漏斗轉換、每日上游成本與錯誤日誌，並備妥一鍵回滾指令。
