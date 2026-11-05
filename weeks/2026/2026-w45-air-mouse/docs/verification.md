# W45 驗證與範圍

2026-11-05：以來源公開 Git 快照整理學員包，檢查受追蹤檔案與可取得 Git 歷史中的常見憑證格式，保留原始 MIT LICENSE，排除 `.git`、日誌、設定、金鑰及構建輸出。模式掃描有範圍限制，無法證明完全沒有敏感資訊。

本次 Windows 工作環境執行分發檔案契約、原始檔雜湊比對、倉庫結構與 ZIP 內容檢查；未執行 macOS Swift 編譯、App 簽章、Gatekeeper、系統授權或 AirPods 實際操作。Node.js 僅用於此包的離線檢查，學員執行 macOS App 不需要 Node.js。

來源所載 macOS 建置、簽章、ZIP、歷史耳機感測及其限制見[來源驗證文件](../completed/air-mouse/docs/verification.md)；這些是來源紀錄，並非本次重跑結果。不同 AirPods 型號、macOS 版本、長時間可靠性及首次安裝仍待驗證。
