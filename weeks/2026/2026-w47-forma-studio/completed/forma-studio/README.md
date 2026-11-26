# Forma Studio 0.1.0｜學員預覽版

本機數位人工作室，包含可編輯的角色資料、場景、圖片與語音任務。推薦用 Windows 10/11 x64、Node.js 24 或更新版本。Windows 本機金鑰用目前 Windows 帳戶的 DPAPI 保護；其他系統用本機檔案權限、不可視同 Windows 加密。這次教材未做跨平台實機驗收。

## 1. 啟動（不需 API 金鑰）

從有 `package.json`、`public/`、`server/` 的這一層執行。基本工作室使用 Node 內建模組；無需 `npm install`、Python、FFmpeg 或 GPU。

```powershell
node --version
node server/index.mjs
```

開啟 [本機工作室](http://127.0.0.1:4317/)；可先瀏覽五個角色範本、十二個內建場景、手動建立角色。成功啟動後，[健康檢查](http://127.0.0.1:4317/api/health) 應顯示 `{"ok":true}`。要停止時在該終端按 `Ctrl+C`。不把埠對外公開，不用 tunnel 或公用反向代理。

## 2. 設定自己的帳號

| 服務 | 操作 | 第一次驗收 |
|---|---|---|
| OpenAI | 到「服務設定 → OpenAI」貼上自己的 API 金鑰，核對**圖片模型**與**角色設定與提示詞模型**，再按「儲存設定」。模型欄位可改；請從帳號可用的模型中選擇分別支援 Images API（含所需的 Edit 功能）和 Responses API 結構化輸出的模型。 | 「儲存並測試連線」會向 OpenAI 查詢兩個模型；模型可見不代表已有生成額度。再依[官方圖像指南](https://developers.openai.com/api/docs/guides/image-generation)核對模型功能。 |
| Fish Audio | 展開「配音與影片服務 → Fish Audio」貼上自己的 API 金鑰，確認語音模型與帳號方案相符，再按該區的「儲存設定」。到角色的「聲音與表演」選 **Fish Audio**，需要指定音色時，填入你有權使用的 `reference_id`。 | 設定頁的連線測試只測 OpenAI。Fish Audio 要用一句無個資的台詞做一次實際配音，確認作品庫有可播放 WAV。請先確認費用，並看 [Fish Audio TTS 文件](https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech)。 |

**請在工作室介面手動輸入。** Codex 可協助啟動與定位欄位，金鑰不需要進 Codex 對話或 `.env`。ChatGPT 訂閱與供應商 API 額度可能分開，請以自己的 API 帳號後台為準。儲存後看到欄位清空是預期的保護行為；OpenAI 區會顯示金鑰已儲存。到同一區可移除已存金鑰。

## 3. 試做一個虛構角色

用首頁範本或建立角色 → 在「人物設定」調整外型與個性（可選擇 Agent 訂製）→ 進「攝影棚」選場景、構圖並生成一張定裝照 → 到「聲音與表演」選 Fish Audio，填一句短台詞 → 到「作品庫」查看、試聽、下載成果。第三方人像／服裝／姿勢圖庫未附；臉孔可用內建範本；服裝、姿勢請在角色選擇器「上傳自備圖片」（PNG／JPG／WebP，單檔 ≤20 MB），或在提示詞描述。避免上傳未授權的人臉、聲音或機密資料。

## 4. 選用功能與本機資料

「生成說話影片」須另備 `longcat-avatar-colab`、其運行依賴與已登入的 Colab CLI，並能配置 A100；使用完整 1–60 秒配音。BreezeTTS 另需相容的本機 WSL/GPU、`breeze-tts-agent-cli` 與模型，或已由你配置的語音服務端點。這些服務、授權與運行環境不在本包內。未準備好時先做圖與 WAV，不要打開 LongCat 或以預設 Breeze 送出配音。

`storage/` 初次啟動自動建立，含作品、SQLite 與本機設定，請勿分發。Windows 的金鑰綁定登入帳戶，搬機需重新配置。可在啟動前以 `PORT` 改埠，或以 `STUDIO_DATA_DIR` 指向另一個私有目錄；請保留舊目錄。運行中不要複製 SQLite 當作完整備份，請先停機，再於私有位置備份。

`npm run validate` 是本機分發檢查。開發者測試另見 `tests/`；`test:ui` 需安裝開發套件與本機 Chromium、相應媒體測試需 FFmpeg。不要把驗證結果當成你的帳號已通過付費生圖、語音或 GPU 驗收。
