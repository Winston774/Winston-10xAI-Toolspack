# 來源、保留內容與授權

日期：2026-10-01。來源為使用者指定的「建立 Video Highlights 技能」專案，獨立技能版本 commit：

`54549f86149954d5b66a8378a8a2180d1203c186`

本次逐一讀取並審查 18 個受版本管理的文字檔，包括技能入口、README、歷史驗證、Agent 設定、4 份參考文件、5 支核心 Python 與4 支測試程式；另讀原對話的需求、交付與本機真實範例／雙語合輯驗證說明，區分可重用技能和一次性成果。沒有重新完整觀看、聆聽訪談或合輯。

## 學員副本

completed/video-highlights 保留全部 18 個來源檔。SKILL.md 僅新增既有真實範例的導覽連結，以符合 Toolspack 參考文件可發現性檢查；不改動 Python、量尺、預設值或 Agent 設定。來源 CRLF/LF 可正規化；其餘文字一致。

[source-manifest.json](source-manifest.json) 記錄來源逐檔 SHA-256 與副本的正規化文字 SHA-256。以 UTF-8 讀取、CRLF 轉 LF、移除尾端換行後補一個 LF 計算 normalized_sha256。

排除 .git、dist、output、快取、原片、完整字幕／轉寫、所有成片、模型、字型及本機一次性剪輯腳本。真實範例只保留來源已整理的筆記與原片連結。套件不用相鄰的 Video Understanding 安裝目錄。

## 授權記錄

來源目前未附 LICENSE 或 NOTICE，也未提供可供本次確認的技能授權條款。因此本週 metadata 設為 unspecified，打包時不加入 Toolspack 根目錄 MIT。未新增授權宣告，也未刪除其他週次的授權檔。

公開可讀取與下載不等於授予所有改作、再散布或商用權限；需要這些使用方式時請向權利人確認。FFmpeg、Python、ASR 套件、模型、字型及示例原片各有各自條款，均未隨此包散布。
