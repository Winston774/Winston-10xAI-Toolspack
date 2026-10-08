# W41｜Source-led Video：把原音精華做成可追溯的影片

從長訪談、Podcast、演講或課程中找出值得保留的完整答案，以短導讀、繁中字幕和重點動畫串起來，交付可追溯的企劃與可編輯影片工程。

本週提供 `source-led-video v1.0.0` 的完整獨立技能，共 27 個原始檔案，另附學員教材。Toolspack 狀態為 **Preview**：合成素材流程已測試，真實素材的語義、發音及連續觀看仍需每案驗收。原始版本號不代表本週所有製作情境已通過驗證。

## 你會學到什麼

- 讀完整份來源資料，記錄缺少的視聽證據，再評估候選片段。
- 用三項語義門檻與八項評分做取捨；未知分數保留 `null`。
- 比較所有候選問題，選出能兌現標題與縮圖承諾的首題。
- 對齊原片時間、旁白 WAV 時間及最終影片時間。
- 將導讀、原音、字幕、重點標記與紙感版型組成可編輯工程。

## 選擇你的學習路徑

| 路徑 | 準備 | 交付 | 時間參考 |
|---|---|---|---|
| 先做企劃 | 技能支援工具、Python 3.11+、有權使用的來源與逐字稿 | 候選評分、首題比較、rundown、旁白草稿、待確認事項 | 約 60–90 分鐘，另計全片閱讀 |
| 完整建片 | 上述資料，加 FFmpeg／FFprobe、WAV、GSAP、字型、Python 字型套件、Node.js／HyperFrames 與瀏覽器 | 1080p30 工程、MP4、字幕、QA 與分享素材 | 入門練習約 180 分鐘，另計下載、渲染與人工審閱 |

技能不附影片、逐字稿、字型、模型或執行環境，也不會自動下載來源、轉錄、生成語音或發布影片。完整依賴與操作命令見 [原始快速開始](completed/source-led-video/references/quickstart.md) 及 [環境說明](completed/source-led-video/references/dependencies.md)。

## 取得與安裝

本週內容以 GitHub 主分支交付，**尚未建立獨立 GitHub Release**。可從本倉庫 Code → Download ZIP 取得內容，或在成功的 [GitHub Actions](https://github.com/Winston774/Winston-10xAI-Toolspack/actions/workflows/validate.yml) 執行頁下載 `toolspack-weekly-release-candidates`，取出 `2026-w41-source-led-video.zip`；Actions 附件通常需要登入，保留 7 天。

1. 解壓本週檔案，找到 `completed/source-led-video/`；該資料夾第一層應直接看見 `SKILL.md`。
2. 先閱讀 [技能入口](completed/source-led-video/SKILL.md) 與 [隱私及內容權利](docs/privacy-and-content-rights.md)。
3. 將整個 `source-led-video` 資料夾複製到自己的 Codex skills 目錄。已設定 `CODEX_HOME` 時使用其下的 `skills`；未設定時通常為使用者家目錄的 `.codex/skills`。同名技能先備份，勿直接覆蓋。
4. 重新開啟對話，以 `$source-led-video` 呼叫。其他工具依各自技能目錄規則安裝。

第一次可以貼上：

> 使用 $source-led-video 分析我提供且有使用權的影片與完整逐字稿。觀眾是剛開始管理團隊的人，目標約六分鐘，原音為主、繁中短導讀串接。先完成全片主題分布、候選評分、首題比較和 rundown，停在企劃。缺少影音證據的欄位保留 null，列出待核對範圍；先不要生成旁白、渲染或上傳。

完整建片時，補上自己的頻道名稱、授權素材與聲音方案，確認企劃後再繼續。六分鐘僅為範例；沒有固定題數或八分鐘門檻。

## 本週文件

- [操作講義與作業](lesson.md)
- [資料流與三種時間座標](docs/architecture.md)
- [功能邊界與限制](docs/limitations.md)
- [疑難排解](docs/troubleshooting.md)
- [驗證紀錄](docs/verification.md)
- [來源、版本與授權邊界](docs/source-and-version.md)

延伸比較：[W40 Video Highlights](../2026-w40-video-highlights/README.md) 聚焦多個候選精華及多比例剪輯；本週加入導讀、首題承諾、專名核聽、完整紙感影片工程與交付流程。兩者為獨立技能，本週不會覆蓋 W40。
