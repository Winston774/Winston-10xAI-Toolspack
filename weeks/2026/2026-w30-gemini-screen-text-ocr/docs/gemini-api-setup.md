# Gemini API Key、模型與免費層

## 這個 Extension 如何使用 Gemini

圖片理解是 Gemini API 的原生多模態能力；圖片可以和文字提示一起送入模型，取得描述、分類、問答或結構化資訊抽取結果。這個 Extension 把裁切 PNG 送到 `generateContent v1beta`，以 JSON Structured Output 取得原文、繁中譯文、語言、不清楚片段與內容類型。

官方參考：[Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding)、[Gemini models](https://ai.google.dev/gemini-api/docs/models)。

## 建立專用 API Key

1. 登入 [Google AI Studio API Keys](https://aistudio.google.com/apikey)。
2. 建立或選擇一個專門給本 Extension 使用的專案。
3. 建立 API Key；若 Google 提供 API 限制，限制為 Gemini API。
4. 回 Extension 設定頁貼上 Key，保留模型預設值。
5. 按「儲存設定」，再按「測試 Gemini」。

請使用可撤銷的個人專用 Key。不要把 Key 放進 GitHub、教材截圖、錄影、Issue、聊天室或打包檔案。Extension 只會在本機 `chrome.storage.local` 保存使用者輸入的 Key，但瀏覽器 storage 不是秘密保管庫。

## 模型選擇

已驗證：

| 模型 | 建議用途 | 備註 |
|---|---|---|
| `gemini-3.1-flash-lite` | 預設；一般 OCR、翻譯與低延遲操作 | 本專案主要回歸測試模型 |
| `gemini-3.5-flash-lite` | 文件抽取、結構化解析與較新的多模態能力 | 已完成實機功能測試 |
| `gemini-3.6-flash` | 複雜畫面或較高推理需求 | 成本、可用層級與配額需自行確認 |

模型名稱、可用地區、免費層與生命週期會改變。若 Google 回覆模型不存在，先查看 [最新模型清單](https://ai.google.dev/gemini-api/docs/models) 與 [Release notes](https://ai.google.dev/gemini-api/docs/changelog)，再回設定頁更換模型。

## 免費層是否可用

截至本週文件建立時，Google 官方定價頁列出 `gemini-3.1-flash-lite` 的文字／圖片／影片輸入與文字輸出可使用免費層；實際可用量受模型、帳號、專案、地區與當下配額限制，不代表永久或不限量免費。免費層提交內容可能用於改善 Google 產品；Paid Tier 的資料使用條件不同。

開始前以官方頁面為準：

- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Billing and tiers](https://ai.google.dev/gemini-api/docs/billing)
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Available regions](https://ai.google.dev/gemini-api/docs/available-regions)

本 Extension 不會替使用者建立帳單，也無法保證不產生費用。若 Key 所屬專案已啟用付費，呼叫可能依該專案方案計費；請在 AI Studio 查看用量與 billing tier。

## 常見測試錯誤

| 類型 | 常見原因 | 處理方式 |
|---|---|---|
| 400 | 模型不接受請求欄位或格式 | 先重新載入最新版；再確認模型名稱 |
| 400 `FAILED_PRECONDITION` | 所在地區不支援免費層 | 查看官方地區與 Billing 說明 |
| 403 | Key 無權限、限制錯誤或專案不符 | 建立新的專用 Key，確認 Gemini API 限制 |
| 404 | 模型名稱不存在或已停用 | 從官方 Models 頁改用仍可用模型 |
| 429 | RPM、TPM、RPD 或花費上限已用完 | 等待配額重置，降低頻率或檢查方案 |
| 5xx／timeout | 暫時性服務或網路問題 | 稍後重試，並查看服務狀態 |

官方錯誤對照：[Gemini API troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting)。
