# 驗證與驗收

## 自動驗證

completed 專案：

```powershell
cd completed\index-studio-indextts-2-5
npm.cmd run validate
uv run --extra htmlui --extra test python -m pytest tests\test_htmlui.py -q
```

Toolspack 根目錄：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-release.ps1 -WeekPath .\weeks\2026\2026-w33-index-studio-indextts-2-5
```

## 本次已驗證

- `npm.cmd run validate`：4/4 Release tests，356 files inspected。
- `tests/test_htmlui.py`：9 passed。
- `htmlui_server.py`：Python compile 通過。
- 已排除 `.venv`、模型權重、outputs、私人 WAV、JSON 與 `resouces/`。
- 來源工作階段曾完成 1200 × 900 與 390 × 844 Browser QA，console errors 0。
- 獨立公開 Repo `main`：`9f65c414f522c5b25e13fbb4eb3cb45b4c6f49ec`。
- GitHub Actions `Validate Index Studio`：run `31675292336` 成功。
- 獨立專案 `v1.0.0`：非 Draft、非 Prerelease。

## 人工／環境邊界

- 真實 NVIDIA GPU 與 IndexTTS 2.5 模型生成：來源工作區已完成一次 health ready 與本機操作；新的公開 clone 冷啟動仍需另驗。
- 音質、聲紋相似、情緒、語速與五語言品質：必須人工聆聽，不由自動測試代替。
- 公開 Repo、CI 與正式 Release已完成 `Public remote`；匿名 clone 與全新機器模型冷啟動仍需另驗。
