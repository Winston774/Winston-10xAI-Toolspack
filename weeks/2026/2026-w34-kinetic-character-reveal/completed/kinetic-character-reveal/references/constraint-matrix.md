# Constraint Matrix

## 變數分級

### HARD — 不可漂移

| 類別 | 綁定內容 | 驗證方式 |
|---|---|---|
| 交付 | 畫幅、fps、總時長、cut 數 | 數值完全一致 |
| 時間軸 | cut 編號連續、無空隙、無重疊 | 起訖時間計算 |
| 角色 | 臉、比例、髮型、服裝、材質、配件、色彩位置 | 每鏡無重新設計 |
| 主從比例 | motion graphics 為主，角色動作為輔 | 全片整體判斷 |
| 運動性格 | fast, hard, percussive, beat-synced | 不得變成柔順慢速 |
| cut 功能 | 13 個功能節點順序 | 不可用隨機動作取代 |
| 品牌收束 | 最後必須是 iconic identity card | 結尾功能明確 |

### CONTROLLED — 可替換，但要成套更新

| 類別 | 可變內容 | 綁定方式 |
|---|---|---|
| 角色 | 新人物、性別呈現、造型、服裝 | 先建立完整新 bible，再全片鎖定 |
| 色盤 | 五種顏色 | 必須定義每色角色並全片重用 |
| 品牌字 | AO、短詞、數字 | 1–4 字母或短詞；不可每鏡換品牌 |
| 動作家族 | 跑酷、滑板、舞蹈、武術等 | 同片維持同一身體語言 |
| 主幾何 | 圓、三角、方框、斜線等 | 至少一個 motif 跨鏡頭進化 |
| 微紋理 | 冰霜、火花、粉塵、像素等 | 顏色與主題一致，不搶主體 |
| 文字詞庫 | 個性詞、口號 | 短、重、全大寫、具物理行為 |

### FREE — 可自由創作

- 每鏡的局部攝影角度
- 次要 UI 刻度配置
- 粒子的具體方向與密度
- 海報 montage 的版式差異
- 特定 action verb，只要保持同一功能與能量
- 局部遮罩、wipe、flash 的具體形式

## 三種變化預算

### Faithful：建議只改 0–15%

可以改：
- 個別字詞
- 同功能的動作替換
- 局部轉場

不應改：
- 角色、色盤、cut 架構、比例、時間

### Series：建議改 30–45%

可以改：
- 角色 bible
- 色盤
- 品牌 token
- 動作家族
- 主 motif

必須保留：
- 13-cut arc
- 15 秒節奏
- 80/20
- 硬節拍 motion grammar
- 物理化字體與圖形互動
- identity-card ending

### Remix：建議改 50–65%

可以改：
- cut 數與時長
- 畫幅
- 動態設計比例
- 更廣的媒材或色盤

仍需保留至少七個核心不變量，詳見 `SKILL.md`。

## 最貼近 AO 參考的硬綁定組合

```text
FORMAT_LOCK = 16:9 + 24fps + exactly 13 cuts + 15.00s
IDENTITY_LOCK = exact face + proportions + hair + outfit + materials + accessories + color placement
DESIGN_RATIO = 80% motion graphics / 20% character action
PALETTE_LOCK = ice blue + cobalt + white + silver-grey + black
GRAPHIC_VOCAB = giant type + hard shapes + split screens + flat fields + barcode + UI ticks + halftone + speed lines + shutter flashes
MOTION_LOCK = fast + hard + percussive + snap-on-beat
INTERACTION_LOCK = character physically changes typography or graphic objects
ARC_LOCK = ignition → identity clue → entrance → escalation → freeze/release → posters → hero landing → identity card
DRIFT_BAN = no redesign + no costume change + no warm palette + no soft cinematic drift + no passive typography
```

## 風格漂移判定

出現以下任三項，應判定已離開原視覺家族：

- motion graphics 低於 60%
- 角色服裝或臉在不同鏡頭改變
- 大量寫實場景取代平面色場
- 字體只作字幕、不參與動作
- 轉場以 dissolve、柔和推拉為主
- 沒有 recurring motif
- cuts 僅是動作清單，沒有功能弧線
- 沒有 freeze/release 或相等的節奏反差
- 沒有 hero climax 與 identity card 的雙段收束
