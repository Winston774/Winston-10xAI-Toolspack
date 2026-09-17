# Hypit 影片理解架構研究筆記

本頁的移植建議為研究結果；本技能實際介面以 [tooling.md](tooling.md) 與 [handoff-contract.md](handoff-contract.md) 為準。

## 研究邊界

- 研究對象是 Hypit upstream 固定 commit `d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66`。
- 來源是 `packages/video-cli`、`packages/media-*`、WhisperX provider/service、相關 README 與 `skills/hypit` reference。
- 本筆記追查短影音從輸入到可交接證據的實際程式路徑，並把可移植設計與證據邊界分開。
- 下列 GitHub 連結都固定到同一 commit；reference/README 的指引會標明為 agent playbook，不能當作另一條執行管線。
- 沒有安裝、啟動或執行 upstream；本次只做 source reading。

## 核心結論

Hypit 已有一條相當清楚的「機械證據」管線：本機影片檔案進入 `hypit media`，由 `ffprobe` 取得摘要、由 `ffmpeg` 解碼指定時間的畫格或裁切片段、由 Sharp/Pango 產生可讀的時間/文字標籤，另由 canonical WAV 進入 WhisperX 取得字詞時間。

這條管線能交接媒體時間軸、串流結構、取樣畫格、文字與對齊時間；它沒有替下一個生成 agent 完成視覺語意、鏡頭敘事、OCR、物件關係或可直接採用的生成提示詞。後者必須在交接文件中作為人工/agent interpretation，附回原始 evidence path 與時間。

實際可移植的單一路徑如下：

```text
video path/URL
  -> (optional) yt-dlp fetch to a new local file
  -> media probe: duration, dimensions, frame rate, audio presence
  -> transcript: canonical 16 kHz mono PCM16 WAV -> WhisperX word windows
  -> frames/tiles: requested times -> decoded actual times + active/context words
  -> boundaries: low-resolution adjacent-frame difference candidates
  -> handoff document: facts, evidence paths, interpretations, unknowns, next actions
```

