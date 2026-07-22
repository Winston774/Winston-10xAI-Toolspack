# 系統架構與工作流

## 元件分工

| 元件 | 主要責任 | 不應持有的資料 |
|---|---|---|
| `content.js` | 反白入口、頁面快捷鍵、拖曳框選、viewport 座標 | API Key、完整 screenshot、OCR 結果 |
| `background.js` | 工作狀態、Side Panel 協調、截圖與裁切、Gemini 呼叫、單字庫 | 持久化的裁切圖與 OCR 歷史 |
| `sidepanel.js` | 準備、預覽、模式選擇、結果編輯與複製 | 框選模式的完整 screenshot；只接收裁切圖。完整可視區模式則接收整個可視區預覽 |
| `popup.js` | 反白翻譯紀錄、單字庫、複習與 OCR 入口 | 頁面框選座標 |
| `options.js` | API Key／模型、主題、快捷鍵、提示偏好 | 裁切圖與 OCR 結果 |
| `lib/gemini-client.js` | `generateContent` 請求、結構化結果、錯誤分類、重試與 timeout | UI 狀態 |
| `lib/capture-utils.js` | CSS viewport 到 screenshot 像素的裁切計算 | Chrome 或 Gemini 狀態 |
| `lib/shortcut-utils.js` | 快捷鍵正規化、比對、衝突檢查 | 擷取工作狀態 |

## 框選工作流

1. 使用者按框選快捷鍵。
2. content script 通知 background 建立新 job。
3. background 開啟 Side Panel，淘汰既有工作，再要求目前頁面進入 selection mode。
4. 使用者拖曳矩形；content script 回傳矩形與 viewport 資料。
5. background 擷取目前可視區並在記憶體裁切；完整 screenshot 不送給框選模式的 Side Panel。
6. Side Panel 顯示裁切預覽。
7. 使用者確認資料範圍、選擇模式並按「送給 Gemini」。
8. background 呼叫 Gemini；成功後只把結構化結果送到 Side Panel。
9. 原始完整 screenshot、裁切圖與結果都不寫入 OCR 歷史。

## 完整可視區工作流

完整可視區快捷鍵略過拖曳選取，直接建立 job、擷取目前可見畫面並顯示預覽。後面的確認、Gemini 呼叫與結果流程相同。

## 反白翻譯工作流

content script 只在有反白文字時顯示 icon。使用者互動後才把選取文字交給 background；background 使用同一組 Gemini 設定翻譯。單字翻譯成功後可寫入本機單字庫，並由 Popup 搜尋、刪除、匯出與複習。

## 狀態與競態控制

每個擷取工作有唯一 `jobId` 與遞增 `generation`。所有非同步回應在更新 UI 前都要確認自己仍是目前工作。新的快捷鍵、按鈕或重新開始操作會：

- 取消頁面的舊 selection overlay。
- 中止仍在進行的 Gemini fetch。
- 清除舊預覽與結果的寫入資格。
- 讓 Side Panel 只渲染最新 job。

截圖呼叫集中排程，至少間隔 550 ms，以遵守 `captureVisibleTab` 每秒最多兩次的限制。

## Gemini 請求

API client 使用：

- `generateContent v1beta`
- `x-goog-api-key` header
- inline PNG data
- JSON Structured Output
- 25 秒 timeout
- 429／5xx／timeout 最多重試一次
- 新欄位被一般 `400 INVALID_ARGUMENT` 拒絕時，在同一 endpoint 以相容格式重送一次

Key、模型、地區、配額等錯誤不會被誤當格式問題重送，UI 也不顯示 Google 原始回應、Key 或提示詞。
