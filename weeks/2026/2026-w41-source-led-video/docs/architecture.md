# 資料流與時間座標

```text
來源影片＋完整逐字稿＋來源權利
  → 全片理解／research → questions＋candidates → score
  → opening-selection＋rundown＋narration-plan
  → 核准文本 → 外部錄音／TTS → 最終 WAV＋核聽
  → cut＋字幕＋markers → resolve → check
  → build_film → HyperFrames 工程 → 瀏覽器檢查／渲染
  → 最終音畫審閱＋縮圖＋來源說明＋QA
```

閱讀、取捨、事實核對由 Agent 與審閱者完成；CLI 處理結構、分數、切片、時間、檔案與工程。只做企劃時可停在 rundown，不需啟動完整建片依賴。

| 座標 | 用途 | 範例 |
|---|---|---|
| 原片秒數 | 來源切點、來源字幕、marker | 切片 10–25 秒；marker 在原片 14 秒 |
| 最終 WAV 局部秒數 | 旁白字幕、card_beats、術語核聽 | 每段 WAV 各自從 0 開始 |
| 最終影片秒數 | resolved-plan 與整片輸出 | 上述切片在成片 40 秒開始，marker 對應 44 秒 |

`resolve` 用實際媒體時長建立影格對齊的計畫；旁白前後留白亦計入。它綁定部分輸入（包含 rundown、profile、旁白計畫、核准文本、旁白字幕與 WAV）以偵測過期，未對所有來源與視覺素材提供全面不可變保證。改動原片後應重新切片，再 resolve／建片與驗收。

技能入口載入七份參考文件；九個 scripts 搭配 `assets/engine/paper_documentary.py` 生成紙感工程。`templates` 六份 JSON 為新集初始資料，`agents/openai.yaml` 提供工具顯示資訊；`version.json` 與 `INDEX.md` 記錄版本及內容索引。
