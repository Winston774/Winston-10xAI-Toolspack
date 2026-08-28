# 教學講義：把學習變成可驗證、可恢復的 Agent Workflow

## 學習目標

完成本週練習後，你會理解：

1. 如何先定義可觀察任務，再建立知識與證據邊界。
2. 如何保留第一次作答，避免回饋污染 baseline。
3. 如何將實際缺口轉成有先修順序的 Learning Map。
4. 如何用新情境 Review 區分記住答案與真的會應用。
5. 如何以不可變事件、idempotent retry 與 phase lock 維持可信狀態。

## 核心模型

```text
Goal Contract
  ↓
Independent Assessment Evidence
  ↓
Gap-linked Learning Map
  ↓
Feedback-exposed Checkpoints
  ↓
New-scenario Review Evidence
  ↓
Delayed Uncued Evidence
```

Mastery Loop 將證據分成 `U / F / E / A / T / D`：未評估、脆弱、能解釋、能應用、能遷移、能持久。每次只晉升到現有紀錄直接支持的層級。

## 模組與責任

| 模組 | 責任 | 主要檔案 |
|---|---|---|
| Skill Router | 判斷新循環或 legacy resume，維持點擊優先契約 | `SKILL.md` |
| Workspace Contract | 定義 cycle、phase、spec、response、report 與 lock | `references/workspace-schema.md` |
| Assessment Design | 建立範圍、10–20 題批次與 report | `references/adaptive-interview.md` |
| Learning Design | 由 gap 建立 prerequisite map、slice 與 checkpoint | `references/lesson-design.md` |
| Review Design | 產生新情境、比較報告與 delayed review | `references/review-loop.md` |
| Evidence Model | 控制證據等級、信心與宣稱邊界 | `references/mastery-model.md` |
| State Core | 規格驗證、不可變寫入、報告重建與 phase lock | `scripts/session_core.py` |
| Local UI | 提供 Assessment／Learning／Review 的單分頁點擊流程 | `scripts/mastery_session_ui.py` |

## 第一階段：先定義任務邊界

好的起點要能被外部行為判定。例如：

```text
在不共享憑證的前提下，能把一個三任務專案拆成 Agent 分工、定義 handoff，
並在局部失敗、timeout 與重試時保留一致狀態。
```

接著定義：

- 3–6 個主要領域。
- 包含與排除項目。
- 正確答案的評估依據與來源狀態。
- 最終需要做到解釋、應用、遷移或耐久的哪一層。
- 哪些宣稱仍需要真實模擬、產物或延遲驗證。

當主題缺少可靠答案、範圍不足以建立十個獨立 kernels，或涉及高風險即時資訊時，先縮小或查證後再出題。

## 第二階段：建立乾淨 Assessment

整批題目要在開始前生成並封存：

- 10–20 題、3–6 領域、每領域至少 2 題。
- 每題一個不同 `knowledge_kernel_id`。
- 3–5 個平衡選項，恰好一個有依據的答案。
- 選項副描述只補充邊界、前提、取捨或遺漏條件。
- 每個選項都有提交後才顯示的解析。

提交後先寫入不可變 response，再顯示回饋。報告由 server-side spec 與 response 重建，瀏覽器不負責傳送分數或正確性。

## 第三階段：用缺口建立 Learning Map

每個領域的 slice 數量為：

```text
min(5 + 獨立缺口 kernel 數, 10)
```

每個 slice 都要有先修關係、可觀察學習目標、核心機制、邊界、失敗條件、全新 worked example 與 Assessment lineage。完成閱讀只代表 exposure；每個領域最後的 checkpoint 才提供有限的修正或應用證據。

## 第四階段：用新情境 Review 測應用

Review 題數為：

```text
clamp(Assessment 與 checkpoint 的獨立 gap kernels + 領域數, 8, 15)
```

Review 要保留核心命題，並同時更換角色、限制、產物、題型、選項、干擾項與正解位置。單純換名詞或改寫句子不算新情境。

直接 scoring 的優先順序：

1. 每個有缺口的領域先放最高優先缺口。
2. 其餘 Assessment gaps 依風險排序。
3. 再放 checkpoint gaps。
4. 超出題數上限的 gaps 只能作為 integrated kernels，並保留在 delayed review。

## 本機狀態與 API 架構

```text
Agent 產生並驗證 phase spec
  → Local Runtime 取得 phase lock
  → 127.0.0.1 單分頁 UI
  → POST start / answer / next / checkpoint-answer
  → CSRF + opaque token + 順序驗證
  → atomic write-once record
  → report rebuild + checkpoint resume
```

安全邊界包含：loopback 綁定、CSRF、嚴格 content type、request body 上限、HTML escaping、CSP、clickjacking 防護、路徑 containment、opaque tokens 與 constant-time token comparison。

相同 `request_id` 的重試回傳既有結果；相同題目改送不同答案會拒絕。這讓 timeout 後的 retry 能維持一致狀態。

## Agent Workflow 分工

建議採用單一 cycle owner，並用階段角色降低上下文負擔：

1. **Scope Agent**：定義任務、知識邊界、benchmark 與證據限制。
2. **Assessment Builder**：建立完整題組與解析，通過 spec validator 後封存。
3. **Learning Architect**：從 Assessment Report 建立 gap-linked map。
4. **Review Designer**：建立真正的新情境批次與 lineage。
5. **Evidence Auditor**：檢查宣稱、獨立性、提示暴露與 delayed review。

所有角色只透過已保存的 phase spec、immutable records 與 report handoff。寫入 ownership 保持單一，避免兩個 Agent 同時改動同一 cycle。

## Token 成本優化

- 一開始保存 `cycle.json` 與來源摘要，後續階段只載入需要的 report 與 reference。
- Assessment 一次建立完整 batch，減少逐題重新規劃與規則漂移。
- 每個 slice 只保留支持下一次表現的最小解釋、邊界與範例。
- Review 以 kernel lineage 選題，避免把整份教材重新送入上下文。
- 使用 server-side report 重建，Agent 不需要重算所有歷史畫面。
- 將殘留問題排入 delayed review，避免同一回合無限巢狀追問。

## 延伸挑戰

- 為自己的專業領域建立一份可引用的 benchmark registry。
- 加入一個真實產物評分 rubric，補足 click evidence 的上限。
- 將 delayed review 接到行事曆或任務系統，同時保留 learner authorization。
- 用全新領域做獨立 forward test，確認規則可轉移且沒有偷讀範例答案。
