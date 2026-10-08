# 工作檔案與時間座標

先執行 `interview.py init` 取得目前模板，勿憑印象重建完整 schema。此頁的片段展示欄位關係；例子使用虛構的園藝教學素材，無真人經歷、授權或已完成核聽的主張。完整建片仍需來源、候選審查、音檔與字幕。

## 哪個檔案負責什麼

| 檔案 | 內容 |
|---|---|
| `brief.json` | 觀眾、用途、標題、承諾、本次要求與狀態 |
| `sources.json` | `sources[]` 中的來源 ID、網址、路徑、標題、頻道、片長與逐字稿 |
| `questions.json` | `questions[]` 的 `id`、`order`、`question`、`viewer_pain`、`key_answer` |
| `candidates.json` | 原片候選 `id/source_id/question_id/start/end`、gate、分數與理由 |
| `opening-selection.json` | 封面承諾、全片 coverage、逐題比較、選定首題與來源項目 |
| `rundown.json` | `items[]`：opening、bridge、source、outro 的編排 |
| `narration-plan.json` | 片頭背景、口播覆蓋原句、原文術語與核聽證據 |
| `markers.json` | 每段來源的視覺判斷、依原片時間出現的重點 |
| `art-direction.json` | 人物／主題素材、來源資訊與片尾內容 |
| `thumbnail-brief.json` | 自有參考、標題層級、肖像來源、輸出和審查 |

ID 使用小寫英文字母起頭，再接小寫字母、數字或連字號，且在各清單內唯一。來源、問題、候選和 rundown 用 ID 相連；不要靠顯示標題串接。

## 來源、問題與候選

```json
{"sources":[{"id":"s1","url":"","path":"media/source.mp4","title":"示範：如何判斷澆水時機","channel":"示範教學","duration_seconds":90,"metadata_verified":false,"transcript_path":"research/transcript.json"}]}
```

```json
{"selection_policy":"content-led; no fixed quota","questions":[{"id":"q01","order":1,"question":"植物真的需要水嗎？","viewer_pain":"只按固定天數澆水","key_answer":"先觀察土壤與植物狀態","packaging_promise":null}]}
```

候選最小骨架如下；未核實 gate 先留 `null`，尚不能排進正式影片。`evidence.transcript` 必須定位真實逐字稿與時間；「待補」不能充當證據。

```json
{"id":"soil","source_id":"s1","question_id":"q01","start":10,"end":25,
 "gates":{"complete_thought":null,"context_preserved":null,"faithful_claims":null},
 "gate_reasons":{"complete_thought":"需核對句尾","context_preserved":"需核對後續限定","faithful_claims":"需核對摘要與原句"},
 "scores":{"content_value":null,"specificity":null,"standalone":null,"hook":null,"narrative":null,"emotion":null,"actionability":null,"audiovisual":null},
 "score_reasons":{"content_value":null,"specificity":null,"standalone":null,"hook":null,"narrative":null,"emotion":null,"actionability":null,"audiovisual":null},
 "evidence":{"transcript":"research/transcript.json，10–25 秒的示範台詞","visual_review":null,"audio_review":null}}
```

## Rundown 的四種項目

`interview.py plan` 會依已撰寫的問題建立骨架。來源段可增加為同題多段，每段都要有自己的候選。`in/out` 必須與候選 `start/end` 一致；改切點就更新候選審查。

```json
{"items":[
 {"id":"i01","type":"opening","chapter":1,"question_id":"q01","title":"植物真的需要水嗎？","question":"植物真的需要水嗎？","text":"此處填完整開場口播。","audio_path":"voice/i01.wav","lead":0.4,"tail":0.9,"card_beats":[]},
 {"id":"c01-01","type":"source","chapter":1,"question_id":"q01","title":"先觀察土壤","source_id":"s1","in":10,"out":25,"candidate_id":"soil","clip_path":"media/c01-01.mp4"},
 {"id":"o01","type":"outro","chapter":1,"title":"觀看完整教學","text":"原影片連結放在說明欄。想看更多相關內容，歡迎訂閱。","audio_path":"voice/o01.wav","lead":0.4,"tail":1.5}
]}
```

`bridge` 與旁白段相同，另填 `chapter/question_id/question`，並可用 `visual: {"layout":"question","lines":["下一題"],"nodes":[]}` 設定短字卡。不要把來源全文塞進旁白。

