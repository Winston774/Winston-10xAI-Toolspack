# 編輯式動態雙語版

這是 paper renderer 之外的可選路徑，源自完整精華片修訂的版面、時間與媒體驗證經驗。不是固定人物、聲線、五題或色盤；完整片與短樣片使用同一資料驅動模型。

## 選擇此路徑時

先完成来源理解、选段與導讀。需要繁中＋英文字幕、簡潔的短句淡入、原片縮入及逐點圖解時，使用 [editorial-motion.json](../templates/editorial-motion.json) 和 [build_editorial_motion.py](../scripts/build_editorial_motion.py)。原 paper 路徑仍使用 `interview.py`／`build_film.py`，兩種 input schema 不可混稱或直接互換。

新 adapter 接受已準備好的本機來源 clip、旁白 WAV、字幕與分拍卡片；不自動下載影片、合成旁白、翻譯、生成圖片或判斷剪點。將計畫範本另存當集 `editorial-motion.json`，並將 [來源主題範本](../templates/source-themes.json) 另存同目錄 `source-theme-registry.json`；兩份範例的虛構 source key 一致。填自己實際媒體、字型、GSAP、時碼與文字，再執行：

```sh
python path/to/source-led-video/scripts/build_editorial_motion.py episode/editorial-motion.json --output episode/revision-02 --validate-only
python path/to/source-led-video/scripts/build_editorial_motion.py episode/editorial-motion.json --output episode/revision-02
```

輸出目錄須為新目錄；已有工程拒覆寫。路徑以 plan 所在資料夾為基準；本機 font、GSAP、media 路徑必須存在。Python 需 Pillow、fontTools、brotli，另需 FFprobe；聲音和來源保持已準備的 bytes，builder 不再次 loudnorm 或變速。`prepared_audio.status` 應如實記 `normalized_once`、`unchanged` 或 `unknown`；前者另附處理證據，unknown不能被包裝成已處理。導讀可填 `disclosure` 顯式顯示聲音來源；外部WAV／自錄不自動貼AI標籤。

渲染由既有本機 HyperFrames 與已配置瀏覽器執行。可用隨附 wrapper，須填自己電腦上已存在的 executable：

```sh
python path/to/source-led-video/scripts/render_editorial.py episode/revision-02 check --hyperframes path/to/node_modules/.bin/hyperframes --browser path/to/chrome
python path/to/source-led-video/scripts/render_editorial.py episode/revision-02 render --hyperframes path/to/node_modules/.bin/hyperframes --browser path/to/chrome
```

wrapper檢查成功才渲染，保存logs與browser JSON，拒已有final.mp4。它使用臨時localhost伺服器，不上傳媒體；工具版本須支援列出的CLI選项，已在本次固定HyperFrames 0.8.119驗證，不宣稱所有版本相容。不用啟動時的 npx 自動取得最新版。HyperFrames、GSAP、Chrome、FFmpeg和字型要保存版本或 locator；沒有包 runtime 就不能稱免安裝。

## 時間座標

| 輸入 | 起算點 |
|---|---|
| source `source_start/source_end`、來源 cue、marker／step | 原片秒；clip 必須與該範圍吻合 |
| narration cue、cards、line reveal | 當前 WAV 零秒 |
| 輸出 timeline、SRT、章節、影片抽格 | 成片秒，由 builder 解析 |

原音 clip 是1x。用實測媒體長度安排下一段，不用稿中字数猜声音时间。將音長加呼吸後向上取整到影格；避免浮點誤差在恰好整格時多算一格。未聽到的疑詞、說話者或句尾，留在 evidence／pending，不用猜測補進成片。

## 卡片、插畫與縮放

資料支援任意數量段落；每個來源段先判斷是否需要註記，保留理由。需要時通常2–3點一張，按語意而非定額選主要論點。`utterance_at` 是有證據的該句出現候選秒，`at` 不早於它；相等只代表符合輸入的數值關係，不證明真的已聽過。影片大部分時間可保持原畫面。

預設 source `[320,80,1280,720]`，縮入 `[720,125,1120,630]`，概念區 `[90,145,560,595]`，字幕區 `[96,822,1728,258]`。縮入及還原各0.7秒，短句0.45秒淡入／輕滑20px。末點至少2秒可讀，marker結束後需留足還原，下一卡不得撞到恢復動作。

source card 不會提前替講者揭答案；標題也避免過早宣告結論。三點卡不能只沿用兩點卡的字級、padding與行高而假定放得下。量測 DOM 後，仍從實際 MP4 看所有點、卡底和字幕區。

人物用真實來源照片，保留 locator／來源秒／crop／SHA。概念插畫使用符號示意，不能裝成訪談畫面或資料證據。文字由可編輯圖層排版，圖片不畫字幕或可核實職務。可採透明紙張層次、照片拼貼或其他已選風格；避免僅用大白框加空泛圖示填空。使用生成圖片時保存工具模式、prompt、參照角色、輸出 SHA，且將最後素材存入當集，不只留在工具的預設暫存位置。

## 工程與真實驗收

root composition只负责时长／装载，场景内容与GSAP在child composition。非零媒體起點明示時間基準。由 renderer 管理 clip 可見性，不用額外動畫提早藏掉尚未播完的段落。字型使用本機 subset，避免龐大的 inline font 或網路字型依賴。

builder 產生工程、解析時間軸、字幕及建置報告，不等於成片。實際渲染後依 [quality-and-delivery.md](quality-and-delivery.md) 核對規格／完整解碼／每卡動作／最長中英 cue／來源署名／人物／片尾，還需段落頭尾聲音對位與完整連續視聽。量測原生立體声samplepeak时标记是否true-peak；相關與漂移檢查不能取代姓名、字幕疑词与切句核聽。

示例和合成測試只驗資料與技術行為；沒有用真人素材完整核聽時，英文原文及聲音品質仍pending。維持同一版本的工程、MP4、字幕、章節、播放器與索引 SHA，避免短樣片更新後誤稱完整 A/B 已套用。
