# 權限、資料流與隱私

## Manifest 權限

| 權限 | 用途 | 使用者可觀察的行為 |
|---|---|---|
| `storage` | 保存 API 設定、主題、快捷鍵、提示偏好、單字庫 | 設定與單字在同一 Chrome profile 保留 |
| `sidePanel` | 顯示擷取、預覽、OCR 與結果介面 | 按快捷鍵或按鈕時開啟 Side Panel |
| `activeTab` | 保留工具列點擊等既有工作流的目前分頁能力 | 點 Extension 圖示後操作目前頁面 |
| `<all_urls>` | 讓自訂頁面快捷鍵第一次啟動時也能呼叫 `captureVisibleTab()` | 可在普通網頁直接按快捷鍵擷取目前可視區 |

## 為什麼需要 `<all_urls>`

兩組可錄製快捷鍵是由頁面 `keydown` 處理，不是 Chrome 原生 `commands`。這種事件不會自動啟用 `activeTab`；Chrome 的 `captureVisibleTab()` 又明確要求已啟用的 `activeTab` 或 `<all_urls>`。若只保留 `activeTab`，全新頁面第一次直接按快捷鍵會失敗，而先點過 Extension 圖示後才可能成功。

Content script 實際只宣告注入 `http://*/*`、`https://*/*` 與使用者額外允許的 `file:///*`。Chrome 內建頁面、Chrome Web Store 與部分內建 PDF viewer 仍不能注入或框選。

官方參考：[captureVisibleTab](https://developer.chrome.com/docs/extensions/reference/api/tabs#method-captureVisibleTab)、[activeTab](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab)、[Match patterns](https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns)。

## 資料流

| 階段 | 資料位置 | 是否送到 Gemini |
|---|---|---|
| 拖曳框選 | 頁面只有矩形與 viewport 尺寸 | 否 |
| 擷取目前可視區 | background 記憶體 | 否 |
| 框選或完整可視區預覽 | background 與 Side Panel 記憶體；完整可視區模式的預覽就是整個可視區 PNG | 否 |
| 使用者按「送給 Gemini」 | 框選模式送裁切 PNG；完整可視區模式送整個可視區 PNG。兩者都附處理指令、模型名稱，並以 API Key header 向 Google 驗證 | 是 |
| 使用者啟動反白翻譯 | 反白文字、翻譯指令與模型名稱離開瀏覽器，並以 API Key header 驗證 | 是 |
| 顯示結果 | Side Panel 記憶體 | Gemini 已回傳 |
| 清除／新工作 | 舊圖片與結果失去引用 | 不新增傳送 |

Extension 不建立 OCR 圖片或結果歷史。反白翻譯的單字庫與設定例外，會存在本機 `chrome.storage.local`。

## API Key 邊界

- Key 由每位使用者自行建立並貼到設定頁，不包含在 GitHub 或 ZIP。
- `chrome.storage.local` 已限制為 trusted extension contexts，頁面 content script 不會收到 Key。
- 本機 Extension storage 仍不是秘密保管庫；共用、商用或公開發佈應改用自家 HTTPS proxy 保存伺服器 Key。
- Key 應專案專用、可撤銷，並盡可能限制為 Gemini API。

## Google 資料使用、人工審查與費用

依 [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)，使用 Unpaid Services 或 Gemini API 免費額度時，Google 可使用使用者提交的內容與生成結果來提供、改善及開發產品與機器學習技術；人工審查人員也可能閱讀、標註與處理 API 輸入和輸出。條款對 EEA、瑞士、英國及 Paid Services 另有規定，應以使用者的帳號、地區、專案與當時條款為準。

本 Extension 使用 `generateContent`，正常請求明確送出 `store: false`。依 [Logs and datasets](https://ai.google.dev/gemini-api/docs/logs-datasets)，`store` 控制 API developer logging／storage；它不會改寫免費服務的資料使用條款，也不代表零保留。相容格式重送可能省略這個欄位，而專案層級的 logging 設定也可能影響行為。

不要框選或送出：

- 密碼、API Key、Cookie、身分證件或金融資料。
- 個人、醫療、學校或未成年人敏感資訊。
- 公司機密、客戶資料、受 NDA 保護內容。
- 未取得權利的付費內容或私人通訊。

請以 [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)、[Billing](https://ai.google.dev/gemini-api/docs/billing)、[Additional Terms](https://ai.google.dev/gemini-api/terms) 與適用條款為準。
