# Gemini Selection Translator + Screen OCR

Chrome Manifest V3 extension，整合兩條 Gemini 工作流：

1. 反白網頁文字，從頁面上的小 icon 直接翻成台灣繁體中文。
2. 按快捷鍵框選圖片、Canvas 或暫停影片的可視區域，逐字轉錄並可同時翻譯。

目前版本：`0.6.2`，最低 Chrome `116`。

## 功能

### 反白翻譯

- 反白後才顯示 icon；hover、focus 或 click 後才呼叫 Gemini。
- 單字翻譯成功後自動加入單字庫。
- Popup 提供搜尋、刪除、JSON/CSV 匯出與 flashcard 複習。
- 同一頁工作階段有短期翻譯快取；切換 Gemini 設定時會清除。

### 畫面 OCR

- 直接框選快捷鍵預設啟用並設為 `Alt + Shift + X`；按下後會開啟 Side Panel 並立即進入拖曳框選。
- 完整可視區快捷鍵預設啟用並設為 `Alt + Shift + V`；按下後會直接擷取目前可見畫面並顯示確認預覽。
- 第一次使用時不必先點 Extension 圖示；重新載入 Extension 並重新整理網頁後，可直接用 X／V 啟動擷取。
- 兩組快捷鍵都能在 Extension 設定頁個別錄製、停用或恢復預設，不需開啟 Chrome 系統快捷鍵頁；兩組啟用中的快捷鍵不可相同。
- 任一頁面或 Side Panel 的任一狀態再次按快捷鍵，都會立即淘汰舊框選、舊截圖或舊 OCR 顯示流程，以最新一次輸入為準；每次擷取都有新的 jobId／generation，晚到的舊回應不會覆寫新工作。
- Side Panel 連線完成只讀取當前工作，不會自行建立或取代較新的擷取；同一張預覽不會重複送出兩個 OCR 請求，已被新操作取代的 Gemini 請求會主動中止。
- Side Panel 有焦點時也會接收兩組快捷鍵，因此可從準備、框選、預覽、辨識中、結果或錯誤畫面直接開始新的擷取。
- 工具列 Popup 也提供「框選畫面文字」入口。
- Side Panel 不再顯示獨立 READY 頁；沒有進行中的工作時直接顯示「準備框選」。
- Side Panel 仍提供「開始框選」與「擷取完整可視區」按鈕。
- 支援四向拖曳、`Esc` 取消、最小 16 × 16 CSS px。
- Side Panel 初次展開造成的 blur／resize 不再取消框選；尚未拖曳時會重新校準 viewport，真正拖曳後若捲動、縮放、切換分頁或導航仍會安全取消。
- 實際 screenshot 呼叫集中排程並至少間隔 550 ms，遵守 Chrome `captureVisibleTab` 每秒最多兩次的限制。
- 依實際 screenshot／viewport 比例裁切，支援 DPR 與 Chrome zoom。
- Side Panel 顯示裁切預覽；使用者確認後才送往 Gemini。
- 可選「只轉錄」或「轉錄＋繁中翻譯」。
- 原文與譯文可編輯、分開複製；顯示語言、不清楚片段、內容類型與處理時間。
- 裁切圖片與 OCR 結果只放在記憶體，不寫入 OCR 歷史。
- 首次使用會在準備頁或直接快捷鍵完成後的預覽頁顯示截圖與傳送範圍；勾選「我已瞭解，下次不需要再顯示」後不再顯示，並可從設定頁重新開啟。
- 「清除並重新開始」、取消與捨棄都會回到「準備框選」，不會進入額外的 READY 頁。

## 安裝

1. 開啟 `chrome://extensions`。
2. 開啟右上角「開發人員模式」。
3. 點「載入未封裝項目」。
4. 選擇此 extension 資料夾。
5. 在工具列 Popup 點「設定」，貼上 Gemini API Key。

兩組頁面快捷鍵由 content script 在一般網頁內處理，因此不受 Chrome Extension 原生快捷鍵註冊衝突影響；網頁輸入欄位、網址列、`chrome://`、Chrome Web Store 與內建 PDF viewer 不會觸發。Side Panel 自己也會接收相同快捷鍵，以便從任何 OCR 畫面立即重新擷取。

若要在 `file://` 使用，需在 Extension 詳細資料頁開啟「允許存取檔案網址」。

## Gemini 設定

新安裝的預設模型：

```text
gemini-3.1-flash-lite
```

相容模型：

- `gemini-3.1-flash-lite`（預設）
- `gemini-3.5-flash-lite`
- `gemini-3.6-flash`

