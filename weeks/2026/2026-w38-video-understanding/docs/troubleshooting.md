# 疑難排解

## 沒有顯示「影片理解」

確認技能資料夾第一層有 SKILL.md、agents、assets、references、scripts 與 tests。RAR 原始雙層目錄已在發布包整理；安裝 completed 下的 video-understanding 資料夾即可。更新前把舊版移到技能目錄外備份，再重新開啟 Agent。

## 找不到 FFmpeg 或 FFprobe

請 Agent 檢查 PATH 與版本。可用 `--ffmpeg <執行檔>`、`--ffprobe <執行檔>` 明確指定。路徑含空白時加引號。Python helper 不需要 pip 套件。

## helper 拒絕輸出或抽樣

輸出資料夾必須不存在；換新名稱保留舊證據。超過預設 240 張上限時，縮短區段或放大抽樣間距。來源損壞、解碼器缺失、時間戳異常或來源處理中被修改時也會失敗，先查看原始錯誤；不要把未完成檔案當成功證據。

## 有音軌卻沒有 WAV

檢查 manifest 的 audio.status。某區段沒有解碼到樣本仍可能是有音軌影片，需保留 audio_present=true；抽取失敗與無音軌分開記錄。

## 字幕或音效時間對不上

使用 manifest 的實際 decoded PTS，不用平均 FPS 推測幀時間。WAV 的局部時間須加回 offset；如音訊不連續，依 audio.segments 分段映射。

## analysis.json 驗證失敗

依序檢查有限數值、時間範圍、重複 ID、引用存在、證據檔相對路徑、reviewed 記錄、素材依賴環，以及 ready 的全片覆蓋條件。空白模板本來就需要填入實際內容，預期無法直接通過。

回傳碼：0 為結構有效、1 為契約錯誤、2 為讀取／JSON 錯誤。通過訊息不代表視聽品質驗收。

## 環境無法看圖或聽音

保存可支持的分析，標示 partial，記錄待檢視區段與所需能力。ASR 可支持轉錄文字，音樂、音效、語氣與聲畫同步仍需要相應檢視。

## 回報問題

附作業系統、Python／FFmpeg 版本、最小命令、錯誤輸出與預期結果。先移除私人路徑、存取 token、影片與逐字稿等敏感資料。
