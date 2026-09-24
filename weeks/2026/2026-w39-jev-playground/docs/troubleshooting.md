# 疑難排解

## 雙擊 start.cmd 沒有成功

確認已安裝 Node.js 20.3 以上，重新開啟終端機後執行 node --version。路徑有空白可正常使用。專案沒有第三方依賴，通常不需要 npm install。

## Cannot find module / dist 不存在

用 npm start，自動建置後啟動；單獨 npm run dev 需要先 npm run build。請使用本週完整 completed/jev-playground 資料夾，勿只複製 public。

## 4321 已被占用

先確認是否已有自己啟動的 Jev 服務，回該終端機用 Ctrl+C 關閉。不要任意結束其他程序。必要時請 Agent 協助確認占用者。

也可在 PowerShell 設定另一個連接埠後啟動：

```powershell
$env:PORT = '4339'
npm.cmd start
```

此時改開 http://127.0.0.1:4339。macOS／Linux 可使用 `PORT=4339 npm start`。

## 直接開 index.html 沒有畫面

請從本機 HTTP 服務進入，使用 http://127.0.0.1:4321。模組、絕對資產路徑與同源轉送需要服務環境。

## 即時模式 401／403／429

核對自己的金鑰、帳戶模型權限與用量限制。先清除再重新填入；不要把金鑰貼到 Issues 或社群。預演模式不需要金鑰，可獨立驗證前端流程。

## 即時模式 502／逾時

可能涉及 upstream、網路或轉送 runtime。此包包含 Cloudflare redirect: manual 和可選 Request.signal 的修正。請記錄時間、HTTP 狀態與顯示錯誤；不要把錯誤稱為模型已成功完成決策。

## 為什麼很多提案在同一位置？

每個動機都有自己的提案 ID，可能選到同一合法落點。畫面同時顯示提案數與獨特位置數。

## 為什麼全部否決後還是落下？

範本設計會明示改採本機基準。這是程式備援；回看 decision.fallback 可區分它與一般裁判選擇。

## 暫停後 API 次數增加／Tokens 不完整

已發出的請求可能已計數或計費；停止無法撤回遠端處理。沒有回傳用量的失敗請求無法補算 Tokens，請以服務帳單為準。

## 重新整理後紀錄消失

遊戲、金鑰與歷史只在分頁記憶體。先用「匯出 JSON」保存需要的決策。重新整理後需要重新填入金鑰。
