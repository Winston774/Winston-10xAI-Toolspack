# 架構與決策資料

## 一次決策如何完成

```text
棋盤 → 引擎列舉合法直落及結果
     → 感知：五個動機
     → 提案：活躍動機 + 本機基準
     → 裁判 Choice + 各提案教練 Noul
     → 程式核對版本及合法性 → 落子 → 保存紀錄
```

在 live 模式，感知、提案、判定各送一批 HTTP 請求，共 3 批。preview 模式使用本機規則完成同樣的畫面階段，網路請求為 0。

## 程式先提供的狀態

20×10 棋盤字串、目前方塊、接下來 5 個方塊、分數、消行數、aggregateHeight、maxHeight、holes、bumpiness、wells。每個候選包含 placement ID、rotation、x/y、四格座標、放置並消行後的特徵和 heuristic。

引擎基準評分為：

```text
1.5 × 消行數 − 0.51 × 高度總和 − 0.9 × 空洞
− 0.19 × 起伏 − 0.1 × 最高高度 − 0.05 × 井深指標
```

動機再調整權重。預演分布用分數轉換，感知啟動與教練風險也使用固定規則；這些百分比是教學顯示值。

## 控制與錯誤

- 啟動門檻 0.5，教練否決門檻 0.65。
- 多個動機可提出相同位置，裁判評估的單位是提案 ID。
- 全部提案遭否決時，明示使用本機基準；這是程式備援策略。
- API 請求失敗、格式／機率錯誤或過期結果會停止該次執行，不會偽裝成成功模型結果。
- reset／stop／clear 會失效化當前執行，防止晚到結果改動新的棋盤。

## TypeSafe 介面

本範本使用 POST /v1/systemone、Bearer 認證與 jev-latest。state 放局面，questions 放命名問題；回傳 answers 與 usage。介面已於 2026-09-24 核對[官方 API 文件](https://docs.typesafe.ai/api)。

Noul 是 yes／no 的機率；Choice 選擇有限選項並返回分布。本範本不使用 Score。Worker 會清理回應，只保留已知答案與用量，輸出 model 記為 jev-latest，因此匯出紀錄不保證保存 alias 背後的精確模型版本。

## 本機與公開模式

同一份前端由 Worker 提供。瀏覽器把請求送到同源 /api/jev，轉送服務僅呼叫固定 TypeSafe endpoint。公開站與本機服務各自處理請求；本機執行不會經過 Winston 的公開站。

建置將 7 個 allowlist 前端資產與 Worker 組合，沒有讀取母專案郵件資料、環境金鑰或既有部署識別檔。
