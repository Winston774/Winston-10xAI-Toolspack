# 分析文件與索引契約 v1.0

## 交付結構

```text
<analysis-dir>/
  VIDEO_UNDERSTANDING.md     人可直接讀完的主文件
  analysis.json              可查核的事件／證據／素材索引
  transcript/                有語音辨識時保存原始輸出與校訂版本
  evidence/                  manifest、幀圖、片段、音訊
  PROGRESS.md                partial 或仍有下一步時保留
```

用 `assets/VIDEO_UNDERSTANDING.template.md` 及 `assets/analysis.template.json` 起稿；模板本身未完成，不可作為驗收通過的分析。索引的時間皆為秒，相對第一條視訊軌的第一張解碼影格。音訊與裁切片段的局部時間須映回此時鐘。所有範圍採 `[start, end)`；最後一段的 end 可等於總長。

主文件承載完整解釋、逐段事件表、系統細節、聲音、素材需求及交接規則。索引是精簡登錄，`EV-*`、`SYS-*`、`ASSET-*`、`E-*` ID 與主文件一致；避免兩邊寫成不同版本。主文件遇到有意義的事實都應附時間及相關 ID。

## analysis.json 欄位

| 欄位 | 必填內容 |
| --- | --- |
| `schema_version` | 字串 `1.0` |
| `source` | `path`、64 位 SHA-256、`duration_seconds`、`clock: video_start`、`audio_present` 布林 |
| `inspection.video` | 已檢視區間 `{start,end,method,evidence_ids}`；method 為 `playback`、`dense_frames`、`sampled_frames`；dense_frames 另需 `max_gap_seconds` |
| `inspection.audio` | 已檢視區間，同上；method 為 `listened`、`transcript_only` |
| `evidence` | `{id,path,kind,start,end,reviewed}`；kind 為 `frame`、`clip`、`audio`、`transcript`、`metadata` |
| `systems` | `{id,role,description}`；role 為 `a_roll`、`b_roll`、`caption`、`typography`、`mg_ui`、`effect`、`audio` |
| `events` | `{id,start,end,system_ids,anchor,observed,interpretation,confidence,evidence_ids}` |
| `assets` | `{id,kind,description,event_ids,depends_on,generation_brief}`；kind 由所需產物描述，依賴指其他 asset ID |
| `unknowns` | `{id,question,start,end,blocks_generation}`；unknown 可定位全片或某段 |
| `handoff` | `{status,invariants,changeable,next_steps}`；status 為 `partial` 或 `ready`，後三者是字串陣列 |

每個 `anchor` 含 `kind: speech|action|clock`、`cue`、`occurrence`（語句／動作第幾次出現，從 1 起；clock 用 null）、`timing_precision: frame_verified|aligned|estimated`。`confidence` 為 `high|medium|low`，表示該事件分析的把握，不是模型機率。

影格的 start=end，表示單一觀測時間，且必須嚴格小於影片總長；事件、檢視區段與其他連續媒體 start<end。每個引用必須存在；IDs 在各類中唯一。素材依賴不得成環。所有數字應為有限值，不接受 NaN、Infinity 或負時間。

證據 `path` 用相對 analysis.json 目錄的路徑，留在交付資料夾內。原始影片 `source.path` 可為絕對路徑或原始 URL；不要求複製大檔，但需讓接手者知道原片是否隨包附帶。helper 的 manifest 另存 source hash 與準備參數，可供交叉檢查。

## observed 與 interpretation

- `observed`：確實看見或聽見的行為，含具體內容／形態／變化。
- `interpretation`：對敘事功能、注意力與表意的解釋；可明寫暫定。
- `generation_brief`：下一階段的製作需求與建議，不能混成原片事實。
- 無法確定的字體、相機、光源、音樂名稱、原始素材或特效參數放 `unknowns`，或在主文件以標明為估計的描述處理。

系統描述在主文件中應覆蓋內容、外觀、空間、進場、活躍、持續、變化、退場和觀眾作用。素材 brief 應包含主體／場景、鏡頭／裁切、必要動作、起終狀態、版面預留區、身份／道具連續性、獨立後製內容、語義同步，以及必要輸入證據；靜態圖文可省略無關的表演項目。

## 檢視、覆蓋與完成的不同含義

只將實際完成的檢視寫入 `inspection`。抽出 0–30 秒的檔案，不代表已檢視該 30 秒。每列須引用 `reviewed: true` 且相符類型的證據：playback→clip；dense/sampled frames→frame；listened→audio 或含音訊 clip；transcript_only→transcript。連續媒體證據的區間聯集需覆蓋所宣告的檢視區間；事件至少有一項證據與自身區間相交。

`dense_frames` 必須引用至少兩個不同時間的 frame，並寫 `max_gap_seconds`：將引用的幀時間與區段首尾排序後，計算相鄰時間的最大差。驗證器會核對這個值，抽樣密度是否足以解釋該段行為仍需 agent 判斷。主文件及證據 manifest 保留間距。metadata 或概覽圖的存在不應被當成完成檢視。轉錄只能支持文字內容，不能替代音樂、音效、語氣和混音的聆聽。

`ready` 表示有足夠證據可以進行生成規劃，條件為：

1. 事件區間聯集覆蓋原片 0 到總長，重要系統沒有已知遺漏；
2. 已播放或密幀檢視的區間聯集覆蓋全片；只做粗抽樣不能標 ready；
3. 有音軌時，`listened` 覆蓋全片；無音軌時，audio_present=false 且 inspection.audio 留空；
4. 沒有 `blocks_generation: true` 的待解問題；素材需求足以表達所有要保留的部分。

機械驗證對合併後的總未覆蓋時間容許最多 0.001 秒、且不超過該區段 0.1%，避免多個小缺口累積。不能把容許值當抽樣精度。驗證器不解碼證據檔，不驗證媒體類型宣告、實際聆聽或語義；`reviewed` 是執行者的檢視紀錄。是否真的看／聽過、抽樣密度是否足夠、觀察是否正確，由執行 agent 對證據負責。驗證器通過只表示紀錄一致。

不能滿足上述條件時交付 `partial`，寫明已完成範圍與缺口，讓接手者補足相應事件；不把能力缺失當作素材原本不存在。若素材原本有音軌卻抽取失敗，audio_present 仍維持 true。

## 下游讀取順序

1. 閱讀主文件的狀態、整體論述與重大問題。
2. 沿主文件系統及事件 ID，在索引找 source time、證據與素材依賴。
3. 補完阻塞問題，再依使用者的新目標決定人物、產品、台詞與風格變更。
4. 依素材依賴準備資產；以新語音／動作重建語義 anchor，重新建立目標時間軸。
5. 由原片關係制定驗收：事件順序、圖層持續、字幕可讀、聲畫同步、生成片長及交接處的畫面覆蓋。

若下一階段使用 Hypit、HyperFrames、Remotion 或其他生成方式，轉換器可讀此契約，但本技能不依賴其 DSL 或 runtime。
