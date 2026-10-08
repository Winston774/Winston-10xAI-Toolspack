# 依賴、環境與替代方式

本技能包含流程、資料模板與建片程式；影音素材、合法字體、語音服務、模型及瀏覽器環境由使用者自己的設備提供。環境不同時先做最小樣本，不把路徑檢查當成完整製作測試。

## 能力與所需依賴

| 能力 | 依賴 | 缺少時仍可完成什麼 |
|---|---|---|
| 人工來源分析與文案 | 可讀來源、逐字稿、來源查證能力 | 保留可追溯企劃與未核實欄位 |
| JSON 初始化、評分、部分檢查 | Python 3.11 以上；大部分使用標準函式庫 | 未安裝時可先做文字企劃，不能聲稱腳本已跑 |
| 原片裁切、探測、音訊處理、解碼 | FFmpeg、ffprobe | 完成選段規格，等待可用素材處理工具 |
| HTML 工程、字型處理 | 本機 GSAP JavaScript、合法 sans/serif 字型、fontTools、brotli | 完成 rundown、字幕和視覺規格 |
| 影格檢查輔助 | Pillow | 可人工查看影格，標記自動像素檢查未執行 |
| HyperFrames 檢查與渲染 | Node.js、npx、相容瀏覽器、所需運行環境 | 保留工程；先核對實際失敗點 |
| 自錄／TTS | 使用者可用的錄音軟體或語音引擎 | 完成經核對的旁白稿，不假造聲音檔 |

HyperFrames 命令的版本基準為 `0.8.119`。其他版本先查看該版 `--help` 與實際檢查結果；版本號相同也不保證新機器的瀏覽器、編碼器或 GPU 已可用。

## 建立自己的設定

從模板 `templates/environment.json` 開始，填入實際位置。不要把同學或教師電腦的絕對路徑直接當成自己的設定。必要時使用本機虛擬環境，將所需 Python 套件放在那個 interpreter 中。

```powershell
$skill = '<source-led-video 資料夾>'
$py = '<Python 執行檔>'
& $py -X utf8 "$skill/scripts/configure.py" --out '<自己的 environment.json>' --ffmpeg '<ffmpeg 執行檔>' --ffprobe '<ffprobe 執行檔>' --npx '<npx.cmd>' --gsap-js '<本機 gsap.min.js>' --sans-ttf '<中文字型.ttf>' --serif-ttf '<標題字型.ttf>'
```

`configure.py` 僅整理路徑和寫入設定，不安裝軟體、不下載模型、不載入聲音。它拒絕覆蓋設定檔；改用新檔名檢視差異，或明確編輯自己的既有檔案。

設定欄位：

- `python`：執行腳本的 interpreter；實際命令使用哪個 Python 仍以本次執行為準。
- `ffmpeg`、`ffprobe`、`npx`：可執行檔路徑或能由環境找到的名稱。
- `gsap_js`：本機可讀取的 GSAP 腳本。
- `sans_ttf`、`serif_ttf`：能涵蓋目標文字的字型檔。
- `font_licenses`：字型授權文件位置，可追溯嵌入與分享權利。
- `python_extra_paths`：必要的額外模組路徑，通常保留空陣列。
- `voice_tool`：可選的外部聲音工具位置；設定此欄不會自動生成音訊。

常用全域位置為家目錄下 `.config/source-led-video/environment.json`。亦可透過 `SOURCE_LED_VIDEO_ENV` 環境變數或 `init --environment '<設定檔>'` 指定；明確 `--environment` 優先。

```powershell
& $py -X utf8 "$skill/scripts/interview.py" init --out '<新製作目錄>' --environment '<自己的 environment.json>' --brand '<品牌>'
& $py -X utf8 "$skill/scripts/interview.py" doctor '<新製作目錄>'
```

初始化把設定複製到當集 `environment.json`，並記錄設定來源。移到另一台機器時更新環境設定和素材路徑，保留內容與聲音來源紀錄。

## 軟體與素材取得

需要安裝依賴時，遵循當前機器的軟體安裝權限與工具文件。首次執行 `npx --yes hyperframes@0.8.119` 可能連網下載 npm 套件；離線環境使用已準備的相容依賴，或停在可交付工程的階段。

GSAP、字體、瀏覽器、HyperFrames 及其他外部工具各有授權或服務條款。技能沒有附上它們的外部程式碼、字型或授權替代品，分享影片工程前確認所帶檔案可以一起分發。

來源下載／字幕取得可用現有連接器、官方字幕、本機檔案或可用工具。取得受限時記錄缺口；HTTP 429、Cache miss 或私有影片存取失敗不能推導出影片沒有內容。

本包不附其他技能的內容或完整工具手冊。若目前環境有影像生成、轉錄、配音或 HyperFrames 專用能力，可按任務使用其當前說明；它們缺席時，仍可用自己的工具提供相同的素材與檔案契約。

## 最小可用性驗證

`doctor` 分別報告企劃、裁切、視覺建置、渲染與影格檢查所需路徑是否存在。它不執行模型、下載、語音合成或成片渲染；`execution_verified: false` 不得改寫成已完成測試。

首次建片可用合成色塊、測試字卡和合成 WAV 驗證讀檔、時間軸、字幕、動畫與編碼。這類 fixture 不使用真人聲音，也不能證明真實訪談的語意、發音、聲畫同步或可讀性已通過。

確認短樣本成功後，再使用實際來源素材檢查裁切、人物安全區和聲音。保留報告中的命令、版本與實際執行結果；只報告本機本次驗證過的能力。

分享技能時，將機器設定、私有來源影片、參考聲音、金鑰、模型與成片留在各集工作目錄或機器設定目錄，排除於技能分享目錄之外。若需讓學員接續製作，另提供有權分發的示範素材與相對路徑說明。
