# Hypit 影片理解與生成交接方法

本文件把 Hypit v0.2.1 的 reference-video、creation、craft、format 與範例生產筆記，整理成獨立的「短影音輸入 → 下一個 agent 可生成影片」交接方法。所有 upstream 引用固定在 commit `d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66`；本文件沒有執行 upstream，也沒有驗證任何模型輸出。

本頁的欄位與狀態為研究提案；正式執行以 [handoff-contract.md](handoff-contract.md) 為準。

## 讀法與證據界線

- 【來源明載】直接由固定 commit 的文件或範例支持，連結中的行號指向原文。
- 【工程改寫】為本 skill 將來源方法壓縮成可交接的欄位、狀態與檢查；需要在實作中驗證。
- 【未驗證】短影音輸入、工具、音訊、轉錄、模型或生成結果尚未提供時，保留未知，不能從檔名、格式或預期風格補出答案。
- 來源要求理解 reference 的「時間點語義」：片子說了什麼，以及精確的視聽選擇如何支撐它。[reference-video.md L1-L5](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L1-L5)
- 來源把證據和詮釋分開：重新開啟爭議區間，分別寫看見／聽見的事實與推測作用。[reference-video.md L152-L154](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L152-L154)
- 每個交接主張帶 `evidence_ref`、來源區間與 `confidence`；無證據欄位用 `unknown`、`unavailable` 或 `blocked`，並寫明原因。【工程改寫】

## 端到端方法

1. 先界定輸入：保存原始路徑、檔案雜湊、時長、寬高、fps、音訊存在與可用工具。`hypit media probe` 提供 duration、dimensions、frame rate、audio presence；`transcribe`、`cut`、`frames`、`tile/tiles`、`boundaries` 支援文字和局部視覺檢查。[reference-video.md L92-L101](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L92-L101)
2. 先看完整片，從 opening、hook、argument/story、attention shifts、payoff 讀到 close；同步記錄表演者、畫面貢獻、Caption、MG、Typography、Effect、Audio 哪些系統持續或重現。[reference-video.md L10-L15](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L10-L15)
3. 形成暫定 whole-piece model：觀眾被帶往什麼感受、理解或決定，節奏怎樣分配注意力，各層如何互相回答；再用局部證據修正。[reference-video.md L17-L25](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L17-L25)
4. 對每個 distinct system 追蹤內容、外觀、空間關係、entry、active behavior、persistence、exit，以及服務的 words、pause 或 action。[reference-video.md L17-L22](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L17-L22)
5. 以疑問帶動取樣：全片／長段看 argument 與持續系統，窄區間看 entrance、replace、crop、cover、handoff；必要時放大讀字與版面。[reference-video.md L103-L112](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L103-L112)
6. 將發現回寫到整體解釋與時間線：先寫事實，再寫 viewer job，最後寫目標片要保留、改編或重設的關係。

### 粗略層與精準層

- 粗略層回答「整片如何發展」：時間標籤 tile 覆蓋完整片段，辨認 hook、段落轉折、持續物件、主要說話者與 payoff；示例用 0–12 秒、每秒一格。[reference-video.md L119-L126](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L119-L126)
- 精準層回答「變化怎麼發生」：在候選 boundary 前後用密集樣本、局部 clip 與單格 frames，讀出 arrival、state change、settling、exit、handoff；示例用 6.8–8.4 秒、每 0.1 秒取樣。[reference-video.md L127-L136](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L127-L136)
- 取樣格只證明被取到的時刻；鄰格相同不能證明中間沒有短事件。代表性 still 不能代替 temporal account。[reference-video.md L114-L117](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L114-L117)
- `--around`、`--padding`、`--occurrence` 讓 phrase 對應局部視覺；範圍要包含 incoming 與 outgoing handoff。[reference-video.md L138-L146](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L138-L146)
- 【工程改寫】同時保存 `overview_evidence[]` 與 `detail_evidence[]`，每個 detail 指回它修正的 overview 假說。

## 音訊、文字與時間

### 輸入稽核與缺失狀態

