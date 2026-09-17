# Video Understanding v0.1.0 Preview

這是一個以繁體中文運作的 Agent Skill，用來把短影音整理成附時間證據的 `VIDEO_UNDERSTANDING.md` 與 `analysis.json`。它協助下一個 Agent 回看原片、補足缺口、建立素材依賴並規劃生成；它不包含影片生成或渲染 runtime。

## 先讀這三件事

1. 只處理你已確認有權利分析與使用的本機影片檔。helper 不會下載 URL。
2. 預設採本機處理。影片、畫格、WAV、逐字稿、metadata 與分析輸出屬私有工作資料；外部服務需取得針對該檔案的明確確認。
3. 本資料夾受 [LICENSE](LICENSE) 的 Hypit modified Apache-2.0 條款與額外條件約束。它不適用 Toolspack 根目錄的 MIT 授權推定。

詳細邊界請讀 [PRIVACY_AND_SAFETY.md](PRIVACY_AND_SAFETY.md)、[NOTICE](NOTICE) 與本週的 `docs/`。

## 安裝

將整個 `video-understanding` 資料夾複製到：

- Windows：`%USERPROFILE%\.codex\skills\video-understanding`
- macOS／Linux：`~/.codex/skills/video-understanding`
- 共用 Agent Skills：`~/.agents/skills/video-understanding`

重新啟動 Agent 後，用下面的請求開始：

```text
使用 $video-understanding，以本機優先方式分析我已授權的短影音。
請把工作輸出到 analysis/<影片名稱>/，先交付 partial，並在傳送任何資料到外部服務前向我逐檔確認。
```

## 需求

- Python 3.10 以上；兩支 Python scripts 只使用標準函式庫。
- FFmpeg 與 FFprobe，必須能讀取輸入影片、輸出 JPEG 與 16 kHz PCM WAV。
- 能實際檢視本機畫格、播放影片與聆聽音訊的工具。

核心 helper 不需要 API Key、雲端模型或帳號。任何雲端視覺、ASR、儲存或生成服務均屬獨立選擇。

## 快速流程

1. 在使用者工作目錄建立新的分析資料夾，例如 `analysis/my-short/`。
2. 以 helper 準備概覽證據：

```text
python <SKILL_DIR>/scripts/prepare_video.py <input.mp4> --out <analysis-dir>/evidence/overview --every 1
```

3. 真正檢視抽出的畫格；針對切點、快閃字、字幕變化或動作加做密集區段。
4. 用 `assets/VIDEO_UNDERSTANDING.template.md` 和 `assets/analysis.template.json` 建立交接文件。
5. 如實記錄看過、聽過與尚未檢視的範圍。音軌未完整聆聽時，保持 `partial`。
6. 驗證索引：

```text
python <SKILL_DIR>/scripts/validate_analysis.py <analysis-dir>/analysis.json
```

驗證器只檢查結構、時間、引用與檔案位置。它不會驗證畫面、音訊或語義內容。

## 合成範例與測試

- [`examples/partial-analysis/`](examples/partial-analysis/) 是不含真實媒體、可通過結構驗證的 `partial` 範例。
- `tests/` 含 30 個單元與媒體整合測試。未設定 `VIDEO_TEST_FFMPEG`、`VIDEO_TEST_FFPROBE` 時，7 個媒體測試會跳過；skipped 不等於通過。
- 來源和本週 Release 的驗證紀錄見 [VALIDATION.md](VALIDATION.md)。

## 目錄

```text
video-understanding/
  SKILL.md                     Agent 入口與工作邊界
  PRIVACY_AND_SAFETY.md        資料、權利、外部服務與未信任資料規則
  assets/                      主文件與 JSON 模板
  references/                  觀察方法、交接契約、工具與來源研究
  scripts/                     本機證據準備與結構驗證
  examples/partial-analysis/   合成、可驗證的 partial 範例
  tests/                       可重跑的標準函式庫測試
  LICENSE / NOTICE             上游條款與改寫範圍
```
