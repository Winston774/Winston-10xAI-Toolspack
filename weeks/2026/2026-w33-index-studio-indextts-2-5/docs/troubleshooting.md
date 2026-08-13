# 疑難排解

## 啟動前最小診斷

```powershell
nvidia-smi
uv --version
python --version
uv run tools/gpu_check.py
```

## 常見問題

### 找不到 uv

依 [uv 官方安裝說明](https://docs.astral.sh/uv/getting-started/installation/)安裝，關閉並重開 PowerShell。

### CUDA 或 Torch 無法使用 GPU

記錄 `nvidia-smi`、驅動、GPU 型號與 `uv run tools/gpu_check.py` 輸出。這個專案的 PyTorch index 使用 CUDA 12.8；舊驅動可能不相容。

### 模型一直載入

首次下載可能數 GB。確認網路、硬碟空間與 `checkpoints/` 是否持續增加。不要把未完成的 checkpoints 放進 Git 或分享 ZIP。

### Port 7861 被占用

```powershell
.\start_htmlui.ps1 -Port 7862
```

### 生成失敗或顯存不足

- 關閉其他 GPU 程式。
- 用短文字與單一工作測試。
- 確認沒有同時啟動兩個 Index Studio。
- 必要時執行 `.\start_htmlui.ps1 -FullPrecision` 比較 BF16 相容性；它通常會增加顯存用量。

### 音質或聲紋不穩

使用 5–15 秒、單人、無音樂、無混響的合法參考聲音。固定 Seed 與採樣參數，一次只改一個變因。

## 回報資訊

提供 Windows、GPU、驅動、Python、uv 版本、`/api/health`、最小錯誤文字與是否通過 `tests/test_htmlui.py`。移除聲音、路徑、個資與 Token。
