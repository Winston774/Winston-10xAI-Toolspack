# 資料流與模組

```text
右鍵目標影片
  → source-content.js：目標定位、Threads 解析、X 貼文／封面資訊
  → background.js：工作鎖、X resolver／頁面備援、訊息權限
  → offscreen.js＋policy.js：HTTPS MP4 下載、檔頭／大小／中繼資料檢查
  → db.js：IndexedDB 保存目前一支影片與 metadata
  ├→ 剪貼簿 video-bridge:<id>
  ├→ Chrome Downloads：下載請求與 Blob URL 生命週期
  └→ social-content.js：分塊取回 → File → 發文框附件
       → 平台上傳／處理 → 使用者確認與發布
```

## 來源身分

來源程式以右鍵上下文、可見影片與指標確認目標，不從全頁挑第一支影片。上下文超過兩分鐘、路由變更或目標移除時須重新右鍵。X 對引用區塊與貼文永久連結另做定位。

- **直接 MP4**：驗證來源平台相符的 HTTPS 媒體網域，再下載完整內容。
- **X blob／串流**：`x-resolver.js` 以精確 status ID 查詢公開 embed 資料，核對 ID、封面或播放器長度／比例，選定影片的最高 bitrate MP4。資料缺少該影片時，可由來源分頁讀取公開貼文頁，以封面媒體 ID 選出相同影片的最高解析度 MP4。
- **Threads blob／串流**：來源分頁從內嵌 JSON 或同站貼文頁找 `video_versions`；輪播先比封面檔名，再比時長／比例。可得尺寸時選最大畫素面積的版本。

這些流程尋找現成 MP4，未實作 HLS／DASH 分段合併。若身分仍有歧義，停止並顯示錯誤。

## 快取與狀態

`offscreen.js` 在完整新影片通過檔頭及 Chrome 中繼資料檢查後，才替換 `video-bridge` IndexedDB 的 `current` 與 `metadata`。`chrome.storage.session` 保存工作進度、錯誤及下載追蹤；`chrome.storage.local` 保存 `themeMode`。

右鍵「下載並複製」使用 `saveAs: false`，面板「另存影片」使用 `saveAs: true`。`downloads.onChanged` 在完成／中斷後釋放對應 Blob URL。下載錯誤保留已備妥快取，使用者可重試另存或插入。

## 接收端

接收程式只在支援的精確網域、頂層頁面處理一個可見的新貼文視窗、一個可編輯文字區及一個相容影片附件欄位。可信任的貼上／點擊動作才觸發匯入。

每次以 256 KiB 分塊讀取，核對影片 ID、總長、Base64 長度及 EOF，再建立 File。每個非同步步驟確認發文框仍相同，保留既有附件並阻擋重複插入；寫入附件後觸發 input／change 事件，由平台接手。提示成功只代表交給欄位，需再查看實際附件預覽與處理狀態。
