# 驗證紀錄

日期：2026-10-01。下列區分工具行為、內容判斷與人工驗收。

## 已執行

- **38 個 unittest 全數通過，0 skipped**：逐字稿多行／時間界線、全長分塊、重疊 cue、數值驗證、真實引用、來源 hash、完整性門檻、長度限制、去重、主題上限、計畫重驗、字幕相對時間、旋轉、SAR、無音軌與失敗狀態。
- 媒體整合案例真正執行 FFmpeg／FFprobe，包含直式、橫式、方形、保留原比例、固定裁切、補邊與燒錄字幕。
- **一小時合成素材完整流程**：prepare → 13 個重疊文字區塊 → inspect → select → validate → render。2 個片段（45 秒與 60 秒，含原片接近結尾處）產生 4 支直橫版 MP4 與 SRT，所有 MP4 完整解碼通過，原檔 hash 不變。
- 獨立 agent 以 90 秒合成素材走同一套操作說明，輸出 50 秒直橫版與字幕成功，確認檢視不足仍維持 partial。
- **約 100 分鐘真實訪談流程**：使用者提供的 Kevin Kelly 訪談，來源 6019.913 秒、854×480。已安裝的本機 Whisper small 在 GPU 轉寫原聲，產生 1,173 段原始 ASR；全部文字讀完，提出 10 個候選，依預設 30–90 秒限制選出 5 段。經 prepare → inspect → select → validate → render 產生 10 支 MP4 與 10 份英文 SRT。
- 真實範例的 10 支 MP4 全部完整解碼通過、保留音軌，來源 SHA-256 不變。FFprobe 驗證直式 404×720、橫式 1280×720，實際長度與計畫誤差皆在 0.15 秒內。已查看五段候選附近抽樣圖，以及每支成片中點影格；所有報告仍保留 partial 與 human_audiovisual_signoff=false。
- H009 另以本機詞級 ASR 估計切點，拆分兩個跨界 cue 並保留全部原文字。原始 ASR 及 project 不變，修整後使用獨立的 project-refined.json。五段成片在修整後的字幕上均無跨切點 cue，詞級時間仍未經原音驗證。

測試環境為 Windows、Python 3.11、FFmpeg 6.1.1（含 libx264／libass）、FFprobe 7.1.5。工具版本不隨技能封裝。doctor 可揭露缺少編碼器的 FFmpeg build。

## 證據界線

合成測試使用人工 fixtures 字幕與預先指定分數，無真實訪談語音；它驗證時間、資料與輸出流程，無法衡量重要內容辨識率、評分校準、真實 ASR 準確率或人類視聽品質。所有合成成片保留 human_audiovisual_signoff=false。

真實訪談案例驗證本機 ASR 資料可以接入整套流程；ASR 由本機既有模型工具產生，再經 --transcript-json 匯入。這次沒有以 CLI 的 --asr-model 入口重新跑完整影片，也沒有量測字錯率、召回率、分數校準或發布成效。未完整觀看成片或聆聽原音；ASR 專名、句尾、聲畫同步與英文字幕仍待複核。最後約 20 秒沒有 ASR 文字，coverage 明示 unreviewed。內容筆記與分數見 [真實範例](references/example-kevin-kelly.md)。

已測試目前 Windows 環境，未在 macOS、Linux 與其他 Python/FFmpeg 版本重跑。動態人臉追蹤、多機位智慧切換、HDR 色彩管理及發布平台串接不在此版本範圍。

## 重現

依 [操作說明](references/usage.md) 設定 VH_FFMPEG／VH_FFPROBE，執行 `python -m unittest discover -s tests -v`。再執行 `python tests/smoke_workflow.py --out <new-directory> --ffmpeg <ffmpeg> --ffprobe <ffprobe>`。

實際學員素材仍需完成全片內容閱讀、候選視聽核對及成片回看。
