# 疑難排解

## `Missing ffmpeg` 或 `Missing ffprobe`

在終端機確認：

```text
ffmpeg -version
ffprobe -version
```

若工具未在 PATH，安裝受信任來源的版本，或把明確執行檔路徑傳給 helper：

```text
python scripts/prepare_video.py <input.mp4> --out <new-output-dir> --ffmpeg <ffmpeg-path> --ffprobe <ffprobe-path>
```

路徑含空白時用 shell 的引號包住整個參數值。不要使用不明來源的可執行檔。

## `Output already exists`

helper 以新資料夾輸出，避免覆蓋既有 evidence。保留原資料夾，改用可辨識的新名稱，例如 `overview-v2` 或 `reveal-6.8-8.4`。不要為了重跑而直接刪除舊資料。

## URL 或串流輸入失敗

`prepare_video.py` 會拒絕 URL。先確保你有取得與分析的權利，再將檔案下載到受控的本機工作目錄。不要把含 token、簽章或帳號資訊的 URL 寫進公開文件。

## `VALID (partial)` 以外的驗證錯誤

依順序檢查：

1. `source` 是否有非空 path、64 位 SHA-256、正確 duration、`clock: video_start` 與布林 `audio_present`。
2. `evidence.path` 是否以 `analysis.json` 所在資料夾為根、存在且沒有離開資料夾。
3. 每個 event 是否有已標記 `reviewed: true` 的重疊證據、有效系統 ID 與有效 anchor。
4. `dense_frames` 是否引用至少兩個不同時間的幀，且 `max_gap_seconds` 等於實際最大間距。
5. `ready` 是否有全片事件覆蓋、全片視覺檢視、音軌存在時全片實際聆聽、素材需求、保留規則與零個阻塞未知項。

先從 [`completed/video-understanding/examples/partial-analysis/`](../completed/video-understanding/examples/partial-analysis/) 的可通過 `partial` 範例開始比較。

## Python 測試有 `skipped`

未設定 `VIDEO_TEST_FFMPEG` 與 `VIDEO_TEST_FFPROBE` 時，媒體整合測試會跳過。此結果只代表純 Python 單元測試已跑；不能視為 FFmpeg／FFprobe 整合驗證。設定兩個環境變數後再重跑：

```powershell
$env:VIDEO_TEST_FFMPEG = '<absolute-path-to-ffmpeg>'
$env:VIDEO_TEST_FFPROBE = '<absolute-path-to-ffprobe>'
python -X utf8 -m unittest discover -s completed/video-understanding/tests -v
```

## 不能確認畫面或聲音

沒有圖片檢視能力、播放能力或聆聽能力時，只保留可支持的 metadata 或逐字稿資訊，並列出缺口。ASR 完成、WAV 存在、幀圖被抽出都不能單獨支持「已聆聽」或「已看見」的描述。

## 需要回報問題

先移除影片、音訊、逐字稿、人物名稱、帳號、預簽名 URL、絕對路徑與 metadata，再提供：

- Python、FFmpeg、FFprobe 版本。
- 完整錯誤訊息。
- 已使用的命令與參數。
- 可公開的最小合成重現檔案。
- 期待結果與實際結果。
