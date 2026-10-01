# 資料契約

JSON 採 UTF-8，時間為有限數值秒，拒絕 NaN、Infinity 與布林值。schema_version 為 1。

## project.json（prepare 產生）

```json
{
  "schema_version": 1,
  "source": {"path": "/absolute/interview.mp4", "sha256": "64 lowercase hex", "duration": 3600.0, "width": 1920, "height": 1080, "has_audio": true, "clock": "zero_based_media"},
  "transcript": {"method": "srt", "language": "zh", "segments": [{"id": "S000001", "start": 1.0, "end": 4.0, "text": "原始台詞"}]},
  "chunks": [{"id": "CH001", "start": 0.0, "end": 300.0, "file": "chunks/CH001.md"}],
  "overview": [{"file": "frames/overview-000001.jpg", "requested_time": 0.0}]
}
```

字幕座標須與本機媒體零點一致。腳本自動接受容器與主要音視訊起點接近 0 的一般影片；特殊起點須先製作同步檢查過的正規化副本。FFmpeg 轉正畫面與非方形像素。requested_time 是抽樣請求時間，非逐幀 PTS 證據。

## candidates.json（agent 依原片填寫）

```json
{
  "schema_version": 1,
  "source_sha256": "same as project",
  "coverage": [{"start": 0.0, "end": 3600.0, "kind": "speech", "summary": "實際逐段閱讀後的主題摘要"}],
  "candidates": [{
    "id": "H001", "title": "忠於內容的標題", "topic": "主題一",
    "start": 120.0, "end": 175.0,
    "summary": "核心論點與必要條件", "hook": "片頭吸引力的依據", "reason": "為何值得保留",
    "quotes": [{"segment_id": "S000031", "text": "逐字稿中實際存在的片語"}],
    "scores": {"content_value": 4, "specificity": 4, "standalone": 4, "hook": 3, "narrative": 4, "emotion": 2, "actionability": 4, "audiovisual": 3},
    "confidence": "medium",
    "gates": {"complete_thought": true, "context_preserved": true, "faithful_claims": true},
    "review": {"visual": "sampled", "audio": "transcript_only", "evidence": ["frames/overview-000005.jpg"], "notes": "音訊未聆聽；切點待複核"},
    "framing": {"mode": "pad"},
    "unresolved": ["尚未聆聽原音"]
  }]
}
```

示意時間、引文、分數和檢視紀錄須由本次素材重建。coverage 依時間順序完整涵蓋原片，依主題拆段；kind 可為 speech、silence、unreviewed。未檢視範圍保留 unreviewed，候選不得落入其中。

review.visual 為 unreviewed / sampled / watched；review.audio 為 unreviewed / transcript_only / listened / no_audio（原片確無音軌）。evidence 為相對 project.json 目錄且存在的媒體路徑；觀看／聆聽無法由程式證明。confidence 為 low / medium / high，與分數分開。

裁切：`{"mode":"crop","x":0.5,"y":0.5,"reason":"已回看首中尾，主體位置固定"}`。x/y 為多餘寬高的裁切位置（0 靠左／上，1 靠右／下）。須有視覺檢視及證據；多人或移動採 pad。每段固定取景。

## plan.json（select 產生）

包含 project（project.json 絕對路徑）、source_sha256、constraints、weights、selected、rejected、status。selected 保留 candidate 並增加 score（0–100）、review_status（reviewed / partial）。render 再核對來源 hash、時間與規格。

partial 可輸出草稿 MP4，報告列明缺口。只有 visual=watched、audio=listened（或 no_audio）且無 unresolved 才標 reviewed。這是自述檢視狀態，結構驗證不等於人類視聽驗收。
