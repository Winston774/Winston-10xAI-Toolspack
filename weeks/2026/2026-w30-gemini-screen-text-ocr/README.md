# 2026-W30：Gemini 畫面文字 OCR

> 在任何一般網頁上用快捷鍵框選圖片、Canvas 或暫停影片中的文字，確認截圖後交給 Gemini 轉錄，並可同時翻成台灣繁體中文。

## 本週成果

本週提供可直接載入 Chrome 的完整 Extension `Gemini Selection Translator v0.6.2`。它把原本的「截圖 → 儲存圖片 → 上傳 AI → 複製結果」縮成一次快捷鍵啟動的連續流程，並保留既有的反白翻譯、單字庫與複習功能。

主要能力：

- `Alt + Shift + X`：直接進入拖曳框選。
- `Alt + Shift + V`：直接擷取目前分頁的完整可視區。
- 圖片送出前先顯示裁切預覽，使用者確認後才呼叫 Gemini。
- 可選「只轉錄」或「轉錄＋繁中翻譯」，原文與譯文都能編輯、複製。
- 反白網頁文字可快速翻譯，並將單字加入可搜尋、匯出與複習的單字庫。
- 快捷鍵可在 Extension 設定頁直接錄製、停用或恢復預設。
- 任一狀態再次按快捷鍵，都以最新操作為準並淘汰舊工作。

成品位置：[`completed/gemini-selection-translator/`](completed/gemini-selection-translator/)

延伸文件：

- [Gemini API Key、模型與免費層](docs/gemini-api-setup.md)
- [系統架構與工作流](docs/architecture.md)
- [權限、資料流與隱私](docs/permissions-and-privacy.md)
- [疑難排解](docs/troubleshooting.md)
- [自動測試與實機驗收](docs/verification.md)

## 基本資料

- 類型：Chrome Extension（Manifest V3）
- 難度：中級
- 預估時間：安裝與體驗約 30 分鐘；完整拆解約 90 分鐘
- 支援平台：Windows／macOS／ChromeOS，Chrome 116 以上
- Extension 版本：`0.6.2`
- 本週內容版本：`0.9.0 Preview`；合併並建立正式 Release 後升為 `1.0.0 Stable`

## 需要準備

- Google Chrome 116 以上。
- Google 帳號。
- 自己建立、可撤銷的 Gemini API Key；請勿共用講師或公司的 Key。
- 一個含圖片文字、影片字幕或 Canvas 文字的普通 `https://` 網頁。

