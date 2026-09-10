# 疑難排解

## Python 或虛擬環境

**現象：** `py -3.11` 或 `.venv\Scripts\python.exe` 找不到。

1. 在 PowerShell 執行 `py --list`，確認已安裝 Python 3.11 以上。
2. 在 `completed/xunjian-local-video-editor` 重新建立 `.venv`：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

3. 若你使用了不同版本的 Python，請用該版本完整路徑執行；不要把另一個專案的 `.venv` 複製進來。

## localhost 無法開啟

**現象：** 瀏覽器無法連到 `http://127.0.0.1:8321`。

1. 保持 `start-local-editor.ps1` 的 PowerShell 視窗開啟，先查看第一個錯誤。
2. 確認該連接埠沒有被其他服務使用。可改用不同連接埠：

```powershell
.\start-local-editor.ps1 -Port 8331
```

3. 以 `http://127.0.0.1:8331` 開啟，並讓 MCP 設定的 URL 使用相同連接埠。
4. 只接受 localhost 連線是本工具的安全邊界；不要為了遠端存取而把服務直接暴露到公開網路。

## FFmpeg 或 FFprobe 找不到

**現象：** 匯入、證據、波形或匯出顯示找不到媒體工具。

1. 安裝與你的 Windows 環境相容的 FFmpeg，並把 `ffmpeg`、`ffprobe` 加進 `PATH`。
2. 關閉並重新開啟 PowerShell，分別執行 `ffmpeg -version` 與 `ffprobe -version`。
3. 回到工作台的「環境」重新檢查。不要把二進位檔塞進 GitHub 作業或 Issue。

## 本機 ASR 模型或測試語音失敗

**現象：** `scripts/setup-local-asr.ps1` 或 `scripts/verify-local-asr.ps1` 失敗。

- 模型設定需要網路、足夠磁碟空間與相容 Python 套件；它是選用功能，不會阻止你使用基本時間軸。
- 本輪打包環境中，`verify-local-asr.ps1` 找到中文 Windows 語音後，因該主機的系統安全性設定拒絕選取語音而停止。這是測試語音 fixture 的主機環境阻塞，沒有被當成「本機 ASR 已通過」的發布證據。
- 先確認 Windows 是否有可用的中文語音與 `System.Speech` 支援；不要為了通過測試自動降低系統安全設定。
- 可先使用自己有權處理的短音訊、手動匯入 SRT／VTT，或記錄第一個錯誤後再回報。

## MCP 沒有出現或連到錯的工作台

1. 先啟動工作台，再啟動 `python -m local_editor mcp --url ...`。
2. 將 `examples/local-editor.codex.toml` 或 `examples/local-editor.mcp.json` 裡的 `C:\\path\\to\\xunjian-local-video-editor` placeholder 改成你的解壓縮資料夾與 `.venv` Python 路徑。
3. 檢查服務 URL 和設定中 `--url` 的連接埠一致。
4. stdio 程序等待輸入時不會顯示剪輯介面；它必須由支援 MCP 的宿主啟動。
5. 任何寫入工具前先讀取 `editor_get_context`。若版本過期，重讀並重新提案。

## KIE、YouTube 或舊 Agent Video Editor 失敗

這些功能不是本週最短學習路徑。先確認你是否真的需要外部服務、是否有權處理內容、帳號是否有費用限制，以及 `.env` 是否只保留在本機。不要把 Token、Cookie、完整字幕、下載素材或真實專案資料附到公開回報。
