# 常見問題與重試

| 問題 | 可採取的下一步 |
| --- | --- |
| 技能未出現在清單 | 核對 video-highlights/SKILL.md 層級，保留全部子目錄，重開對話；可直接提供 SKILL.md 路徑 |
| doctor 報缺工具 | 確認 Python 3.10+、FFmpeg/FFprobe；PATH 外執行檔用 --ffmpeg / --ffprobe 指定 |
| 無字幕 | 提供同步 SRT/JSON，或明確選用本機 ASR；先確認模型下載與運算成本 |
| 英語素材 ASR 異常 | --language 預設 zh；英語應明確指定 --language en，再回聽核對 |
| 字幕時間超出影片 | 檢查是否來自相同版本；先同步時間軸，勿直接截掉錯誤 |
| 媒體起點超出 0.1 秒 | 製作同步確認過的零點副本，並使用同一座標的字幕 |
| 輸出目錄已存在 | 用新版本目錄重跑，保留原片及前次結果 |
| 沒有片段入選 | 查看 HIGHLIGHTS.md 的 rejected；修正片長、上下文、引用或候選數，勿暗中降門檻 |
| inspect 圖片超過上限 | 縮短候選區段或調整 --every；預設最多 120 張 |
| 直式人物被裁掉 | 改用 pad；crop 只有固定 x/y，無動態追蹤 |
| 直式尺寸太小 | height 是垂直像素；要 1080×1920，指定 portrait 與 height=1920 |
| 字幕燒錄缺字或失敗 | 檢查 FFmpeg libass 和字型；先交 SRT，實際查看字形後再發布 |
| 想要中英雙語或合輯 | 另安排翻譯、對齊及拼接工作；本版 CLI 只按計畫分段匯出 |
| 來源 hash 不符 | 確認是否換了原片；對新來源重新 prepare，不直接修改 hash 繞過檢查 |
| render.failed.json / .incomplete | 該階段未完成；保留紀錄，修正原因並以新目錄重跑 |
| 單元測試顯示 skipped | 透過 VH_FFMPEG、VH_FFPROBE 指定工具，重跑媒體整合；不能算全數通過 |

CLI 詳細命令見 [操作說明](../completed/video-highlights/references/usage.md)。不熟命令的學員可以請 Agent 依錯誤排查，回報實際執行與仍缺的項目。
