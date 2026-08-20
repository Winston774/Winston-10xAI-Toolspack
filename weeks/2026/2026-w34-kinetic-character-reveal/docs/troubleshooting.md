# 疑難排解

## Skill 沒有出現在清單

確認資料夾結構為：

```text
kinetic-character-reveal/
├── SKILL.md
├── agents/openai.yaml
├── assets/
├── references/
└── scripts/
```

不要多包一層同名資料夾。重新啟動 Agent 工具後，用 `$kinetic-character-reveal` 明確呼叫。

## `quick_validate.py` 顯示編碼錯誤

Windows PowerShell 先設定：

```powershell
$env:PYTHONUTF8='1'
```

確認 Markdown、YAML、CSV 與 Prompt 都儲存為 UTF-8。

## Prompt Validator 找不到 CUT

每一鏡都要使用：

```text
CUT 01 | 0.00-1.00s — description
```

編號需連續，分隔符可用一般減號、en dash 或 em dash。

## 時間軸出現 gap 或 overlap

逐段確認前一個結尾值等於下一個開頭值。預設最後一鏡必須在 15.00 秒結束。若你有意使用不同規格，傳入 `--cuts` 與 `--duration`。

## 角色在不同鏡頭變形

- 將完整角色聖經放在 cut list 前。
- 寫清楚服裝構造、材質、配件與色彩位置。
- 移除互相矛盾的形容。
- 先生成身份特寫與英雄鏡頭，確認角色基準。

## Motion graphics 被場景搶走

降低寫實場景描述，重申 graphic-to-character ratio、平面色場、字體物理行為與每鏡唯一視覺命題。

## 影片模型無法處理 13 cuts

依 cut functions 分成 3–4 段生成，再於剪輯軟體依原時間軸組合。每段都重複角色鎖與色盤鎖，並保留前後 handoff frame 作為接點。

## 回報問題時提供

- Agent／模型名稱與版本。
- 使用模式與完整 Brief。
- 驗證器輸出。
- 最小可重現 Prompt。
- 哪一個 cut、角色細節或約束失敗。

公開回報前移除客戶名稱、未公開品牌、真人資料、API Key 與付費平台帳號資訊。
