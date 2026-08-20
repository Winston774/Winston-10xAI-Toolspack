# 2026-W34：Kinetic Character Reveal — 13-Cut 動態角色登場提示詞系統

> 把一段高密度角色影片 Prompt 拆成可重複使用、可控制變體、可檢查時間軸的 motion-graphics 視覺系統。

## 本週成果

本週提供 `kinetic-character-reveal v1.0.0`。技能聚焦 15 秒、13-cut、16:9 的動態角色登場片，會先固定角色與視覺規則，再建立逐鏡時間軸、圖形接力、負面約束與驗證摘要。

主要能力：

- 從參考 Prompt 抽取 Style DNA。
- 將變數分成 HARD、CONTROLLED、FREE 三層。
- 支援 EXTRACT、FAITHFUL、SERIES、REMIX、AUDIT 五種模式。
- 建立不可漂移的角色聖經、五色色盤角色與動作家族。
- 產生精確到秒、無缺口、無重疊的 13-cut Prompt。
- 用零依賴 Python 腳本檢查 cut 數、時間軸、fps、畫幅與角色鎖定。

成品位置：[`completed/kinetic-character-reveal/`](completed/kinetic-character-reveal/)

延伸文件：

- [完整教學講義](lesson.md)
- [驗證方式](docs/verification.md)
- [疑難排解](docs/troubleshooting.md)
- [角色、品牌與參考素材權利](docs/content-rights.md)

## 基本資料

- 類型：AI Skill
- 難度：中級
- 預估時間：安裝與第一次使用約 20 分鐘；完整拆解與變體練習約 90 分鐘
- 支援平台：Codex，以及可讀取 Agent Skills 或直接接受 `SKILL.md` 的 AI Agent
- Skill 版本：`1.0.0`
- 本週狀態：`Stable`
- API Key：技能本身不需要；實際影片生成服務可能需要帳號、點數或 API Key

## 安裝與開始

1. 從本週 GitHub Release 下載 `2026-w34-kinetic-character-reveal.zip` 並解壓縮。
2. 找到 `completed/kinetic-character-reveal`。
3. 將整個資料夾複製到：
   - Windows：`%USERPROFILE%\.codex\skills\kinetic-character-reveal`
   - macOS／Linux：`~/.codex/skills/kinetic-character-reveal`
   - 共用 Agent Skills 目錄：`~/.agents/skills/kinetic-character-reveal`
4. 重新啟動 Agent 工具，確認技能出現在可用技能清單。

明確呼叫範例：

```text
使用 $kinetic-character-reveal 的 SERIES 模式，幫我做一支 15 秒、13 cut、動態字體主導的角色登場片。

角色：冷靜的 techwear roller-skater
品牌字：RX
色盤：ultraviolet / magenta / white / silver / black
保留：角色一致性、80/20 視覺比例與固定時間軸
```

若環境無法安裝 Skill，可以直接把 `SKILL.md`、必要的 `references/` 與需求交給 Agent。

## 五種模式怎麼選

| 模式 | 適合情境 | 主要輸出 |
|---|---|---|
| EXTRACT | 先拆解一份參考 Prompt | Style DNA、約束與漂移風險 |
| FAITHFUL | 只替換少量內容 | 高度保留原角色、色盤與鏡頭功能 |
| SERIES | 換角色、色盤、品牌與動作 | 同視覺家族的新版本 |
| REMIX | 想改時長、cut 數或畫幅 | 保留核心動態文法的較大變體 |
| AUDIT | 已有 Prompt，需要檢查或修復 | 時間軸、角色與風格稽核 |

## 本週任務

1. 選擇一個自己有權使用的原創角色或角色設定。
2. 先用 EXTRACT 模式拆解 `examples/original-ao-prompt.txt`。
3. 用 SERIES 模式換成自己的角色、五色色盤、品牌 token 與動作家族。
4. 將最終 Prompt 存成 UTF-8 文字檔。
5. 執行驗證器，修到 PASS：

```powershell
python .\completed\kinetic-character-reveal\scripts\validate_prompt.py .\my-character-prompt.txt
```

6. 再用 AUDIT 模式檢查角色漂移、重複構圖、文字過量與跨鏡頭接力。
7. 若要送進影片模型，先做低成本測試，確認服務條款與素材權利後再投入點數。

## 成果證據

- 一份 Style DNA 與 HARD／CONTROLLED／FREE 約束表。
- 一份完整角色聖經與五色色盤角色分工。
- 一份 13-cut 最終 Prompt。
- 驗證器的 PASS 輸出，顯示 `Cuts detected: 13` 與 `Timeline detected: 0.00-15.00s`。
- 一份變更摘要，列出相較參考內容只改了哪些軸。
- 若公開影片或圖片，附上 AI 生成揭露與角色／品牌權利說明。

## 通過標準

- [ ] 技能可被辨識，或 Agent 能完整讀取技能所需檔案。
- [ ] 最終 Prompt 明確寫出 16:9、24fps、13 cuts、15.00 秒。
- [ ] 角色聖經位於 cut list 前方，且每鏡沒有改髮型、服裝、配件或比例。
- [ ] 13 個 cut 編號連續，時間軸無缺口、無重疊。
- [ ] 動態平面設計與角色動作比例有明確定義。
- [ ] 至少四組跨鏡頭 handoff，且主 motif 會逐步進化。
- [ ] Hero climax 與 identity card 的功能清楚區隔。
- [ ] Python 驗證器回傳 PASS。
- [ ] 公開成果未使用無權使用的真人、角色、品牌、商標、音樂或參考素材。

## 失敗時的最短路徑

1. 技能沒觸發：用 `$kinetic-character-reveal` 明確呼叫。
2. 找不到參考檔：確認整個技能資料夾已複製，未只取出 `SKILL.md`。
3. 驗證器找不到 cuts：每鏡使用 `CUT NN | START-ENDs` 格式。
4. 出現 gap／overlap：從 Cut 01 開始逐段核對前一段結尾與下一段開頭。
5. 角色漂移：把完整角色聖經與 immutable lock 放在所有 cuts 前。
6. 畫面太亂：每一 cut 保留一個主要動作、一個主要圖形事件與一個 handoff。
7. 影片模型無法同時遵守全部條件：先測三個關鍵 cuts，再依模型限制分段生成與剪輯。
8. 仍失敗：依[疑難排解](docs/troubleshooting.md)保留最小 Prompt 與驗證輸出。

## 版本紀錄

- `v1.0.0 Stable`：五種工作模式、13-cut Blueprint、Style DNA、約束矩陣、Prompt 資產、觸發評估案例與零依賴驗證器。
