# Jev Playground｜W39 學員版 v0.1.0 Preview

繁體中文俄羅斯方塊三層決策展示台。預演使用本機規則；Jev 即時使用訪客自己的 TypeSafe API Key。兩種模式共用棋盤與提案顯示，資料來源在畫面與匯出紀錄中區分。

## 啟動

需要 Node.js 20.3 以上，無 npm 第三方依賴。

- Windows：雙擊同層 start.cmd。
- 其他環境：在此資料夾執行 `npm start`。
- 瀏覽器：開啟 [http://127.0.0.1:4321](http://127.0.0.1:4321)。
- 關閉：服務終端機按 Ctrl+C。

start 會先建置，再啟動僅監聽 127.0.0.1 的服務。請先使用本機預演；即時模式需要自行設定金鑰。

```text
npm test
npm run validate
npm run build
npm run dev
```

validate 檢查語法、11 項離線測試與暫存建置；不呼叫真實 Jev，也不在成品目錄留下 dist。build／start 則會在你的本機建立 dist/server。

## 程式位置

- public/lib/engine.mjs：可序列化棋盤、方塊序列、合法直落與評分。
- public/lib/brain.mjs：三層問題、預演規則、Jev provider 與否決策略。
- public/session.mjs：每個分頁的棋盤、暫存金鑰、取消與匯出。
- public/app.js、index.html、styles.css：操作、畫布、決策網路與視覺。
- worker.mjs：固定 TypeSafe 上游的同源轉送，回應白名單與錯誤遮蔽。
- scripts/：本機建置、啟動、預覽、驗證。
- tests/：隱私隔離、轉送相容性、獨立建置。

公開展示：[Jev Playground](https://jev-playground-winston.noisewinston.chatgpt.site/)。

## 金鑰與紀錄

金鑰只保存在該分頁的 JavaScript 記憶體；即時請求經同源服務轉到 TypeSafe。清除、離頁或重新整理時清除應用程式持有的金鑰，不寫入檔案、瀏覽器儲存、應用程式日誌或匯出。

已開始的請求會嘗試取消；傳輸層與供應商端是否已收到、處理或計費，無法靠前端清除回溯撤銷。應用層的不持久儲存也不代表託管商或供應商沒有基礎設施紀錄。

棋盤與最近 300 個完整決策存在分頁中，畫面只列最近 30 個。重新整理會失去遊戲紀錄，請先匯出。

## 分發變更

本包採用來源 GPTsite 的公開程式與修正版 Worker，排除個人 .openai 部署設定與線上診斷腳本。建置改成可獨立執行，新增啟動與驗證入口。它不會自動部署或更新既有線上網站。

授權欄位為未指定；沒有在來源程式上新套用授權。週次教材另有完整操作、來源與驗證文件。
