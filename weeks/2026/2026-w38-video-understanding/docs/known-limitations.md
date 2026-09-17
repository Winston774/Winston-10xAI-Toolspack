# 已知限制

- `prepare_video.py` 只接受本機影片檔，沒有下載 URL 的能力。
- helper 準備畫格、WAV、probe 與時間量測，沒有執行語義理解、OCR、ASR 或實際觀看／聆聽。
- `validate_analysis.py` 只驗證 JSON 結構、時間、引用、檔案存在與 `partial`／`ready` 紀錄一致性。它不會開啟畫格、解碼證據、聽音訊或判斷敘事品質。
- `reviewed: true` 是分析者的紀錄，結構驗證器無法獨立證明該檔案真的被人或 Agent 檢視。
- helper 會掃描完整影片的解碼 timestamp；指定短區段仍可能解碼整支影片。它沒有內建輸入大小、時長、CPU、記憶體、磁碟或外部程序 timeout 上限。
- 選取第一條可用視訊與音訊 stream。多音軌或私人音軌需要人工確認；16 kHz mono WAV 只適合分析／ASR，音樂、空間與混音品質應回看原檔。
- 本週 Release 在 Windows、Python 3.11 與 FFmpeg／FFprobe 7.1.1 的來源環境曾完整測試；其他作業系統、Python 與 FFmpeg 組合尚未做同等範圍驗證。
- 來源分析方法衍生自 Hypit；本技能未包含 Hypit runtime、生成程式、雲端服務或完成的影片渲染流程。

上述限制是選擇 `Preview` 狀態的原因。遇到任何關鍵缺口時，保留 `partial` 和明確的 `next_steps`。
