# Contributing

感謝你改善 Stylebase。

## 開始

1. Fork Repository。
2. 建立功能分支。
3. 保持修改範圍單一。
4. 執行：

```powershell
npm.cmd run validate
```

5. 在 Pull Request 說明改了什麼、原因、驗證方式與人工驗收狀態。

## Pull Request 邊界

- 不要提交自己的 `data/`、`.env` 或 `library/inbox` 圖片。
- 不要以真實客戶或學員資料建立 fixture。
- 新增依賴時說明用途、授權、替代方案與維護成本。
- 變更傳輸行為、安全標頭或 localhost bind 時，必須更新隱私文件與回歸測試。
- UI 變更需附桌面與手機驗收結果；無障礙狀態需以鍵盤檢查。

## Commit

使用簡短、可理解的動詞描述，例如：

```text
add markdown export
fix missing asset reconciliation
document Codex retry states
```
