# 安裝、操作與排錯

## 環境

- Python 3.10+。核心腳本只用標準函式庫。
- FFmpeg 與 FFprobe；FFmpeg 需 libx264、AAC、MJPEG、PCM16 編碼器。燒錄字幕另需 subtitles/libass 與中文字型。安裝來源見 [FFmpeg 官方下載](https://ffmpeg.org/download.html)。
- 無逐字稿時可選配 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)：`python -m pip install faster-whisper`。本技能以 CPU/int8 轉寫，首次使用模型名稱會下載模型；模型與 Python 環境不含於技能 ZIP。可傳本機模型目錄。

```text
python <SKILL_DIR>/scripts/highlights.py doctor
python <SKILL_DIR>/scripts/highlights.py doctor --ffmpeg <path-to-ffmpeg> --ffprobe <path-to-ffprobe>
```

doctor 回傳 0 代表核心工具可執行且必要編碼器存在；選配 ASR 未安裝不影響已有字幕的流程。FFmpeg 與 FFprobe 不在 PATH 時，所有媒體命令都帶同樣的覆寫參數。

## 自然語言使用

安裝後，給 agent 本機檔案與這類需求：

> 使用 Video Highlights，分析這支一小時訪談，挑 6 個最值得分享的片段，每段 45–75 秒，同時輸出直式和橫式，附每段評分、理由與字幕。影片：D:\Media\interview.mp4，字幕：D:\Media\interview.srt。

agent 應自行完成 prepare → 讀完整份逐字稿／候選視聽精讀 → 填 candidates → select → render → 驗收。需要使用者提供的只會是缺失的素材、無法推斷的約束或未授權的外部服務存取。

## CLI 分階段操作

以下 `<SKILL_DIR>`、`<work>` 與影片路徑都需換成實際位置；路徑有空白時加引號。Windows 使用 `python` 或 `py -3`；macOS/Linux 視安裝方式使用 `python3`。

```text
python <SKILL_DIR>/scripts/highlights.py prepare <interview.mp4> --srt <interview.srt> --out <work>/source
python <SKILL_DIR>/scripts/highlights.py prepare <interview.mp4> --asr-model small --language zh --out <work>/source-asr
```

上面是替代選項，選一種輸入方式。`--transcript-json` 接受 `{ "segments": [{"start":0,"end":3,"text":"…"}] }` 或直接陣列。SRT/JSON 時間必須與原片同步；SRT 讀 UTF-8，保留原文字，不自動繁簡轉換或改寫專名。轉寫模型回傳空稿時留下明確缺口。

prepare 預設 `--chunk-seconds 300 --overlap 20 --every 60`。這是讀取和導航粒度，與成片長度分開。腳本沒有語義評分；必須由 agent 依 SKILL.md 真正分析後，建立符合 [契約](contract.md) 的 candidates.json。

```text
python <SKILL_DIR>/scripts/highlights.py inspect <work>/source/project.json --start 110 --end 190 --every 3 --out <work>/source/evidence/H001
python <SKILL_DIR>/scripts/highlights.py select <work>/source/project.json <work>/candidates.json --out <work>/selection --min-seconds 45 --max-seconds 75 --count 6 --min-score 65 --per-topic 2
python <SKILL_DIR>/scripts/highlights.py validate <work>/selection/plan.json
python <SKILL_DIR>/scripts/highlights.py render <work>/selection/plan.json --out <work>/exports --formats portrait landscape --height 1080
```

`--height` 指輸出畫布的垂直像素數，寬度依比例取最接近的偶數。因此 height=1080 的 landscape 為 1920×1080、portrait 為 608×1080；需要 1080×1920 直式時另跑 `--formats portrait --height 1920`。方形用 square；source 保留來源顯示比例並依 height 縮放。標準 H.264 4:2:0 偶數尺寸可能使比例有小幅捨入，metadata 記錄實際結果。

取景由每段的 framing 設定控制：pad 保留完整畫面補黑邊；crop 依固定 x/y 位置填滿畫布，需視覺檢視與理由。未包含人臉追蹤、動態縮放或分割多人視窗。

燒字幕加 `--burn-subtitles`；預設只輸出可編輯 SRT。原片已燒有字幕時留意重疊。字幕跨越切點時會裁其顯示時間並保留完整 cue 文字，需回看片尾／片頭是否顯示未說出的詞；優先在選段時避開此情況，必要時人工對齊後修訂字幕。

## 產物與續跑

```text
work/
  source/project.json             來源 hash、規格、逐字稿與分塊索引
  source/transcript.json          原片座標逐字稿
  source/chunks/*.md              全片閱讀材料
  source/frames/*.jpg             稀疏概覽
  source/audio.wav                有音軌才產生；mono16k 分析副本
  source/evidence/H001/            候選預覽、幀圖與時間映射
  candidates.json                 agent 編寫的可追溯候選
  selection/plan.json              通過約束的剪輯計畫
  selection/HIGHLIGHTS.md          全片主題地圖、分數、理由、未入選原因
  selection/scores.csv             可用試算表比較的分項分數
  exports/H001-portrait.mp4        每段各比例成片
  exports/H001-portrait.srt        已改為片段相對時間
  exports/metadata/render.json     FFprobe 驗證、視聽狀態與實際檔案規格
```

產物路徑可含本機原片絕對位置。要分享分析案，需一起搬移來源和證據，再更新 project.source.path 及 plan.project、核對 hash 並 validate。技能安裝包沒有使用者素材或本機路徑依賴。

繼續同一素材時不必重新轉寫：核對 SHA-256 後重用 source，新增 evidence 目錄，修正 candidates，再輸出 selection-v2 / exports-v2。`.incomplete` 或 render.failed.json 表示該階段未完成，保留問題紀錄並重跑到新目錄。

## 常見狀況

| 狀況 | 處理 |
| --- | --- |
| 缺 FFmpeg 或 libx264 | 執行 doctor，指定含需要編碼器的 FFmpeg 完整路徑 |
| 字幕超出原片 | 檢查字幕是否同一剪輯版本、是否有偏移；先修正時間，不直接截掉錯誤 |
| 媒體起點／音畫差超過 0.1 秒 | 先製作同步檢查過的零點副本，再用同一時間軸字幕；不要各自重置音視訊造成偏移 |
| 無候選入選 | 讀 HIGHLIGHTS.md 的排除原因，重找自然句界或和使用者調整規格 |
| 僅能讀稿／看圖 | 完成能支持的草稿、採 pad、維持 partial，列待聆聽／待觀看項目 |
| 中文燒字幕缺字 | 安裝可用中文字型或交付 SRT，實際看圖確認；編碼成功不代表字形正確 |
| 影片沒有語音 | 本技能以有語言內容的長片為主；可分析可見內容，但目前選段契約要求帶時間文字依據，無依據時不產生假引用 |

## 開發驗證

```text
python -m unittest discover -s tests -v
python tests/smoke_workflow.py --out <new-smoke-directory> --ffmpeg <ffmpeg> --ffprobe <ffprobe>
```

整合測試以 `VH_FFMPEG`、`VH_FFPROBE` 環境變數指定工具；未提供且 PATH 不含工具時媒體測試會 skip，不能將 skip 報作通過。smoke 使用一小時合成素材和人工測試字幕驗證整個 CLI 流程；不代表真實訪談理解或 ASR 品質。
