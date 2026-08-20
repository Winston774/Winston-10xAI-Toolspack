# Kinetic Character Reveal 驗證方式

## 驗證分層

本週驗證分成技能結構、Prompt 合約、發行包與人工行為四層。結構與腳本通過，仍不代表任何影片模型都能完整遵守 Prompt。

## 1. 技能結構

在技能目錄執行：

```powershell
$env:PYTHONUTF8='1'
python C:\path\to\skill-creator\scripts\quick_validate.py .
```

預期顯示：

```text
Skill is valid!
```

另需檢查：

- 資料夾名稱與 frontmatter `name` 都是 `kinetic-character-reveal`。
- `SKILL.md` 引用的四份 reference 都存在。
- `agents/openai.yaml` 具有 `display_name`、25–64 字元的 `short_description` 與包含 `$kinetic-character-reveal` 的 `default_prompt`。
- `FILES.txt` 與實際發行檔案一致。
- 不含 API Key、Token、Cookie、私人路徑或未公開素材。

## 2. Prompt 合約

```powershell
python .\scripts\validate_prompt.py .\examples\original-ao-prompt.txt
python .\scripts\validate_prompt.py .\examples\example-output.md
```

兩次都應顯示：

```text
Cuts detected: 13
Timeline detected: 0.00-15.00s
PASS
```

驗證器只使用 Python 標準函式庫。

## 3. 觸發評估資料

`evals/trigger-prompts.csv` 收錄 8 個正向案例與 4 個負向案例。CSV 結構可自動檢查；實際是否正確觸發需要在目標 Agent 環境執行，不能由靜態掃描替代。

人工抽查至少包含：

- 正向：Style DNA 抽取、SERIES 變體、時間軸 AUDIT。
- 負向：三分鐘對白短片、靜態角色海報、訪談剪輯腳本。

## 4. Toolspack 與 ZIP

在 Toolspack 根目錄執行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-release.ps1 `
  -WeekPath .\weeks\2026\2026-w34-kinetic-character-reveal
git diff --check
```

ZIP 必須包含根目錄 `LICENSE`、週次教材與 `completed/kinetic-character-reveal/`；不得包含 `.git`、`AGENTS.md`、`SKOOL-POST.md`、快取、憑證或另一個 ZIP。

## 5. 人工驗收邊界

本次自動驗證涵蓋技能結構、兩份範例 Prompt、Python 語法、CSV 結構、Toolspack 結構與 ZIP 內容。

以下項目需在學員環境另行執行：

- 目標 Agent 的實際自動觸發準確度。
- 不同影片模型對角色一致性、圖形物理互動與鏡頭時間的遵循程度。
- 影片品質、點數成本、生成時間與商業使用資格。
- 公開角色、品牌、音樂、參考圖片與真人肖像的權利確認。
