# v0.1.1 學員發布驗證

日期：2026-09-17。來源：video-understanding2.rar。

此文件依本次發布結果重新編寫，取代 RAR 中的歷史驗證紀錄。功能文件、模板、Python 程式與測試保持本次 RAR 的內容。

## 已驗證

Windows、Python 3.11.15、FFmpeg／FFprobe 8.0.1：

```text
python -B -X utf8 -m unittest discover -s tests -v
Ran 30 tests
OK
```

已設定 VIDEO_TEST_FFMPEG、VIDEO_TEST_FFPROBE，因此 7 項合成媒體整合測試有實際執行；0 項跳過。其餘為 7 項 helper 單元測試及 16 項索引驗證器測試。

整合測試涵蓋音畫區段映射、小數邊界、非零視訊起點、無音軌、變動幀率、延遲音訊、像素比例與旋轉。使用暫存合成媒體，不需要私人影片。

## 尚未驗證

本次未執行跨平台或真實影片完整分析，也未進行人工觀看／聆聽品質驗收。索引驗證器通過只表示資料契約一致；觀看、聲音、文字與敘事的正確性需實際證據支持。

完整分發驗證範圍見 [W38 驗證紀錄](../../docs/verification.md)，來源與授權見 [來源說明](../../docs/source-and-license.md)。
