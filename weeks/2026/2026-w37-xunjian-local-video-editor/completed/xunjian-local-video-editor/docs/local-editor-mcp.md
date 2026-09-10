# 本地剪輯工作台：Agent／MCP 操作契約

工作台與 Agent 共用同一個 Python 服務、SQLite 專案庫與背景工作佇列。MCP 使用 **stdio JSON-RPC**；內部 HTTP API 是同源工作台 API。

## 啟動與客戶端設定

在 PowerShell 執行：

    Set-Location <project-root>
    .\.venv\Scripts\python.exe -m pip install -e .
    .\.venv\Scripts\python.exe -m local_editor serve --port 8321 --data-dir .local-editor --open

工作台：[http://127.0.0.1:8321](http://127.0.0.1:8321)。保持服務執行，Agent 再啟動 stdio 橋接：

    .\.venv\Scripts\python.exe -m local_editor mcp --url http://127.0.0.1:8321

MCP 指令 stdout 僅輸出協定 JSON，直接啟動後等待 stdin 是正常行為。診斷訊息寫至 stderr；EOF 結束程序。

Claude Code／其他支援 MCP JSON 設定的客戶端：

    {
      "mcpServers": {
        "local-editor": {
          "command": "C:\\path\\to\\xunjian-local-video-editor\\.venv\\Scripts\\python.exe",
          "args": ["-m", "local_editor", "mcp", "--url", "http://127.0.0.1:8321"]
        }
      }
    }

Codex MCP 設定：

    [mcp_servers.local-editor]
    command = 'C:\path\to\xunjian-local-video-editor\.venv\Scripts\python.exe'
    args = ["-m", "local_editor", "mcp", "--url", "http://127.0.0.1:8321"]

先完成 editable install，可讓客戶端從其他工作目錄啟動模組。設定由使用者加入自己的 MCP 設定位置；本專案不會修改全域設定。

## v2：六個理解窗口

新 Agent 以 **editor_get_context → editor_inspect_range → editor_read_evidence → editor_prepare_edit → editor_apply_edit → editor_verify_edit** 建立閉環。需要訊號候選時加入 editor_analyze_range；需要局部語音複核時使用 editor_review_caption。工具足以取得時間軸狀態與區間聲畫，不需要讀原始碼、取得素材實體路徑或自行執行 FFmpeg。

| 窗口 | 回傳與判斷邊界 |
|---|---|
| editor_get_context | 目前 UI 專案與精確版本、選取片段／字幕／標題、播放頭、選取區間、brief、背景工作、Agent 最近活動、能力與缺少的分析 |
| editor_inspect_range | 最多 30 秒來源或合成聲畫、最多 8 張影格、短音訊／短片、逐字稿、圖層、來源映射與切點；回傳 job |
| editor_analyze_range | 同一區間的低音量、畫面變化、逐字稿語速／重複候選、字幕問題與未知；回傳 job。低音量與低像素變化均不代表可以刪除 |
| editor_prepare_edit | 將 operations 整批試剪，保存 before/after 快照；回傳精確差異、時長、受影響 ID、切點與警告，保持目前專案版本 |
| editor_apply_edit | 驗證提案 base_version 與 expected_version，整批原子套用成一個可復原步驟；保留 undo_receipt、修改副作用及驗證結果 |
| editor_verify_edit | 分開呈現結構檢查、字幕版面風險、切點問題、複核記錄與未檢查範圍；不會將已生成證據等同於已觀看或聆聽 |

第一個呼叫通常不帶參數：`editor_get_context({})`。UI 每次操作會同步情境，閒置時亦定期更新；記錄超過 60 秒失效，重啟後不沿用。沒有有效 UI 時回傳 `context_status: no_live_ui`，再以 `editor_list_projects` 與明確 `project_id` 選定背景專案。多頁籤狀態會回傳 `sessions`、`ambiguous` 與選取政策，亦可明確指定 `client_id`。UI 顯示版本與目前資料版本不同時，`ui.version_matches` 為 false，請重新讀取。

`brief` 是持久保存的剪輯方向，包含 `goal`、`audience`、`pacing`、`target_duration`、`must_keep`、`notes`。使用 `brief_update` 修改；目標時長為秒，`null` 清除，必須保留內容使用文字陣列。工具不會從影片名稱推測使用者意圖。

## 區間證據與媒體通道

呼叫範例：

```json
{
  "project_id": "project-id",
  "expected_version": 71,
  "time_space": "timeline",
  "range": {"start": 20, "end": 30},
  "include": ["composite_frames", "audio", "video", "transcript", "layers", "cut_boundaries"],
  "detail": "review",
  "max_frames": 4
}
```

- `time_space: source` 必須指定 `media_id`；時間表示來源媒體秒數。
- `time_space: timeline` 使用多軌、變速、位移、標題與字幕的合成結果，不接受 `media_id`。
- `include` 支援 `frames`、`composite_frames`、`audio`、`video`、`transcript`、`layers`、`cut_boundaries`。合成影格與正式輸出共用 FFmpeg 渲染器；低解析度及品質差異記錄於 `render_parity`。
- 觀察與分析單次最多 30 秒、8 張影格。長影片依章節或切點區間逐段取得；抽樣影格無法證明未抽樣部分沒有操作。
- 回傳的 job 可以 `editor_job_status({"job_id":"...","wait_ms":20000})` 等待。完成後使用 `result.evidence.evidence_id`。

`editor_read_evidence({"evidence_id":"..."})` 直接回傳 MCP 原生 `image`／`audio` 區塊及影片 `resource_link`。預設選取最多 3 張影格、1 段音訊與影片連結。需要其他影格時，使用 `file_ids` 明確選取。

結構 JSON 保留 `files` metadata、`included_file_ids`、`linked_file_ids`、`omitted_file_ids`、`coverage`、`unknowns` 及 `render_parity`，不放入 base64。二進位只出現在協定媒體區塊。影片採 `evidence://{evidence_id}/{file_id}`，客戶端可用 `resources/read` 取得；單次媒體回傳總上限 12 MiB，超過時縮短區間或減少檔案。HTTP 下載也只接受已登錄的不透明證據 ID，不接受任意 URL、重新導向或實體檔案路徑。

**語意由 Agent 對證據進行判斷。** 本機現有分析提供訊號與結構，OCR、人物偵測、游標操作辨識、跨段語意重錄判定、聽感自然度自動評分皆明確列為 unavailable／unknown，避免把剪輯 metadata 當成素材內部的畫面理解。

## 提案、複核與驗證

```json
{
  "project_id": "project-id",
  "expected_version": 71,
  "intent": "縮短片尾停頓，保留完整操作步驟",
  "operations": [
    {"action": "clip_update", "params": {"clip_id": "clip-id", "changes": {"end": 42.5}}},
    {"action": "brief_update", "params": {"goal": "清楚呈現教學步驟", "must_keep": ["提交後的成功結果"]}}
  ],
  "preview_range": {"start": 35, "end": 42}
}
```

提案包含 `edit_id`、`base_version`、`status`、`intent`、`operations`、`before`、`after`、`diff`、`affected_ids` 與 `warnings`。`editor_get_edit` 可讀回提案及目前 `can_apply`。

要比較套用前後，以 `editor_inspect_range` 指定提案 `edit_id`，分別給 `preview_side: before`／`after`，以及各側有效時間範圍。這些聲畫證據屬於提案快照，尚未改動現有專案。明確選定後再呼叫 `editor_apply_edit({project_id,expected_version,edit_id})`。批次上限 100 動作；`media_add`、`undo`、`redo` 禁止放入提案，匯入與歷程操作使用其專用流程。`smart_cut_apply` 可作為批次操作，參數仍是 `plan_id`、`candidate_ids`。

字幕的 `alignment_status` 分為 `valid`、`stale`、`missing`：

- `valid`：詞級文字／時間結構一致，仍須對照音訊確認辨識內容與實際時間。
- `stale`：文字或時間已變更，先前詞級資訊失效。`caption_update` 未同時提供一致的 `words` 時會揭露副作用與警告。
- `missing`：沒有可用詞級時間，不能宣稱局部刪字一定沒有截斷詞句。

`editor_review_caption({project_id,expected_version,caption_id,options?})` 擷取原句前後最多 2 秒上下文，重新執行本機辨識，回傳候選文字、ASR 詞時間、差異與音訊證據。**不會自動覆寫原字幕**；也未提供任意修正文稿的強制對齊。確認候選後，使用 `caption_update` 的 `changes:{text,start,end,words}` 明確採用需要的欄位，避免直接帶入候選的診斷 metadata。

實際檢視後可留下複核：

```json
{
  "project_id": "project-id", "expected_version": 72,
  "evidence_id": "evidence-id", "file_ids": ["frame-id", "audio-id"],
  "reviewer": "Agent 或人工複核者",
  "checks": ["visual", "audio"], "outcome": "pass",
  "notes": "已聽完此區間並查看列出的影格；切點語句連續，未遮擋已抽樣的操作結果。"
}
```

`editor_record_review` 強制指定實際檢視的 `file_ids`。`checks` 可包含 `visual`、`audio`、`subtitle_layout`；證據的專案／版本／提案與檔案類型必須匹配，字幕版面需時間軸合成證據。提案複核另帶 `edit_id` 與相符的 `preview_side`；before 的審閱不會計入 after。驗證提案亦可指定 `preview_side`，預設 after；此欄位只能與 `edit_id` 一起使用。記錄清楚標示 `reviewer_self_report`，生成、傳送或結構檢查皆不會自動登錄通過。

`editor_verify_edit` 列出目前精確版本的結構與字幕問題、已登錄複核的範圍、未完成的聲音／畫面檢查。抽樣影格檢查、整段音訊聆聽與完整影片觀看不可互相替代；局部通過不擴張為全片通過。

## 既有素材與智能剪口播 Workflow

1. **editor_doctor** 檢查 FFmpeg 與本機語音模型；**editor_list_projects** 選擇專案。
2. **editor_get_project** 取得精確 version 與素材、片段、來源字幕。
3. **editor_import_media** 指定本機路徑，取得新 version 與 media.id。
4. **editor_edit → clip_add** 把素材加入時間軸。
5. **editor_transcribe** 建立字幕，或 **editor_import_captions** 匯入 SRT／VTT。
6. **editor_prepare_smart_cut** 分析口播；每 1–2 秒呼叫 **editor_job_status**。
7. 審閱 result.plan.candidates 的時間、原因及文字，再以 **editor_apply_smart_cut** 明確列出 candidate_ids。
8. 重新讀取專案檢查結果；需要復原時 **editor_edit → undo**。
9. **editor_export_captions** 輸出時間軸字幕；**editor_export** 渲染 MP4，輪詢取得本地 path 與下載 url。

智能剪口播候選使用來源媒體時間；套用時投射到主影片軌，再同步壓縮其他軌道。字幕依來源範圍、變速與時間軸位移映射。提案建立後若專案版本變動，需重新讀取及建立提案。

「刪文剪片」使用 **editor_prepare_plan**，把已讀取字幕的來源區間建立為候選；**caption_delete** 只移除字幕文字。兩種操作分開，避免修改文字時誤刪影片。

## 工具清單

| 工具 | 用途 | 寫入／背景工作 |
|---|---|---|
| editor_doctor | 執行環境與模型狀態 | 讀取 |
| editor_list_projects | 專案摘要 | 讀取 |
| editor_create_project | 建立專案 | 建立 |
| editor_get_project | 編輯狀態及版本 | 讀取，省略波形及縮圖降低 token |
| editor_import_media | 複製素材至受管理目錄 | 精確版本寫入 |
| editor_edit | 剪輯、字幕、標題、畫布與復原 | 精確版本寫入 |
| editor_prepare_smart_cut | 停頓、語助詞、相鄰重複字幕分析 | 背景提案 |
| editor_prepare_plan | 指定來源區間建立刪文剪片提案 | 保存提案，保留專案版本 |
| editor_get_smart_cut_plan | 提案與候選原因 | 讀取 |
| editor_apply_smart_cut | 套用指定候選 | 精確版本寫入 |
| editor_import_captions | SRT／VTT → 來源字幕 | 精確版本寫入 |
| editor_export_captions | 時間軸字幕 → SRT／VTT／TXT | 讀取 |
| editor_transcribe | 本機 faster-whisper 辨識 | 背景工作；完成時驗證版本 |
| editor_export | 當前快照 → MP4 | 背景工作 |
| editor_job_status | 狀態、進度與結果 | 讀取 |
| editor_get_context | UI 情境、剪輯方向與能力探索 | 讀取 |
| editor_inspect_range | 來源／合成聲畫證據 | 背景工作，寫入證據快取，保留專案 |
| editor_analyze_range | 訊號、字幕／切點分析與原始證據 | 背景工作，寫入證據快取，保留專案 |
| editor_prepare_edit | 批次試剪、差異與不可變前後快照 | 保存提案 |
| editor_get_edit | 提案狀態、差異與可套用條件 | 讀取 |
| editor_apply_edit | 整批套用為一個復原步驟 | 精確版本寫入 |
| editor_verify_edit | 結構、版面風險與複核覆蓋 | 讀取 |
| editor_review_caption | 局部 ASR 複核與音訊證據 | 背景工作，保留字幕 |
| editor_record_review | 登錄具體證據的複核者自述 | 保存版本綁定複核記錄 |
| editor_read_evidence | 原生影格／音訊與影片資源 | 讀取，單次二進位上限 12 MiB |

每次變更提供最近讀取的 **expected_version**。通用編輯動作：

| action | params 範例 |
|---|---|
| rename | {"name":"第一集"} |
| settings | {"width":1080,"height":1920,"fps":30} |
| brief_update | {"goal":"教學清楚完整","audience":"初學者","pacing":"保留操作等待","target_duration":180,"must_keep":["最後成果"],"notes":"繁體字幕"} |
| clip_add | {"media_id":"...","track":"video","start":0,"end":10,"offset":0} |
| clip_update | {"clip_id":"...","changes":{"speed":1.1,"volume":0.8,"brightness":0.05}} |
| clip_move | {"clip_id":"...","changes":{"offset":3,"track":"overlay"}} |
| clip_split | {"clip_id":"...","at":5}，at 為時間軸秒 |
| clip_delete | {"clip_id":"...","ripple":false} |
| captions_set | {"media_id":"...","captions":[{"start":0,"end":2,"text":"繁體字幕"}]} |
| caption_update | {"caption_id":"...","changes":{"text":"修正字幕"}} |
| caption_delete | {"caption_id":"..."} |
| caption_style | {"font_size":48,"color":"#ffffff","background":"#000000","position":"bottom"} |
| title_add | {"text":"開場","start":0,"end":3,"font_size":64,"color":"#ffffff","x":0,"y":0} |
| title_update | {"title_id":"...","changes":{"text":"新標題"}} |
| title_delete | {"title_id":"..."} |
| titles_set | {"titles":[{"text":"標題","start":0,"end":3}]} |
| undo／redo | {} |

片段 start/end 為來源秒，offset 為時間軸秒；實際時長為 (end-start)/speed。track 支援 video、audio、overlay，音訊素材使用 audio。

`tools/list` 逐一揭露 action 的參數 schema，`action` 與 `params` 以 `oneOf` 綁定，不接受未知欄位、錯誤型別、非有限數值或超出範圍。MCP 宣告每個 action 的標準寫法，HTTP／服務保留既有 UI 使用的別名；驗證器與 schema 位於同一模組，避免文件與實作分離。縮短回應仍保留 `warnings`、`side_effects`、復原憑據及驗證結果。

## HTTP 契約

JSON 請求與回應皆 UTF-8。先 GET /api/session 取得 token；寫入帶 X-Editor-Token 與 Content-Type: application/json。跨來源要求回傳 403。錯誤格式：

    {"error":{"code":"version_conflict","message":"專案已變更，請重新讀取。"}}

以下 {id} 為 project_id：

| Method／路徑 | Body／結果 |
|---|---|
| GET /api/session | {token,version} |
| GET /api/doctor | FFmpeg、FFprobe、辨識模型狀態 |
| GET /api/projects | {projects:[摘要]} |
| POST /api/projects | {name,width?,height?,fps?} → project |
| GET /api/projects/{id} | project，附素材 URL、duration、history、can_undo、can_redo |
| POST /api/projects/{id}/edit | {expected_version,action,params} → project |
| POST /api/projects/{id}/media/import | {expected_version,path} → project |
| POST /api/projects/{id}/media/upload?name=...&expected_version=N | 原始 File bytes，需 Content-Length；上限 10 GiB，1 MiB 區塊串流保存 |
| GET /api/projects/{id}/media/{media_id}/file | 受管理素材，支援 HTTP Range |
| GET /api/projects/{id}/media/{media_id}/thumbnail | 已產生的縮圖 |
| POST /api/projects/{id}/smart-cut | {expected_version,media_id,options?} → job |
| POST /api/projects/{id}/plans | {expected_version,candidates,metadata?} → plan |
| GET /api/projects/{id}/plans/{plan_id} | plan |
| POST /api/projects/{id}/smart-cut/apply | {expected_version,plan_id,candidate_ids} → project |
| POST /api/projects/{id}/captions/import | {expected_version,media_id,text,format} → project |
| GET /api/projects/{id}/captions/export?format=srt | {format,text} |
| POST /api/projects/{id}/transcribe | {expected_version,media_id,options?} → job |
| POST /api/projects/{id}/export | {expected_version,options?} → job |
| GET /api/jobs/{job_id} | job |
| GET /api/jobs?project_id=... | 最近 50 筆 jobs |
| GET /api/exports/{job_id}/{filename} | 成功工作已登錄的輸出檔 |
| GET /api/events | 最近 80 筆 UI／Agent 操作摘要 |
| GET /api/context?project_id=...&client_id=... | v2 情境、能力、剪輯方向；兩個 query 皆可省略 |
| POST /api/context | UI 心跳 {client_id,project_id,project_version,selected,playhead,range,mode,media_id,focused,sequence}；不修改專案 |
| POST /api/agents | MCP 連線／活動記錄 {client_id,client_info,status,last_tool} |
| POST /api/projects/{id}/inspect | {expected_version,time_space,range,media_id?,include?,max_frames?,detail?,edit_id?,preview_side?} → job |
| POST /api/projects/{id}/analyze | {expected_version,time_space,range,media_id?,max_frames?,options?,edit_id?,preview_side?} → job |
| POST /api/projects/{id}/edits | {expected_version,intent,operations,preview_range?} → proposal |
| GET /api/projects/{id}/edits/{edit_id} | proposal、current_version、can_apply |
| POST /api/projects/{id}/edits/apply | {expected_version,edit_id} → project＋undo_receipt＋verification |
| POST /api/projects/{id}/verify | {expected_version,edit_id?,preview_side?,range?} → report |
| POST /api/projects/{id}/captions/review | {expected_version,caption_id,options?} → job |
| POST /api/projects/{id}/reviews | {expected_version,evidence_id,file_ids,reviewer,checks,outcome,notes,edit_id?,preview_side?} → record |
| GET /api/evidence/{evidence_id} | 無實體路徑的 manifest |
| GET /api/evidence/{evidence_id}/files/{file_id} | 已登錄證據二進位，支援 Range |

工作結果範例：

    {
      "id": "job-id", "kind": "smart_cut", "project_id": "project-id",
      "project_version": 4, "status": "succeeded", "progress": 100,
      "result": {"plan": {"id": "plan-id", "base_version": 4, "candidates": []}}
    }

status 為 queued/running/succeeded/failed；progress 為 0–100。GET /api/jobs/{job_id}?wait_ms=20000 最多等待 20 秒。轉錄結果含 project；輸出結果含 path/url/project_version/current_version；觀察結果含 evidence、structure、cache_hit、current_version。輸出與觀察使用排入當下快照，後續編輯不污染該次渲染；結果版本與目前版本必須再比對。預設 2 個工作執行緒、最多 8 個未完成工作；額滿回傳 429。重啟將未完成工作標記為 interrupted，可重新執行。

## 本地資料與邊界

- 服務僅綁定 127.0.0.1，檢查 Host、Origin、Sec-Fetch-Site 與寫入 token，拒絕跨站讀取及變更。
- 檔案下載僅提供套件前端資源、專案登錄且位於 assets 的素材／縮圖、成功渲染且登錄的輸出。
- 匯入保留來源，副本位於 assets/。通用 edit 禁止偽造媒體路徑。
- 專案／歷程／提案位於 projects/projects.sqlite3；工作記錄在 jobs/，渲染在 exports/。
- 安全模型適用單一使用者桌面，本機使用者與程序可操作服務；未提供多使用者登入或遠端服務。
- 操作事件為程序內近期記錄；專案版本與可復原歷程持久保存。長期稽核可另加事件存儲。
- 證據位於 evidence/{opaque_id}/，使用內容／版本／請求鍵快取並保存 manifest。複核位於 reviews.json，綁定專案版本及證據；UI 情境與 Agent 最近活動為短期狀態。

## 驗證與協定來源

    .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_local_editor_api.py" -v
    .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_local_editor_mcp_v2.py" -v

測試涵蓋真實 stdio 子程序、live HTTP 共用專案、初始化與錯誤、版本衝突、字幕剪片、串流上傳、Range、來源限制及工作重啟。媒體編解碼與辨識由媒體引擎測試另外驗證。

v2 增加真實 stdio 二進位 image/audio 與 video resource 讀取、精確 action schema、錯誤參數拒絕、情境同步、提案套用、過期版本、證據 URL／ID 邊界與 12 MiB 上限驗證。傳輸測試的二進位 fixture 僅驗證協定；實際 FFmpeg 與本機 ASR 另由媒體／證據測試驗證。

MCP 預設 2025-11-25，可協商支援原生媒體資源的 2025-06-18。實作 initialize、notifications/initialized、ping、tools/list、tools/call、resources/list 與 resources/read；沒有 resources 訂閱或工具動態變更通知。MCP 初始化與工具呼叫登錄客戶端活動，EOF 標記斷線。協定依據：[初始化與版本協商](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)、[stdio 傳輸](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)、[工具 schema 與媒體結果](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)、[媒體資源](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)。
