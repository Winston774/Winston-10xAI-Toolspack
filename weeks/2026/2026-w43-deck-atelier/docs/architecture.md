# 架構與資料流

```text
來源文件／URL／媒體
  → ingest.py：source.md、manifest、chunks、figures／frames／pages
  → Agent 理解：來源核對、核心論點、SCQA、storyline.md
  → new_deck.mjs + 模板 + 版型／圖解參考
  → deck.html + engine/ + 自備 assets/ + 講者備註
  → 靜態 QA → 動態／逐步編排
  → build.mjs：CJK 分詞、內嵌引擎／本機素材／選定字型
  → 靜態 HTML + 動態 HTML
  → snapshot.mjs + 無頭瀏覽器：PNG、總覽、JSON 檢查、PDF
```

`ingest.py` 主要負責轉換與結構化輸出，故事線與內容判斷由宿主 Agent 完成。技能不提供獨立 LLM 服務；宿主處理來源時的模型、資料傳輸與費用依你使用的產品設定。

`atelier.css` 定義 1920×1080 舞台、版型、十種風格、亮暗色、列印與編輯顯示。`atelier.js` 提供換頁、逐步揭露、原生 Web Animations、講者視窗、總覽、風格切換與儲存。

新建器將引擎複製到每份簡報自己的 `engine/`。既有 Attention 範例直接連到技能的 `assets/engine/`，移動範例時應保留目錄或先建置成單檔。

`phrase.mjs`／`phrase.py` 為 CJK 加入可斷行位置與字詞黏合，不處理已手動控制的部分、SVG 及講稿。`build.mjs` 使用 Google Fonts 取得字型子集，字型成功嵌入後才有機會完成離線交付。

`snapshot.mjs` 透過 CDP 控制獨立無頭瀏覽器，將各頁及動態狀態輸出為圖檔，並可產生 PDF。它會在輸入 HTML 旁建立暫存 `.snapshot-*` 檔案，結束後清除；輸入位置需要寫入權限。檢查結果為診斷資料，需另外解讀每頁的問題。
