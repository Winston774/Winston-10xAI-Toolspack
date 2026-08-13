# Index Studio 學員快速導讀

## 這個專案解決什麼

Index Studio 把 IndexTTS 2.5 的模型能力整理成一個本機實驗 Workflow：

```text
準備合法聲音 → 固定基準參數 → 一次只改一個變因 → 生成 WAV → 保存 JSON → 人工聆聽比較
```

你會練習四件事：

1. 用單一聲紋建立零樣本語音合成。
2. 分開控制語言、情緒、語速、發音與採樣參數。
3. 用固定 Seed 與 JSON Metadata 保留可重現證據。
4. 把模型宣稱拆成可比較、可評分、可重試的實驗。

## 建議學習路徑

1. 先讀[隱私、聲音權利與安全](PRIVACY_AND_VOICE_RIGHTS_ZH.md)。
2. 依[操作與架構](HTML_UI_ZH.md)完成安裝。
3. 先做一筆「沿用聲音情緒」的中文短句基準。
4. 依[能力實驗流程](CAPABILITY_EXPERIMENTS_ZH.md)選一組實驗。
5. 保留 WAV、JSON 與人工評分，不公開聲紋原檔。
6. 依[驗證與驗收](VERIFICATION_ZH.md)區分自動測試與人工聆聽。

## 最小成果證據

- 一張工作台完成畫面，避開本機路徑與私人資訊。
- 同一聲紋、同一句文字、只改一個變因的兩個 WAV。
- 對應的兩份 JSON Metadata。
- 100–200 字觀察：聲紋相似、可懂度、自然度與變因效果。

## Token 與 Agent 成本

本工具的語音生成在本機 GPU 執行，基本 Workflow 不需要 LLM Token。若讓 Codex 協助分析 JSON 或設計實驗，先提供欄位摘要與觀察結果，避免上傳聲音與整份模型輸出。
