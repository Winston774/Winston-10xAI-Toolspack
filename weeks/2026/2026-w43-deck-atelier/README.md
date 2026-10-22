# 2026-W43｜Deck Atelier 簡報工坊

把文件、文章或逐字稿整理成有故事線、來源註記與講者備註的 HTML 簡報，再完成靜態版、動態版、截圖檢查與 PDF。

本週為 `0.1.0 Preview`，此版本號屬於 Toolspack 學員包。技能來源未標示獨立版本。本週透過主分支與 CI 打包附件交付，尚無獨立 GitHub Release。

## 學習成果與準備

預估 120 分鐘。你會完成一份 6–8 頁、每頁一個主張的簡報，並保留故事線、來源與 QA 證據。

- 已能使用本機 Codex 或 Claude Code，並能開啟資料夾、把檔案交給 Agent。
- 先準備一份有分享權限、無機密資訊的 Markdown／TXT；第一次練習先用文字資料。
- 製作／建置需要 Node.js 22 以上（建議 24）；文字匯入需要 Python 3.10 以上。完整 CJK 分詞及其他格式需要 `uv` 與額外依賴，詳見[安裝與依賴](docs/setup-and-dependencies.md)。
- 截圖／PDF 需要 Chrome 或 Edge；單純觀看隨附範例可直接用瀏覽器。

產物是 HTML 簡報與 PDF。本包沒有 PPTX 匯出器；PDF 保留靜態畫面，互動與動畫由 HTML 提供。

## 先看範例：不用輸入 CLI

1. 下載本週資料夾或週包 ZIP 並解壓，保持目錄完整。
2. 用瀏覽器開啟 [Attention 範例](completed/deck-atelier/examples/attention/deck.html)。原始範例會連線取得 Google Fonts。
3. 用方向鍵換頁；按 `G` 看總覽、`M` 切換動畫、`T` 切換亮暗色、`Y` 選風格、`S` 開講者視窗。
4. 按 `E` 進入文字編輯，修改標題後按 `Ctrl+S`。瀏覽器可能詢問儲存位置，或改為下載檔案；確認存到哪個檔案後再關閉。

隨附 Attention 範例共有 15 頁，供學習故事線、SVG 圖解與引擎用法。示意權重、引用數與年代敘述應依原始來源重新核對，範例內容沒有經本週獨立事實查核。

## 安裝技能

請將整個 [completed/deck-atelier](completed/deck-atelier/README.md) 資料夾複製到技能目錄，不能只複製 `SKILL.md`。

- Codex：`%USERPROFILE%\.codex\skills\deck-atelier\SKILL.md`。
- Claude Code：目前專案的 `.claude/skills/deck-atelier/SKILL.md`。
- 若同名技能已存在，先備份或更名，確認版本後再替換；重新開啟工作階段並確認能讀到技能。

原始技能以 Claude Code 敘述為主。Codex 使用時，請讓 Agent 將來源中的宿主操作對應到當前可用工具，依核准權限執行。首次安裝的人類冷啟動驗收仍待完成。

## 用自己的資料完成第一份簡報

把來源檔與以下要求交給已載入技能的 Agent，基本路徑無須手寫指令：

```text
使用 $deck-atelier，讀取我提供的 Markdown，製作繁體中文 8 頁簡報。
對象：初次接觸這個主題的學員；場合：10 分鐘課堂分享。
先完整理解來源並提出 storyline.md：一句核心論點、SCQA、每頁行動標題、
視覺證據與來源位置。讓我確認故事線後再製作。
使用 Swiss 風格、16:9；每頁一個主張，附講者備註。
輸出到新的專用資料夾，保留原始檔；先做好靜態版，再加入動態。
建置靜態／動態 HTML，完成逐頁截圖、字型及溢出檢查，輸出 PDF。
先告知需要的下載與外部連線；Google Fonts 字元子集查詢須先徵得我同意。
遇到缺少依賴或未完成查核，明確列出待辦與限制。
```

已啟用技能但宿主不接受 `$` 呼叫時，直接指定 `deck-atelier` 與安裝位置。

## 操作與交付

十種風格：`swiss`、`press`、`lab`、`tokyo`、`kinfolk`、`dopamine`、`glitch`、`geometric`、`postmodern`、`riso`。切換風格後須重新做逐頁 QA；字型與換行會改變。

鍵盤：方向鍵／空白鍵推進、`F` 全螢幕、`S` 講者視窗、`G`／`Esc` 總覽、`M` 動畫、`T` 亮暗色、`Y` 風格、`E` 文字編輯、`B` 黑幕。互動時請依畫面提示操作。

請保留 `storyline.md`、可編輯的 `deck.html` 與其 `engine/`、素材及來源對照，再交付建置後的靜態／動態 HTML、PDF、截圖與問題清單。只分享你有權公開的資料；HTML 內的隱藏講稿也會隨檔案交付。

## 成果證據與通過標準

- 故事線：核心論點清楚；每頁行動標題連成可講述的順序。
- 內容：數字、引文、圖解均能回指來源；示意資料有明確標示。
- 畫面：逐頁檢查標題、CJK 換行、SVG 文字、圖表、頁碼及對比，沒有溢出或缺字。
- 操作：確認靜態／動態兩版都可開啟；逐步動畫、講者備註與儲存位置符合預期。
- 交付：用另一個資料夾打開交付檔；若要宣稱離線可用，須實際斷網重開並確認外部字型與素材都已移除或嵌入。
- QA：保留截圖、檢查 JSON 與未通過項目。`snapshot --check` 的結束碼為 0 仍需閱讀 `issues` 和字型狀態。

## 失敗時的重試方式

先保留現有成品與來源，查看[疑難排解](docs/troubleshooting.md)，在新的專用資料夾重試。`ingest.py --out` 會先清除該輸出位置的 `chunks/`、`frames/`、`figures/`、`pages/`，請勿指向既有素材目錄或專案根目錄。

## 文件導覽與版本

- [課堂講義](lesson.md)：從來源到故事線、靜態版、動畫與交付。
- [安裝與依賴](docs/setup-and-dependencies.md)／[架構與資料流](docs/architecture.md)。
- [隱私與內容權利](docs/privacy-and-content-rights.md)／[功能限制](docs/limitations.md)。
- [疑難排解](docs/troubleshooting.md)／[驗證紀錄](docs/verification.md)／[來源與分發範圍](docs/source.md)。

2026-10-22：建立 W43 學員包，保留 21 個來源技能檔案，補齊學員導覽與六項離線契約測試。來源執行程式未修改；技能入口的六個參考資料欄位改成可點擊連結。來源未附 LICENSE／NOTICE，本週標記授權未指定，ZIP 不附根目錄 LICENSE，亦不套用根目錄 MIT。