- 有 audio 且可轉錄：保存 transcript JSON、語言、word-level times、工具／版本與錯誤備註。timed wording 可連到 cuts、illustrations、reveals、emphasis。[reference-video.md L68-L74](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L68-L74)
- 有 audio 但 transcribe tool 不可用：`audio_status=present`、`transcript_status=unavailable`；仍可由人工聆聽、可用播放器或其他已驗證工具記錄逐字內容，但每個詞與時間都要標出其實際證據來源。只有未聆聽、未讀取或未對齊的內容才維持 `unknown`。【工程改寫】
- 無 audio：`audio_status=absent`、`speech_status=not_observed`；只從 actions、scene changes、可見文字讀取意義。來源對 speechless work 的方法是追蹤 actions 與 scene changes。[reference-video.md L92-L93](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L92-L93)
- 媒體或 frames 工具不可用：`tool_status=blocked`；可由其他已驗證路徑讀取實際畫面或 Caption，則保存該路徑與信心，無任何證據時才禁止聲稱 frame、OCR、duration 或 boundary，並將待辦放入 review queue。【工程改寫】
- 轉錄拼字不能單獨證明發音；專有名詞與新造詞特別容易被替換。目標 Script 的 Dual Text 或 direction 才能指定 pronunciation。[reference-video.md L86-L90](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L86-L90)

### 原片時間與目標時間分離

