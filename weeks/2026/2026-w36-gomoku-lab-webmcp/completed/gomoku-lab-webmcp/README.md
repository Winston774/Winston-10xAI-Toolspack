# Gomoku Lab WebMCP

15×15 五子棋頁面，將即時棋盤註冊為 8 個 WebMCP 工具。Agent 必須先讀盤、公開決策摘要，再用同一棋盤版本落子。

## 開始

```powershell
npm ci
npm run validate
npm run dev
```

打開終端顯示的 localhost 網址；首頁導向 `/gomoku.html`。

## Scripts

- `npm test`：解析 standalone HTML script，檢查 8 個工具與讀盤 → 公布 → 落子契約。
- `npm run typecheck`：TypeScript 靜態檢查。
- `npm run build`：Vinext production build。
- `npm run validate`：執行零依賴契約測試，供 Toolspack CI 在未安裝套件時驗證。
- `npm run lint`：Oxlint；v0.1.0 Preview 尚有 19 項未使用 UI scaffold 診斷。

## Preview 限制

新棋局的人工核准尚未在按下核准時重新比較棋盤版本。待核准期間請不要繼續落子。完整說明在週次的 `docs/known-limitations.md`。

## 部署

`.openai/hosting.json` 保留來源專案綁定以利追溯。部署前請建立自己的專案並更新 `project_id`；它不是憑證，也不授予原專案寫入權限。

## License

本專案自行創作內容依 MIT License 發布。npm 相依套件各自適用原授權，且未打包 `node_modules`。