`opening-selection.json` 的 `candidates[]` 每列使用 `question_id`、`first_source_item`、三個開場 gate、五維分數及理由、`evidence`。最上層 `selected_question_id` 和 `selected_source_item` 必須對應 rundown 的第一個來源段；`coverage.whole_source_reviewed` 只有完成全片審閱後才改為 `true`。

## 三種時間不能混用

| 欄位 | 起算點 |
|---|---|
| 候選 `start/end`、來源段 `in/out`、來源字幕、markers | 原片零秒 |
| 旁白字幕 `start/end`、`card_beats`、核聽範圍 | 該項最終 WAV 的零秒 |
| `qa/resolved-plan.json` 的 `start/end/frames` | 成片零秒，由 resolve 計算 |

原片 10–25 秒切成來源段後，marker 的 14 秒仍填 `14`。若該來源段在成片 40 秒開始，marker 出現在成片 44 秒；不把 `44` 寫回來源 marker。

來源字幕使用 `{"cues":[{"source_id":"s1","start":10,"end":14,"zh":"先觀察土壤。","en":"Observe the soil first."}]}`。`en_display` 可保存有依據的顯示修正，原 ASR 與修正紀錄另存；字幕跨越切點時先忠實分句。

旁白字幕使用 `{"items":[{"item":"i01","cues":[{"start":0,"end":2.4,"zh":"此處為實際說出的第一句。"}]}]}`。上例秒數只示範格式，須按自己的 WAV 重新對齊。

開場 `card_beats` 須覆蓋整個實測 speech duration、相鄰時間連續，且至少三拍。可用 hook → 人物 → 問題；訪談可分主持人與來賓兩拍，單人來源用講者一拍。以下只示範欄位；秒數須以實際 WAV 修訂：

```json
[
 {"type":"question","start":0,"end":3,"title":"植物真的\n需要水嗎？","kicker":"第一個問題","art_key":"hook","art_alt":"示範植物插圖"},
 {"type":"person","start":3,"end":9,"person_role":"speaker","portrait_key":"host","name":"示範講者","role":"園藝教學者","body":"本段填經查證的相關背景"},
 {"type":"question","start":9,"end":12,"title":"先看土壤，\n再決定時機","kicker":"先聽來源回答","art_key":"hook"}
]
```

人物卡 `person_role` 可用 `host/guest/speaker`，`person_label` 可覆寫顯示稱呼。`portrait_key` 和 `art_key` 指向 `art-direction.json.assets` 內的本機 PNG/JPEG/WebP 路徑；單人來源也可以把講者照片放在 `assets.host`。`art-direction.json` 還需填 `source_channel`、`source_topic_lines`、`runtime_label`，供片尾使用。

## 原片縮入與逐點揭示

```json
{"clock":"original source seconds",
 "review":[{"item":"c01-01","decision":"annotate","reason":"兩個條件需依說話順序區分","source_evidence":"示範逐字稿 12–20 秒","marker_ids":["soil-check"]}],
 "markers":[{"id":"soil-check","item":"c01-01","start":12,"end":23,"type":"pair","eyebrow":"澆水前先看",
 "steps":[{"at":12,"text":"土壤狀態"},{"at":17,"text":"植物反應","display_lines":["植物反應"]}]}]}
```

每個來源項目恰有一筆 review。`keep_source` 表示原畫面足以支撐理解，`marker_ids` 使用空陣列並寫理由。marker 需落在來源段內、結束後留 0.7 秒還原；`steps.at` 遞增。`display_lines` 接起來須等於 `text`。

## 正式旁白輸入與實測輸出

`voice/approved-narration.txt` 精確收錄 rundown 中所有非 source 項目的 `text`，維持順序，以兩個換行分隔；只允許 UTF-8 BOM 與一個檔尾換行的差異。它適用自錄提示稿，也適用 TTS 輸入稿。

`narration-plan.json` 的 coverage 字串要逐字出現在 opening 的 `text` 中；背景只放字卡不算口播覆蓋。詳見 [聲音與專名](voice-and-terms.md)。

`resolve` 量測 WAV、加上 `lead/tail`、向上取整為影格，產生 `qa/resolved-plan.json`、字幕時間軸、中英 SRT、章節與實測 rundown。它也記錄文字、字幕、profile 和 WAV 的 hash；後續變更會要求重新 resolve。

若最終片長低於本次最低要求，補選能回答問題的來源內容，再重算。不要增加空白或重複旁白湊時長。所有教學示例皆為資料格式示範，沒有代表真人來源審查已完成。
