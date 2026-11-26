# W46｜All Around You Preview：Windows 四位置喇叭

把 Windows 上的多組喇叭分配到左前、右前、左後、右後，提供全喇叭立體聲、模擬環繞、原音分流與麥克風延遲校正。本週分享可攜式 **Windows x64 0.1.0-preview.1**，預估練習 120 分鐘，維持 Preview。

## 下載：請選 Release 的程式附件

- [W46 Release](https://github.com/Winston774/Winston-10xAI-Toolspack/releases/tag/2026-w46-v0.1.0-preview.1)
- [下載完整 Windows x64 程式 ZIP](https://github.com/Winston774/Winston-10xAI-Toolspack/releases/download/2026-w46-v0.1.0-preview.1/All-Around-You-Preview-Windows-x64-0.1.0-preview.1.zip)
- [下載 SHA-256](https://github.com/Winston774/Winston-10xAI-Toolspack/releases/download/2026-w46-v0.1.0-preview.1/All-Around-You-Preview-Windows-x64-0.1.0-preview.1.zip.sha256)

程式 ZIP 為 58,577,023 bytes（約 55.9 MiB）。SHA-256：

```text
e30c04e3d1c8e821e6522ac579c4ec2509aea40d3ba8140a9ca3a0c4323b5e7a
```

GitHub 自動提供的 Source code ZIP 與 CI 教材 ZIP 只包含教材和下載資訊，**沒有可執行程式**。請下載上述具完整產品名稱的附件；不要只取 EXE，必須保留 `_internal`。二進位原包不放進 Git 歷史，也不嵌入教材 ZIP，原有 AGENTS 入口、官方驅動及授權內容均保留於 Release 原包。

## 準備與安全範圍

- Windows x64、可用的前後四位置喇叭；可使用四個獨立端點或受支援的立體聲組合。需要麥克風才可做自動聲學校正。
- 不需另裝 Python、Node.js 或開發工具。主程式未簽章，請核對來源與雜湊；若 Defender、SmartScreen 或組織政策阻擋，保留訊息交由使用者／管理員判讀，勿停用防護。
- 官方 VB-CABLE 標準 Pack46 原始套件隨程式提供。缺少端點時安裝可能要求 UAC 或重新啟動，由學員自行確認，不自動重啟。
- 改動音訊設定前先備份；第一次測試音與麥克風校正前先通知學員，確認音量、房間與麥克風位置。
- 裝置名稱無法證明實體位置，FL／FR／RL／RR 必須由學員確認。

## 最快開始：交給 Agent

完整解壓程式 ZIP 到可長期保留的資料夾，再交給能操作該 Windows 電腦的 Agent：

```text
請幫我安裝及設定這個 All Around You Preview。
完整解壓後，先讀程式資料夾的 AGENTS.md，再完整讀 AGENT_INSTALL.md。
先檢查雜湊並備份既有設定，再列出裝置，讓我確認左前、右前、左後、右後。
測試音及麥克風校正前先通知我；UAC 或需要重啟時讓我自行處理。
不要停用防護、自動重啟或上傳我的資料。
最後區分已驗證、需要我實聽確認、未測及阻擋項目，
並說明如何停止程式與還原原本 Windows 音訊輸出。
```

完整[Agent 安裝手冊](completed/all-around-you-preview/AGENT_INSTALL.md)、[先讀說明](completed/all-around-you-preview/README-FIRST.md)與[使用指南](completed/all-around-you-preview/使用指南.md)也附在教材內；實際操作請以程式原包及當次 CLI 報告為準。

## 交付與通過標準

1. 比對 ZIP 與包內清單，確認完整解壓，舊設定已備份。
2. 以當次裝置清單建立四位置映射，不套用其他電腦的裝置 ID、補償或設定。
3. 自檢、端點格式、實際路由、四位置實聽與延遲量測分開驗收。`--check` 通過不等同有聲或同步。
4. 需要麥克風量測時，整輪有效才套用；沒有麥克風就明確標示未完成自動校正。
5. 確認常駐的新鮮狀態與 PID 後才切換預設輸出，保存還原快照；停止使用前先切回實體輸出。

## 隱私與限制

設定、狀態與備份位於 `%LOCALAPPDATA%\DoubleSoundSurround`，舊名稱為相容用途。報告可含裝置 ID、名稱、路徑、時間與量測值，應留在學員電腦，公開回報前先檢查。麥克風分析依來源實作在本機記憶體進行；本次未執行錄音或路由。

本包仍待另一台乾淨 Windows 完整安裝、實體四位置校正與長時間漂移驗收。來源宣稱 189 項測試通過，本次沒有重跑這些測試；[驗證紀錄](docs/verification.md)列出實際完成範圍。

VB-CABLE 由 [VB-Audio](https://vb-cable.com/) 提供，採 donationware，歡迎[捐款／購買適用授權](https://shop.vb-audio.com/)。特定專業部署須依[官方條款](https://vb-audio.com/Services/licensing.htm)確認；EasySurround MIT 不涵蓋驅動。參見[隱私與內容權利](docs/privacy-and-content-rights.md)及[疑難排解](docs/troubleshooting.md)。

版本註記：Toolspack 教材 metadata 使用 `0.1.0`，程式實際版本為 `0.1.0-preview.1`。本次不修改原樣程式 ZIP。
