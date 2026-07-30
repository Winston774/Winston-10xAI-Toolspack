# Stylebase｜設計靈感資料庫

> 2026-W31 SKOOL 開源專案：把散落的網頁、UI、產品與品牌設計截圖，整理成可搜尋、可分析、可轉成實作提示詞的本地資料庫。

Stylebase 是一套 local-first 視覺參考資料庫。圖片與 SQLite 資料預設只保存在自己的電腦；只有使用者主動按下「送交 Codex」時，選取的圖片才會交給已登入的 Codex CLI 分析。

## 這個專案能做什麼

- 從 `library/inbox` 或網頁介面匯入 JPG、PNG、WebP、GIF。
- 以 SHA-256 去重，建立 SQLite 索引與全文搜尋。
- 依設計領域、風格、色票、收藏與分析狀態篩選。
- 透過 Codex 產生 Visual DNA、構圖／字體／色彩描述、實作建議與 Prompt Kit。
- 保留來源網址、作者、授權備註與人工修正空間。
- 服務只綁定 `127.0.0.1`，不對區域網路或網際網路公開。

## 30 秒開始

### 需求

- Windows 10／11。
- Node.js 24 或更新版本。
- 只瀏覽、搜尋與手動整理時，不需要 Codex。
- 要使用 AI 圖片分析時，需安裝並登入 [OpenAI Codex CLI](https://github.com/openai/codex)。

本專案沒有第三方 npm 依賴，因此不需要執行 `npm install`。

### 啟動

在專案資料夾開啟 PowerShell：

```powershell
.\start-stylebase.ps1
```

或：

```powershell
npm.cmd start
```

接著開啟：

```text
http://127.0.0.1:4177
```

### 啟用 Codex 分析

尚未安裝 Codex CLI 時：

```powershell
npm.cmd install -g @openai/codex
codex login
```

確認狀態：

```powershell
codex --version
codex login status
```

## 使用 Workflow

```text
圖片匯入
  → 本地掃描與 SHA-256 去重
  → SQLite 索引
  → 瀏覽／搜尋／人工補充來源
  → 主動按「送交 Codex」
  → 單工分析佇列
  → JSON Schema 驗證
  → Visual DNA／色票／Prompt Kit 回寫
```

操作步驟：

1. 把圖片放進 `library/inbox`，可建立子資料夾。
2. 在 Stylebase 按「重新掃描」；也可直接從介面匯入。
3. 選取圖片後按「送交 Codex」。
4. 工作會出現在「Codex 分析佇列」；同一時間只執行一個工作。
5. 完成後檢查並修正 AI 分類、描述與提示詞。
6. 補上來源、作者與授權備註，避免把靈感誤認成可直接複製的資產。

## 資料與隱私邊界

```text
stylebase-design-inspiration-library/
├─ library/inbox/       原始圖片；Git 預設忽略
├─ data/catalog.sqlite  本地 SQLite；Git 預設忽略
├─ public/              HTML、CSS、瀏覽器程式
├─ src/                 資料庫、掃描與 Codex Agent 介面
├─ tests/               自動測試
└─ docs/                課程、架構、隱私與疑難排解
```

- 匯入、掃描、搜尋不會呼叫 AI。
- 只有按「送交 Codex」才會把該張圖片傳至 Codex 服務。
- Stylebase 不保存 API Key；它沿用本機 Codex CLI 的登入狀態。
- Agent 工作採一次性 session、唯讀 sandbox 與嚴格 JSON Schema。
- `data/`、`.env`、SQLite 檔與 `library/inbox` 圖片都不會提交到 Git。
- 請勿分析機密、個資或沒有權利上傳的圖片。

更多說明請讀[資料、隱私與圖片權利](docs/privacy-and-content-rights.md)。

## 本週課程

- [完整教學講義](lesson.md)
- [系統架構與 Agent Workflow](docs/architecture.md)
- [資料、隱私與圖片權利](docs/privacy-and-content-rights.md)
- [疑難排解](docs/troubleshooting.md)
- [自動驗證與人工驗收](docs/verification.md)
- [課程 metadata](metadata.yml)

## 開發與驗證

```powershell
npm.cmd run check
npm.cmd test
npm.cmd run validate:release
```

一次完成：

```powershell
npm.cmd run validate
```

`validate:release` 會檢查必要文件、Markdown 內部連結、版本與授權，並阻止 `.env`、SQLite、圖片素材或常見 Token 格式被包進公開版本。GitHub Actions 會在每次 push 與 pull request 執行相同流程。

## 備份

先停止 Stylebase，再備份：

- `library/`：原始圖片。
- `data/`：SQLite 索引與分析結果。

還原時將兩個資料夾放回同一位置即可。原始圖片是主要資料來源；缺少資料庫時可重新掃描，但既有分析與人工欄位需要從備份還原。

## 已知邊界

- 目前以 Windows 10／11、Node.js 24 為主要驗證環境。
- 第一版支援 JPG、JPEG、PNG、WebP、GIF，不處理影片與 PDF。
- AI 分析是可編輯的設計觀察，不代表事實、權利狀態或專業判斷。
- `node:sqlite` 在目前 Node 版本可能顯示 ExperimentalWarning；專案測試會驗證所需功能。
- 本專案不是 OpenAI 官方產品，也不包含任何 Codex 服務額度。

## 授權

程式碼與文件採 [MIT License](LICENSE)。

你匯入的圖片不會因為放進 Stylebase 就自動改採 MIT。圖片仍受原作者、來源平台與個別授權條款約束；公開分享前請自行確認權利。

## 版本

- `v1.0.0`／2026-W31：首次學員開源版。

完整紀錄見 [CHANGELOG.md](CHANGELOG.md)。
