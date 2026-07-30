# 貢獻與每週發布流程

## 建立新週次

1. 從 `templates/weekly-unit/` 複製一份到 `weeks/YYYY/YYYY-wNN-topic/`。
2. 依內容類型，將 `templates/skill/`、`templates/chrome-extension/` 或 `templates/local-ai-tool/` 複製到該週的 `completed/`。
3. 完成該週 `README.md`、`metadata.yml`、starter、completed、assets 與 tests。
4. 更新 `CATALOG.md`。
5. 在 Windows PowerShell 執行 `powershell -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1`。
6. 建立 Pull Request，確認安裝流程與通過標準後合併。
7. 建立標籤與 GitHub Release，例如 `2026-w31-v1.0.0`。

## 命名規則

- 週次資料夾：`YYYY-wNN-kebab-case-topic`
- 發布標籤：`YYYY-wNN-vMAJOR.MINOR.PATCH`
- 製作分支：`week/YYYY-wNN-kebab-case-topic`

## Pull Request 完成條件

- 學員能只看 README 完成安裝與操作。
- 不需要手寫 CLI 才能完成基本學習路徑。
- 已寫明成果證據、通過標準與重試方式。
- 沒有 API Key、Token、Cookie 或個人資料。
- 沒有講師用發布文案或 SKOOL 貼文草稿。
- 自動驗證通過。
