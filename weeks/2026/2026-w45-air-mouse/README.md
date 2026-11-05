# 2026-W45｜Air Mouse：把 AirPods 充電盒變成 Mac 空中滑鼠

用打開蓋子的 AirPods 充電盒控制游標，停穩後輕敲執行左鍵或雙擊。這是原生 Swift 選單列工具，動作處理在 Mac 本機完成。本週 `0.1.0 Preview`，預估練習 60 分鐘。

## 使用條件與重要限制

- Apple Silicon Mac、macOS 14 或更新版本，以及可提供動作資料的 AirPods。macOS 14 是建置下限，並不代表所有版本都已實測。
- 來源的歷史感測測試使用 AirPods Pro 第一代；其他型號、長時間控制及斷線恢復尚未廣泛驗證。完整邊界見[相容性文件](completed/air-mouse/docs/compatibility.md)。
- 雙耳留在充電盒內、盒蓋打開，並關閉「自動耳朵偵測」。先保留可使用的實體滑鼠或觸控板。
- 需要動作與健身、藍牙及輔助使用權限。輔助使用允許 App 移動游標並送出點擊，請自行確認程式來源後授權。
- 按 `Control + Option + M` 暫停游標控制；**暫停期間仍會讀取動作資料並寫本機記錄**。選單「結束」才會停止 App。

## 安裝與第一次練習

1. 到來源的 [GitHub Releases](https://github.com/Winston774/air-mouse/releases/latest) 查看可用的 macOS arm64 ZIP。下載前核對發布版本與 SHA-256；也可在 Mac 使用本週包的[原始碼](completed/air-mouse/README.md)自行建置。
2. 解壓後將 `Air Mouse.app` 放入「應用程式」。來源標示該版本使用 ad-hoc 簽章，尚未經 Apple 公證。若系統阻擋，先確認下載來源，再參考來源 README 連結的 Apple 指引。若系統明確指出惡意內容或檔案損毀，停止開啟並查證。
3. 開啟選單列 App，依提示授權；連接 AirPods，兩耳放入盒內、保持開蓋並關閉自動耳朵偵測。
4. 依校正視窗保持盒子前端朝螢幕、拿穩，再依指示向上抬並停住；來源耳切換時可能需要重新校正。
5. 使用選單「點按校正測試」，在安全位置練習移動、單擊與雙擊；隨時用 `⌃⌥M` 暫停控制。結束練習時選「結束」。

本週包包含程式原始碼與文件，並未另附 macOS 已編譯 App。學員應確認來源 Release 實際存在及適用性；此工作環境為 Windows，沒有執行 Mac 安裝或耳機操作。

## 成果證據與通過標準

使用自有裝置，在不影響工作的重要視窗外練習。記錄裝置型號、macOS 版本、是否收到感測資料、校正結果，以及游標、單擊、雙擊和暫停是否符合預期。若無資料，先確認開蓋、耳朵偵測及藍牙連線，再依[使用指南](completed/air-mouse/docs/usage.zh-TW.md)重試。不要公開藍牙位址或完整日誌。

## 本機資料與授權

App 預設寫入 `~/Library/Logs/AirPodsAirMouse`；設定保存優先重連的藍牙位址。記錄不自動清除，詳細 `--raw` 模式會增加逐筆感測資料。分享前先檢查日誌與設定，詳見[隱私說明](completed/air-mouse/docs/privacy.md)。

來源採 MIT 授權；本週保留來源 [LICENSE](completed/air-mouse/LICENSE)，不額外附加 Toolspack 根目錄授權檔。本週的[驗證紀錄](docs/verification.md)區分原作者先前測試與本次實際執行範圍。
