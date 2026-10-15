# 權限與隱私

## Manifest 權限

| 權限 | 本版用途 |
|---|---|
| contextMenus | 建立複製／下載並複製的右鍵選單 |
| storage | 工作狀態與下載追蹤使用 session，主題使用 local |
| offscreen | 在背景 DOM 環境讀取影片資訊、保有 Blob URL 與寫剪貼簿 |
| clipboardWrite | 寫入 `video-bridge:<id>` 識別文字 |
| downloads | 將快取影片交給 Chrome 下載並追蹤完成／中斷 |
| host_permissions | `*.twimg.com`、`*.cdninstagram.com`、`*.fbcdn.net` 的 HTTPS 媒體／公開資料請求 |

content scripts 僅配置於 X／Twitter、Threads、Facebook 的 manifest 指定頁面。背景另以精確來源／接收端網域及訊息角色檢查讀取請求；接收影片分塊限同一擴充功能的 Threads／Facebook 頂層 content script。

## 哪些資料會離開本機

- X embed 查詢包含貼文 ID；X 貼文頁備援及影片 CDN 下載使用 `credentials: omit`。檔案下載拒絕重新導向，保留來源簽名 query 以供正常取檔。
- Threads 先讀目前頁面內嵌資料，必要時請求 **同站永久連結，使用 `credentials: same-origin`**，瀏覽器可能隨請求帶上既有登入 Cookie。程式沒有直接讀取／匯出 Cookie，也沒有要求 API Key。
- 插入影片會把檔案交給 Threads／Facebook 的附件機制，平台可能立即開始上傳，依其帳號及服務設定處理。實際發布由使用者操作。
- 本版沒有自有後端、遙測或廣告請求。來源站與媒體 CDN 仍可看到正常網路請求。

## 本機保存與清理

IndexedDB 保存目前影片 bytes、UUID、檔名、大小、時長、尺寸、來源頁 origin／path 與建立時間；來源頁 query／hash 不寫入這份 metadata。成功取得新影片後替換舊快取。沒有自動到期機制，可在面板「清除暫存」。

清除快取不會刪除已下載檔案、平台附件或剪貼簿原有標記。需要移除標記可另複製一般文字；平台附件和下載檔案自行處理。請確認分享素材的使用權，並避免把私人來源資訊或未獲授權的影片上傳到其他平台。

本週公開包包含程式、圖示、樣式、教材與模擬測試，未包含實際下載影片、瀏覽器 profile、Cookie、帳號資料或來源專案的私人驗證輸出。
