# 2026-W31：Stylebase 設計靈感資料庫

> 把散落的網頁、UI、產品與品牌設計截圖，整理成可搜尋、可分析、可轉成實作提示詞的本地資料庫。

## 本週成果

本週提供可直接在 Windows 本機執行的 `Stylebase v1.0.0`。它使用 Node.js 與 SQLite 建立 local-first 視覺參考資料庫；圖片預設留在自己的電腦，只有使用者主動按下「送交 Codex」時，選取的圖片才會交給已登入的 Codex CLI 分析。

主要能力：

- 從資料夾或網頁介面匯入 JPG、PNG、WebP、GIF。
- 以 SHA-256 去重，使用 SQLite 與 FTS5 建立索引及全文搜尋。
- 依設計領域、風格、色票、收藏與分析狀態篩選。
- 產生 Visual DNA、構圖／字體／色彩描述、實作建議與 Prompt Kit。
- 保留來源網址、作者、授權備註與人工修正空間。
- 服務只綁定 `127.0.0.1`，不對區域網路或網際網路公開。

成品位置：[`completed/stylebase-design-inspiration-library/`](completed/stylebase-design-inspiration-library/)

延伸文件：

- [系統架構與 Agent Workflow](docs/architecture.md)
- [資料、隱私與圖片權利](docs/privacy-and-content-rights.md)
- [疑難排解](docs/troubleshooting.md)
- [自動驗證與人工驗收](docs/verification.md)

## 基本資料

- 類型：Local AI Tool
- 難度：中級
- 預估時間：安裝與體驗約 30 分鐘；完整拆解約 90 分鐘
- 支援平台：Windows 10／11
- Runtime：Node.js 24+
- Stylebase 版本：`1.0.0`
- 本週內容版本：`1.0.0 Stable`

## 需要準備

- Windows 10／11。
- Node.js 24 或更新版本。
- 至少三張自己有權使用的設計參考圖。
- 只瀏覽、搜尋與人工整理時，不需要 Codex。
- 要使用 AI 圖片分析時，需安裝並登入 [OpenAI Codex CLI](https://github.com/openai/codex)。

本專案沒有第三方 npm 依賴，不需要執行 `npm install`。Codex 服務的可用資格與用量依學員自己的帳號方案為準。

## 安裝與開始

不熟悉 Git 時：

1. 從 [`2026-w31-v1.0.0` GitHub Release](https://github.com/Winston774/Winston-10xAI-Toolspack/releases/tag/2026-w31-v1.0.0) 下載 `2026-w31-stylebase-design-inspiration-library.zip`。
2. 解壓縮後，進入 `completed/stylebase-design-inspiration-library`。
3. 在資料夾空白處按住 `Shift` 再按右鍵，選擇「在終端機中開啟」。
4. 執行：

```powershell
.\start-stylebase.ps1
```

5. 瀏覽器開啟 `http://127.0.0.1:4177`。

若要使用 Codex 分析：

```powershell
npm.cmd install -g @openai/codex
codex login
codex login status
```

## 使用示範

1. 將一張非敏感、可合法使用的 JPG 或 PNG 放進 `library/inbox`。
2. 在 Stylebase 按「重新掃描」。
3. 打開素材並補上標題、來源與授權備註。
4. 確認 Codex 已登入後，按「送交 Codex」。
5. 等待 Visual DNA、色票、設計描述與 Prompt Kit 出現。
6. 人工修正不準確或過度肯定的分析。

匯入、掃描、搜尋與人工編輯都不會呼叫 AI；只有按下「送交 Codex」才會傳送該張圖片。

## 本週任務

1. 匯入至少 6 張、涵蓋 2 種設計類型的合法參考圖。
2. 為每張圖補上來源與授權備註。
3. 選 3 張送交 Codex，人工校正分析結果。
4. 用 Prompt Kit 改寫一份自己的設計實作 Brief。
5. 用搜尋或篩選重新找到這 3 張圖。

完整拆解見[教學講義](lesson.md)。

## 成果證據

- 一張素材牆截圖：至少看見 6 張素材與 2 種分類。
- 一張 Inspector 截圖：需看見來源、授權備註與人工校正後的分析。
- 一段 15–30 秒錄影：從搜尋關鍵字到找到素材，再打開 Prompt Kit。
- 一份自己改寫的設計實作 Brief。

截圖與錄影不可顯示私人路徑、個資、客戶機密或未獲授權公開的圖片。

## 通過標準

- [ ] Node.js 24 環境能啟動服務並開啟 `127.0.0.1:4177`。
- [ ] 相同圖片重複匯入不會產生第二筆素材。
- [ ] 沒有 Codex 時，匯入、瀏覽、搜尋與人工編輯仍能使用。
- [ ] 圖片在按下「送交 Codex」前不會傳送給模型。
- [ ] Codex 完成後，結果通過 Schema 並顯示在 Inspector。
- [ ] 至少一筆 AI 分析經過人工校正。
- [ ] 每張成果圖都有來源與授權備註。
- [ ] `.env`、`data/` 與 `library/inbox` 素材沒有進入 Git。

## 失敗時怎麼做

1. 執行 `node --version`，確認是 24 或更新版本。
2. 在成品資料夾執行 `npm.cmd run validate`。
3. 確認 `http://127.0.0.1:4177` 是否有服務監聽。
4. AI 不可用時執行 `codex login status`。
5. 用一張小型、非敏感的 JPG 做最小測試。
6. 仍失敗時依[疑難排解](docs/troubleshooting.md)收集版本與錯誤證據。

## 版本紀錄

- `v1.0.0 Stable`：首次 Toolspack 正式發布，包含完整本地工具、教材、隱私說明、測試與 MIT License。
