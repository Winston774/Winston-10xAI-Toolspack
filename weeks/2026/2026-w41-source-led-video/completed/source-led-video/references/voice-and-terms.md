# 旁白、專有名詞與聲音版本

旁白以短引言和問題串接來源，音色由創作者自行選擇。可使用自錄聲音、取得使用權的聲音或可用 TTS；技能不附個人聲音、參考錄音、模型權重或帳號，也不會自動呼叫語音服務。

## 先檢查文本，再試聲

先完成 `rundown.json` 的旁白、`narration-plan.json` 和 `voice/approved-narration.txt`。最後一份精確等於所有非 source 項目的 `text`，以兩個換行分隔。自錄也保存這份提示稿，方便修訂追溯。

```powershell
& $py -X utf8 "$skill/scripts/check_narration.py" $episode --text-file voice/approved-narration.txt --out qa/narration-script.json
```

通過後，先錄製或合成含最難人名、術語與問題句的一小段，檢查發音、語速、停頓和混合語言的自然度，再做其餘段落。已被授權的聲音製作不需再新增固定批准關卡。

TTS 的語言指示無法修正已寫成中文音譯的正式稿。英文姓名與英文術語保留原始拼字；中文姓名依原本語言呈現。若來源使用縮寫或短名，先確認其身分和可用形式，再記入術語表。

## 片頭語意計畫

`narration-plan.json` 的 `opening` 使用以下欄位；短句必須真正在口播中出現。

| 欄位 | 用法 |
|---|---|
| `source_format` | `interview` 或 `solo` |
| `source_published_at` | 原片發布日期，`YYYY-MM-DD` |
| `host` | `name/program/positioning/credibility/evidence`；單人來源記講者 |
| `guest` | `name/role/role_as_of/evidence`；單人來源為 `null` |
| `why_now` | `explanation/time_basis/evidence/verified_at` |
| `coverage` | `host_excerpt/guest_excerpt/why_now_excerpt/question_excerpt` |

`host_excerpt` 包含原文姓名、節目名、定位與相關背景；`guest_excerpt` 包含原文姓名與當時職務。`why_now_excerpt` 包含所登錄的理由。這些 excerpt 須逐字存在 opening `text`，不能改成字卡文案。

`time_basis` 可用 `source_period`、`current_verified` 或 `evergreen`。只有引用本次近期資訊時才需要 `current_verified` 與核實日期；來賓職務須對應原片時點。單人來源將 `guest_excerpt` 設為 `null`。

## 術語表與未完成的核聽

下例使用虛構人物名稱，僅示範欄位。未核聽時保留空陣列與空發音來源，不預先聲稱已確認。

```json
{
  "canonical":"Alex Rivers",
  "spoken_forms":["Alex Rivers","Alex"],
  "language":"en",
  "avoid_forms":["亞歷克斯"],
  "source_evidence":"research/name-notes.md：示範人物名稱",
  "pronunciation_reference":"",
  "audio_reviews":[]
}
```

清點全部人名、節目、品牌、產品、縮寫與技術術語後，才將最上層 `terminology_reviewed` 設為 `true`。該欄位表示完成清點，不能證明音訊發音正確。未出現在旁白的詞無須塞入清單。

Latin 字母組成的人名與節目名要登錄可用的 `spoken_forms`；姓名第一次可用全名，其後短名須能清楚指涉。不要為了讓某個引擎發聲而把中文音譯混入正式稿；引擎若支援發音字典，將指令與正式稿分開保存。

參考原講者或主持人真實發音，保留 URL 與時間碼；字典可輔助一般術語。聽不清的姓名留待確認，不猜測拼音或 IPA 當成已驗證事實。

## WAV 與速度

預設 `narration.engine` 為 `external-audio`，速度係數 `1.0`。先依原始音檔聽感調整；不同引擎的 1.0 不代表同一語速。問題、陌生名詞與轉折需留觀眾反應時間。

逐段 WAV 可直接放到 rundown 的 `audio_path`，例如 `voice/i01.wav`。保存原始錄音或未處理 take；如需變速，只從原始版本處理一次，避免再對已加速檔套用相同係數。來源人物原音維持 1x。

手上只有一份長的原生 PCM16 WAV 時，可使用 `prepare_voice.py` 依已核對的 sample 邊界拆段。`voice/segments.json` 的形狀為：

```json
{"input_kind":"recorded-native-master","master_path":"voice/native-master.wav","segments":[{"id":"i01","start_frame":0,"end_frame":48000,"text":"與 rundown 完全一致的本段文字"}]}
```

`input_kind` 只接受 `recorded-native-master` 或 `generated-native-master`；不能傳入私有參考錄音或已處理 take。上例 frame 是音訊 sample frame，48 kHz 時 48000 frame 為一秒；它與影片影格不同。實際清單須恰好包含所有旁白項目，按原總檔順序、互不重疊。

```powershell
& $py -X utf8 "$skill/scripts/prepare_voice.py" $episode --segments voice/segments.json --tempo 1.0
```

工具拒絕覆蓋輸出，也不會推測分段邊界或生成聲音。音訊來源不同時，自行使用合適的錄音／TTS 工具，最後提供合約所需的 WAV 即可。

## 將核聽綁定到當前音檔

每個含術語的旁白項目都要實際核聽。完成後，在該詞 `audio_reviews` 記 `item`、`audio_path`、當前 WAV 的 `audio_sha256`、局部 `start/end` 秒數、`heard_original_language` 與具體 `notes`。只有真正聽過並確認後才填 `true`。

```powershell
(Get-FileHash -LiteralPath "$episode/voice/i01.wav" -Algorithm SHA256).Hash.ToLowerInvariant()
& $py -X utf8 "$skill/scripts/check_narration.py" $episode --text-file voice/approved-narration.txt --require-listening --out qa/narration-listening.json
```

此檢查核對檔案、hash、時間範圍及審查紀錄，沒有執行語音辨識或自動聆聽。同一項內重複出現的詞應全部聽過，筆記寫清覆蓋範圍；ASR 拼對字不足以證明發音正確。

## 每次修訂之後

旁白改字後重錄受影響段落；換音檔後更新字幕、人物卡節奏與專名核聽記錄。新版 WAV 的 hash 會不同，舊核聽紀錄不能沿用。

執行 `interview.py resolve` 重新量長，再執行 `build_film.py`。工具會把 rundown、profile、旁白計畫、實際輸入文字、字幕和 WAV 綁定到解析結果；修稿後直接建片會被當成過期時間軸。

最後核對旁白與來源音量、句尾、呼吸及轉場。無法實聽時可交付技術樣本與待驗記錄，完成狀態維持 `partial`。
