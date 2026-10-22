# W43 驗證紀錄

日期：2026-10-22。驗證對象為本週 `completed/deck-atelier/`，使用 Windows、Node.js 24 系列、Python 3.12、uv 與獨立無頭 Edge；中文分詞設定 `PYTHONUTF8=1`。

## 本機已執行

| 項目 | 結果與範圍 |
|---|---|
| 離線契約測試 | 6 通過、0 失敗、0 跳過 |
| 語法 | 六個 Node 腳本與引擎 JS 可解析；三個 Python 檔 AST 可解析，未寫入快取 |
| 新建／風格 | 十種風格可建立五頁模板；標題跳脫、預設拒絕覆寫、無效風格不改檔；Glitch 切換保留講稿並更新風格／字型 |
| 離線打包契約 | 跳過分詞與字型時能產生靜態／動態 HTML，內嵌引擎且來源不變；明確確認仍保留線上字型連結 |
| CJK 目標契約 | 只挑適用文字；保留 SVG、講稿及手動控制片段 |
| 範例依賴 | 15 頁 Attention 範例的本機引擎路徑皆存在 |
| 真實 Markdown 匯入 | 合成 102 詞測試資料，輸出 source／manifest 與 3 個 chunks；未使用私人輸入 |
| 完整範例建置 | 產生靜態／動態單檔；82 個元素分詞、206 個 wbr、28 個 glue；723 個字元子集，約 363 KB 字型內嵌 |
| 瀏覽器逐頁檢查 | 15 頁均產生 PNG，逐頁 issues 為空；Archivo、IBM Plex Mono、Noto Sans TC 均回報載入 |
| PDF | 無頭 Edge 成功輸出 Attention PDF；PyMuPDF 確認 15 頁，頁面為 1440×810 pt |
| 動態抽驗 | 第 8 頁轉場的 0、160、360、620、950、1500 ms 六張畫格；第 12 頁 motion on 的四個逐步狀態 |
| 風格抽驗 | 十種風格各截前兩頁，共 20 張畫面；沒有把這項抽樣寫成全風格全頁驗收 |
| 圖像審閱 | 檢視 15 頁總覽、六時點轉場、四狀態及十風格總覽；未逐字核查每張圖的全部內容 |

完整建置仍有 `missing asset %23n` 警告，對應範例內嵌 SVG 的片段參照。未修改來源解析器；保留已知限制與逐頁瀏覽器結果。上述字型檢查只針對選定 Swiss 建置版，不涵蓋所有風格。

## 可重跑方式

在技能根目錄執行：

```powershell
node --test tests/distribution.test.mjs
# 同一組測試也可用 npm run validate
```

完整建置／截圖／PDF 指令見[安裝說明](setup-and-dependencies.md)。公開包不附本機驗證 PNG、模型、字型輸出或成品 PDF；可由本包範例重建。

倉庫根目錄執行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/validate-repo.ps1`，再以 `scripts/build-release.ps1 -WeekPath weeks/2026/2026-w43-deck-atelier` 打包。發布時另檢查本機 Markdown 連結、來源／completed 雜湊、ZIP 路徑及逐檔內容一致性；PR 與主分支 CI 狀態以當次 GitHub Actions 紀錄為準。

## 未執行與驗收邊界

- 未逐項端到端測試 PDF／EPUB／Office／URL／影音匯入、真實 YouTube 字幕或 ASR；未啟動大型模型。
- 未由人類完成新帳號安裝、Codex／Claude Code 首次技能觸發、投影講述與全瀏覽器測試。
- 未人工操作全螢幕、講者雙視窗、真實檔案儲存選擇器或斷網重開。
- 未重新查核範例的所有科學、歷史及引用數聲明；未對第三方著作授予額外權利。

自動與瀏覽器技術驗證不等同上述人類驗收，本週維持 Preview。
