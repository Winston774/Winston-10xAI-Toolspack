# 驗證紀錄與證據邊界

本文件區分「本輪實際執行」與「尚未驗收」。它不把結構檢查、抽樣畫面、開發機環境或歷史紀錄擴大成完整影音品質保證。

## 來源與封裝前檢查

| 項目 | 本輪結果 |
|---|---|
| 來源 Git 狀態 | 製作者本機工作樹乾淨，來源 HEAD 為 `3c458b19fed68f75265fb2dcddcea845f6f31090`。 |
| 來源範圍 | 以 114 個 Git 追蹤檔案建立公開包基底；核心程式碼、測試與必要設定保留，公開包另對少數文件、範例與清理腳本做去識別化／安全加固，清單見[來源範圍](source-snapshot.md)。 |
| 秘密資料盤點 | 沒有追蹤的 `.env` 或常見 API／GitHub／OpenAI 私鑰格式；追蹤的 `.env.example` 只有 KIE 變數佔位文字。 |
| 排除項目 | `.env`、`.venv`、`.local-editor`、`.editor-test-data`、實際媒體、SQLite、模型、快取、驗證產物與瀏覽器截圖均未放入來源 archive。 |
| 靜態 MCP registry | 以目前來源 Python 匯入 `local_editor.mcp.TOOLS`，得到 25 個工具。 |

## 自動測試（本輪實際執行）

| 指令 | 結果 | 範圍 |
|---|---|---|
| `.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -q` | 通過：135 tests，15.811 秒，`OK (skipped=26)` | Python 單元／整合測試；跳過項目仍屬未執行範圍。 |
| `node --test tests/editor_frontend.test.mjs tests/playhead_edit.test.mjs tests/timeline_gestures.test.mjs tests/timeline_scrub.test.mjs tests/transcript_edit.test.mjs tests/waveform.test.mjs` | 通過：23 passed、0 failed | 前端與時間軸測試檔案。 |
| `agent-video doctor` | 此打包主機顯示 FFmpeg、FFprobe、WhisperX 與 yt-dlp 可用 | 僅代表打包主機，不能保證學員電腦。 |

## 隔離瀏覽器驗證（本輪實際執行）

以全新的外部資料目錄啟動 `python -m local_editor serve --port 8337`，沒有讀取來源既有 `.local-editor`。完成以下流程：

1. 首頁成功載入，顯示「檢查本機環境」與「建立新專案」。
2. 開啟建立專案對話框，輸入 `W37 介面驗證專案`。
3. 成功進入空白工作台，可見素材、智能剪口播、字幕、音訊、文字、調色、Agent、環境與時間軸介面。

截圖只留在打包工作區的外部驗證資料夾，未放入 Git、ZIP 或學員包。驗證服務和瀏覽器工作階段已在完成後關閉。

## 本輪未通過／未執行範圍

| 項目 | 狀態與原因 |
|---|---|
| `scripts/verify-local-asr.ps1` | **未通過為有效 ASR 證據**：測試語音程式找到中文 Windows voice 後，該主機的安全性設定拒絕選取語音。這是主機環境阻塞，沒有被包裝成成功。 |
| 實際 Codex／Claude Code 宿主 MCP | 未於本輪以真實宿主完成端到端寫入流程。 |
| KIE／Seedance、YouTube、yt-dlp | 未呼叫，避免未授權的外部傳輸、費用或內容取得。 |
| 授權真人長片 | 未匯入；沒有連續聲畫、字幕語意、逐切點黑閃或最終 MP4 匯出驗收。 |
| 學員乾淨機安裝 | 尚待不同 Windows 環境重現。 |

## 發布前包裝驗證（本輪實際執行）

| 項目 | 結果 |
|---|---|
| `npm run validate` | 通過：零依賴 student-runtime wrapper 檢查 117 個來源檔案，會略過學員自己的執行期資料。 |
| `npm test` | 通過：同一個 student-runtime 靜態檢查。 |
| `npm run validate:release` | 通過：乾淨 checkout 的 release mode 檢查 119 個檔案；拒絕 `.env` 與執行期目錄，並限制 `projects/`、`outputs/` 只能保留 `.gitkeep` scaffold。 |
| `scripts/validate-repo.ps1` | 通過：Toolspack 結構、metadata、文件、package scripts、禁止檔案與常見 secret pattern 檢查。 |
| 來源保真 | 通過：114 個來源檔在包內都有對應；其中 99 個檔與來源 Git 正規化 blob 一致，15 個公開化差異只落在[來源範圍](source-snapshot.md)明列的文件、範例、MCP UI path、prune 安全防護與檔尾 whitespace 正規化。 |
| 額外 secret／禁止檔掃描 | 通過：沒有 `.env`、私鑰、ZIP、log、`SKOOL-POST.md` 或常見 token pattern。 |

GitHub CI、ZIP 清單／雜湊和 Release 新鮮下載驗證會在 PR 與發布階段另行執行。它們只驗證檔案完整性與發布流程；不替代上表列出的媒體品質和宿主驗收。
