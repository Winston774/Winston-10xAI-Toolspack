# 從來源影片到第一支成片

本技能可產出可追溯的影片企劃，也附有本機建片工具。先決定本次交付範圍；只做企劃時，不必準備聲音模型、字體或渲染環境。工具不會收到網址就自動理解全片，來源閱讀與取捨仍須完成。

## 安裝與第一次呼叫

將封裝解壓為單一 `source-led-video` 資料夾，確認第一層直接包含 `SKILL.md`、`scripts`、`templates` 與 `references`。先解壓到暫存位置檢視內容；已有同名技能時保留備份，勿直接覆蓋。

使用 Codex 時，將資料夾放入自己的 `$CODEX_HOME/skills/`；未設定 `CODEX_HOME` 則通常位於使用者家目錄下的 `.codex/skills/`。重新開啟對話後以 `$source-led-video` 呼叫。其他支援技能的工具，依該工具的技能目錄規則安裝。

可直接提出：

> 使用 source-led-video 分析這部影片。觀眾是剛開始管理團隊的人，目標約六分鐘，保留來源原音，以簡短繁中導讀串接。先完成候選評分、首題選擇與 rundown，再製作可編輯影片。頻道名稱使用我提供的名稱。

只做企劃時改為「交付到企劃與 rundown 即可」。最低片長與題數依本次要求設定；省略 `--questions`，讓題數在理解來源後決定。內建的最低秒數只避免空影片，並不代表建議影片長度。

## 建立獨立工作目錄

以下命令使用 PowerShell。`$skill` 指本次技能資料夾，`$episode` 指尚未存在的新集目錄；請以實際位置取代示意字串。

```powershell
$skill = '<source-led-video 資料夾>'
$py = '<Python 3.11 以上的執行檔>'
$episode = '<新的製作目錄>'
& $py -X utf8 "$skill/scripts/interview.py" init --out $episode --source-url '<來源網址>' --brand '<頻道名稱>' --minimum-seconds 360
```

`360` 只示範「至少六分鐘」的要求。沒有最低長度要求時可省略；實際編排依內容決定。`init` 拒絕覆蓋既有工作目錄，續作直接使用已存在的資料。品牌預設空白，建片前須填自己的頻道或作者名稱。

## 模式一：企劃與剪輯規格

1. 將來源標題、頻道、日期、原片路徑、實測片長與逐字稿位置填入 `sources.json`。若只有字幕，明確記錄未取得的影音證據。
2. 理解全片後，保存主題分布與限制於 `research/`，撰寫 `questions.json`。問題可重排、合併，數量由答案內容決定。
3. 在 `candidates.json` 記錄來源切點、原句、三項語意門檻、八維評分與理由；缺證據留 `null`。
4. 建立 rundown 骨架，填入來源候選、短旁白與切點。完成 `opening-selection.json` 的全題比較，確保第一個原音答案兌現封面與標題。
5. 交付企劃、逐段來源連結、評分、rundown、旁白草稿、縮圖 brief 及待確認事項。尚無 WAV 時不要執行 `resolve`，也不要把預估時長寫成實測結果。

```powershell
& $py -X utf8 "$skill/scripts/interview.py" score "$episode/candidates.json" --out "$episode/qa/candidate-scores.json"
& $py -X utf8 "$skill/scripts/interview.py" plan $episode
& $py -X utf8 "$skill/scripts/opening_selection.py" $episode
```

`plan` 只接受已有問題且尚未填寫的 rundown；既有編排請直接修訂。填法見 [資料與 rundown](rundown-and-data.md)，取捨方法見 [編輯決策](editorial.md)。

## 模式二：完整本機建片

先按 [依賴與環境](dependencies.md) 建立自己的環境設定。工具會讀取明確的 `--environment`、`SOURCE_LED_VIDEO_ENV`，或家目錄下 `.config/source-led-video/environment.json`；初始化後每集另有 `environment.json`。

```powershell
& $py -X utf8 "$skill/scripts/interview.py" doctor $episode
& $py -X utf8 "$skill/scripts/interview.py" cut $episode
```

`doctor` 檢查路徑及 Python 套件可用性，沒有執行真正的渲染或語音生成。`cut` 保留來源聲音、以原片秒數切片，既有輸出需先核對，工具不會直接覆蓋。

填好 `narration-plan.json`，把旁白逐段以兩個換行串起來，保存為 UTF-8 的 `voice/approved-narration.txt`。先核對真正要錄製或送入 TTS 的文本，再依 [聲音與專名](voice-and-terms.md) 準備 WAV。

```powershell
& $py -X utf8 "$skill/scripts/check_narration.py" $episode --text-file voice/approved-narration.txt --out qa/narration-script.json
```

實際核聽後，保存每個術語對應的 WAV hash 和局部範圍，再執行 `check_narration.py` 加上 `--require-listening`；尚未核聽時明確保留待驗狀態。

建立來源字幕與旁白字幕，英文來源可加英文行，沒有英文內容時將 `en` 留空。按最終 WAV 安排 `card_beats`，原片秒數與 WAV 局部秒數不可混用。完成每段來源的 marker 判斷與必要素材後執行：

```powershell
& $py -X utf8 "$skill/scripts/interview.py" resolve $episode
& $py -X utf8 "$skill/scripts/interview.py" check $episode
& $py -X utf8 "$skill/scripts/build_film.py" $episode
```

## 檢查與渲染

內建工程支援 1920×1080、30 fps。先檢視工程與代表快照；其他畫幅需改版型與驗證，直接改數字不會完成適配。下列為版本 `0.8.119` 的操作基準；先讀本機 `--help`，若版本不同，核對參數後再執行。

```powershell
Set-Location -LiteralPath "$episode/motion"
npx.cmd --yes hyperframes@0.8.119 --help
$env:PRODUCER_BROWSER_GPU_MODE = 'software'
npx.cmd --yes hyperframes@0.8.119 check --timeout 30000 --snapshots --json
npx.cmd --yes hyperframes@0.8.119 render --quality delivery --fps 30 --workers 2 --strict --no-best-effort --no-browser-gpu --output ../exports/final.mp4
& $py -X utf8 "$skill/scripts/interview.py" check $episode --video "$episode/exports/final.mp4" --decode
```

首次 `npx` 可能下載套件；無網路或未安裝瀏覽器時，保留工程並說明限制。worker 數依本機資源調整。工具不會替你安裝完整環境，也不會發布影片。

從最終 MP4 抽取代表影格並觀看動態，執行 [交付檢查](quality-and-delivery.md)。交付 MP4、縮圖、標題、來源說明、章節、字幕、可編輯工程與 QA；未完成實聽或連續觀看時，標記 `partial` 並列明範圍。
