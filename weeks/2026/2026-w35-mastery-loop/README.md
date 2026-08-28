# 2026-W35：Mastery Loop — 可驗證的點擊式精熟學習系統

> 把「我想學會」轉成一個有範圍、有證據、可續跑的評估 → 學習 → 新情境複習循環。

## 本週成果

本週提供 `mastery-loop v1.0.0`。安裝後，Agent 會先給三個可點擊目標，再依確認的任務建立完整批次評估、證據連結學習地圖與新情境複習。每次作答會立即保存，重新整理或重開後可從既有紀錄續跑。

主要能力：

- 以 10–20 題、3–6 個領域建立第一輪能力證據。
- 每個選項都補充邊界、前提或取捨，作答前不洩漏答案。
- 依實際答題缺口，為每個領域建立 5–10 個循序 Learning Slices。
- 每個領域包含一個 formative checkpoint，錯誤會保存並進入後續複習。
- 以 8–15 題全新情境做整合 Review，保留 Assessment → Learning → Review 的證據鏈。
- 將殘留缺口排入三天後的無提示複習。
- 使用本機 loopback 頁面、不可變回應與可恢復 checkpoint 保存學習狀態。

成品位置：[`completed/mastery-loop/`](completed/mastery-loop/)

延伸文件：

- [完整教學講義](lesson.md)
- [驗證方式與邊界](docs/verification.md)
- [資料、隱私與安全](docs/privacy-and-security.md)
- [疑難排解](docs/troubleshooting.md)

## 基本資料

- 類型：AI Skill
- 難度：進階
- 預估時間：安裝與設定約 15 分鐘；最小完整循環約 3–5 小時，可分段完成
- 支援平台：Windows、macOS、Linux；Codex 或可讀取 Agent Skills 的 AI Agent
- 需求：Python 3.10 以上；核心腳本只使用 Python 標準函式庫
- Skill 版本：`1.0.0`
- 本週狀態：`Stable`
- API Key／付費服務：技能本身不需要；若學習主題要求即時研究，查證工具可能另有帳號或費用

## 安裝與開始

1. 從本週 GitHub Release 下載 `2026-w35-mastery-loop.zip` 並解壓縮。
2. 找到 `completed/mastery-loop`。
3. 將整個資料夾複製到：
   - Windows：`%USERPROFILE%\.codex\skills\mastery-loop`
   - macOS／Linux：`~/.codex/skills/mastery-loop`
   - 共用 Agent Skills 目錄：`~/.agents/skills/mastery-loop`
4. 重新啟動 Agent 工具，確認 `Mastery Loop` 出現在可用技能清單。
5. 用一句話明確呼叫技能：

```text
使用 $mastery-loop，幫我建立一個「能規劃、委派、驗收多 Agent Workflow」的完整學習循環。
```

Agent 會先呈現三個可點擊目標：端到端交付、診斷改進、複習教學。選定後再確認範圍、評估依據與排除項目。

新循環一律使用 version 3。`click_choice_ui.py` 只用於前置點擊確認，或續跑歷史 version 1／2 紀錄。

## 核心 Workflow

```text
三個目標選項
  → 確認可觀察成果與知識邊界
  → 10–20 題 Assessment
  → Assessment Report
  → 3–6 領域 Learning Map
  → 每領域 5–10 Slices + 1 Checkpoint
  → 8–15 題 New-Scenario Review
  → Comparison Report
  → 三天後 Delayed Review
```

每個階段在同一個本機瀏覽器分頁完成。Agent 產生規格、驗證規格，再啟動頁面；學員只需點擊選項、提交與前往下一題。

## 本週任務

1. 選一個可以用具體行為驗收的目標，例如「能為一個三任務專案設計 Agent 分工、handoff 與失敗復原」。
2. 從三個目標中點選一個，確認包含範圍、排除項目與證據限制。
3. 完成整批 Assessment，不中途重設分數或刪除錯題。
4. 檢查 Assessment Report：每個缺口都要指回原始題目與知識 kernel。
5. 完成完整 Learning Map 與每個領域 checkpoint。
6. 完成 Review，確認題目使用新情境，沒有複製 Assessment 或教學範例。
7. 保存比較報告與三天後複習排程。

## 成果證據

- 一份已確認的任務範圍：3–6 個領域、包含／排除項目、評估依據與證據限制。
- 完整 `assessment/report.json`，可追溯每個 gap 與 misconception。
- 完整 `learning/report.json`，所有 slices 與 checkpoints 皆有不可變紀錄。
- Review comparison report，分開標示已修正、殘留、整合覆蓋與新發現缺口。
- 三天後 delayed review 的固定 due date 與 kernel 清單。
- 若目標是端到端交付，再提供一份模擬或實作產物；單次點擊正確無法證明完整交付能力。

## 通過標準

- [ ] Skill 可被 Agent 辨識，或 Agent 能完整讀取 `SKILL.md` 與七份 references。
- [ ] 新循環使用 version 3，學員決策優先採用點擊操作。
- [ ] Assessment 有 10–20 題、3–6 個領域、每領域至少 2 題，且每題使用不同 kernel。
- [ ] 作答前的畫面沒有正解、解析、內部 ID、未來題目或提示性選項描述。
- [ ] 每次作答自動且不可變地保存，重新整理可回到正確狀態。
- [ ] 每個領域有 5–10 個 Learning Slices 與恰好 1 個 checkpoint。
- [ ] 每個 proposed gap 都連到至少一個 slice，每個 slice 也能回溯 Assessment 證據。
- [ ] Review 有 8–15 題、涵蓋所有領域，並使用真正的新情境。
- [ ] 最終報告沒有把閱讀、信心或同場提示後答對直接宣稱為 Transfer／Durable。
- [ ] 殘留與新發現缺口已排入三天後的無提示複習。
- [ ] 個人 `mastery-sessions/` 沒有進入 Git、分享 ZIP 或公開 Issue。

## 失敗時的最短路徑

1. Skill 沒觸發：以 `$mastery-loop` 明確呼叫，並確認資料夾沒有多包一層。
2. 無法建立題目：先縮小目標，確保至少有 10 個可由可靠基準判定的知識 kernels。
3. 頁面無法啟動：確認 Python 版本、cycle 路徑與 phase 規格，先執行 `validate`。
4. 顯示 phase lock：關閉舊頁面與舊程序，保留 cycle 資料後再啟動。
5. 提交後斷線：不要重建 cycle；以相同狀態重開，系統會依不可變紀錄復原。
6. Review 無法生成：確認所有 slices 都完成，且每個 area checkpoint 都已有回應。
7. 仍失敗：依[疑難排解](docs/troubleshooting.md)保留錯誤訊息、phase、cycle ID 與最小可重現步驟；分享前移除個人學習內容。

## 版本紀錄

- `v1.0.0 Stable`：version 3 批次 Assessment、證據連結 Learning Map、新情境 Review、不可變狀態、loopback 點擊介面與 90 項自動測試。
