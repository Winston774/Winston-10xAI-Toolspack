# Changelog

所有重要變更都會記錄在此。版本格式遵循 Semantic Versioning。

## [1.0.0] - 2026-07-30

### Added

- 本地圖片匯入、掃描、SHA-256 去重與 SQLite 索引。
- 以 FTS5 搜尋設計分類、風格、描述與提示詞。
- Codex 單工分析佇列、一次性 session、唯讀 sandbox 與 JSON Schema 驗證。
- Visual DNA、色票、實作建議與 Prompt Kit。
- 來源、作者、授權備註、收藏與人工修正介面。
- CSP-safe SVG 色票與桌面／手機響應式版面。
- 學員 README、完整教學、SKOOL 文案、架構、隱私、疑難排解與驗證文件。
- GitHub Actions 與開源內容防誤上傳檢查。

### Security

- 服務固定綁定 `127.0.0.1`。
- `.env`、SQLite 與 `library/inbox` 素材預設不進入版本控制。
- 公開版本未包含講師的資料庫、分析結果或參考圖片。
