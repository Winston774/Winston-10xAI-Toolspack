# 2026-W38：Video Understanding — 附時間證據的短影音理解與生成交接

> 把參考短影音拆成可追溯的敘事、視聽系統、事件與素材依賴，讓下一位 Agent 能從證據接手生成規劃。

## 本週成果

完成本週練習後，你會交出一份自己的 `VIDEO_UNDERSTANDING.md` 與 `analysis.json`。它們會把原片從開頭到結尾的時間、可見與可聽證據、系統生命週期、事件、素材需求、保留規則與待解問題整理成可續跑的交接包。

本週提供的 `video-understanding v0.1.0` 包含：

- 本機 FFmpeg／FFprobe 證據準備 helper，保留真實解碼時間、畫格與音訊時鐘資訊。
- 結構驗證器，檢查交接索引的時間範圍、引用、檔案位置、覆蓋與 `partial`／`ready` 狀態。
- 人可讀的交接模板、機器可檢查的 JSON 模板，以及可通過結構驗證的合成範例。
- 30 項可重跑的 Python 測試；其中媒體整合案例需要本機可用的 FFmpeg 與 FFprobe。
- 來源、授權、隱私、內容權利與限制說明。

成品位置：[`completed/video-understanding/`](completed/video-understanding/)

延伸文件：

- [教學講義](lesson.md)
- [驗證方式與證據邊界](docs/verification.md)
- [隱私、內容權利與公開分享](docs/privacy-and-content-rights.md)
- [來源與授權](docs/source-and-license.md)
- [疑難排解](docs/troubleshooting.md)
- [已知限制](docs/known-limitations.md)

## 基本資料

- 類型：AI Skill
- 難度：進階
- 預估時間：180 分鐘；可拆成「先做 `partial` 分析」與「補足為 `ready`」兩段
- 支援平台：Windows、macOS、Linux；能讀取 Codex／Agent Skills 的 Agent
- 需求：Python 3.10 以上；FFmpeg 與 FFprobe；可實際查看畫格與聆聽音訊的工具
- Skill 版本：`0.1.0 Preview`
- API Key／付費服務：核心 helper 不需要。雲端視覺、ASR、下載或生成服務屬選配，每個檔案都要先取得使用者明確同意
- 授權：`completed/video-understanding/` 受 Hypit modified Apache-2.0 條款與額外條件約束，請先讀 [LICENSE](completed/video-understanding/LICENSE) 與 [NOTICE](completed/video-understanding/NOTICE)

## 安裝與開始

1. 從本週 GitHub Release 下載 `2026-w38-video-understanding.zip` 並解壓縮。
2. 開啟 `completed/video-understanding`。
3. 將整個資料夾複製到其中一個 Skills 位置：
   - Windows：`%USERPROFILE%\.codex\skills\video-understanding`
   - macOS／Linux：`~/.codex/skills/video-understanding`
   - 共用 Agent Skills 目錄：`~/.agents/skills/video-understanding`
4. 重新啟動 Agent 工具，確認 `影片理解` 出現在可用技能清單。
5. 選一支你擁有分析與使用權利的 15–60 秒本機影片。把它與輸出資料夾放在工作目錄，避開已安裝的 skill 目錄與公開 Git 資料夾。
6. 明確呼叫技能：

```text
使用 $video-understanding，以本機優先方式分析這支影片。
先建立 analysis/<影片名稱>/，產出 partial 的 VIDEO_UNDERSTANDING.md 與 analysis.json；
列出未檢視或未聆聽的範圍，未經我逐檔同意不得上傳任何影片、畫格、音訊或逐字稿到外部服務。
```

`prepare_video.py` 只接受本機影片檔，不會下載網址。若影片起點是 URL，先自行確認取得權利、下載安全性與保存位置，再交給 helper。

## 第一個練習

1. 先用低密度概覽讀完整片，建立開場、發展、轉折、揭露與收束的暫定假說。
2. 對字幕變化、切點兩側、快閃字、重要動作與聲畫同步區段加做密集抽樣或播放。
3. 將真正在工具中看過或聽過的證據記入 `analysis.json`，使用與主文件相同的 `EV-*`、`SYS-*`、`ASSET-*`、`E-*` ID。
4. 先以 `partial` 交付。只有完整覆蓋、全片視覺檢視、音軌存在時全片實際聆聽、沒有阻塞問題且素材需求完整時，才可標示 `ready`。
5. 執行結構驗證：

