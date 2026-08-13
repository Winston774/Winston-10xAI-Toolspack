# Index Studio HTML UI

Index Studio 是 IndexTTS 2.5 的本機單頁實驗工作台。前端集中在根目錄的 `webui.html`，不需要 Node.js、打包器或 CDN。Python 服務負責模型載入、音檔隔離、輸入驗證與 GPU 生成。

## 視覺系統

介面沿用 Noise Winston Design System 的雙速架構：Warm Ivory、White 與 Ink 組成 Calm Layer，承載閱讀、設定與表單；Purple 用於操作與選取狀態，Signal Lime 僅用於生成結果與完成證據。深色模式使用獨立 semantic tokens，避免直接反轉黑白造成層級與對比失真。

所有主題色、圓角、字體與 motion timing 均集中在 `webui.html` 的 `:root` 變數。產品維持單檔、無 CDN 依賴；繁體中文優先使用系統內的 Noto Sans TC、PingFang TC 或 Microsoft JhengHei。

## 快速啟動

Windows 可直接雙擊：

```text
start_htmlui.bat
```

或在 PowerShell 執行：

```powershell
.\start_htmlui.ps1
```

瀏覽器會開啟 `http://127.0.0.1:7861`。第一次執行會透過 `uv` 建立環境，並在 `checkpoints/` 缺少必要檔案時下載 IndexTTS 2.5 模型。

首次安裝包含 CUDA 版 PyTorch 與完整音訊工具鏈。本次 Windows 實測的 `.venv` 約 8 GB，模型與輔助模型還需要數 GB，下載與解壓可能持續數分鐘且暫時沒有終端輸出。

如需手動控制：

```powershell
uv run --extra htmlui python htmlui_server.py --no-open-browser
```

服務啟動後也可直接雙擊 `webui.html`。HTML 會連線到本機的 `127.0.0.1:7861` API。

## 能力實驗

| 能力 | 介面入口 | 參數 |
| --- | --- | --- |
| 零樣本聲紋複製 | 聲紋參考音檔 | `spk_audio_prompt` |
| 臺灣正體中文 | 語言選單 | 正體原文保留，推論前轉為簡體並使用 `ZH` |
| 五語言合成 | 語言選單 | `ZH`, `EN`, `JA`, `ES`, `AR` |
| 情緒與聲紋分離 | 情緒參考音檔 | `emo_audio_prompt`, `emo_alpha` |
| 八維情緒控制 | 情緒向量 | `emo_vector` |
| 文字情緒描述 | 文字描述 | `use_emo_text`, `emo_text` |
| 語速控制 | 時長係數 | `duration_factor` 0.5 到 2.0 |
| 發音控制 | 文字中的標註 | 中文拼音、CMU 音素、日文假名 |
| 可重現採樣 | 生成設定 | Seed 與 GPT 採樣參數 |

「文字描述」沿用上游的實驗性情緒分析能力。情緒向量順序為高興、憤怒、悲傷、害怕、厭惡、低落、驚訝、平靜。

「中文」是預設模式。瀏覽器、歷史紀錄與 JSON Metadata 都保留使用者輸入的正體原文；Python 服務只在呼叫 IndexTTS 2.5 前，使用 OpenCC `tw2s` 轉換合成文字與情緒描述，並將模型語言映射為 `ZH`。為相容舊頁面，`ZH-TW` 與 `ZH` 請求都會執行相同轉換。簡體推論文字不會回傳到使用者介面。

建議依 [能力實驗流程](CAPABILITY_EXPERIMENTS_ZH.md) 固定聲紋、Seed 與採樣參數，逐輪只修改一個變因。

## 執行架構

```text
webui.html
    -> POST /api/generate
htmlui_server.py
    -> 驗證與暫存上傳音檔
    -> 臺灣正體模式：OpenCC tw2s，模型語言 ZH
    -> 單一 GPU Lock
IndexTTS 2.5
    -> outputs/htmlui/<task-id>.wav
    -> outputs/htmlui/<task-id>.json
```

API 預設只監聽 `127.0.0.1`。每次推理只允許一個 GPU 工作，避免同時生成造成顯存競爭。上傳暫存檔在生成後刪除，輸出的 WAV 與 JSON 實驗紀錄會保留在 `outputs/htmlui/`。

## API

- `GET /api/health`：模型載入與 GPU 忙碌狀態。
- `GET /api/capabilities`：UI 可用能力與參數範圍。
- `POST /api/generate`：上傳音檔與生成參數。
- `GET /api/audio/{task_id}`：取得生成的 WAV。
- `GET /api/runs/{task_id}`：取得可重現的 JSON 參數。
- `GET /api/docs`：本機 OpenAPI 文件。

## 驗證

不載入模型的 API 與驗證測試：

```powershell
uv run --extra htmlui --extra test python -m pytest tests/test_htmlui.py -q
```

完整模型驗收需要先下載 checkpoints，並使用實際聲紋音檔執行一次生成。靜態與 API 測試成功只代表整合契約通過，不能取代音質、聲紋相似度與情緒表現的人工聆聽。
