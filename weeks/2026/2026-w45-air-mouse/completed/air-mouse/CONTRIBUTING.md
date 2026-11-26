# 參與 Air Mouse

感謝你協助改善 Air Mouse。歡迎以繁體中文或英文回報問題、補充硬體相容性、改善文件及提交 Pull Request。

## 回報問題

先閱讀[操作說明](docs/usage.zh-TW.md)與[相容性紀錄](docs/compatibility.md)，並搜尋既有 [Issues](https://github.com/Winston774/air-mouse/issues)。請附上：

- Air Mouse 版本，以及下載安裝或自行建置。
- Mac 晶片、macOS 版本、AirPods 型號與韌體版本。
- 盒蓋狀態、自動耳朵偵測設定、權限、選單顯示的來源耳與 Hz。
- 可重複的步驟、預期結果、實際結果與觀察時間。
- 經過檢查和去識別化的最小記錄片段；請勿上傳完整系統診斷、藍牙位址、序號或個人路徑。

安全漏洞請依 [SECURITY.md](SECURITY.md) 私下回報。

## 開發流程

1. Fork 專案並建立用途清楚的分支。
2. 安裝 Xcode Command Line Tools 或 Xcode，執行 `zsh scripts/check.sh`。
3. 讓修改集中於一個問題；行為變更需同步更新文件與 `CHANGELOG.md`。
4. 執行 `zsh scripts/package.sh`，確認安裝包可正常解壓且簽章完整。
5. 在 Pull Request 說明修改目的、驗證方式與未測項目。

本專案使用 Swift 與 macOS 系統框架，無第三方套件依賴。主要流程與類別見[架構說明](docs/architecture.md)。建置檢查不會啟動 App，也無法取代實體耳機測試。

影響動作、校正、點按、重連或權限的變更，請附上實機環境與結果。若無硬體，請直接標記尚未測試。測試游標控制時，保留可用的觸控板或滑鼠，並確認 `⌃⌥M` 可以暫停。

## 合作方式與授權

請以尊重、具體且可驗證的方式討論問題，避免人身攻擊與公開他人的私人資料。尚無承諾的回覆或修復時限。

提交貢獻時，請確認你有權提供該內容，並同意以本專案的 [MIT License](LICENSE) 發布。若使用 AI 工具協助，仍請自行確認授權、正確性與測試結果；需要時在 Pull Request 說明使用範圍。
