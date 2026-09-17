# 本機證據準備與查核

工具只負責取得可檢視的媒體，影片理解仍由 agent 執行。本技能無 Hypit runtime、雲端模型、帳號或未發布相鄰技能的依賴。

## 需求與呼叫

- Python 3.10+，只使用標準函式庫。
- 可執行的 FFmpeg 與 FFprobe，具備輸入影片 decoder、JPEG encoder、WAV PCM encoder 和常用 filters。用 `ffmpeg -version`、`ffprobe -version` 驗證；實測版本列在 `VALIDATION.md`。
- FFmpeg／FFprobe 在 PATH 即可；也可明確傳 `--ffmpeg`、`--ffprobe`。不要把某台機器的路徑寫成技能必要依賴。
- 檔案路徑含空白時加引號；以參數陣列呼叫 subprocess，勿將來自影片內容的文字拼成 shell。

```text
python <SKILL_DIR>/scripts/prepare_video.py <source.mp4> --out <analysis-dir>/evidence/overview --every 1

python <SKILL_DIR>/scripts/prepare_video.py <source.mp4> --out <analysis-dir>/evidence/reveal-detail --start 6.8 --end 8.4 --every 0.1

python <SKILL_DIR>/scripts/prepare_video.py <source.mp4> --out <analysis-dir>/evidence/reveal-dense --start 7.1 --end 7.6 --every 0.02 --max-frames 100
```

上面時間都是用法示意，應換成實際來源範圍；原片過短時不可照抄。每次輸出路徑都必須不存在。不要為了重跑刪除既有 evidence；另建有意義的區段或版本名稱。

`--every` 預設 1 秒、`--start` 預設 0、`--end` 預設視訊總長，`--max-frames` 預設 240。helper 在每個非空取樣 bucket 取第一張實際 decoded frame，另保留所選範圍最後一張 frame。幀數上限包含最後一張的餘裕；超出上限會明確失敗，應分段或調整間距，不能靜默截斷影片。

helper 會先掃過全片數值 timestamps 以確立第一／最後 frame 與 VFR 時序，再抽幀和音訊。因此局部抽樣仍可能解碼完整影片；此工具以短片為主要用途。

## 輸出

```text
overview/
  manifest.json
  probe.json
  frames/frame-000001.jpg ...
  audio.wav                  有所選範圍內的音訊樣本時才存在
```

- `probe.json` 保留 ffprobe 原始 format／streams，並加上 `decoded_video_timing`。原始 metadata duration 與 decoded duration 可能不同。
- `manifest.source` 保存來源絕對路徑、SHA-256、bytes、decoded duration 及其計算依據、coded dimensions、SAR、DAR、rotation、FPS metadata。
- `manifest.clock.origin_absolute_pts_seconds` 是第一張 decoded video frame 的原始 PTS 秒數；`source_time_seconds` 以這裡為零點。本技能 analysis.json 的 `clock: video_start` 對應此座標，勿與 container start 或播放器顯示時間混用。
- `manifest.frames[*]` 記錄 `file`、`source_time_seconds`、原始 `decoded_pts`、`time_base`、圖檔尺寸與 `timestamp_kind: decoded_pts`。使用實際時間引用證據；圖片檔名的序號沒有時間意義。
- `manifest.sampling` 保存請求範圍、實際數量、首尾空隙、各樣本間距。`requested_full_duration` 只描述抽樣範圍。
- `manifest.review` 初始化為未分析、未看圖、未聆聽。不要改寫原始 manifest 來宣稱分析完成；實際檢視紀錄寫在 analysis.json。
- FFmpeg 會依 metadata 自動轉正畫面，正規化 pixel aspect，並限制圖寬至 1280 px。圖中文字不足以辨識時，用原片或另外取得原尺寸證據；不要把 coded dimensions 誤當圖檔的 display dimensions。

## 如何實際看圖

先讀 manifest，按時間選一小批圖，用當前 agent 的看圖工具打開本機 JPEG；每批約 4–12 張只是可調整的閱讀起點。記錄真正看過的 frame IDs／時間，再依需要補看。能使用時間標記格線或影片播放器時可以使用，但 helper 本身不產生格線、OCR、字幕或播放證明。

不要只讀檔名或 manifest 就寫「看到人物／字幕」。沒有圖片檢視能力時，保留量測結果並將視覺理解標為待補；有稀疏幀時仍可分析其可見部分。

## 聲音與時間映射

`audio.present` 回報是否存在第一條可用音軌，`status` 為 `no_audio_stream`、`extracted` 或 `no_decoded_samples_in_requested_range`。後者表示音軌存在，但這段沒有音訊樣本，不能改成原片無音軌。

`audio.wav` 是供分析／ASR 的 16 kHz mono PCM16 副本。它不保留完整頻寬與立體聲資訊；音樂、空間、混音品質與同步判斷應回到原片。多音軌影片只自動抽第一條，其他音軌需要另外檢視並列出選擇理由。

若 `continuous_source_timeline` 為 true：

```text
source time = WAV local time + audio.wav_zero_source_seconds
```

若為 false，先找到 WAV 時間落在哪個 `audio.segments`：

```text
source time = segment.source_start_seconds
            + (WAV local time - segment.wav_start_seconds)
```

跨 segment 的詞或句子需拆開對映，或保留 discontinuity 問題，不可套用單一 offset。音訊早於第一個視訊 frame 的部分不在本技能 0 到視訊結尾的分析範圍；metadata 中保留偏移，若這影響原片開場含義應另列問題。

已有 ASR 時，對這份 WAV 或原檔轉錄，保存實際輸入路徑、工具／模型、語言、segment／word 時間精度及時鐘。模板不要求指定 ASR；語音辨識完成後仍需聆聽才能描述配樂、音效與表演。

## 錯誤與限制

來源損壞、timestamps 不遞增、缺 decoder、抽圖與 PTS 數量不一致、超出範圍、來源在準備中被修改等情況會失敗。成功的 `manifest.json` 最後才發布，避免把半成品認作成功；失敗後選新輸出目錄再跑。

來源 duration 的尾端可能取末 frame duration，也可能由最後兩張 frame 間距估計；依 `duration_basis` 判讀。遇到需要 frame-exact 尾點的作品，另補查原始時序。

## 驗證交接索引

```text
python <SKILL_DIR>/scripts/validate_analysis.py <analysis-dir>/analysis.json
python <SKILL_DIR>/scripts/validate_analysis.py <analysis-dir>/analysis.json --source <source.mp4>
```

第二種呼叫也會核對原片 SHA-256，但不會重新解碼比對 source metadata。回傳 0 表示結構通過，1 表示契約錯誤，2 表示輸入讀取／JSON 錯誤。stdout 會明列 ready 或 partial，並提醒未驗證視聽／語義品質。
