# 2026-W33：Index Studio — IndexTTS 2.5 本機語音實驗工作台

> 用自己的 Windows 與 NVIDIA GPU，將單一合法聲紋變成可控制語言、情緒、語速與發音的本機語音實驗。

## 本週成果

本週提供 `Index Studio v1.0.0`。它保留 IndexTTS 2.5 的完整推論程式，加入臺灣正體中文優先的單檔 HTML 工作台、FastAPI 本機橋接、可重現 JSON Metadata、能力實驗流程與 Noise Winston Calm／Signal 視覺系統。

主要能力：

- 零樣本聲紋複製。
- ZH、EN、JA、ES、AR 五語言合成。
- 聲紋情緒、獨立情緒音檔、八維向量、文字描述四種情緒模式。
- `duration_factor` 語速控制與拼音／CMU 音素／日文假名標註。
- 固定 Seed、採樣參數、WAV 下載與 JSON 實驗紀錄。
- 正體原文保留在介面與紀錄，推論前才在本機轉成簡體中文。
- API 預設只監聽 `127.0.0.1`，單 GPU 工作序列化。

- 獨立專案：<https://github.com/Winston774/index-studio-indextts-2-5>
- 獨立專案 Release：<https://github.com/Winston774/index-studio-indextts-2-5/releases/tag/v1.0.0>
- Toolspack 成品：[`completed/index-studio-indextts-2-5/`](completed/index-studio-indextts-2-5/)

## 基本資料

- 類型：Local AI Tool
- 難度：中級
- 預估時間：首次安裝 30–90 分鐘；實驗與拆解約 120 分鐘
- 支援平台：Windows 10／11
- Python：3.10 或 3.11
- 建議硬體：NVIDIA GPU、CUDA 12.8 或更新版本、至少 25 GB 可用空間
- 內容版本：`1.0.0 Stable`

首次安裝的 Python 環境實測約 8 GB，模型與輔助模型另需數 GB。實際空間、下載時間與速度會隨硬體、鏡像與上游版本改變。

## 需要準備

- Git 與 [uv](https://docs.astral.sh/uv/getting-started/installation/)。
- NVIDIA 顯示卡與可用驅動；先執行 `nvidia-smi`。
- 一段 5–15 秒、乾淨、單人、自己有權使用的聲紋音檔。
- 足夠的硬碟與網路流量下載 CUDA Python 套件與模型權重。

本工具不要求 API Key，也不消耗 LLM Token。模型、Python 套件與必要資源會在首次安裝／啟動時從外部來源下載。

## 安裝與開始

學員可以從獨立 Repo clone，或從本週 Toolspack ZIP 解壓：

```powershell
git clone https://github.com/Winston774/index-studio-indextts-2-5.git
cd index-studio-indextts-2-5
```

啟動：

```powershell
.\start_htmlui.ps1
```

也可以雙擊 `start_htmlui.bat`。瀏覽器會開啟 `http://127.0.0.1:7861`；等待狀態顯示「模型已就緒」再生成。

## 本週任務

1. 用已授權聲紋生成一段臺灣正體中文基準音檔。
2. 固定聲紋、文字、Seed 與採樣參數，只改 `duration_factor`，比較 `0.8` 與 `1.2`。
3. 再選一組情緒模式做 A/B，比較情緒效果與音色穩定度。
4. 保存四份 WAV、JSON Metadata 與人工評分。
5. 用 100–200 字寫出「哪個參數真的改變結果、代價是什麼」。

完整拆解見[教學講義](lesson.md)。

## 成果證據

- 一張工作台完成畫面，避開私人路徑與敏感資料。
- 四份 WAV 與對應 JSON；公開分享時確認聲音本人同意。
- 一張比較表：唯一變因、可懂度、自然度、聲紋相似、情緒或語速效果。
- 100–200 字觀察與下一輪假設。

## 通過標準

- [ ] `http://127.0.0.1:7861/api/health` 顯示模型 ready。
- [ ] 正體中文原文保留在 JSON，內部模型語言映射為 `ZH`。
- [ ] 四次實驗每輪只改一個指定變因。
- [ ] WAV 可播放，JSON 可對應 Seed 與採樣參數。
- [ ] 聲紋音檔、WAV、JSON、模型權重與 `.venv` 未進入 Git。
- [ ] 成果使用的聲音有明確權利，公開內容揭露為 AI 生成。
- [ ] 已閱讀專案 `LICENSE`、`LICENSE_ZH.txt`、`DISCLAIMER` 與 `NOTICE.md`。

## 失敗時的最短路徑

1. 執行 `nvidia-smi`、`uv --version`、`python --version`。
2. 執行 `uv run tools/gpu_check.py`。
3. 重新用 `uv run --extra htmlui --extra test python -m pytest tests/test_htmlui.py -q` 驗證合約。
4. 檢查 `checkpoints/` 必要模型是否下載完成、硬碟是否足夠。
5. Port 被佔用時執行 `.\start_htmlui.ps1 -Port 7862`。
6. 音質問題先縮短文字、改用乾淨 5–15 秒聲紋並固定基準參數。
7. 仍失敗時依[疑難排解](docs/troubleshooting.md)收集證據。

## 授權提醒

Index Studio 是 IndexTTS 的衍生散布，沿用 `bilibili Model Use License Agreement`，包含下游散布、商業規模、高風險用途與模型改進限制。Toolspack 根目錄 MIT License 只適用根倉庫自行創作的教材與工具，不會覆蓋 `completed/index-studio-indextts-2-5/` 內的上游授權檔。

## 版本紀錄

- `v1.0.0 Stable`：HTML 工作台、臺灣正體流程、能力實驗、學員文件、Release validator 與 CI。
