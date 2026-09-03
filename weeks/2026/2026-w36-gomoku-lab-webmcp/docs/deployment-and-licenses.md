# 部署、專案綁定與授權

## 本機優先

學員練習只需 `npm ci`、`npm run dev` 與 localhost，不需要部署或雲端帳號。

## `.openai/hosting.json`

來源快照保留原始 `project_id`，讓架構與來源可追溯。它不是祕密，但代表原專案綁定。公開 ZIP 沒有授權學員覆寫或更新原專案。

若要部署：

1. 在自己的帳號建立新的 Sites／hosting 專案。
2. 依平台產生的新設定取代原 `project_id`。
3. 確認 D1／R2 綁定符合自己的需求；本版皆為 `null`。
4. 先跑 `npm run validate`。
5. 只在自己的專案與權限範圍內執行部署。

部署指令、權限與產品行為可能更新，請以當下平台 UI／官方文件為準。本週 Release 只保證公開 ZIP 與本機驗證，不宣稱外部網址已同步到 Release commit。

## 第三方套件

ZIP 不含 `node_modules`。執行 `npm ci` 時會依 `package-lock.json` 下載相依套件；各套件的授權、供應鏈風險與更新政策仍由套件發布者決定。商業使用或再散布前，請檢查實際安裝版本的授權與 notices。