- `source_start/source_end` 是 reference 的證據位置，並保存它服務的關係，例如 reveal 回答問題、image illustration 對應 phrase、exit 替下一 claim 騰位置。[reference-video.md L194-L198](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L194-L198)
- 目標片把關係綁到自己 Script 的 `Selection` 或 `Moment`；新 performer、語言、copy、delivery 會改變實際秒數，不能直接複製 reference timestamp。[script-and-time.md L376-L379](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/script-and-time.md#L376-L379)
- `Selection` 是意義範圍，適合 demonstration、coverage、comparison；`Moment` 是 answer、verdict、reveal 等事件，適合多層同步回應。[script-and-time.md L23-L34](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/script-and-time.md#L23-L34)
- 目標 generation duration 先由 pronunciation units、language、pace、padding 估算，再用 accepted performance 的實際 alignment 決定 Caption、B-roll、MG、Effects 的 frame 位置。[script-and-time.md L237-L264](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/script-and-time.md#L237-L264)
- measurement 只回答要請求多少 media，不提供 timeline anchors；生成後要 normalize、align，讓真實 word positions 取代估算分布。[script-and-time.md L279-L284](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/script-and-time.md#L279-L284)
- 【工程改寫】每個時間值加 `clock_kind`：`source_clock`、`target_semantic`、`target_aligned` 或 `target_authored`。`source_clock` 只能定位證據。

### 詞、語義 anchor 與字幕

- Script 是 target 唯一 verbal authority；不混入 reference timecode、media、visual style、prompt 或 provider decision。[script-and-time.md L16-L21](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/script-and-time.md#L16-L21)
- Caption 顯示正在說的 speech；title、lower-third、label、editorial paraphrase 依角色歸 Typography、Text 或 MG。[captions.md L1-L10](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/captions.md#L1-L10)
- `||` 是同一 Segment、turn、Style 內的 Caption Cue handoff；不會替 picture 關閉 gap。Cue 是可讀的 meaning block，visual line break 不會形成新的 Cue。[captions.md L101-L112](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/captions.md#L101-L112)
- 中文最小 timed display unit 通常是 Han character，但 Cue 應以 compounds、names、modifier/object 與完整短句的意義分組；固定字數不能決定可讀性。[captions.md L114-L126](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/captions.md#L114-L126)
- 【工程改寫】缺 transcript 時，`anchor.type` 只能是 `visual_event`、`clock_boundary` 或 `unknown`；不得產生 phrase、character timing、Caption text 或 speaker name。

## 視覺系統、覆蓋與邊界

- 時間線條目描述 active objects、content、placement、entry、change、persistence、exit、服務的 word/action、source time 與 evidence path。[project-files.md L132-L142](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/project-files.md#L132-L142)
- 跨 camera cut 存活的 object 屬於較長生命週期 system；記錄 system 一次，再定位 state changes。[reference-video.md L39-L43](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L39-L43)
- Coverage 問 boundary 前、中、後觀眾應看到什麼；風險包括 pause 無人認領、source 早於 Item window、opacity 暴露底層、component 只在 item activation 畫圖。[frame-coverage.md L1-L18](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/frame-coverage.md#L1-L18)
- B-roll 的 exact correspondence 適合每個 claim 需要指定畫面；montage over a thought 適合幾個場景共同表達 habit、history 或 attitude。[b-roll.md L21-L37](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/b-roll.md#L21-L37)
- `Selection` 決定 Item active window，Recipe 決定 source frames；自然 coverage 優先 native-speed pass，短 window 可截斷，長 window 讓底層畫面回來，不自動 freeze、loop 或 retime。[b-roll.md L39-L65](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/b-roll.md#L39-L65)
- Picture 與 speech 可以不同時交接：montage 仍在畫面上時 partner voice 已進來，形成 J-cut；端點由 thought、reaction、reading time 決定。[b-roll.md L67-L76](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/b-roll.md#L67-L76)
- 相鄰 coverage 若要無縫，兩側選同一 instant；`||` 只處理 Caption grouping，不能修 visual gap。[b-roll.md L78-L102](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/b-roll.md#L78-L102)
- 【工程改寫】每個 boundary 產生 `before/during/after_expected` 與 `coverage_risk`；frame 密度或 source duration 不足時標 `needs_review`。

## 版面、比例與合成

- 分開記錄 physical scene、camera composition、editorial composite：前者是物理世界，中者是 viewpoint／framing／crop，後者是 Caption、MG、inset、mask、stack order。[compositing.md L7-L20](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/compositing.md#L7-L20)
- Canvas dimensions、intrinsic media extent、destination Frame、fit/crop 是不同事實，要檢查最終組合，不能只保存 Frame 座標。[compositing.md L34-L38](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/compositing.md#L34-L38)
- 生成影像的 aspect ratio 通常是 model parameter；它不等於 editorial Frame。範例把 Capture、Person、Shot、Setting 與 `9:16` model parameter 分開，derived view 可因 parent 已建立事實而縮短 prompt。[conversation-images.md L1-L22](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/examples/conversation-images.md#L1-L22)
- A-roll 可 full-frame、split、cutout、circular inset 或 audio-only；semantic timing 與 sound role 不因呈現方式改變。[compositing.md L70-L87](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/compositing.md#L70-L87)
- 【工程改寫】每個 shot 列 `source_aspect`、`target_canvas`、`destination_frame`、`fit_crop`、`safe_regions`、`layer_order`；缺比例資料用 `unknown`，不能從平台名稱猜比例。

## 聲音與生成依賴

- Soundtrack 可分開理解為 speech、music、ambience、sound effects；speech 要在 phone/laptop 上易懂，其他層為 consonants、names、numbers、claims、punchlines、CTA 讓位。[sound-mix.md L7-L38](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/sound-mix.md#L7-L38)
- sound effect 若服務 spoken meaning，綁 Selection 或 Moment；事件真正獨立於 speech 才用 clock time。accepted speech alignment 才能定位 semantic event。[sound-mix.md L40-L61](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/sound-mix.md#L40-L61)
- Picture cut 不必造成 acoustic cut；room tone、music 或 speech 可以跨 coverage，也可能因換場、speaker perspective、narrative state、designed silence 需要聲音轉場。[sound-mix.md L63-L77](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/sound-mix.md#L63-L77)
- 依賴圖追蹤下一張圖或 Take 需要的 person、camera view、place、product、physical state；reference count/depth 是需求結果。[generated-dependencies.md L1-L5](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/generated-dependencies.md#L1-L5)
- Useful parent 保持靠近：main host → complementary view、shared interview scene → close views、main character → lifestyle scenes；「Reference 2」不能補上不存在的 image。[generated-dependencies.md L7-L19](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/craft/generated-dependencies.md#L7-L19)
- exact private identity、product、logo、UI、data 要接入 supplied reference；只為餵下一次 generation 的中間圖應避免，除非該場景本身需要它。[transformations.md L86-L115](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/transformations.md#L86-L115)
- exact movement/camera path 若是 adaptation 核心，保存 source excerpt 作 motion evidence；provider/model 支援仍待驗證。[reference-video.md L216-L228](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/creation/reference-video.md#L216-L228)
- 【工程改寫】generation request 列出 `depends_on[]` 的實際 asset/evidence IDs、保留事實與改變事實；缺 asset、endpoint 或 capability 時狀態為 `blocked`。

## Format 只作分類先驗

- `narration-led`：獨立 speech 是 audio-only A-roll，畫面由 product、screen、demonstration、B-roll、Typography 或 MG 回答；一條 narration 可承載多次 picture change。[narration-led-demo.md L1-L19](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/formats/narration-led-demo.md#L1-L19)
- `presenter-led`：spoken performance carry explanation，presenter 可 lead frame、share frame、進 inset 或被覆蓋；一個 Take 內可多次改 presentation。[presenter-led-explainer.md L1-L6](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/formats/presenter-led-explainer.md#L1-L6) [presenter-led-explainer.md L28-L46](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/formats/presenter-led-explainer.md#L28-L46)
- `talking-head/UGC`：人的 attitude carry the piece；同一 character-and-scene image 可支援多個自然剪接 talking Takes。[talking-head.md L1-L4](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/formats/talking-head.md#L1-L4) [talking-head.md L9-L28](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/formats/talking-head.md#L9-L28)
- `ranking/listicle`：board state 保存過往判斷，person、evidence、performance 說明新判斷；preset、entry、outer Window 與 reveal event 分開。[ranking-listicle.md L1-L22](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/formats/ranking-listicle.md#L1-L22)
- `two-person podcast/interview`：question、claim、reaction、reply 形成 argument；shared view 建立 world，再 derive complementary/close views，注意力跟著目前重要的人移動。[two-person-podcast.md L1-L15](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/formats/two-person-podcast.md#L1-L15) [street-interview.md L6-L14](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/formats/street-interview.md#L6-L14)
- `short-drama`：performance-led 因果事件；wants、reaction、action、relationship、surroundings 驅動下一 beat，Segment 不等於 camera shot。[short-drama.md L1-L23](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/skills/hypit/references/playbooks/formats/short-drama.md#L1-L23)
- 【工程改寫】先標 `format_hypothesis` 與依據，再列 format-specific questions；不能將例子的鏡頭數、顏色、Kit、時長或 asset inventory 當通則。

## 下游生成 handoff 契約（研究提案）

以下結構是本研究對最小完整契約的提案，供正式 handoff-contract skill 調整與採用；它不取代 repo 內正式契約。【工程改寫】

```yaml
contract_version: "hypit-video-understanding/0.1"
source:
  input_path: "..."
  sha256: "..."
  duration_s: 0
  width: 0
  height: 0
  fps: 0
  audio: present|absent|unknown
  transcript: available|unavailable|not_applicable|unknown
  tools: { probe: ok|blocked, frames: ok|blocked, transcript: ok|blocked }
whole_piece:
  format_hypothesis: "..."
  viewer_promise: "..."
  argument_or_story: "..."
  pacing_arc: "..."
  recurring_systems: [system_id]
evidence:
  - id: ev-001
    source_start_s: 0
    source_end_s: 1.2
    kind: frame|tile|clip|transcript|audio|ocr|tool_metadata
    observation: "可直接看到／聽到的事實"
    interpretation: "它對觀眾的作用"
    confidence: high|medium|low
    path_or_locator: "..."
timeline:
  - id: phase-001
    source_start_s: 0
    source_end_s: 2.4
    clock_kind: source_clock
    phase: "..."
    speech_anchor: { type: word|selection|moment|visual_event|unknown, value: "..." }
    active_systems: [system_id]
    handoff_in: "..."
    handoff_out: "..."
    evidence_refs: [ev-001]
systems:
  - id: presenter|caption|mg|broll|music|effect|...
    role: "..."
    lifecycle: { entry: "...", active: "...", persistence: "...", exit: "..." }
    layout: { physical: "...", camera: "...", editorial: "..." }
    coverage: { before: "...", during: "...", after: "...", risk: none|review }
    target_relation: preserve|adapt|redesign|drop
target_bridge:
  brief_constraints: ["user goal, audience, platform, language, duration, CTA"]
  treatment_direction: ["new viewer experience and creative choices"]
  source_to_target_rules:
    - source_relation: "..."
      target_anchor: "story.selection.x or story.moment.y"
      target_time_policy: aligned_performance|authored_clock|unknown
generation_requests:
  - id: shot-001
    purpose: context|proof|broll|a_roll|screen|mg|transition|sound
    target_anchor: "..."
    duration_basis: measured_words|source_reference|authored|unknown
    requested_duration_s: null
    aspect_ratio: "... or unknown"
    frame_intent: "subject, camera, safe area, crop"
    action_or_performance: "..."
    depends_on: [{ asset_or_evidence: "...", preserves: "...", changes: "..." }]
    exact_facts: ["private identity, UI, number, logo, prop state"]
    status: planned|needs_asset|needs_tool|needs_user_fact|blocked
    execution_readiness: planning_ready|execution_blocked|unvalidated
audio_plan:
  speech: known|unknown|absent
  music: observed|not_observed|unknown
  ambience: observed|not_observed|unknown
  effects: [{ event_anchor: "...", role: "...", status: observed|proposed|unknown }]
unknowns_and_review:
  - id: q-001
    question: "..."
    blocks: words|timing|layout|generation|sound|none
    next_evidence: "..."
```

## 交接驗收規則

- 每個 whole-piece 結論至少連到 evidence；每個精準 timeline event 都有 source interval 或明確 `unknown`。
- 每個 visual system 都有 entry、active behavior、persistence、exit；只寫「有字幕／有 B-roll／有轉場」不算完成。
- 每個 target relation 都說明 preserve、adapt、redesign 或 drop，並指出 viewer job。
- 原片秒數與目標秒數各有 clock kind；從原片帶入的數字附可沿用的設計理由，否則只作 evidence locator。
- 沒有 audio 時，不能產生語音內容、speaker role、word-level anchor 或語音節奏；畫面 Caption 仍可在實際 frame/OCR 證據支持下記錄。沒有 transcript 時，不能產生未經聆聽或對齊的逐字時間敘述。
- 沒有 frames／OCR／probe 工具時，若無其他可驗證觀察路徑，不能聲稱看見細節、讀出字、確認 fps／時長或找出 boundary，寫入 blocked review item。
- 每個 generation request 列實際依賴、保留事實、改變事實、比例與 safe area；缺 asset、endpoint、provider capability 或成本狀態就停在相應 status。
- B-roll coverage 檢查 source duration、window、native-speed、pause ownership、return layer；不能用假 freeze 或自動 retime 填空。
- Final handoff 的 `planning_ready` 只表示已形成可供下一 agent 展開的生成規劃，與 endpoint/provider/cost 執行準備分開；尚未生成、未觀看或未聆聽的結果保持 `unvalidated`。

## 值得抽取與不宜照搬

值得抽取的是多尺度觀察迴圈、觀察與詮釋分層、system lifecycle、詞／Selection／Moment 語義綁定、source／target clock 分離、coverage 邊界、physical/camera/editorial 三種空間、sound role、淺層 reference dependency graph。

不宜照搬的是範例的粉紅 pixel treatment、足球／肌肉／餐廳題材、固定的 137 秒與 17 Takes、某一 Kit 名字、特定 aspect、具體 prompt inventory、worker／render 設定與已接受 Outputs。複雜 explainer 的 `CRAFT-NOTES` 說明可移植的是問題如何被理解並交給 owner；粉紅 treatment、scene inventory、production settings 屬於該作品選擇。[CRAFT-NOTES.md L1-L6](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/examples/complex-explainer/productions/explainer/CRAFT-NOTES.md#L1-L6)

範例的可移植精髓是：scene content、style、frame evaluation 與 shared mechanics 分開；meaningful event name 綁到 Script Moment；同一 accepted footage 可改 presentation；網站真實錄製與 authored illustration 分工；判斷回到它改變的 owner。[CRAFT-NOTES.md L23-L40](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/examples/complex-explainer/productions/explainer/CRAFT-NOTES.md#L23-L40) [CRAFT-NOTES.md L59-L79](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/examples/complex-explainer/productions/explainer/CRAFT-NOTES.md#L59-L79)

實際 podcast 範例把三個 lifestyle scene 合成短 montage，覆蓋 host examples 與 partner response 的 Selection，允許 partner voice 先於畫面回來；exact scene-to-cue reconstruction 改用分開 clips 與相鄰 Selections。[podcast/README.md L35-L50](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/examples/podcast/README.md#L35-L50)

實際 interview 範例把 shared encounter 作為 close views 的父依賴，讓同一 answer Moment 同時驅動 emoji strip、sound、colored flash；新生成若要追頭部字幕，先對實際新 footage 重新測量，不能重用舊片 frame 數字。[interview/README.md L7-L24](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/examples/interview/README.md#L7-L24) [interview/README.md L43-L57](https://github.com/hypit-ai/hypit/blob/d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66/examples/interview/README.md#L43-L57)

以上契約讓下一個 agent 拿到可查證的影片理解、可執行的生成需求與明確缺口；它仍需在自己的 Brief、Treatment、Script、Source 與實際 provider 能力中做最後選擇。
