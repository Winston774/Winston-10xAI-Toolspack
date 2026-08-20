# 教學講義：把角色影片 Prompt 變成可維護的視覺系統

## 學習目標

完成本週練習後，你會理解：

1. 如何把參考 Prompt 拆成交付規格、角色鎖、視覺語彙、動作文法與鏡頭功能。
2. 如何用 HARD／CONTROLLED／FREE 控制創意變體。
3. 如何讓 13 個 cuts 形成清楚的 reveal arc。
4. 如何用角色與圖形的物理互動維持 motion-graphics 主導。
5. 如何用腳本驗證 cut 數與時間軸，並保留人工視覺驗收。

## 核心 Workflow

```text
合法角色設定
  → EXTRACT Style DNA
  → 建立 Binding Map
  → 鎖定角色與五色色盤
  → 配置 13 個 cut functions
  → 建立跨鏡頭 handoff
  → 套用負面約束
  → 腳本驗證
  → AUDIT 人工稽核
  → 小額生成測試
```

## 模組拆解

| 模組 | 目的 | 對應檔案 |
|---|---|---|
| Skill Router | 選擇 EXTRACT／FAITHFUL／SERIES／REMIX／AUDIT | `SKILL.md` |
| Style DNA | 定義構圖、色彩、字體、動態與攝影語彙 | `references/style-dna.md` |
| Constraint Matrix | 分配變化預算，防止意外漂移 | `references/constraint-matrix.md` |
| Cut Blueprint | 固定 13 個鏡頭功能與時間 | `references/cut-blueprint.md` |
| Input Brief | 將零散需求正規化 | `assets/input-brief.yaml` |
| Output Contract | 保持交付格式完整 | `assets/output-template.md` |
| Validator | 驗證 cut、時間軸與必要聲明 | `scripts/validate_prompt.py` |

## 第一階段：抽取 Style DNA

先讀 `examples/original-ao-prompt.txt`，請技能使用 EXTRACT 模式。輸出至少回答：

- 交付契約是什麼？
- 哪些角色細節必須鎖定？
- Motion graphics 與角色動作各占多少？
- 有哪些反覆出現的圖形與字體？
- 哪些轉場具有跨鏡頭接力？
- 開場、高潮與結尾各自負責什麼？

高密度 Prompt 的重點在於「規則之間如何合作」。只摘錄形容詞，後續變體很容易只剩表面相似。

## 第二階段：建立 Binding Map

### HARD

數值契約、角色身份、時間軸、動態性格與結尾功能。這些條件一旦改變，作品會失去同系列辨識度或驗收能力。

### CONTROLLED

角色、色盤、品牌 token、動作家族、主幾何與文字詞庫。可以更換，但同一變數的所有依賴位置都要同步更新。

### FREE

局部攝影角度、UI 刻度、粒子方向、海報版式與同功能的 action verb。這一層提供創意空間。

實作時先列出變更軸。SERIES 練習建議一次更換角色、色盤、動作家族與主 motif，並保留 13-cut arc、15 秒、80/20 與硬節拍文法。

## 第三階段：先鎖角色，再寫鏡頭

角色聖經應包含：

- 臉型、五官比例、眼睛、膚色與年齡區間。
- 髮長、輪廓、質地、顏色與瀏海。
- 身體比例。
- 每件服裝的版型、材質、拉鍊、口袋、標籤、配件與鞋子。
- 五色色盤如何配置到角色與圖形系統。

角色細節寫在 cut list 前方，並加入 immutable lock。每鏡重寫不同版本的角色描述會增加漂移風險。

## 第四階段：建立 13-Cut Arc

13 個 cut 依序負責：

1. 圖形點火。
2. 局部身份揭露。
3. 全身高速進場。
4. 動作拆解。
5. 空中主秀。
6. 字體物理互動。
7. 旋轉回聲。
8. 個性詞連擊。
9. Freeze target。
10. Release drive。
11. Campaign posters。
12. Hero climax。
13. Identity card。

每鏡保持一個主要動作與一個主要圖形事件。前一鏡最後的圓、碎片、條帶、鎖定框或前景物件，應成為下一鏡的入口。

## 第五階段：驗證與修復

把最終 Prompt 儲存為 UTF-8，再執行：

```powershell
python .\scripts\validate_prompt.py .\prompt.txt
```

自動驗證可以確認：

- cut 數量與編號。
- 0.00–15.00 秒範圍。
- gap、overlap 與非正時長。
- 畫幅、fps 與角色鎖定語句。
- 基本色盤、動態字體、節拍、freeze／release 語言。

人工驗收仍要確認：

- 角色細節是否自相矛盾。
- 每鏡視覺命題是否可讀。
- 圖形與角色有沒有真正互動。
- recurring motif 是否持續進化。
- Hero climax 與 identity card 是否有明確差異。
- 生成模型實際上能否遵守 Prompt。

## Agent Workflow

推薦把工作拆成三個連續角色：

1. **Extractor**：只整理 Style DNA 與 Binding Map。
2. **Prompt Builder**：依確認後的約束產生變體。
3. **Auditor**：使用原始 Brief、最終 Prompt 與驗證輸出做獨立稽核。

這三個角色可以使用同一 Agent 的不同階段。需要多 Agent 時，再指定唯一 Prompt 擁有者，避免多人同時重寫時間軸。

## Token 與生成成本優化

- 先保存 Style DNA 與 Binding Map，後續變體只傳角色與變更軸。
- 使用 `input-brief.yaml` 取代長篇自然語言來回確認。
- Prompt Builder 完成後先跑本機驗證器，再交給模型 AUDIT。
- 影片模型先測 Cut 02、06、12，分別驗證身份、圖形互動與高潮。
- 先使用低解析、短預覽或單鏡測試，再投入完整生成點數。

## 延伸挑戰

- 建立 9:16、12-cut、18 秒 REMIX，並使用參數調整驗證器。
- 將同一角色做三個 SERIES 版本，每次只改一個概念軸。
- 為生成結果建立 shot-by-shot continuity scorecard。
- 將驗證器擴充為 JSON 報告，供 CI 或 Agent Workflow 讀取。
