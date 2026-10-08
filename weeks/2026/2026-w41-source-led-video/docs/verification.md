# 驗證紀錄

日期：2026-10-08。範圍：本週實際分發的技能副本及 Toolspack 學員封裝。

## 本機已驗證

- 來源 ZIP 重新開啟、CRC 檢查、路徑安全與 UTF-8 解碼通過；全部 27 個檔案的大小與 SHA-256 符合原始 manifest。
- 本週 completed 副本與來源 27 檔逐一比對，未改動位元組。Python 語法編譯（不產生快取）、JSON 解析及學員 Markdown 相對連結檢查通過。
- 以本週副本執行 `scripts/smoke_test.py`，搭配本機明確指定的外部環境。20 項流程契約通過，包括拒絕覆蓋、未知分數、不完整證據、門檻優先、拒絕候選不可 resolve、實測影格對齊、空白品牌／外部聲音預設、動態題數、opening 背景須在旁白中出現及旁白計畫整合。
- 測試使用合成色塊影片與靜音 WAV；實際切片並產生兩題、35.0 秒、1,050 影格的可編輯工程。五個 scene 的紙感字幕帶結構、marker 時序與恢復規則檢查通過。
- 執行倉庫 `validate-repo.ps1` 與本週 `build-release.ps1`；重開 ZIP 核對逐檔內容，且確認沒有影音、私人環境檔、快取、金鑰或巢狀壓縮包。

測試輸出與本機路徑不納入學員包。來源附帶測試覆蓋的是上述 20 項契約，不能解讀成所有分支均已測完。

## 尚未驗證

- 本次未執行 HyperFrames 瀏覽器畫面檢查、最終 MP4 渲染或渲染影格回歸。
- 未使用真實訪談驗收全片理解、選段忠實度、人物事實、專名發音及連續觀看體驗。
- 未呼叫外部 ASR／TTS／生成模型，未估算供應商費用。
- 沒有實際縮圖與人工核聽／觀看紀錄；`visual_acceptance`、`continuous_viewing` 均不能宣告成立。

因此本週維持 **Preview**。套件可供學習與試用，實際成片仍需遵循原始 [交付檢查](../completed/source-led-video/references/quality-and-delivery.md)。

## GitHub CI 範圍

沿用現有工作流程，驗證倉庫結構、執行既有工具檢查並建立各週 ZIP。W41 Python 的合成整合測試在本機執行，現有 CI 沒有代跑該測試。可在 [Actions](https://github.com/Winston774/Winston-10xAI-Toolspack/actions/workflows/validate.yml) 查看對應提交結果；合併後主分支亦需確認成功。

本機與 CI ZIP 的壓縮位元組可能因平台、時間戳不同；比較解壓後的檔案清單與 SHA-256，不能僅以整包 hash 是否相同判斷內容差異。
