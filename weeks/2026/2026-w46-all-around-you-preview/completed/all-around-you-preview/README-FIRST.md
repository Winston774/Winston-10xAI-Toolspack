# All Around You Preview 版

把 Windows 上的多組喇叭分配到左前、右前、左後、右後，支援全喇叭立體聲、模擬環繞，以及麥克風延遲校正。這是提供 Skool 學員試用的 Windows x64 預覽版本。

## 最快開始

1. **完整解壓縮 ZIP** 到你打算長期保留的位置。不要直接在壓縮檔內執行，也不要只抽出 EXE。
2. 把解壓後的整個 `All-Around-You-Preview` 資料夾交給能操作你這台 Windows 的 agent，貼上下方指令。
3. 連接喇叭，告訴 agent 每個裝置放在什麼位置。準備麥克風可做自動校正；沒有麥克風也能設定播放，延遲需要手動調整。

**可以直接貼給 agent：**

```text
請幫我安裝及設定這個 All Around You Preview Windows 測試版。
先讀這個資料夾裡的 AGENTS.md，再完整讀 AGENT_INSTALL.md，依實際檔案和 CLI 報告操作。
請完整保留 _internal，選擇持久的使用者資料夾，不要替我安裝 Python 或其他開發環境。
先備份既有設定、檢查檔案，再列出我電腦的音訊裝置。
需要我確認哪顆喇叭在左前、右前、左後、右後時，請一次列出清楚的選項讓我選。
確認位置後，協助完成虛擬端點、四位置分流、常駐播放與適用的延遲校正。
測試及錄音前先通知我，讓我調低音量、把麥克風放好；UAC 或需要重開機時告訴我。
不要自動重開機、停用防護或上傳我的資料。
最後列出已驗證、我已確認、尚未測試及被阻擋的項目，並告訴我如何停止、復原原本音訊輸出。
```

也可以自行開啟 `AllAroundYouPreview.exe`，依 `使用指南.md` 操作。第一次若缺少虛擬音訊端點，需安裝隨附的官方 VB-CABLE 驅動；Windows 可能要求管理員授權及重新啟動。

## 先知道的幾件事

- 已附執行環境，無須另裝 Python。應用程式尚未簽章；若系統安全政策阻擋，請保留訊息交給 agent 判讀，不要停用防護。
- Windows 音效輸出名稱仍是 **CABLE Input (VB-Audio Virtual Cable)**。選擇它之前，All Around You Preview 的路由必須已啟動。
- 程式需留在通知區運作。視窗右上角 X 會隱藏視窗；通知區的「停止並退出」才會停止。停止前先把 Windows 音效輸出切回原本的實體喇叭。
- 藍牙可自動量測四個位置的相對延遲；重新連線後可能需要再驗證。本版尚未完成各種電腦與長時間時鐘漂移的驗收。
- 模擬環繞是立體聲的空間效果；原生環繞片源可使用「原音分流」。
- `profile.example.json` 是給 agent 改寫的格式範例，不能直接使用。

VB-CABLE 由 [VB-Audio Software](https://vb-cable.com/) 提供，採 donationware 方式發行。包內保留官方原始驅動與授權說明；歡迎依[官方條款](https://vb-audio.com/Services/licensing.htm)支持作者或購買適用授權。
