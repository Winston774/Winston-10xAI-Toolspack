# 2026-W40：Video Highlights — 把長訪談剪成有依據的精華

一支一小時的訪談，可能有方法、案例、反駁與結論。只抓一句金句，容易漏掉前提。本週技能讓 Agent 先讀完整份帶時間逐字稿，建立主題地圖，再核對候選的畫面、聲音與前後文，最後輸出多支有評分的精華影片。

**版本：v0.1.0 Preview｜類型：AI Skill｜預估：120 分鐘，不含完整轉寫與長片聽看時間。**

- [完整講義](lesson.md) · [技能與安裝說明](completed/video-highlights/README.md)
- [操作與排錯](completed/video-highlights/references/usage.md) · [本次驗證紀錄](docs/verification.md)
- [GitHub 本週目錄](https://github.com/Winston774/Winston-10xAI-Toolspack/tree/main/weeks/2026/2026-w40-video-highlights)
- 本週先以合併至主分支交付，未建立獨立 GitHub Release。可在倉庫首頁選 Code → Download ZIP，解壓後進入本週資料夾；CI 也會產生保留 7 天的週次 ZIP，下載 Actions 附件需要 GitHub 登入。

## 這週能做什麼

- 從訪談、Podcast 影片、課程或直播回放建立全片主題地圖。
- 依受眾、重點、片數與時長找候選，保留引用、理由與未入選原因。
- 用八項量尺計算 0–100 分，並分開記錄信心及檢視狀態。
- 輸出直式、橫式、方形或原比例 MP4，以及片段時間從零起算的 SRT。
- 修改 JSON 計畫後重跑，來源 hash 與驗證規則協助避免剪錯版本。

CLI 負責媒體處理、驗算和約束檢查；內容理解、評分與視聽核對由執行技能的 Agent 完成。無需另架伺服器或 UI，已有字幕時核心流程不需額外 LLM API 或 ASR 模型。

## 準備與安裝

1. 準備能載入 Agent Skills 的工具、Python 3.10+、FFmpeg 與 FFprobe。FFmpeg 需含 libx264、AAC、MJPEG、PCM16；燒字幕另需 libass 及可顯示字幕的字型。
2. 將本週的整個 `completed/video-highlights` 資料夾放入 Skills 目錄。Codex 在 Windows 通常使用 `%USERPROFILE%\.codex\skills\video-highlights`。
3. 已有同名技能時，先備份舊資料夾到 Skills 目錄之外，再換入新版。保留 scripts、references、agents、tests 子目錄。
4. 重新開啟對話，請 Agent 讀取此技能並執行 doctor。若技能清單尚未更新，可直接提供已安裝的 SKILL.md 路徑。
5. 準備有使用權利的本機影片，最好附上與原片時間同步的 UTF-8 SRT。沒有字幕可選配本機 faster-whisper；模型名稱可能觸發下載，先確認儲存空間與授權。

本包不含 Python、FFmpeg、模型或測試影片。首次可先用 5–10 分鐘素材走一遍，再處理長訪談。

## 直接貼給 Agent

```text
使用 $video-highlights，幫我把這支訪談整理成最多 5 段精華。
每段 45–75 秒，同時輸出直式與橫式，重點放在能實際採用的方法。
影片：<本機影片路徑>
字幕：<與原片同步的 SRT 路徑；沒有則說明>
輸出：<新的工作目錄>

先檢查環境，讀完整份逐字稿，建立全片主題地圖。
每個候選核對前後文、畫面與聲音；回報真的看過／聽過的範圍。
附 MP4、SRT、總分與分項評分、入選理由、未入選原因及原片時間。
素材不足時少交並說明。未完成視聽核對的片段保留 partial。
先保留全幅補邊；需要裁切時說明依據，不覆寫原片。
```

未指定時採最多 5 段、每段 30–90 秒、直橫兩版。影片總長及模型速度會影響實際處理時間。

## 交付物與通過標準

| 產物 | 要看什麼 |
| --- | --- |
| project.json 與 chunks | 原片 hash、同步時間軸、全片文字分塊 |
| candidates.json | 原文引用、八項評分、三項語義門檻、證據及未解問題 |
| plan.json、HIGHLIGHTS.md、scores.csv | 入選時間、理由、總分、主題覆蓋與未入選原因 |
| 每段 MP4、SRT | 指定比例與片長，字幕以片段零點重定位 |
| metadata/render.json | 實際尺寸、時長、音軌及仍待視聽確認的項目 |

- [ ] 全片時間地圖涵蓋首尾，無文字或未檢視部分有明確標記。
- [ ] 每段具備可核對的原文依據，必要前提、否定與發言者被保留。
- [ ] 片長符合規格，數量不足有解釋，沒有硬切半句或重複湊數。
- [ ] 總分與分項一致；知道分數代表編輯判斷，無法預測流量。
- [ ] MP4 可播放、尺寸與音軌符合需求；字幕起終及跨切點文字已檢查。
- [ ] 分享前回看成片並聆聽原音，確認字幕、人物、切點及權利。
- [ ] 機械檢查通過與人類發布驗收分開記錄；未補齊時可交 partial 草稿。

## 重試路徑

先讀錯誤與缺口，再從出問題的階段續跑：缺工具請跑 doctor；無候選請看 rejected；字幕不準先修正來源時間；裁切丟人改用 pad。使用 source-v2、selection-v2、exports-v2 等新目錄，保留前次資料及原片。

[疑難排解](docs/troubleshooting.md) · [架構與資料流](docs/architecture.md) · [限制](docs/known-limitations.md) · [隱私與素材](docs/privacy-and-content-rights.md) · [來源與授權](docs/source-and-license.md)

## 版本紀錄

- v0.1.0 Preview（2026-10-01）：收錄完整獨立技能與測試，補齊每週教材、來源清單、資料流與交付驗證。技能入口新增既有範例的導覽連結，核心 Python 功能維持來源內容。
