# 迅剪 Local Studio｜本地剪輯工作台

> **W37 發布註記（2026-09-10）**：以下是來源 commit 的歷史技術說明，僅供追溯設計與功能脈絡。文中關於 ASR、瀏覽器、MP4、MCP、`artifacts/`、`output/`、`.local-editor/` 或 `.venv/` 的成功敘述與檔案引用，並非本週發布的現況證據，且相關本機資料與驗收產物沒有隨 ZIP 附上。作者機器路徑已改成 generic placeholder；本輪可採信的測試與未驗收範圍請看[W37 驗證紀錄](../../docs/verification.md)。

繁體中文的本機影片剪輯器，提供智能剪口播、字幕工作台、多軌剪輯，以及供 Codex／Claude Code 呼叫的 MCP。原有 `agent-video` 與 Seedance CLI 保留在本專案。

## v0.2：Agent 理解與驗收閉環

Agent 現在可透過正式工具取得目前工作情境、剪輯方向與區間聲畫證據，再完成提案、預覽、套用及驗證。工作台的 **Agent 理解工作台** 與 MCP 使用相同服務。

| 新入口 | 能回答的問題 |
|---|---|
| `editor_get_context` | 正在剪哪個專案、精確版本、選取項目、播放頭、區間、目標與保留規則、缺少哪些分析 |
| `editor_inspect_range` ＋ `editor_read_evidence` | 來源或合成時間軸實際顯示什麼；直接取得原生影格、音訊與短片資源、逐字稿及圖層映射 |
| `editor_analyze_range` | 區間低音量、畫面變化、語速、文字相似候選與字幕問題；偵測結果與刪除價值分開標示 |
| `editor_prepare_edit` ＋ `editor_get_edit` | 修改的精確差異、前後快照、受影響項目與字幕對齊副作用；可取得兩側合成預覽 |
| `editor_apply_edit` | 依精確版本整批套用；全部成功或全部不寫入，一次復原可還原 |
| `editor_verify_edit` ＋ `editor_record_review` | 結構／字幕檢查、實際審閱檔案、抽樣影格與連續聲畫範圍，以及尚未確認的切點 |
| `editor_review_caption` | 指定一句做本機語音複核，取得候選文字、詞級時間及辨識機率，保留原稿供審閱 |

在 Agent 面板保存「剪輯方向」，再選取最多 30 秒區間按「聲畫證據」或「分析區間」。智能剪口播與逐字稿刪句現在會先開啟批次提案，提供前後預覽再確認套用。

字幕對齊明示 `valid / stale / missing`；`valid` 表示文字與詞級區間符合結構契約，不保證辨識文字正確。只修改文字或時間會揭露對齊失效。語音重新辨識的候選可經審閱後以 `caption_update changes.words` 一起保存；專用 forced alignment 尚未支援。

聲畫證據生成不代表已完成審閱。只看一張影格只記錄該抽樣時間；音訊與短片才可登錄其連續範圍。原始素材與合成時間軸、提案 before／after、不同版本的審閱紀錄不會混用。MCP 客戶端或模型如果不支援音訊，聽感仍須保留未確認。

架構與驗收：[Agent 理解升級](docs/agent-understanding-v02.md)、[MCP 完整契約](docs/local-editor-mcp.md)。

## 直接啟動

Windows 雙擊 **start-local-editor.cmd**，或在 PowerShell：

```powershell
cd <project-root>
.\start-local-editor.ps1
```

