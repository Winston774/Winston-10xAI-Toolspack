# 疑難排解

| 狀況 | 處理方式 |
|---|---|
| 下載後找不到 EXE | GitHub 的 Source code ZIP／CI 教材 ZIP 不是程式包；下載 W46 Release 具完整產品名稱的附件 |
| SHA-256 不符 | 停止執行，核對版本、檔名與來源，重新下載；不要自行忽略差異 |
| 找不到 DLL／_internal | 完整重新解壓，不單獨移動 EXE |
| SmartScreen／組織政策阻擋 | 保留訊息，請使用者或管理員判讀；不要停用防護 |
| 驅動需要 UAC／重啟 | 由使用者處理；取消不代表完成，不自動重啟 |
| 無法確定喇叭位置 | 列出裝置讓學員確認 FL／FR／RL／RR，不靠名稱猜測 |
| 切到 CABLE Input 後無聲 | 先確認 fresh status、PID、running 與設定；路由失敗先切回原本實體輸出 |
| 校正部分失敗 | 整輪不套值，調整環境後依手冊重試，不拼接部分補償 |
| 長時間或重連後不同步 | 重新驗證，記錄硬體與觀察時間；尚無跨設備長時間同步保證 |

詳細 CLI、備份與還原步驟見 [AGENT_INSTALL.md](../completed/all-around-you-preview/AGENT_INSTALL.md)。本週不自動執行這些系統操作。