Gemini API 是否免費、可用額度與支援地區會隨模型、帳號和 Google 政策改變。Google 目前為 `gemini-3.1-flash-lite` 提供免費層的圖片輸入與文字輸出，但免費層有用量限制，內容也可能用於改善 Google 產品。開始前請查看 [Google 官方定價](https://ai.google.dev/gemini-api/docs/pricing) 與 [Billing 說明](https://ai.google.dev/gemini-api/docs/billing)。不要框選密碼、個資、醫療資料、公司機密或未獲授權的內容。

## 安裝與開始

不需要 Git，也不需要終端機：

1. 正式發佈後，從 GitHub Releases 下載 `2026-w30-v1.0.0` 的 ZIP 並解壓縮。Preview 期間可在 GitHub 按 `Code → Download ZIP` 下載目前分支，再找到 `weeks/2026/2026-w30-gemini-screen-text-ocr/completed/gemini-selection-translator/`。
2. 在 Chrome 開啟 `chrome://extensions`。
3. 打開右上角「開發人員模式」。
4. 按「載入未封裝項目」。
5. 選取直接包含 `manifest.json` 的 `gemini-selection-translator` 資料夾。
6. 從 Chrome 拼圖選單找到 `Gemini Selection Translator`，釘選到工具列；點 Extension 圖示，再按「設定」。
7. 從 [Google AI Studio](https://aistudio.google.com/apikey) 建立自己的 API Key，貼到設定頁。
8. 模型先保留預設 `gemini-3.1-flash-lite`，按「儲存設定」，再按「測試 Gemini」。

看到測試成功後，先重新整理要操作的普通網頁。若要在本機 HTML 或圖片頁使用，還要到 Extension 詳細資料頁開啟「允許存取檔案網址」。

## 使用示範

### 框選圖片或影片字幕

1. 打開含文字的圖片，或先暫停含字幕的影片。
2. 按 `Alt + Shift + X`。
3. 按住滑鼠拖曳要辨識的區域。
4. 在 Side Panel 檢查裁切預覽。
5. 第一次使用時，閱讀傳送範圍並勾選「我已瞭解，下次不需要再顯示」；未勾選時不會送出。
6. 選擇「只轉錄」或「轉錄＋繁中翻譯」。
7. 按「送給 Gemini」。
8. 檢查原文後複製；若有翻譯，也檢查譯文再使用。

### 擷取完整可視區

1. 把要辨識的內容移到目前分頁可見範圍。
2. 按 `Alt + Shift + V`。
3. Side Panel 會直接顯示完整可視區預覽；確認後再送出。

### 反白翻譯

1. 反白一般網頁文字。
2. 點選取文字旁出現的翻譯 icon。
3. 查看繁中翻譯；單字翻譯成功後會加入單字庫。

快捷鍵不會在網址列、輸入欄位、`chrome://`、Chrome Web Store 或 Chrome 內建 PDF viewer 中觸發。

## 本週任務

完成以下三個情境：

1. 從一張圖片框選至少兩行文字，只做逐字轉錄。
2. 從暫停影片框選一段非中文字幕，取得原文與繁中翻譯。
3. 不先點工具列圖示，在重新整理後的普通網頁直接以 `Alt + Shift + V` 擷取完整可視區。

進階挑戰：到設定頁錄製兩組不同快捷鍵，測試後恢復預設；再快速交替觸發兩組快捷鍵，確認最後只留下最新一次擷取。

## 成果證據

- 一張結果畫面截圖，需同時看見裁切預覽來源或辨識結果。
- 一張設定畫面截圖，需看見兩組已啟用且互不相同的快捷鍵。
- 一段 10–20 秒錄影，需從快捷鍵開始，經過框選或完整可視區預覽，到取得文字結果。
- 請勿在成果證據中顯示 API Key、個資或敏感內容。

## 通過標準

- [ ] Extension 能在 Chrome 116 以上成功載入，沒有 manifest 錯誤。
- [ ] 「測試 Gemini」成功，且 API Key 沒有出現在截圖或原始碼中。
- [ ] 第一次不點工具列圖示，兩組快捷鍵都能直接啟動對應擷取。
- [ ] 框選後顯示的預覽範圍與滑鼠選取一致。
- [ ] 完整可視區快捷鍵能直接進入預覽。
- [ ] Gemini 能回傳可複製原文；翻譯模式還會回傳繁中譯文。
- [ ] 在處理中再次按快捷鍵，最後只留下最新工作的結果。
- [ ] 使用者尚未確認預覽前，裁切圖片不會送往 Gemini。

## 失敗時怎麼做

1. 先查看 [疑難排解](docs/troubleshooting.md) 對照錯誤訊息。
2. 到 `chrome://extensions` 按「重新載入」，再重新整理測試網頁。
3. 用普通 `https://` 網頁重測，不要使用 Chrome Web Store、`chrome://` 或內建 PDF viewer。
4. 回設定頁按「測試 Gemini」，確認 Key、模型、地區與額度。
5. 先用高對比、清晰、水平的兩行文字做最小測試。
6. 回報問題時附上 Chrome 版本、Extension 版本、操作步驟與去除敏感資訊後的錯誤畫面。

## 分享成果

可修改以下文字：

> 本週我把圖片／影片字幕的 OCR 流程做成 Chrome Extension：按快捷鍵框選、先確認截圖，再交給 Gemini 轉錄與翻譯。這次測試的內容是＿＿＿，原本需要＿＿＿個步驟，現在縮短成＿＿＿。

建議搭配「框選前 → 預覽 → OCR 結果」三段式截圖或短錄影。分享前務必遮住 API Key、姓名與敏感資料。

## 版本紀錄

- 本週內容 `v0.9.0 Preview`：首次整理進 Toolspack，包含 Extension `v0.6.2`、完整教學與驗證文件；完成 PR、CI 與正式 Release 後升為 `v1.0.0 Stable`。
- Extension `v0.6.2`：修正第一次只用自訂快捷鍵時缺少截圖權限的冷啟動問題，並完成 region／viewport 回歸測試。