開啟 [http://127.0.0.1:8321](http://127.0.0.1:8321)。服務需保持執行；`Ctrl+C` 可停止前景啟動的服務。

本次已在專案 `.venv` 完成 editable install、安裝 Whisper small 本機模型與 OpenCC，並驗證完全離線的中文語音辨識。移到另一台電腦時：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
# 安裝 FFmpeg／FFprobe 並加入 PATH 後，下載本機語音模型：
.\scripts\setup-local-asr.ps1
.\start-local-editor.ps1
```

首次模型安裝會從官方 Hugging Face 模型庫下載約 486 MB；正常辨識採離線載入，不上傳影片或音訊。詳細依賴狀態可在工作台「環境」查看。預設 CPU int8；CUDA 需要另外具備相容 GPU runtime。

## 已完成的工作流程

1. **建立專案**：命名與選擇橫式、直式或方形畫布；本機自動儲存。
2. **匯入素材**：影片、音訊、圖片；支援檔案選擇、拖放與完整路徑匯入，建立本機副本。
3. **加入時間軸**：點素材上的＋，或拖到主影片、疊加畫面、音訊軌。
4. **智能剪口播**：調整靜音門檻、最短停頓、保留停頓；產生候選後試聽、勾選與套用。來源逐字稿可同時檢閱。
5. **字幕校正**：本機語音辨識或 SRT／VTT 匯入；逐句修改、調時間、尋找取代、刪文剪片、樣式調整。
6. **精修畫面**：拖曳、修剪、分割、複製、刪除、變速、位移、縮放、旋轉、透明度、調色、音量與淡入淡出。
7. **匯出**：H.264／AAC MP4、字幕燒錄；字幕另存 SRT／VTT／TXT。結果與背景工作紀錄保存在本機。

智能剪口播採可檢查的本地規則：音量靜音偵測、獨立語助詞及相鄰完全相同字幕。語意贅句判斷、重錄最佳版本選擇與呼吸聲分類仍待擴充。沒有逐字時間的外部 SRT 若被局部剪除，應在工作台校正該句字幕。

## 功能覆蓋與界線

| 模組 | 目前能力 | 後續擴充 |
|---|---|---|
| 專案 | SQLite、自動保存、版本防衝突、100 步復原重做 | 專案封裝、搬移與素材重新連結 |
| 剪輯 | 主影片／疊加／音訊、標題與字幕獨立顯示；分割、移動、修剪、連動刪除 | 動態增刪軌道、群組、磁吸細節、代理媒體 |
| 智能剪口播 | 真實靜音偵測、贅詞／重複候選、逐字稿剪片、試聽與復原 | 語意贅句、重錄句排序、呼吸分類 |
| 字幕 | 本機 Whisper＋繁體轉換、逐字時間映射、手動校正、SRT／VTT／TXT | 說話人分離、雙語字幕、逐字動畫、進階斷句 |
| 畫面 | 疊加、位移、縮放、旋轉、透明度、亮度／對比／飽和度 | 關鍵影格、轉場、遮罩、色鍵、追蹤、防震、LUT |
| 聲音 | 混音、音量、變速、淡入淡出；API 可啟用降噪與音量正規化 | 音量表、ducking、分離人聲、錄音、曲線變速 |
| 匯出 | 真實 MP4、尺寸／畫質設定、字幕燒錄、背景佇列與下載 | NVENC、兩階段 loudness、更多編碼、批次輸出設定 |
| Agent | 25 個 stdio MCP 工具、情境同步、原生聲畫證據、批次提案／預覽／驗證、共享剪輯方向 | 語意視覺分析、強制對齊、素材層級增量分析快取 |
| 桌面 | Windows 一鍵啟動、本機瀏覽器工作台 | 安裝包、自動更新、完整離線依賴安裝 |

這是可實際剪輯與輸出的本地版本；尚未達成剪映全部功能等價。完整分工、架構與 TODO 見 [架構文件](docs/local-editor-architecture.md)。預覽的 CSS 調色為近似結果、音量最高預覽至 1 倍；正式匯出由 FFmpeg 處理。分割會重新計算片段的淡入淡出，精確延續曲線需要後續 envelope 模型。

## Agent／MCP 入口

```powershell
.\.venv\Scripts\python.exe -m local_editor mcp --url http://127.0.0.1:8321
```

先保持本機工作台服務執行。MCP 程序透過 stdin/stdout 接受 JSON-RPC，啟動後等待輸入屬正常狀態。完整 Codex TOML、Claude Code JSON 與工具參數見 [MCP 操作契約](docs/local-editor-mcp.md)。可直接複製 [Claude Code 設定範例](examples/local-editor.mcp.json) 或 [Codex 設定範例](examples/local-editor.codex.toml)；未修改使用者全域設定。

Agent 工作順序：`讀取精確版本 → 辨識／匯入字幕 → 產生提案 → 指定 candidate_ids 套用 → 校正 → 匯出 → 查詢工作結果`。長工作先回傳 job ID，讀取專案會省略波形以降低 token。

## v0.1 驗收與證據（歷史紀錄）

- Python：完整收集並執行 51 項，零跳過；初次發現的舊工具路徑優先序問題已修復，對應 9 項定向重跑通過。JavaScript：6 項通過。
- 真 FFmpeg：裁切、變速、空隙、圖片、無聲影片、疊加、混音、字幕與標題、降噪／正規化、不同輸出尺寸皆有實際編碼與解碼測試。
- 真本機 ASR：17.16 秒 Windows 合成中文語音產生 4 段繁體字幕；瀏覽器也完成相同流程。
- 瀏覽器：從空白目錄建立專案；6 秒素材剪除 2 段靜音後為 4.4 秒；逐字稿剪句後為 3.1 秒；復原回到 4.4 秒；字幕、標題與 MP4 下載完成。
- UI 匯出檔案再次驗證為 1920×1080、30fps、4.4 秒、H.264／AAC，完整解碼 exit 0。
- 真 stdio MCP：初始化、15 個工具清單、讀取正式服務狀態與 ping 成功。

驗證文件：[瀏覽器驗收](docs/local-editor-acceptance.md)、`artifacts/verification/automated-tests.json`、`artifacts/verification/ui-export.json`。本機驗收成品：`output/local-editor-demo/ui-verified-final.mp4`。測試素材均有合成標示；尚未以使用者實際長篇口播驗證辨識品質與效能。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/editor_frontend.test.mjs
.\scripts\verify-local-asr.ps1
```

## 本機資料與原有工具

`local_editor/` 包含剪輯核心、字幕映射、媒體引擎、服務／MCP 與 `web/`。`.local-editor/` 保存專案、素材副本、模型、工作與匯出；`output/`、`artifacts/` 為驗收產物，已列入忽略規則。前端採原生 JavaScript 模組，無需 npm build；伺服器只綁定 loopback 且限制同來源。瀏覽器無法直接以編輯命令注入素材路徑。

---

# 原有 KIE AI Seedance Client

This workspace contains:

- `seedance`: a small Python CLI for KIE AI Bytedance Seedance 2.0.
- `agent-video`: a Claude Code style Agent Video Editor pipeline modeled after the referenced video.

## Agent Video Editor

The editor is a project-folder pipeline, not a monolithic GUI. Each job follows the same seven steps:

1. Intake
2. Rough cut
3. Graphics
4. Second pass
5. Captions
6. Background music
7. Export

Format variants are preset-driven:

- `short-explainer`: 9:16, top-half graphics cards, centered burned-in captions.
- `short-tiktok-raw`: 9:16, hook card then raw footage, low captions.
- `long-form-youtube`: 16:9, glass/zoom graphics, no burned-in captions.

### Install locally

```powershell
cd <project-root>
python -m pip install -e .
```

Optional subtitle fetching:

```powershell
python -m pip install -e ".[subtitles]"
```

### Check external tools

```powershell
agent-video doctor
```

For full media automation, install these separately and put them on `PATH`:

- `ffmpeg` and `ffprobe`
- `whisperx`
- `yt-dlp` or the optional Python subtitle dependency

If a tool is installed but Codex does not see it on `PATH`, set it in `.env`:

```powershell
FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
FFPROBE_PATH=C:\ffmpeg\bin\ffprobe.exe
WHISPERX_PATH=C:\path\to\xunjian-local-video-editor\.venv\Scripts\whisperx.exe
YT_DLP_PATH=C:\path\to\Python\Scripts\yt-dlp.exe
```

`agent-video` also checks this workspace's `.venv\Scripts`, plus common Windows locations such as Scoop shims, Chocolatey, WinGet links, and Python Scripts folders. The project invokes `ffmpeg`/`ffprobe` as external CLIs instead of vendoring them.

### Create and run a job

```powershell
agent-video init demo --format short-explainer --raw C:\path\to\raw.mp4
agent-video run demo --format short-explainer
```

Dry run without real video processing:

```powershell
agent-video run demo --format short-explainer --raw C:\path\to\raw.mp4 --dry-run
```

Outputs are promoted to:

```text
outputs/<job>.final.mp4
```

### Fetch YouTube subtitle summary

The referenced video exposes English auto-generated captions. The repo stores a summary at `references/XeTAlZiIWHE.caption-summary.json`, not the full transcript.

```powershell
agent-video fetch-subtitles https://www.youtube.com/watch?v=XeTAlZiIWHE
```

Writing a full VTT file requires an explicit rights confirmation:

```powershell
agent-video fetch-subtitles https://www.youtube.com/watch?v=XeTAlZiIWHE --write-vtt --i-own-rights
```

### Project structure

```text
projects/<job>/
  raw/
  work/
  scripts/
  graphics/
  captions/
  music/
  review/
  premiere/
  exports/
  logs/
  tmp/
```

Core method files:

- `skills-lock.json`
- `skills/*/SKILL.md`
- `agent_video_editor/pipeline.json`
- `agent_video_editor/presets`

---

## Seedance Client

The KIE docs for Seedance 2.0 use:

- `POST https://api.kie.ai/api/v1/jobs/createTask`
- `GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId=...`
- model id `bytedance/seedance-2`

## Setup

```powershell
cd <project-root>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

Edit `.env` and replace `KIE_API_KEY` with your KIE AI API key.

## Create a text-to-video task

```powershell
seedance create --prompt "A cinematic Taipei street at night after rain, neon reflections, slow dolly forward" --duration 15 --resolution 720p --aspect-ratio 16:9
```

## Check status

```powershell
seedance status task_bytedance_1765186743319
```

## Create, wait, and download

```powershell
seedance generate --prompt "A cinematic Taipei street at night after rain, neon reflections, slow dolly forward" --download
```

Downloaded files are saved in `outputs`.

## Image-to-video

```powershell
seedance generate --prompt "Camera slowly pushes in, fabric moving in the wind" --first-frame-url "https://example.com/first.png" --download
```

For strict first and last frame control:

```powershell
seedance generate --prompt "Smooth transition between the two frames" --first-frame-url "https://example.com/first.png" --last-frame-url "https://example.com/last.png" --download
```

## Multimodal references

```powershell
seedance generate --prompt "Match the subject and motion style from the references" --reference-image-url "https://example.com/ref.png" --reference-video-url "https://example.com/ref.mp4" --download
```

KIE documents first/last-frame mode and multimodal reference mode as mutually exclusive, so the CLI rejects a request that mixes them.

## Fast variant

```powershell
seedance generate --model bytedance/seedance-2-fast --prompt "Fast draft video of a product rotating on a clean studio table" --download
```
