# 教學講義：把「看得到但複製不到」變成可編輯文字

## 為什麼要做這個工具

網頁圖片、Canvas、線上簡報與影片字幕中的文字通常沒有 DOM 文字節點，滑鼠看得到卻無法反白。一般解法要先截圖、儲存、打開另一個 AI 工具、上傳、下提示詞，再把結果複製回來。本週 Extension 把這些步驟收進瀏覽器，並在送出前保留一道人工確認。

這個案例適合拆解三件事：

1. Chrome Extension 如何在頁面、background service worker、Popup、設定頁與 Side Panel 之間傳遞工作。
2. 如何把目前可視區截圖裁成使用者拖曳的 CSS 座標範圍。
3. 如何將圖片與指令送給多模態 Gemini，並用 JSON Structured Output 取得穩定欄位。

## 核心觀念

### 1. OCR 不是另一個獨立 API

Gemini 是原生多模態模型，可以同時接收圖片與文字提示，完成圖像理解、資訊抽取與翻譯。這個 Extension 使用 `generateContent v1beta`，把裁切 PNG 當作 inline image data，要求模型回傳結構化 JSON。它不是傳統、保證逐字一致的專用 OCR；低畫質、小字、特殊字型與遮擋內容仍需要人工核對。

官方參考：[Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding)、[Structured output](https://ai.google.dev/gemini-api/docs/structured-output)。

### 2. 先截圖，再裁切，再確認

頁面 content script 只取得拖曳矩形與 viewport 尺寸。完整 screenshot 由 background service worker 呼叫 `chrome.tabs.captureVisibleTab()` 取得，再依 screenshot 與 CSS viewport 的比例裁切。框選模式的 Side Panel 只收到裁切圖；完整可視區模式沒有較小的裁切範圍，因此預覽本身就是整個可視區擷取圖。

這個順序同時處理裝置像素比與 Chrome zoom，也把「使用者真正框選的內容」變成送往模型前的最後確認範圍。

### 3. 自訂快捷鍵和 `activeTab` 不一樣

本專案的兩組快捷鍵由頁面 `keydown` 處理，方便直接在設定頁錄製。它們不是 Chrome `commands` API，也不會像點擊 Extension 圖示那樣自動啟用 `activeTab`。但 `captureVisibleTab()` 需要已啟用的 `activeTab` 或精確的 `<all_urls>` host permission，因此 manifest 必須宣告 `<all_urls>`，才能在全新頁面第一次只按快捷鍵時成功截圖。

權限並不代表 Extension 會把所有頁面內容送到外部；實際傳送仍受使用者框選、預覽確認與「送給 Gemini」按鈕控制。詳見 [權限、資料流與隱私](docs/permissions-and-privacy.md)。

### 4. 最新使用者輸入優先

擷取流程可能同時遇到 Side Panel 開啟、截圖、裁切、Gemini 網路請求與使用者再按快捷鍵。每次操作都建立新的 `jobId` 與 `generation`：

- 新工作會淘汰 selecting、capturing、preview、running、result 或 error 中的舊工作。
- 舊的 Gemini 請求會中止。
- 晚到的舊回應即使完成，也不能覆寫目前工作。
- 同一張預覽只能送出一次 OCR 請求。

這是一個簡單但重要的「latest wins」非同步設計。

## 動手做

### 步驟一：載入並設定

依 [README](README.md#安裝與開始) 載入 `completed/gemini-selection-translator/`，建立自己的 Gemini API Key，保留預設模型並按「測試 Gemini」。

預期結果：設定頁顯示連線測試成功，且不會回顯完整 Key。

### 步驟二：驗證冷啟動快捷鍵

1. 到 `chrome://extensions` 重新載入 Extension。
2. 重新整理一個普通 `https://` 網頁。
3. 不點工具列 Extension 圖示，直接按 `Alt + Shift + X`。
4. 完成一次框選，再捨棄預覽。
5. 關閉 Side Panel，直接按 `Alt + Shift + V`。

預期結果：X 立即進入拖曳框選，V 直接顯示完整可視區預覽；兩者第一次都不需要先打開 Popup。

### 步驟三：觀察安全確認點

第一次進到預覽時閱讀「截圖與傳送範圍」。保持確認選項未勾選時，送出按鈕不可繼續；勾選「我已瞭解，下次不需要再顯示」後才送出。下一次擷取不再顯示提示，也可從設定頁恢復。

### 步驟四：比較轉錄與翻譯

用同一張非中文圖片分別執行：

- 只轉錄：應盡量保留原文、換行與標點。
- 轉錄＋繁中翻譯：除原文外，另回傳台灣繁體中文。

比較不清楚片段標記、語言判斷與翻譯是否合理。不要把生成式模型輸出當成不可質疑的原稿。

### 步驟五：製造競態

在 Gemini 處理中立刻按另一組快捷鍵，建立新工作。預期 Side Panel 立即切換到新擷取流程，舊結果之後也不會跳回來。

## 延伸挑戰

- 加入「摘要」、「轉成 Markdown 表格」或「解釋畫面中的程式碼」模式，但仍保留預覽確認。
- 讓使用者建立自己的處理模板，而不是把所有提示詞寫死。
- 對同一裁切圖提供專用 OCR 與 Gemini 兩種結果，設計差異比對介面。
- 將 BYOK 架構改成自家 HTTPS proxy；在伺服器保存共用 Key，加入身分驗證、額度與稽核。
- 為無障礙需求加入鍵盤框選或放大預覽。
