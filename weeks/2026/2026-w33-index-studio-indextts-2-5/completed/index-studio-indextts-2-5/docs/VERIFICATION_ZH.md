# 驗證與驗收

## 自動驗證

Release 邊界與相對連結：

```powershell
npm.cmd run validate
```

HTML UI 與 API 合約：

```powershell
uv run --extra htmlui --extra test python -m pytest tests/test_htmlui.py -q
```

`npm run validate` 不會下載模型，會檢查必要檔案、授權聲明、敏感資訊樣式、相對連結、版本與禁止進入發行包的本機資料夾。

## 人工冷啟動驗收

- [ ] 全新 checkout 可執行 `start_htmlui.bat`。
- [ ] 首次下載後 `/api/health` 顯示 `ready`。
- [ ] 1200 × 900 與 390 × 844 沒有欄位錯位或水平溢位。
- [ ] 只使用已授權聲音完成一筆生成。
- [ ] WAV 可播放，JSON 保留原始繁體文字與參數。
- [ ] 暫存上傳音檔在工作後刪除。
- [ ] 關閉服務後，外部網路無法連入本機 API。

## 證據分級

- `Automated`：Release validator、Python tests、compile、CI。
- `Local manual`：本機瀏覽器、GPU、模型與人工聆聽。
- `Public remote`：公開 Repo、匿名下載、main CI、Release 雜湊。

2026-08-13 的來源工作區重新執行 `tests/test_htmlui.py` 為 `9 passed`。這只能證明 UI／API 合約，音質、聲紋相似、情緒與五語言品質仍需逐項人工聆聽。
