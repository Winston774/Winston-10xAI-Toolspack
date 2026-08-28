# Mastery Loop 驗證方式

## 發行來源邊界

- 來源快照：`mastery-loop` Git commit `038b14406f7afb872d6efc1f78a2ecbebed5b9cd`。
- 發行包只採用該 commit 的 17 個 tracked files。
- 來源中的 `.git/` 與未追蹤 `mastery-sessions/` 不在發行包內。
- `completed/mastery-loop/` 的 17 個檔案與來源 commit 逐檔 Git blob hash 相符。

## 1. Python 與技能結構

在 `completed/mastery-loop/` 執行：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest discover -s tests -v
python C:\path\to\skill-creator\scripts\quick_validate.py .
git diff --check
```

本次發行驗證結果：

- 四個 Python scripts 語法編譯通過。
- `quick_validate.py`：`Skill is valid!`
- `unittest`：90 tests 通過，1 個 Windows symlink 權限案例依測試設計跳過。
- 介面 anti-pattern 靜態掃描：0 finding。
- 追蹤檔敏感字串掃描未發現 API Key、Cookie、密碼、個人資料或私人工作階段。

跳過的 symlink 測試需要 Windows「建立符號連結」權限；其他路徑 containment、traversal 與非法 evidence surface 測試均已執行。若部署環境允許 symlink，仍應在該環境重跑完整測試。

## 2. 完整流程驗證

本次由獨立 Agent 在全新隔離工作目錄完成 forward test：

- Scope：3 個領域。
- Assessment：12 個獨立 kernels，6/12，三區皆為 `mixed_signal`；兩個預設隱藏 misconception 均被報告捕捉。
- Learning：每區 7 個 slices，共 21 個；3 個 checkpoints 完成，其中 2 個刻意答錯仍可續跑。
- Review：11/11 完成；6 個 gaps corrected、2 個 residual、1 個 newly exposed。
- Delayed review：3 個無提示項目，固定到期日為 `2026-08-31`。
- Reliability：相同選擇 retry 維持單一紀錄；conflicting answer 回傳 HTTP 409。
- Evidence：所有同場 Review 記錄皆為 `feedback_exposed`，沒有宣稱 Transfer。
- Legacy：version 2 spec 的 validate、render 與 stable-ID concealment 通過。

測試另外確認 Assessment、Learning、Review 三個 public CLI phase 都回傳 `complete:true`，並在重新產生報告時保持 completion anchor、delayed queue 與既有報告不變。完整流程證據保存在隔離測試目錄，沒有複製進學員 ZIP。

## 3. Toolspack 與 ZIP

在 Toolspack 根目錄執行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-release.ps1 `
  -WeekPath .\weeks\2026\2026-w35-mastery-loop
git diff --check
```

ZIP 必須包含根目錄 `LICENSE`、本週教材與 `completed/mastery-loop/`；不得包含 `.git`、`mastery-sessions`、`AGENTS.md`、`SKOOL-POST.md`、`__pycache__`、憑證或另一個 ZIP。

## 4. 人工驗收邊界

本次自動驗證涵蓋資料結構、狀態轉移、不可變寫入、retry、路徑防護、答案防洩漏、phase reports、Learning gate、Review novelty 的確定性規則與發行包內容。

以下項目需要在實際學習主題與目標 Agent 環境另行驗證：

- 題目與 benchmark 的領域正確性、時效性與引用品質。
- 新情境在語意層級是否真正不同；字串相似度檢查只能攔截部分近似案例。
- 學員是否能在真實模擬或產物中完成端到端任務。
- 三天後 delayed review 的真實保留表現。
- 真人 GUI 點擊、螢幕閱讀器、響應式版面與視覺回歸；本次使用真實 loopback HTTP 流程驗證單一 base URL 與頁面狀態。
- 正式證照、身份確認與受監管領域的治理要求。
