# 驗證與驗收

## 自動驗證

```powershell
npm.cmd run validate
```

包含：

1. JavaScript 語法檢查。
2. Node 測試套件。
3. 隔離暫存目錄的 HTTP 冷啟動 Smoke Test。
4. 必要文件與版本檢查。
5. Markdown 相對連結檢查。
6. `.env`、SQLite、素材圖片與常見 Token 格式檢查。

GitHub Actions 在 push 與 pull request 執行同一指令。

## 自動測試覆蓋

- 按鈕狀態與 disabled 語意。
- CSP-safe 色票輸出與 HEX 驗證。
- Library 掃描、格式與去重行為。
- Codex Agent 命令組裝、輸出驗證、錯誤分類與暫存清理。

## 人工冷啟動驗收

自動測試不能證明真實瀏覽器、真實 Codex 帳號與實際圖片分析一定成功。公開前另做：

### A. 全新資料

- [ ] 確認 `data/` 不存在。
- [ ] 啟動後自動建立 SQLite。
- [ ] 空白素材庫顯示正常。

### B. 本地功能

- [ ] 匯入一張合法測試圖。
- [ ] 重複匯入不新增第二筆。
- [ ] 搜尋、收藏、人工欄位可用。
- [ ] 重啟後資料仍存在。

### C. Codex

- [ ] `codex login status` 成功。
- [ ] 選取圖片前沒有外部傳送。
- [ ] 送交後佇列狀態依序變化。
- [ ] Visual DNA、色票與 Prompt Kit 顯示。
- [ ] 失敗工作可理解且可重試。

### D. 響應式與可及性

- [ ] 1440 × 900 桌面版可操作。
- [ ] 390 × 844 手機斷點沒有關鍵控制被遮住。
- [ ] 鍵盤可到達主要操作，焦點可見。
- [ ] 狀態不只依靠顏色。

### E. 開源邊界

- [ ] `git ls-files` 沒有資料庫、圖片與 `.env`。
- [ ] Repository Public 頁面可匿名開啟。
- [ ] CI 為綠色。
- [ ] README 內部連結可用。

## 證據分級

- `Automated`：指令與測試通過。
- `Local manual`：本機瀏覽器實際操作完成。
- `Live Codex`：使用真實登入帳號完成一次非敏感測試。
- `Public remote`：匿名 GitHub 頁面與 CI 可驗證。

交付時應逐項標示，不用自動測試代替其他三種證據。
