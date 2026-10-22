# 安裝、依賴與進階指令

基本學習路徑見[學員 README](../README.md)，可請 Agent 代為執行。以下指令均在 `completed/deck-atelier/` 執行；`decks/`、`exports/`、`qa/` 是你自己的工作輸出，不屬於本週隨附內容。

## 環境需求

| 用途 | 依賴 | 注意事項 |
|---|---|---|
| 新建、風格、建置 | Node.js 22+，建議 24 | 無 npm 套件依賴；截圖使用全域 WebSocket，較舊 Node 不適用 |
| Markdown／TXT 匯入 | Python 3.10+ | 可直接執行，先確認 UTF-8 |
| PDF／EPUB／Office 等匯入 | uv、Python；依 PEP 723 腳本宣告安裝 | PyMuPDF、pymupdf4llm、markitdown[office]、OpenCC 等，會下載套件 |
| CJK 分詞 | uv 與 `phrase.py` 的宣告依賴 | BudouX 與 ICU；Windows 請先設定 `PYTHONUTF8=1` |
| 媒體／YouTube | FFmpeg、yt-dlp、Whisper 等路徑 | 可能下載媒體、套件與模型，耗時及空間另計；本週未跑實際 ASR |
| 截圖、PDF | Chrome 或 Edge | Windows 自動搜尋僅涵蓋特定 Chrome 路徑；Edge 請設定 CHROME_PATH |

Python 與 uv 必須能從宿主執行環境找到。FFmpeg 建議先自行安裝並加入 PATH；腳本的自動 fallback 不保證適用每台 Windows。轉檔能力受工具支援、檔案結構及權限影響。

## Windows PowerShell 範例

```powershell
$env:PYTHONUTF8 = '1'
$env:CHROME_PATH = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
node scripts/new_deck.mjs decks/my-first-deck --title "我的第一份簡報" --style swiss
```

請確認 Edge 的實際位置；使用 Chrome 時改成 Chrome 執行檔。新建器會複製引擎、建立五頁模板與來源／素材資料夾，內容仍須由你與 Agent 完成。

```powershell
python -B scripts/ingest.py "我的來源.md" --out decks/my-first-deck/source/import-001
# PDF 等格式需依宣告安裝套件，例如：
uv run scripts/ingest.py "有權使用的來源.pdf" --out decks/my-first-deck/source/import-002
node scripts/set_style.mjs decks/my-first-deck/deck.html --style tokyo
node scripts/build.mjs decks/my-first-deck/deck.html --out exports/my-first-deck --name my-first-deck
node scripts/snapshot.mjs exports/my-first-deck/my-first-deck.html --out qa/my-first-deck --check --slides 1-99 --pdf qa/my-first-deck/my-first-deck.pdf
```

每次匯入使用新的衍生資料夾。`--lang` 表示媒體原始口語語言，和最終簡報語言分開處理。先取得原語字幕／辨識結果並保留來源，再做翻譯與敘事整理。

## 動畫與十種風格 QA

```powershell
node scripts/snapshot.mjs exports/my-first-deck/my-first-deck.html --out qa/steps --steps --motion on --slides 3
node scripts/snapshot.mjs exports/my-first-deck/my-first-deck.html --out qa/film --film 3 --at 0,160,360,620,950,1500
node scripts/snapshot.mjs exports/my-first-deck/my-first-deck.html --out qa/styles --styles all --slides 1,2
```

先確認你選的頁碼有動畫／逐步內容。film 的早期畫格可能仍是前一頁，請以時間序列解讀。全風格預覽只涵蓋指定頁碼，其餘頁面仍須另驗。

## 建置與儲存行為

- `build.mjs` 產生靜態 `name.html` 與動態 `name-motion.html`，不修改來源 `deck.html`，但會覆寫同名輸出。
- 預設分詞與嵌字型可能觸發 uv／Google Fonts 網路請求。`--no-phrase --no-fonts` 可略過這兩步；略過字型時通常保留線上字型連結，無法據此宣稱離線可用。
- 圖片／字型缺失時可能警告後繼續。請打開輸出檔確認，必要時實際斷網測試。
- `new_deck --force` 會覆寫現有 deck；`--update-engine` 更新引擎。`set_style` 會修改原檔，必要時更新同目錄引擎，操作前先備份。
- 瀏覽器 `Ctrl+S` 會開啟檔案選擇器或下載副本，未實作固定檔案控制代碼的自動覆寫。修改後確認檔案位置並重新建置交付版。
