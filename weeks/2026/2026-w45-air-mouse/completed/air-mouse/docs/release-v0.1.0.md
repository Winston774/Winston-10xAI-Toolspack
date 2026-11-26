# Air Mouse v0.1.0 — 開蓋第一版

把 AirPods 留在打開蓋子的充電盒內，用盒子的轉動控制 Mac 游標，停住後點按盒子即可送出左鍵。這是 Air Mouse 的第一個公開開源版本，由 Winston 發起。

## 下載

- `Air-Mouse-v0.1.0-macos-arm64.zip`：Apple Silicon Mac 安裝包，內含 `Air Mouse.app`、安裝說明與 MIT 授權。
- `SHA256SUMS.txt`：安裝包 SHA-256 校驗檔。將兩個檔案放在同一資料夾後，執行 `shasum -a 256 -c SHA256SUMS.txt`。
- GitHub 提供的 Source code ZIP／tar.gz：此版本完整公開原始碼。

建置目標為 macOS 14 以上、arm64。實際發布建置與相容性範圍見[驗證紀錄](https://github.com/Winston774/air-mouse/blob/v0.1.0/docs/verification.md)。

## 第一次使用

1. 解壓縮，把 `Air Mouse.app` 放入「應用程式」。
2. 此包採 ad-hoc 簽章，尚未經 Apple 公證。若 macOS 阻擋開啟，確認來源與校驗碼後，依 [Apple 官方說明](https://support.apple.com/en-us/102445)在「系統設定 → 隱私權與安全性」允許這個 App 開啟。
3. 允許動作與健身、藍牙及輔助使用權限。App 圖示會顯示在選單列。
4. 將 AirPods 連接至 Mac，關閉自動耳朵偵測，雙耳放回充電盒並保持開蓋。
5. 依提示校正方向；左右耳各需校正一次。先確認游標移動，再使用點按校正測試。

`⌃⌥M` 可暫停／恢復游標控制。完整流程見[使用手冊](https://github.com/Winston774/air-mouse/blob/v0.1.0/docs/usage.zh-TW.md)。

## 此版內容

- 轉動控制游標、點按左鍵與連續點按雙擊。
- 方向校正、點按門檻測試、速度與靈敏度設定。
- 資料過期停止移動、可選藍牙自動重連。
- 本機診斷記錄，無雲端服務或第三方套件依賴。
- MIT 授權、繁中／英文首頁、開發文件與 GitHub 建置流程。

## 已知範圍

目前以開蓋操作為範圍。既有硬體研究集中在 AirPods Pro 第一代；其他型號、Intel Mac、長時間穩定性尚未完整驗證，合蓋仍無可靠重現流程。此版沒有右鍵、捲動或獨立拖放手勢。

點按校正若中途斷線，仍可能產生門檻建議；請確認全程有動作資料，斷線後重新測試。暫停控制仍會讀取動作與寫入本機記錄；退出 App 才停止。

此次公開整理保留第一版的核心控制邏輯；建置、封裝與文件檢查不代表重新完成實體耳機端到端測試。

[專案首頁](https://github.com/Winston774/air-mouse) · [完整版本紀錄](https://github.com/Winston774/air-mouse/blob/v0.1.0/CHANGELOG.md) · [回報問題](https://github.com/Winston774/air-mouse/issues)