Extension 的翻譯、OCR 與連線測試統一使用 Gemini `generateContent v1beta`、`x-goog-api-key` header、JSON Structured Output 與 25 秒 timeout，不再使用 Interactions API。正常請求使用 `responseJsonSchema` 與 `store: false`；若 Google 對新欄位回傳一般 `400 INVALID_ARGUMENT`，只會在同一個 `generateContent` endpoint 以四週前版本的 `responseMimeType` 極簡格式重送一次。Key、專案與模型錯誤不會觸發格式重送；429／5xx／timeout 最多重試一次。錯誤訊息會區分 Key、模型、地區、配額與請求格式，但不顯示 Google 的原始回應或任何 Key／提示文字。API Key 可從 [Google AI Studio](https://aistudio.google.com/apikey) 建立。

若「測試 Gemini」顯示 Key 無效或權限不足，先到 Google AI Studio 檢查舊 Key 是否標示為 `Standard`／`Unrestricted`；Google 已拒絕未限制的 Standard Key。可將它限制為 Gemini API 專用，或建立新的 Auth Key，再回設定頁覆寫。「API key 已設定」只代表瀏覽器內已有值，不代表 Google 已驗證成功。

## 資料與安全邊界

- 網頁 content script 只負責文字選取、兩組頁面快捷鍵和框選座標，不接收 API Key、完整 screenshot、裁切圖片或 OCR 結果。`chrome.storage.local` 已限制為 trusted extension contexts；content script 只會從 background 收到非敏感的 theme mode 與快捷鍵設定。
- 自訂頁面快捷鍵不是 Chrome 原生 `commands` 手勢，因此不會啟用暫時性的 `activeTab`。Chrome 的 `captureVisibleTab` 明確要求已啟用的 `activeTab` 或精確的 `<all_urls>`；manifest 因而宣告 `<all_urls>`，讓第一次直接按自訂快捷鍵也能擷取。Content script 仍只注入 `http://`、`https://` 與使用者允許的 `file://` 頁面；`file://` 仍需另外開啟檔案網址權限。
- 截圖先在 background service worker 的記憶體裁切；Side Panel 只收到裁切圖。
- 只有使用者在預覽畫面按「送給 Gemini」後，裁切圖才會離開瀏覽器。
- API Key 保留既有工作流，存於 `chrome.storage.local`；這不是秘密保管庫。僅適合自用／BYOK Preview，請使用可撤銷的專用 Key。
- Gemini 請求會把使用者的 API Key 放在 `x-goog-api-key` header 傳給 Google 驗證；反白翻譯會傳送選取文字，畫面 OCR 則在確認後傳送裁切圖或完整可視區圖。
- 正式公開發布應改用自家 HTTPS proxy 在伺服器保存 Key，不應把共用 Key 包進 Extension。
- 依 [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)，免費額度的輸入與輸出可用於改善 Google 產品，並可能由人工審查人員閱讀、標註與處理；不要提交密碼、個資、醫療資料、公司機密或未獲授權內容。
- 正常 Gemini 請求送出 `store: false` 控制該次 developer logging；若 Google 只接受舊式極簡格式，相容重送會省略這個欄位，因此專案 logging 設定可能適用。`store: false` 不會改寫免費服務資料使用條款，也不代表零資料留存。參考 [Logs and datasets](https://ai.google.dev/gemini-api/docs/logs-datasets)。

## 已知限制

- 只擷取目前分頁的可視區域，不做長截圖或跨捲動 OCR。
- Chrome 內建頁面、Chrome Web Store、部分 PDF viewer 與未授權的 `file://` 頁面無法插入框選工具。
- DRM 影片、Picture-in-Picture、真正全螢幕影片、企業 DLP 畫面可能是黑畫面或無法擷取。
- 播放中的影片可能在框選期間換影格；請先暫停。
- Gemini 是生成式多模態模型，不是保證逐字一致的專用 OCR；不清楚片段應由使用者核對。

## Design System

Noise Winston Calm / Signal 視覺系統由 `design-system.css` 提供語意 tokens，`theme.js` 同步 system／light／dark 模式到 Popup、設定頁、Side Panel 與網頁浮層。PNG icon 使用 Signal Lime `#DFF813`。

## 驗證

```powershell
node --test tests/design-system-smoke.mjs
node --test tests/theme-runtime.mjs
node --test tests/capture-utils.test.mjs
node --test tests/gemini-client.test.mjs
node --test tests/shortcut-utils.test.mjs
node --test tests/integration-contract.test.mjs
node --test tests/background-routing.test.mjs
node --check background.js
node --check content.js
node --check options.js
node --check popup.js
node --check sidepanel.js
node --check theme.js
node --check lib/capture-utils.js
node --check lib/gemini-client.js
node --check lib/shortcut-utils.js
```

### Chrome 實機驗收

每次更新後，在 `chrome://extensions` 重新載入此 Extension，再用一般 `https://` 網頁完成一次：

1. 確認反白文字的既有翻譯、單字庫與複習功能仍可使用。
2. 在設定頁確認 `Alt + Shift + X` 與 `Alt + Shift + V` 都已啟用；分別錄製、停用、重新啟用與恢復預設，並確認相同組合會被拒絕。
3. 暫停含字幕的影片或開啟一張含文字的圖片；在 Side Panel 關閉與已開啟兩種情況按框選快捷鍵，都應穩定出現拖曳框；完整可視區快捷鍵應直接進入預覽。
4. 首次確認提示預設未勾選；直接快捷鍵可以先在本機擷取，但預覽頁必須勾選後才能送出。勾選後建立下一個工作，確認提示隱藏，再從設定頁恢復提示。
5. 按「清除並重新開始」、取消框選與捨棄圖片，確認都回到「準備框選」，且不再出現 READY 頁。
6. 在 selecting、capturing、preview、running、result、error 任一狀態快速交替按 X／V，確認舊工作立即被淘汰，最後只留下最新輸入的結果。
7. 切換到另一個分頁後，從 Side Panel 按鈕或快捷鍵重新擷取，確認工作綁定新的 active tab；再快速連按完整可視區兩次，確認沒有 API 頻率錯誤。
8. 分別測試「只轉錄」與「轉錄＋繁中翻譯」，並確認複製按鈕、`Esc` 取消、過小框選、拖曳中切換分頁等狀態。
9. 在 Extension 的 Service Worker 與 Side Panel DevTools 確認沒有未處理錯誤。