CLI 的入口會把 `studio` 交給 Studio，其餘命令導到 `packages/video-cli/src/cli.ts`；CLI 會註冊 tsx、安裝 distribution package resolution，再路由 creation、media、capture 與 vocabulary 命令。[入口程式](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/bin/hypit.mjs#L1-L44) [命令路由](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/index.ts#L1-L51)

官方 video CLI distribution 內建 `hypihub.default`、`media.local` 與 `hyperframes.local` 等 runtime profile endpoint；compiler 的 source package resolution 僅允許 workspace/distribution root。[distribution profile](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/distribution.ts#L21-L62) [compiler scope](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/compiler.ts#L6-L31)

## CLI 能力與輸出

`video-cli` 的 media help 將能力定義成 `probe`、`cut`、`frames`、`tile`、`tiles`、`boundaries`、`fetch`；它們處理局部視圖、選段、時間格與候選變化，transcript 標註沿用同一輸入媒體秒數。[media 命令說明](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L13-L19) [help 與 dispatch](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L663-L708)

| 命令 | 實際產物 | 適合交接的欄位 |
| --- | --- | --- |
| `media probe` | JSON 或人讀摘要 | duration、width、height、frameRate、hasAudio |
| `media cut` | H.264/AAC MP4 選段 | requested start/end、輸出檔、probe 摘要 |
| `media frames` | 每個指定時間一張 JPEG | requestedAt、實際 decoded `at`、frame path、字詞 |
| `media tile` | 單張時間標籤 grid | sample times、columns/rows、每格實際時間、words |
| `media tiles` | 分頁 grids | ranges、grid paths、每頁 samples |
| `media boundaries` | 分數候選 JSON | rate、threshold、candidate `at`、score |
| `media fetch` | 新的本機影片檔 | source URL、local path、下載後 probe |

Media CLI 解析旗標、要求輸入檔存在，並在輸出已存在時拒絕覆寫；資料夾會先建立。這些約束適合直接保留到獨立 skill 的 evidence writer。[CLI 輸入/輸出約束](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L42-L65) [source/destination validation](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L109-L129)

`media fetch` 只接受 HTTP/HTTPS，目的地限 `.mp4`、`.mkv`、`.webm`、`.mov`，下載後會重新 probe；`prepare-fetch` 是另外的準備命令。playbook 要求先明確準備 yt-dlp/JavaScript solver，CLI fetch 本身不安裝相依套件。[fetch 實作](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L647-L657) [下載 playbook](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/production/video-downloads.md#L1-L45)

## Probe 與時間軸

CLI `probe` 用 `ffprobe -v error` 讀 `format.duration` 與 stream 的 `codec_type,width,height,r_frame_rate`；它挑第一條 video stream，要求正的 duration/尺寸，解析 `r_frame_rate`，並以是否存在任一 audio stream 回報 `hasAudio`。[CLI probe 實作](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L135-L165)

這個摘要 probe 與 `@hypit/media-execution` 的 `inspect-media` 是兩層不同介面。後者會同時取得 ffprobe 的 format、streams、frames，解析每條 stream 的 PTS、duration、SAR、rotation、frame rate、sample shape 與 timingStatus，再封裝 immutable `MediaInspection`。[inspectFile](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-execution/src/execute.ts#L303-L328) [inspection parsing](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-execution/src/probe.ts#L221-L315)

Probe 的時間證據以 decoded frame/sample 的 timestamp 為主。parser 會從 `pts` 或 `best_effort_timestamp` 推導缺少的 duration，檢查單調性，並把 audio gap/discontinuity 與 video cadence/discontinuity 納入 timingStatus。[timing parser](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-execution/src/probe.ts#L131-L218)

影像的 display rotation 只接受 90 度整數倍，SAR 與 rotation 會保留；例如 45 度 rotation 會被拒絕。這些欄位是下一個 agent 判斷畫面方向與裁切風險的必要事實。[rotation/SAR parser](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-execution/src/probe.ts#L63-L106) [probe tests](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-execution/test/probe.test.ts#L8-L91)

可移植設計應同時保存：CLI 摘要、完整 stream inspection、原始 duration、timingStatus、time base、PTS 起止點、SAR、rotation、moving/attached-picture 判定。只存一個浮點 duration 會丟失後續生成所需的同步與方向上下文。

## Snapshot、格線與候選邊界

精確取樣會在目標時間前先倒退最多兩秒做 keyframe seek，再以 post-input decode 找畫面；原始碼註明這可把 1080p JPEG seek 從約 11.6 秒改善到約 0.2 秒。回傳的 `at` 是實際解出的 timestamp，不能用 requested time 取代。[精確 seek](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L167-L183)

`cut frame` 使用 ffmpeg `trim=start=<at>,showinfo`，從 stderr 的 time_base/PTS 解析實際 decoded time；有 `--label-time` 時先寫乾淨 JPEG 再覆蓋時間標籤。這保留了「要求的位置」與「實際畫格」兩個證據欄位。[frame extraction](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L292-L318)

格線預設每秒約 1.5 張，總數限制在 4 至 9 格；sample time 使用每個 bin 的中點，避免只取邊界。每格會 resize，並在圖下方標示 timecode、active words 與前後各最多三個 context words。[grid sampling](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L320-L349)

`tileFrames` 會將 requestedAt、實際 `at`、`wordsAt` 一起回傳；`frames` 用暫存 staging directory 寫完後再 rename，並產生 deterministic `frame-<time>s.jpg` 名稱。`tile`/`tiles` 也回傳 samples、columns、rows、cellWidth、grids，適合讓交接文件以 path 引用影像 evidence。[tileFrames 與 frames](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L351-L392) [frames JSON](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L510-L535) [tile JSON](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L537-L551) [paginated tiles](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L553-L632)

取樣規則允許明確 `--at`，或 `--start/--end` 搭配 `--every`、`--frames`；時間必須嚴格遞增、落在 duration 內，`--frames` 至少兩張。`--around` 需要 transcript，重複 phrase 需要明確 `--occurrence`。[sampling options](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L426-L485)

`boundaries` 只把影片縮成 32×32 RGB，在固定 sample rate 下計算相鄰畫格平均 absolute RGB difference，再用 threshold 輸出 candidates；預設 rate 12/s、threshold .1。原始碼與 help 都明確說這些分數是導航證據，不能直接叫作 shot labels。[visual boundaries](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L394-L421) [boundary CLI](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/media.ts#L634-L645)

因此獨立 skill 應把 boundary candidate 放在 `change_candidates`，保留 rate、threshold、score 與原始時間；下一個 agent 必須回看候選前後的 dense frames/clip，才能提出「鏡頭切換」或「視覺事件」解釋。

## Transcript 與語音證據

`hypit transcribe` 是 creation CLI 的一次性 immediate request。它要求單一存在的 source file 與明確的小寫 2/3 字母 `--language`，先把媒體音訊轉成 canonical PCM s16 mono 16 kHz，再把 bytes 放入 MemoryResourceStore，建立 `whisperx-alignment` Need，最後只接受 inline fulfillment 並寫出 `hypit.transcript@1`。[transcribe flow](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/creation.ts#L281-L337) [language type](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/whisperx/src/types.ts#L3-L17)

若原始音訊已是 canonical 格式，會直接重用；其餘情況用 ffmpeg 明確指定第一條 audio stream、`-vn -ac 1 -ar 16000 -c:a pcm_s16le -bitexact`，再驗證 WAV header、sample rate、channel、sample format。[speech evidence extraction](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/creation.ts#L198-L245)

transcript JSON 的 passage 由 words 組成；每個 word 有 text、可選 start/end、score。CLI 讀取時只接受 `hypit.transcript@1`，會 flatten passages.words，保留缺少 timing 的 word，不自行填補。[transcript reader](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/transcript.ts#L3-L33)

`wordsAt` 以半開區間 `start <= at < end` 決定 active words，找不到重疊 word 時再以最近的 start/end 作 fallback anchor，context 取前後三個 word。phrase search 會 NFKC、轉小寫、去標點/空白並要求整段 phrase 的首尾都有 timed boundaries。[word labels/search](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/transcript.ts#L35-L70)

WhisperX service 的語意邊界很窄：canonical 16 kHz mono WAV 進入 faster-whisper ASR，再進語言專用 WhisperX alignment，產出 raw measured words；服務不切字幕 cue、不推導 segment、不建立 SemanticTake，也不替缺 timing 的字補時間。[服務職責](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/services/whisperx/README.md#L3-L17)

本機 provider 預設 loopback `http://127.0.0.1:8765`，服務與 provider 必須匹配 protocol、serviceVersion、WhisperX version、model、device、compute、batch 等 identity；HTTP response 有大小上限，輸入音訊必須在允許的 local roots。[local provider defaults/handler](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/provider-whisperx-local/src/provider.ts#L18-L29) [identity and request](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/provider-whisperx-local/src/provider.ts#L103-L191)

服務採單一 inference process，第二個同時請求回 `503 BUSY`，沒有隱藏 queue；`/health` 表示 ASR 已載入，但不代表每個 alignment language resource 都已準備好。[服務限制](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/services/whisperx/README.md#L51-L92) [busy/no-queue](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/services/whisperx/README.md#L122-L130)

CLI README 也把 transcript 描述成非 durable、不可 resumable 的 immediate work；這是操作 playbook，實作則由上述 Need/provider 路徑證實。轉錄檔仍應保留 provider、language、audio_seconds、passage/word counts 與 extracted flag，以便下一 agent 知道它引用的是原始音訊或轉換副本。[CLI transcription playbook](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/README.md#L62-L98)

## Media extraction 與 provider 邊界

`@hypit/media-pipeline` 把流程定義為 `BlobArtifact -> inspect-media Need -> MediaInspection -> deterministic stream selection -> normalize-media Need -> SynchronizedMedia`；stream selection 的政策和 speech semantic 明確分離，選中的 audio 不代表它就是 speech。[pipeline overview](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-pipeline/README.md#L3-L38)

Need 型別包括 Normalize、Transform、ExtractAudio、ExtractFrame、RenderStillVideo 與 ProjectSpeechEvidenceAudio。通用 extraction 只交付 artifact，沒有語意或 alignment claim。[Need shapes](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-pipeline/src/types.ts#L95-L136) [operation semantics](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-pipeline/README.md#L83-L113)

stream selection 只接受 moving、非 attached-picture、timing admissible 的 video，audio 也必須有可用 PTS；預設政策名稱會被記錄。`MediaInspection`/selection/synchronized media 還有 seal、unique index 與 frame/sample invariant，可作為交接資料的結構驗證基礎。[selection policy](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-pipeline/src/selection.ts#L17-L110) [identity invariants](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media/src/identity.ts#L123-L186)

local media provider 只依賴 `@hypit/media-execution`、local ResourceStore、ffmpeg/ffprobe；inspect、normalize、transform、extract audio/frame 與 StillVideo 是 immediate transient endpoint，speech projection/render/mux 則屬 build-only。[local media provider](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/provider-media-local/src/provider.ts#L46-L146)

media execution 會把 BlobRef stage 成暫存檔，所有 subprocess 以 shell-less、hidden Windows process 執行，有 timeout、stdout bytes 上限與 stderr tail；外部 toolchain 只從環境取得 PATH/必要 process vars。[execution environment](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-execution/src/execute.ts#L46-L70) [process/toolchain](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-execution/src/process-env.ts#L1-L20) [tool checks](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-execution/src/toolchain.ts#L1-L81)

extract audio 的固定交付是單一 48 kHz stereo PCM16 WAV；extract frame 以 first/last/index/time 選擇並輸出單張 PNG。speech projection 再從 48 kHz master 精準降為 16 kHz mono，補齊/裁切到 exact sample count。[audio/frame execution](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-execution/src/execute.ts#L991-L1075) [speech projection](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/media-execution/src/execute.ts#L1077-L1138)

## agent playbook 與實作的分界

`skills/hypit/references/creation/reference-video.md` 要 agent 從全片 hook/argument/payoff 讀到細節，使用 transcript-linked grids，並把 Analysis 與 Timeline 寫成可實作的語意模型。[reference understanding playbook](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L1-L38)

同一份 playbook 建議以 probe、cut、frames、tile/tiles、boundaries、fetch 逐步縮放觀察範圍，提醒 samples 只證明各自時間點且區間之間可能漏掉短事件。[evidence workflow](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L91-L169)

它要求把「可見/可聽」和「解釋」分開，寫出全片 Analysis、帶 source time 的 Timeline、evidence paths 與仍待查問題；這是交接格式與閱讀方法的建議，並非 `media.ts` 會自動生成的欄位。[durable account playbook](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L170-L220)

`skills/hypit/SKILL.md` 的「watch、inspect、record Analysis/Timeline、done means watched」是 director/producer 工作規則；可借用其 evidence discipline，卻不能宣稱 Hypit CLI 已完成觀看、聆聽或語意理解。[director instructions](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/SKILL.md#L1-L39) [evidence responsibility](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/SKILL.md#L210-L240)

## 建議獨立 skill 的可移植交接契約

以下是基於上游資料形狀的設計建議，標為 skill-level inference；它不代表 upstream 已有同名完整文件。

1. `source`：`input_path`、可選 `source_url`、extension、byte size/hash、fetch method、created_at，以及 fetch 後的 probe JSON。
2. `media`：duration、dimensions、frameRate、streams、selected video/audio indexes、timingStatus、timeBase、SAR、rotation、A/V offsets。
3. `transcript`：schema/version、language、provider identity、audio_seconds、extracted flag、passages、word text/start/end/score；缺時間的 word 保持 `null`。
4. `visual_samples`：每個 request 的 `requestedAt`、實際 decoded `at`、frame path；grid path、columns/rows/cellWidth、sampling rule 另存。
5. `word_context`：每個 sample 的 active/context word，並標明它來自同一 source clock 的 transcript。
6. `change_candidates`：rate、threshold、每個 candidate 的 at/score，欄名使用 candidate，避免暗示已是 shot boundary。
7. `observations`：只寫 frame/clip/transcript 可支持的可見或可聽事實；每筆附 `evidence_refs`、source time 與 asset path。
8. `interpretations`：下一 agent 對敘事、視覺系統、節奏、情緒、生成方向的推論；附 `confidence`、支持 evidence、仍未知項。
9. `handoff`：建議下一步 dense sampling、需人工回看的時間區間、需補做 OCR/音訊聆聽/語意分析的工作，以及可直接供生成 agent 使用的 constraints。

可考慮以 manifest 加上 `tool_version`、固定 commit、每個命令的 argv、provider identity 與失敗訊息，讓回看者知道 evidence 是怎樣產生。這是可重現性推論；Hypit 的現有 JSON 已提供 requested/actual、provider、counts 等局部欄位，但沒有一個完整的 cross-command handoff schema。

獨立 skill 的最小執行順序建議是：先保存/確認 source，接著 probe；有語音才明確選 language 並 transcribe；先做全片低密度 tiles，再按 phrase 或 boundary candidate 產生 dense frames；最後由 agent 讀圖、聽音、結合 transcript 撰寫 interpretation。任何語意句子都要能回鏈到 sample/clip/word evidence。

## 實作缺口、限制與風險

- CLI summary probe 不回報完整 codec、PTS、SAR、rotation、timingStatus；若生成 agent 需要這些欄位，必須接 `media-execution inspect-media` 或另做完整 ffprobe adapter。
- frame seek 的 `at` 是解碼結果；時間接近尾端、VFR、B-frame、rotation 或 timestamp gap 時，requestedAt 與 at 可能不同，交接時必須同時保存。
- 32×32 boundary diff 會漏掉低對比、局部或短暫變化，也可能把整體亮度變化當 candidate；它不產生 shot segmentation。
- 稀疏 grid 只覆蓋離散時間點；playbook 自己承認相鄰 samples 不變仍可能漏掉短事件，密度需按問題調整。
- transcript 是 recognizer/alignment 的量測；專有名詞、造詞、品牌名可能拼錯，score 不是語意真實度。缺失 start/end 不應由 skill 擅自補齊。
- `hypit transcribe` 要求明確 language；WhisperX service 內部雖能把 auto/detect/und/unknown 轉為 None，CLI contract 仍拒絕這些值。
- 本機 WhisperX 依賴 Python/WhisperX 服務、ASR model、語言 alignment resource 與 NLTK/模型快取；health 不能證明所有 language resource 可用。
- WhisperX 單一 process 沒有 queue，並行請求會遇到 `503 BUSY`；獨立 skill 需要序列化或在交接中記錄 retry/未完成狀態。
- canonical audio 有服務設定的 request bytes 上限；長片或未壓縮 WAV 可能超過限制，需在 probe/轉檔前估算。
- local media provider 的 ffmpeg/ffprobe 是外部 executable；缺 encoder/filter、PATH 或版本能力時 readiness 會失敗。不能把 package 安裝狀態當作可執行證據。
- HypiHub provider 是可選 hosted branch，會上傳 reference audio、依 model route 發出 transcription request；它增加網路、帳戶、費用與資料處理邊界，獨立 skill 應在 manifest 明確記錄 provider。[remote transcription](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/provider-hypihub/src/provider.ts#L519-L632)
- capture command 是瀏覽器/HTML reference capture，輸出 `hypit.capture@1`，用途與本機影片理解不同；不要把 browser screenshot、native recording 自動當成 source video analysis。[capture path](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/capture.ts#L8-L46) [capture output](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/packages/video-cli/src/capture.ts#L109-L188)

## 交付判準

一份「可供下一生成 agent 使用」的交接文件至少要讓接手者回答：來源是哪個檔案與時間軸、影片有哪幾條可用 stream、語音使用何種 language/provider、每個觀察句子由哪個 frame/clip/word 支持、哪些變化只是 machine candidate、還有哪些區間與語意尚未確認。

若文件只有一張縮圖、整段 transcript 或一串 inferred shot list，它仍不足以重現 Hypit reference playbook 要求的 whole-piece 與 close reading。最低 evidence 應包含全片 overview tiles、關鍵區間 dense tiles/frames、transcript JSON、完整 probe/inspection 與 unknowns；真正的生成提示詞要放在 interpretation/handoff 層，並保留回鏈。
