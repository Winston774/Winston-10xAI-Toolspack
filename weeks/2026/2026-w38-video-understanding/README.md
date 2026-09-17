# 2026-W38：Video Understanding — 讀懂短影音，交接下一步製作

看到一支想參考的短片，你能描述它用了哪些字幕、鏡頭與音效；真正開始製作時，還需要知道它們何時出現、如何一起推進敘事，以及更換台詞後哪些關係要重新對齊。

本週分享 `video-understanding` 技能。它讓 Agent 從整體敘事回到逐段視聽證據，整理成可回看、可續跑、可交給下一個製作 Agent 的文件。

**目前版本：v0.1.1 Preview。** 本次已依使用者更正的 `video-understanding2.rar` 重建 W38；請使用本版下載包。

- [下載本週 ZIP](https://github.com/Winston774/Winston-10xAI-Toolspack/releases/download/2026-w38-v0.1.1/2026-w38-video-understanding.zip)
- [版本說明](https://github.com/Winston774/Winston-10xAI-Toolspack/releases/tag/2026-w38-v0.1.1)
- [完整講義](lesson.md) · [技能成品](completed/video-understanding/README.md)

## 這週學會什麼

1. 把開場、發展、注意力轉移、揭露與收束整理成時間地圖。
2. 分開追蹤人物表演、插入畫面、口語字幕、獨立文字、動態圖形／介面、特效與聲音。
3. 寫清楚系統的進場、持續、更新、退場，找出跨鏡頭仍然存在的狀態。
4. 將確實看到／聽到的內容、對設計作用的解釋、下階段製作建議分開記錄。
5. 用原片時間找證據，用語句或動作作為新版本重新對齊的依據。

適合要拆解參考短片、製作前研究、建立 Agent 交接流程的創作者。預估 180 分鐘，可先交付部分分析再續跑。

## 準備與安裝

需要能讀取 Agent Skills 的工具、Python 3.10+，以及可用的影片／圖片檢視與音訊聆聽能力。使用本機證據準備工具時，另需 FFmpeg 和 FFprobe。兩支 Python 工具僅使用標準函式庫；ASR、雲端模型與影片生成工具可依實際環境選用。

1. 下載上方 ZIP，解壓縮後開啟 `completed/video-understanding/`。
2. 將整個 `video-understanding` 資料夾放進 Codex Skills 目錄：
   - Windows：`%USERPROFILE%\.codex\skills\video-understanding`
   - macOS／Linux：`~/.codex/skills/video-understanding`
3. 若已有舊版，先把舊資料夾移到 Skills 目錄之外備份，再放入新版，避免殘留舊參考文件。
4. 重新開啟 Codex，確認技能清單出現「影片理解」。其他 Agent 請使用其支援的 Skills 位置。
5. 選一支有分析與使用權利的 15–60 秒短片，放在自己的工作目錄。分析輸出也放在工作目錄，與已安裝技能分開。

把這段交給 Agent，替換影片路徑：

```text
使用 $video-understanding 分析「<我的影片路徑>」。
先完整理解原片，還沒有改編目標，不要替我擬定新人物或新廣告。
輸出到 analysis/<影片名稱>/，交付 VIDEO_UNDERSTANDING.md 與 analysis.json。
請區分觀察、推論與製作建議，列出實際看過／聽過的範圍。
若能力或證據不足，保留 partial 狀態並寫 PROGRESS.md。
```

技能會依使用者已有授權處理外部上傳或付費分析；沒有授權時保留本機工作並列出能力缺口。核心 helper 接受本機檔案，沒有 URL 下載功能。

## 你會拿到什麼

| 產物 | 用途 |
| --- | --- |
| `VIDEO_UNDERSTANDING.md` | 全片論述、事件表、系統生命週期、聲音、素材需求與接手指引 |
| `analysis.json` | 來源、時間、ID、檢視範圍、證據、素材依賴、未知項與狀態 |
| `evidence/` | 使用工具準備並實際檢視的畫格、音訊、片段或量測紀錄 |
| `PROGRESS.md` | 部分分析的已完成內容、缺口與下一次補看順序 |

本技能的交付是分析與製作交接；影片生成、剪輯與渲染由下一階段工具承接。

## 本週任務與通過標準

完成一支短片的初版理解，允許以 `partial` 交付：

- [ ] 來源 hash、時長、音軌與第一張解碼視訊影格為零點的時間座標清楚。
- [ ] 敘事地圖涵蓋全片；無法確認的區段明確標出。
- [ ] 至少挑一個跨鏡頭系統，描述進場、持續／更新、退場與相關事件。
- [ ] 重要判斷附時間及證據；說話內容、Caption 與獨立標題分開。
- [ ] 列出三項重製時要保留或重新計算的關係。
- [ ] 有音軌而尚未實際聆聽時，保留 `partial`。
- [ ] 請 Agent 執行索引驗證並回報真實結果；機械檢查通過仍需視聽與語義核對。

只有完整事件覆蓋、全片播放／密幀檢視、有音軌時全片聆聽，以及沒有阻塞問題、素材需求足夠，才考慮 `ready`。

## 操作卡與重試

請 Agent 檢查 FFmpeg／FFprobe 後準備概覽；對看不清的文字、切點或動作補抽密幀。每次使用新輸出目錄，保留前次證據。

```text
python <SKILL_DIR>/scripts/prepare_video.py <input.mp4> --out <analysis-dir>/evidence/overview --every 1
python <SKILL_DIR>/scripts/validate_analysis.py <analysis-dir>/analysis.json --source <input.mp4>
```

- 找不到媒體工具：確認 `ffmpeg -version`、`ffprobe -version`，或提供明確執行檔路徑。
- 輸出已存在：改用新的目錄名稱；helper 會拒絕覆寫。
- 抽樣超過上限：縮短區段或調整間距，預設上限為 240 張。
- 無法看圖／聽音：完成能支持的部分，明列尚未檢視範圍。
- JSON 驗證失敗：依錯誤檢查 ID、時間、相對證據路徑與狀態條件。

## 延伸文件

[疑難排解](docs/troubleshooting.md) · [已知限制](docs/known-limitations.md) · [驗證紀錄](docs/verification.md) · [來源與授權](docs/source-and-license.md) · [素材與分享](docs/privacy-and-content-rights.md)

## 分享成果

可分享一段去識別的事件分析、你保留的關係，以及仍需補看的問題。例如：「我追蹤了榜單卡片從進場到更新的過程。重製時要保留累積排名的狀態，並依新台詞重新對齊揭露時機。」分享原片或衍生證據前確認權利與隱私。

## 版本紀錄

- v0.1.1：以更正 RAR 為唯一功能來源，重新編寫 W38 教材與分享說明；補齊來源／驗證文件，移除前版額外引入的研究文件與示例。
- v0.1.0：初次發布，已由 v0.1.1 取代。
