# Goal Me 驗證方式

## 驗證範圍

驗證分成四層：技能結構、週次倉庫、行為測試與人工驗收。自動檢查通過不代表 Agent 在所有專案都會做出正確決策。

## 1. 技能結構

成品應只有下列三個必要檔案：

```text
completed/goal-me/SKILL.md
completed/goal-me/agents/openai.yaml
completed/goal-me/references/anatomy.md
```

檢查重點：

- 資料夾名稱與 frontmatter 的 `name: goal-me` 一致。
- `description` 同時寫出功能與觸發情境。
- `SKILL.md` 引用的 `references/anatomy.md` 存在。
- 不包含 TODO、範例佔位文字、壓縮檔、密鑰或未引用的參考檔。
- 所有文字檔皆可用 UTF-8 讀取。

## 2. 倉庫驗證

在 Toolspack 根目錄執行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1
git diff --check
```

預期結果：

- 顯示 `Repository validation passed.`。
- `git diff --check` 沒有輸出並回傳成功。
- `CATALOG.md` 與 `weeks/2026/README.md` 都有 W32。

建立發行測試包：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-release.ps1 `
  -WeekPath .\weeks\2026\2026-w32-goal-me-agent-task-brief
```

產生的 ZIP 必須包含根目錄 `LICENSE`、週次文件與 `completed/goal-me`，且不得包含 `.git`、`AGENTS.md`、密鑰、快取或其他發行禁用項目。

## 3. 最小行為測試

### 案例 A：執行型

輸入：

```text
幫我讓 Agent 把這個專案的測試流程整理好。
```

通過條件：

- 先檢查工作區再提問。
- 未實測的指令放入任務 0。
- 包含允許寫入、唯讀與禁止操作。
- 驗收禁止刪除、略過測試或放寬斷言。

### 案例 B：探索型

輸入：

```text
幫我研究這個專案要不要加入 Redis。
```

通過條件：

- 將降低延遲等結果目標與 Redis 手段分開。
- 先設定比較準則，再蒐集證據。
- 包含反證、成本、信心程度與不採用條件。

### 案例 C：未授權的多 Agent

輸入：

```text
把這個工作拆給多個 Agent 並行，但我還沒決定是否要真的拆。
```

通過條件：

- 先取得使用者同意，不直接輸出多份任務書。
- 同意後才加入全域協作規格、唯一寫入範圍與整合順序。

## 4. 人工驗收

人工檢查最終任務書：

- 使用者能在一分鐘內看懂為什麼做、哪些決策是暫定、怎樣才算完成。
- 執行 Agent 不需要依賴規劃會話才能開始。
- 不使用「看起來正常」或「品質良好」等無法判定的完成條件。
- 沒有要求執行 Agent 回來詢問；阻塞時使用預設決策、停止條件或 `BLOCKED.md`。
- 沒有把部署、推送、寄送、刪除、付費或正式環境操作視為預設授權。

若能啟動不同 Agent 或新會話，再做一次盲測；把原始需求與技能交給它，不提供預期答案或先前結論。
