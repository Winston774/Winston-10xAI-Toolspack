# W38 v0.1.1 驗證紀錄

驗證日期：2026-09-17。範圍：使用者更正 RAR 的技能內容與重新編寫的 W38 分發文件。

## 本次已執行

- Windows／Python 3.11.15／FFmpeg、FFprobe 8.0.1。
- `python -B -X utf8 -m unittest discover -s tests -v`：30 項通過，0 跳過。
- 其中 7 項為 helper 單元測試、7 項合成影音整合測試、16 項索引驗證器測試。
- 合成媒體由 FFmpeg 在暫存目錄建立，涵蓋變動幀率、非零時間起點、延遲音訊、區段抽取、像素比例、旋轉與片尾影格。
- 本次未使用原始 RAR 裡的編譯快取。

發布前另執行原始文字對照、Python 語法檢查、Skill 結構驗證、Toolspack 倉庫驗證、W38 相對連結檢查、禁止內容／常見憑證樣式掃描，以及 ZIP 檔案集合與 hash 回讀比對。最終 ZIP SHA-256 登記在 GitHub Release。

## 重新執行測試

在 `completed/video-understanding/` 執行：

```powershell
$env:VIDEO_TEST_FFMPEG = '<你的 ffmpeg 執行檔完整路徑>'
$env:VIDEO_TEST_FFPROBE = '<你的 ffprobe 執行檔完整路徑>'
python -B -X utf8 -m unittest discover -s tests -v
```

沒有設定這兩個環境變數會跳過 7 項媒體整合案例。請回報實際 passed／skipped 數，不把跳過當通過。

## 證據界線

- 自動測試證明程式在列出的案例下符合預期，無法代替真實影片的語義與視聽驗收。
- 索引測試包含刻意建立的假證據檔，僅用於契約測試，不能拿來宣稱影片真的被看過。
- RAR 原始 VALIDATION.md 的歷史影片案例、上游連結數與舊環境紀錄，未納入本次完成宣稱。
- 本次未做 macOS／Linux、雲端模型、ASR 安裝或真實影片端到端測試。
- Preview 狀態維持不變。Skool 分享文為獨立營運文件，不放入學員 ZIP。
