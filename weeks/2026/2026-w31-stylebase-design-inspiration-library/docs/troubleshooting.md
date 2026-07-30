# 疑難排解

## 啟動前最小檢查

```powershell
node --version
npm.cmd run validate
```

需要 Node.js 24 或更新版本。

## 瀏覽器顯示無法連線

1. 確認啟動視窗仍在運行。
2. 確認網址是 `http://127.0.0.1:4177`。
3. 若變更過 Port，檢查 `.env` 的 `STYLEBASE_PORT`。
4. 用 PowerShell 檢查：

```powershell
Get-NetTCPConnection -LocalPort 4177 -State Listen
```

若沒有 listener，先處理啟動視窗中的錯誤；不要先修改路由或把服務公開到區域網路。

## Node 版本不足

症狀可能是找不到 `node:sqlite` 或無法解析 `--env-file-if-exists`。

```powershell
node --version
```

升級到 Node.js 24 LTS／Current 後，重新開啟 PowerShell。

## Codex 未就緒

```powershell
codex --version
codex login status
```

未安裝：

```powershell
npm.cmd install -g @openai/codex
```

未登入：

```powershell
codex login
```

如果 `codex` 不在 PATH，可複製 `.env.example` 為 `.env`，設定：

```text
STYLEBASE_CODEX_EXECUTABLE=C:\完整路徑\codex.exe
```

## 工作停在「需要設定」

1. 修正 Codex 安裝或登入。
2. 回到 Stylebase 按「重試待設定」。
3. 不需要重新匯入圖片。

## 分析失敗或超時

1. 先用一張小型、清楚、非敏感的 JPG。
2. 確認 Codex CLI 能在終端正常啟動。
3. 若錯誤提到額度或速率限制，等待後只重試該工作。
4. 若錯誤提到 CLI 參數，更新 Codex CLI，再執行測試。
5. 保留錯誤訊息、Node 版本、Codex 版本與重現步驟。

## 原始圖片遺失

Stylebase 不會刪除或移動原圖。若素材顯示遺失：

1. 將同一檔案放回原路徑，或重新放入 `library/inbox`。
2. 按「重新掃描」。
3. 系統會依 SHA-256 對應既有素材。

## SQLite ExperimentalWarning

Node.js 可能仍將 `node:sqlite` 標記為 Experimental。警告本身不代表資料損壞。執行：

```powershell
npm.cmd test
```

確認 SQLite、JSON1 與 FTS5 所需功能通過。

## Port 已被使用

在 `.env` 指定另一個只供本機使用的 Port：

```text
STYLEBASE_PORT=4178
```

不要將 host 改成 `0.0.0.0`。目前專案沒有遠端存取所需的身份驗證與權限層。

## 回報 Issue 時

請提供：

- Windows、Node.js、Codex CLI 版本。
- `npm.cmd run validate` 結果。
- 最短重現步驟。
- 已移除圖片、Token、帳號與私人路徑的錯誤訊息。

不要上傳 `.env`、SQLite 或 `library/inbox`。
