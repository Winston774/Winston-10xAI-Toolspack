# 來源與包裝範圍

日期：2026-09-24。來源任務：「製作蘋果風 Jev 俄羅斯方塊範本」。使用其中可獨立分享的 gptsite 成品，沒有打包整個 Jev 母專案。

## 本次採用

來源 Git commit：`8a216c18dba0a8cef7b1dbf9d93def64f9cf8bd2`。

採用 public/ 的 7 個檔案、worker.mjs、2 份測試、.gitignore，共 11 個來源檔。以換行及檔尾空白正規化後比對保持一致。

另外調整／新增：

- package.json：W39 版本與 validate／start 指令。
- build.mjs：移除個人 .openai/hosting.json 依賴，只產生獨立 Worker bundle。
- start.cmd、start.mjs：Windows 與跨平台啟動入口。
- preview.mjs：保留僅監聽本機的服務，加入 PORT 選項與連接埠占用提示。
- validate.mjs、package.test.mjs：語法、離線測試與臨時建置驗證。
- README、講義、metadata、docs：本週學員文件。

來源 .openai 部署設定、dist、診斷腳本、母專案 .env、郵件、研究資料、原始影片／影格、私人輸出與 Git 歷史皆未加入下載包。來源專案及既有線上站不受修改。

## 來源方法與外部介面

這個展示的三層概念來自原專案對 [chenjingdev 公開演示](https://www.threads.com/@chenjingdev/post/DdcCAYcjuua)的觀察。此次沿用已實作的程式，未重新取得原影片做逐幀分析，也未宣稱重現原作者未公開的 prompts、seed 或精確輸出。

API 型別已於本次核對 [TypeSafe 官方 API](https://docs.typesafe.ai/api)、[Noul](https://docs.typesafe.ai/primitives/noul)、[Choice](https://docs.typesafe.ai/primitives/choice)。本包使用原生 fetch，沒有打包第三方 SDK、模型權重或外部字型。

Apple 風格是介面視覺方向，本專案沒有宣稱由 Apple 或 TypeSafe 官方提供。

來源應用未附授權檔，本週 metadata 記為 unspecified，ZIP 不加入根目錄 LICENSE；不在本次包裝中替來源新指定授權。
