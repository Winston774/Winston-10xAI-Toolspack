# 來源、版本與封裝範圍

- 來源：使用者指定 releases 目錄中的 `source-led-video-v1.0.0.zip` 及相鄰 manifest。
- 來源版本：`1.0.0`，來源標示日期 `2026-10-08`。
- ZIP 大小：84,156 bytes。
- ZIP SHA-256：`ffa2783c1bbbb180cc84ca892d1630a2d04ac1b9992d5e934d29fd928af5efd2`。
- v1.0曾保留 `completed/source-led-video/` 內 **27 個原始檔案，逐檔位元組不變**。v1.1包含明確的入口/参考/版本修訂與新增adapter，不再宣稱現行全部檔案等於原ZIP。七份參考文件、十個 Python 檔（含引擎）、六份模板及其餘入口／版本／顯示資訊已全數閱讀。
- 原 manifest 保存在 [source-manifest.json](source-manifest.json)，供核對來源檔案大小與 SHA-256。
- 另增 README、lesson、metadata 及 docs，將技能轉為可操作的學員內容。未帶入父專案 QA、私有 Plugin、影音、模型或執行環境。

原始 ZIP 保留在來源目錄，未修改。本週 ZIP 使用 Toolspack 的 README／lesson／metadata／completed／docs 結構，內含學员教材，因此與原始技能 ZIP 的大小及雜湊不同。

來源未附授權檔；metadata 記為未指定，打包不附倉庫根目錄 LICENSE，也不新增 LICENSE／NOTICE。這不更動其他週次的授權檔，也不解除外部相依程式、字型與素材的授權義務。

## v1.1 修訂範圍

2026-10-09新增editorial motion builder/engine、明確本機render wrapper、聲線與主題設定範本／参考。原paper Python核心不改；source-manifest.json仍是原v1.0 ZIP的歷史證據。現行技能檔案大小與SHA另存revision-manifest.json，與來源快照分開。

只共享方法、程式、可編輯文字模板和去識別化驗證摘要，不含真實來源影音/完整逐字稿/字幕資料/私人參考聲音/模型/本機路徑或診斷音訊。新增程式在本機依顯式input產生的media/QA/字型subset需保存在自己當集，勿回傳Skill分享包。

授權欄位與include_root_license=false保持原邊界，不將倉庫根MIT套到未指定授權的來源技能，不新增LICENSE/NOTICE。
