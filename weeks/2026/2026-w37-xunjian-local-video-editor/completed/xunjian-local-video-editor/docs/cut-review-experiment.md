# 切點證據與提案驗收實驗

分支：`feat/cut-evidence-acceptance`。

## 試用

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/create-cut-review-demo.py
.\.venv\Scripts\python.exe -X utf8 -B -m local_editor serve --port 8322 --data-dir .editor-test-data/cut-review
```

開啟 http://127.0.0.1:8322 →「切點實驗 A｜合成兩影格黑閃」→ Agent。

1. 觀察區間填 1–3 秒，按「檢查切點與黑畫面」。
2. 預期掃描 40 個影格，在 1.95 秒定位 1 組、連續 2 影格的近黑候選。
3. 打開「待審閱」的修正提案，分別取得修改前、修改後聲畫。
4. 修改後保留紅藍硬切，預期黑畫面候選為 0。
5. 按「更新提案驗收結果」，確認時長 3.9 秒、主影片無空隙、1–3 秒無近黑候選。
6. 可套用與復原。套用後驗收需重新取得新版證據；舊提案證據不計入新版。

示範為合成色塊＋440 Hz 測試音，不代表真實口播品質。資料保存在 `.editor-test-data/cut-review`，與日常 `.local-editor` 分開。

## Agent 工作流程

沿用 25 個工具，不新增同義工具：

`get_context → prepare_edit(checks) → inspect_range(edit_id, sampling, scan_black_frames) → job_status → read_evidence → verify_edit → apply_edit → inspect_range(新版) → verify_edit`

觀察參數範例（ID／版本須由工具讀取）：

```json
{
  "project_id": "PROJECT_ID",
  "expected_version": 1,
  "time_space": "timeline",
  "range": {"start": 1, "end": 3},
  "sampling": {"strategy": "cut_boundaries", "offset_frames": [-2, -1, 0, 1, 2]},
  "scan_black_frames": true,
  "max_frames": 8,
  "include": ["frames", "audio", "video"]
}
```

`prepare_edit.checks` 支援：

```json
[
  {"kind": "no_timeline_gaps"},
  {"kind": "duration_between", "min": 3.89, "max": 3.91},
  {"kind": "no_black_frames", "range": {"start": 1, "end": 3}}
]
```

`get_edit.acceptance` 是建立提案時的結果；動態結果以 `verify_edit.acceptance` 為準。這是可見的驗收報告，未新增自動禁止套用政策。

## 模組契約

| 模組 | 責任 |
|---|---|
| `cut_review.py` | 切點取樣、來源映射、全部解碼影格近黑掃描 |
| `acceptance.py` | 簡單明確的驗收條件；無證據維持 pending |
| `evidence.py` | 真實合成、候選影格優先、來源時間與 file ID |
| `contracts.py` | HTTP／MCP 共用參數、範圍與上限 |
| `observation_service.py` | before／after／新版隔離、快取與驗收結果 |
| `web/agent-workspace.js` | 工作台按鈕、候選摘要、前後比較與驗收 |

Finding 包含 code、range、frame_count、target_ids、source_mapping、bbox、版本、提案側與 evidence_id。bbox 使用專案像素，近黑候選涵蓋全畫布。file_ids 指向候選圖片；被圖片數量上限省略時為空。

## 證據界線與成本

- 保留 30 秒／8 張圖限制；多切點先取接縫，再取最近鄰，回報省略數量。異常影格優先，MCP 預設 3 張也優先選候選。
- 近黑掃描處理區間每個解碼影格，以 FFprobe PTS 對應時間；空解碼、數量不符或超過一格的覆蓋缺口會失敗。非整格尾端可能取整，會回報實際 range 與 uncovered_tail_seconds，驗收不涵蓋未渲染尾段。
- 空間縮至 160×90；灰階值 ≤24 的像素比例 ≥98% 列候選。沒有時間降採樣。這是固定初版門檻，暗場與淡出仍需複核。
- 候選最多回傳 100 組並明示截斷；截斷時不以未找到區間候選宣稱通過。
- 來源素材觀察不接受切點策略／黑畫面掃描；驗收依時間軸合成畫面。
- 自動條件通過不代表看過、聽過或敘事自然；record_review 保持既有版本與覆蓋範圍規則。
- 即時 UI 播放器的 seek／解碼異常、字幕實際 bbox、OCR、語意判斷與音訊銜接評估留待後續實驗。
- 套用後自動找最近 100 份提案中 applied_version 等於目前版本的規格；後續任意修改使版本變更，不沿用舊規格。

## 驗證

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -p test_local_editor_cut_review.py -v
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -p 'test_local_editor*.py'
node --test tests/editor_frontend.test.mjs
```

FFmpeg／FFprobe 無法啟動時，媒體測試會 skipped；不得當作真實媒體驗收通過。