```text
python <SKILL_DIR>/scripts/validate_analysis.py <analysis-dir>/analysis.json
```

驗證成功只表示結構、時間與引用一致；視聽事實、抽樣密度與敘事解釋仍需由實際檢視負責。

## 本週任務

選一支具備使用權利的 15–60 秒直式短片，完成一份可供下一個 Agent 接手的 `partial` 分析：

1. 完整列出來源檔案的 hash、時長、尺寸、音軌存在與 source clock。
2. 用至少一段完整概覽、兩個需補看的關鍵區段，建立時間地圖與系統生命週期。
3. 把觀察與推論分欄；語音內容、畫面字幕與獨立 Typography 分開寫。
4. 寫出至少三項下一階段需要保留或重新計算的關係，例如字幕安全區、揭露事件與素材依賴。
5. 保留尚未確認的音樂、音效、鏡頭參數、文字或權利問題，並寫入 `unknowns` 與 `PROGRESS.md`。

## 成果證據

- `VIDEO_UNDERSTANDING.md`：全片理解、時間地圖、系統、聲音、素材需求與下一步。
- `analysis.json`：與主文件一致的來源、檢視、證據、事件、素材、未知項與 handoff 狀態。
- `evidence/`：只留在私有分析資料夾的 manifest、畫格、片段、音訊或逐字稿；公開分享時不得附上真實來源內容。
- `PROGRESS.md`：`partial` 狀態下的缺口、補看位置與接手順序。
- 一次 `validate_analysis.py` 的成功輸出或可重現的錯誤紀錄。

## 通過標準

- [ ] Skill 可被 Agent 辨識，或 Agent 能完整讀取 `SKILL.md`、5 份 references、`LICENSE`、`NOTICE` 與安全文件。
- [ ] 分析輸出位於使用者工作目錄，沒有寫進已安裝的 skill、公開 Git 倉庫或本週 Release。
- [ ] 來源時間以第一張解碼視訊影格為 0 秒，所有區段採相同時鐘。
- [ ] 每個重要事件有對應系統、觀察、推論、時間與已檢視證據；未知項明確保留。
- [ ] 有音軌卻尚未聆聽時，交付狀態仍是 `partial`。
- [ ] `analysis.json` 通過結構驗證，且沒有把其成功訊息宣稱為完整的視聽或語義驗收。
- [ ] 分享包不含原片、幀圖、WAV、逐字稿、人物資料、預簽名 URL、絕對路徑、工具路徑或原始 metadata。

## 失敗時的最短路徑

1. 找不到 FFmpeg／FFprobe：在終端機執行 `ffmpeg -version` 與 `ffprobe -version`；安裝受信任版本後重試，或以 `--ffmpeg`、`--ffprobe` 傳入明確路徑。
2. 輸出資料夾已存在：保留舊證據，改用新的、有意義的資料夾名稱；helper 會拒絕覆寫。
3. URL 無法處理：helper 不下載網址。先完成取得權利與本機下載，再用本機檔案。
4. 結構驗證失敗：先從 `examples/partial-analysis/` 讀取可通過範例，核對 ID、時間、evidence path 與 `partial`／`ready` 條件。
5. 無法看圖或聽音：輸出可支持的內容並維持 `partial`，不要以 metadata、ASR 或抽出的檔案取代真實檢視。
6. 仍無法排除問題：依[疑難排解](docs/troubleshooting.md)保留錯誤訊息、命令、Python／FFmpeg 版本與最小可重現檔案資訊；先移除影片、逐字稿與任何敏感資料。

## 分享成果

可自行修改以下文字，搭配去識別的文件局部截圖或合成範例分享：

> 我完成了第一份可交接的短影音理解：把開場、事件、字幕系統、素材依賴與待補問題放回同一個 source clock。這次先交付 partial，下一步是補聽音訊並驗證聲畫同步。分享內容沒有包含原片、畫格、音訊、逐字稿或私人 metadata。

## 版本紀錄

- `v0.1.0 Preview`：首次學員發布；本機證據準備、結構驗證、合成範例、來源與權利說明、30 項測試與安全分享界線。
