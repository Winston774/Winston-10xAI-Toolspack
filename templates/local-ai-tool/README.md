# Local AI Tool Template

將已驗證的本地 AI 工具複製到週次的 `completed/<tool-name>/`，並至少包含：

- `README.md`
- `package.json`
- `LICENSE`
- 可直接啟動的程式碼
- `test` 與 `validate` npm scripts
- 不含真實資料的設定範例
- 隱私、疑難排解與驗證文件

工具必須預設只監聽 localhost。匯入本地資料不得自動傳送到外部 AI 服務；若有外部傳輸，需由使用者明確觸發並在 README 說明。
