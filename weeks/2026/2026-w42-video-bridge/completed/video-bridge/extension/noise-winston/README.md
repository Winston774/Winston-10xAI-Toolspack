# Noise Winston — Extension Kit 2.1.0

Chrome 擴充功能專用的介面系統，衍生自 Noise Winston Design System 2.0.0。
目前用於三個外掛：YouTube Outlier（Lab 001）、Gemini 選取翻譯（Lab 002）、影片接力（Lab 003）。

> **Calm structure. Loud signal.** 一張安靜的工作桌，只有下一個關鍵動作亮起。

這個資料夾在三個外掛中必須**逐位元相同**。修改時只改一份，再複製到其他兩個外掛（見「同步」）。

| 檔案 | 用途 | 可以注入第三方網頁？ |
|---|---|---|
| `tokens.css` | 只有 CSS 自訂屬性：顏色、字型、間距、圓角、陰影、動態 | 可以。不得出現元素樣式或 `color-scheme` |
| `components.css` | 擴充頁面（popup、設定頁、側邊面板）的基礎樣式與元件 | 不行 |
| `README.md` | 本文件：設計規範與使用方式 | — |

---

## 1. 六條原則

1. **平面優先。** 用細線（hairline）與留白分組，不用卡片套卡片。一個畫面最多一張 `nw-card`，留給「目前任務」。
2. **字比框重要。** 層級靠字級、字重與留白。中文不加負字距。大寫英文標籤只出現在頁尾簽名，不放在每個區塊上方。
3. **顏色只表達意思。** 紫色＝動作與選取；萊姆＝成果與完成；紅、綠、黃只用於回饋，文字一律用 `-text` 版本。
4. **一個畫面一個主要動作。** 其他動作用 secondary、ghost 或 link。
5. **只有浮在網頁上的東西才有陰影。** 陰影一次宣告（ring＋shadow），不同時加邊框和大陰影。
6. **狀態要有字。** 一律「圓點＋文字」，不讓顏色單獨承擔意思。

## 2. Tokens

### 顏色（語意角色）

| Token | 亮色 | 暗色 | 用途 |
|---|---|---|---|
| `--nw-canvas` | `#F1EFE7` 暖象牙 | `#0D0F12` | 頁面底色 |
| `--nw-surface` | `#FFFFFF` | `#16191E` | 欄位、卡片、次要按鈕 |
| `--nw-surface-raised` | `#FFFFFF` | `#1D2128` | 浮在網頁上的 popover、toast |
| `--nw-fill` / `-hover` / `-press` | 墨色 4.5% / 7.5% / 11% | 象牙 5% / 8.5% / 12% | hover、按下、靜態分組 |
| `--nw-line` | 墨色 10% | 象牙 9% | 分隔細線 |
| `--nw-line-strong` | 墨色 17% | 象牙 15% | 區段分隔、次要按鈕外框 |
| `--nw-line-control` | `#96958F` | `#646A73` | 輸入框邊線（對 surface 3:1） |
| `--nw-control-track` / `-thumb` | 墨色 6% / `#FFFFFF` | 象牙 6% / `#2B303A` | 分段控制：選中的永遠在上層 |
| `--nw-text` | `#111111` | `#F4F1E8` | 主要文字 |
| `--nw-text-muted` | `#6B6B68` | `#B4B5B9` | 次要文字、placeholder |
| `--nw-action` | `#7432FF` | `#8550FF` | 主要按鈕、選取 |
| `--nw-action-text` | `#7432FF` | `#B092FF` | 紫色文字與連結 |
| `--nw-action-tint` | 紫 9% | 紫 18% | 選取底色 |
| `--nw-result` | `#DFF813` 萊姆 | `#DFF813` | 成果、完成；配 `--nw-on-result` 墨色字 |
| `--nw-success` / `-text` / `-tint` | `#18A76B` / `#0F7A4C` | `#46D6A0` | 成功 |
| `--nw-warning` / `-text` / `-tint` | `#D8B400` / `#7D6000` | `#F4C95D` | 提醒 |
| `--nw-error` / `-text` / `-tint` | `#DB1B1B` / `#C21818` | `#FF7272` | 錯誤、破壞性操作 |
| `--nw-focus` | `#1877F2` | `#5DA9FF` | 鍵盤焦點，只用於焦點環 |
| `--nw-brand-ink` / `-ivory` / `-lime` | — | — | 品牌原色，只給商標與網頁上的訊號元素 |

基礎色（如 `--nw-success`）用於圓點與底色；放文字時用 `-text` 版本，確保對比。

### 字型

| Token | 字體 | 用途 |
|---|---|---|
| `--nw-font-body` | Noto Sans TC → PingFang TC → 微軟正黑體 UI | 介面與內文 |
| `--nw-font-signal` | Roboto Condensed → Bahnschrift → DIN Alternate → Avenir Next Condensed | 數字、按鍵、檔名、短資料。搭配 `font-stretch: 87.5%` 與等寬數字 |
| `--nw-font-mono` | ui-monospace → Cascadia Mono → Consolas | 程式碼、儲存鍵名 |
| `--nw-font-display` | Italiana → Georgia | 品牌宣言用，擴充介面不使用 |

字級：`--nw-text-xs` 11 · `sm` 12 · `md` 13（介面預設）· `base` 14 · `lg` 15（標題列）· `xl` 17（區段標題）· `2xl` 22 · `3xl` 28（設定頁標題）。
行高：`--nw-leading-tight` 1.3（標題）· `--nw-leading` 1.55（介面）· `--nw-leading-loose` 1.7（長文）。
字重只用 400、500、600。外掛不打包網路字型；以上字體都是系統字型與後備鏈。

### 間距、圓角、控制項、動態

- 間距（4px 基數）：`--nw-space-1` 4 · `2` 8 · `3` 12 · `4` 16 · `5` 20 · `6` 24 · `8` 32 · `10` 40 · `12` 48。
- 圓角：`--nw-radius-xs` 4（chip、按鍵）· `sm` 6（按鈕、輸入框）· `md` 8（分段控制、媒體、tile）· `lg` 12（卡片、面板）· `xl` 14（網頁上的 popover）· `pill` 999（只給浮動小按鈕）。
- 控制項高度：`--nw-control-sm` 28 · `md` 34（popup 預設）· `lg` 40（主要動作、設定頁）。網頁上的浮動按鈕維持 44px。
- 動態：`--nw-duration-fast` 120ms（hover）· `--nw-duration` 180ms（狀態切換、進場）· `--nw-duration-slow` 280ms。曲線：`--nw-ease-out`（進場）、`--nw-ease-standard`（狀態）。按鈕 hover 不位移，只換顏色。
- 陰影：`--nw-shadow-thumb`（分段控制選中項）· `--nw-shadow-raised`（網頁上的 popover、toast）· `--nw-shadow-overlay`（需要鎖定焦點的對話框）。

## 3. 元件（`components.css`）

| 元件 | Class | 變化與規則 |
|---|---|---|
| 標題列 | `nw-appbar`、`__brand`、`__icon`、`__title`、`__meta` | 32px 圖示＋15px 標題＋12px 說明；右側放 ghost 小按鈕 |
| 按鈕 | `nw-btn` ＋ `--primary` / `--secondary` / `--signal` / `--ghost` / `--danger` / `--link` | 尺寸 `--sm` / 預設 / `--lg`，`--block` 撐滿。`--signal`（萊姆）只用於「完成」類動作，例如「會了」 |
| 欄位 | `nw-field`、`__label`、`__hint`；`nw-input`、`nw-select`、`nw-textarea`；`nw-input--lg` | 標籤常駐在欄位上方；焦點用藍色外環 |
| 分段控制 | `nw-segmented`、`__item`（`aria-selected="true"` 或 `.is-active`） | 用於分頁切換 |
| 選項列 | `nw-option`、`__body`、`__title`、`__hint` | checkbox／radio＋標題＋說明；多列時放在 `nw-rules` 內，以細線分隔 |
| 選擇卡 | `nw-tile` ＋ `nw-tile__frame` | 值得有一塊面的 radio 組。`frame` 必須緊接在 input 之後（見例外 1） |
| 區段 | `nw-section`、`__title`、`__hint` | 設定群組；群組之間用細線，不用卡片 |
| 卡片 | `nw-card` | 每個畫面最多一張，給目前任務 |
| 提示框 | `nw-callout` ＋ `--warning` / `--error` / `--success` | 淡色底，不加彩色側邊條 |
| 狀態 | `nw-status`（`data-state="busy" / "ready" / "error"`） | 圓點＋文字；busy 會呼吸 |
| 訊息 | `nw-message` ＋ `.is-success` / `.is-error` | 控制項下方的結果文字 |
| Chip | `nw-chip` ＋ `--action` / `--result` / `--warning` / `--error` | 非互動標籤 |
| 按鍵 | `nw-kbd` | 快捷鍵顯示 |
| 空狀態 | `nw-empty`（內含 `strong` 標題） | 說明會出現什麼、怎麼開始 |
| 進度 | `nw-spinner` | 等待外部結果時使用 |
| 連結 | `nw-link` | 常駐底線 |
| 簽名 | `nw-signature`、`__mark` | 頁尾唯一的大寫英文標記，例如 `Noise Winston · Lab 002` |
| 工具 | `nw-signal`、`nw-muted`、`nw-rules` | 數字字體、次要文字、細線分隔的堆疊 |

## 4. 畫面模式

**Popup（360–420px）。** 標題列 → 單一「目前任務」區 → 內容 → 頁尾簽名。內容用細線分隔的清單，不要一列一張卡片。主要動作只有一個。

**設定頁。** 頂部固定列（圖示＋產品名、右側簽名）→ 28px 頁標題與一句說明 → 每個設定群組左欄標題、右欄控制項，群組之間用細線。720px 以下改為單欄。

**側邊面板的流程。** 真正有順序的流程才用步驟指示（三段短線：完成＝次要文字色、目前＝紫、完成結果＝綠），標題下方不再加編號圓圈。

**網頁上的介面（content script）。**
- 注入的根元素加上 `data-nw-root`，並由 manifest 把 `noise-winston/tokens.css` 注入頁面，tokens 就會在根元素上生效。
- 有主題設定的外掛，再用 theme runtime 在根元素寫入 `data-nw-theme`。
- Shadow DOM 內的樣式一律寫 `var(--nw-*, 後備值)`，即使 tokens 未載入也能顯示。
- 只有浮在網頁上的元素用 `--nw-shadow-raised`。嵌入網頁內容中的面板（例如 YouTube 資料面板）用 1px ring、不加陰影。
- 影片縮圖上的標記沿用 YouTube 時長標籤的寫法：深色半透明 chip；只有真正的 outlier（≥2×）才變萊姆。

## 5. 主題

- 預設跟隨系統。根元素 `data-nw-theme="light"` 或 `"dark"` 會覆蓋系統設定。
- 擴充頁面由各外掛的 `theme.js` 處理；`components.css` 會依主題設定 `color-scheme`。
- `tokens.css` 永遠不設定 `color-scheme`，避免改變第三方網頁的表單外觀。
- 暗色是另一套語意值，不是把墨色和白色對調。

## 6. 無障礙（實測對比）

| 組合 | 對比 |
|---|---|
| 亮色主要文字／象牙底 | 16.40 |
| 亮色次要文字／象牙底 · 白底 | 4.64 · 5.35 |
| 白字／紫色按鈕（亮 · 暗） | 5.76 · 4.58 |
| 墨色字／萊姆 | 15.80 |
| 成功 · 提醒 · 錯誤文字／象牙底 | 4.67 · 5.15 · 5.31 |
| 輸入框邊線／欄位（亮 · 暗） | 3.00 · 3.23 |
| 暗色次要文字／暗色 surface | 8.60 |

焦點環為 2px `--nw-focus`。尊重 `prefers-reduced-motion`：動畫關閉後，狀態仍可由文字與顏色辨識。

## 7. 已知例外

1. **`nw-tile` 不用 `:has(:checked)`。** Chrome 在程式改變 radio 選取時，不會重新套用 `:has(input:checked)` 的樣式，舊的選取外觀會殘留。因此選取外觀由緊接在 input 後的 `nw-tile__frame`（`input:checked ~ .nw-tile__frame`）負責。
2. **字型未打包。** Roboto Condensed 與 Italiana 不在一般 Windows 上；signal 字體在 Windows 會使用 Bahnschrift。若要完全一致，需另外打包授權字型檔。
3. **側邊面板的 `#cropPreview` 沒有初始 `src`。** 影像由 `sidepanel.js` 在執行時填入，屬預期行為。

## 8. 同步

三個外掛各有一份 `noise-winston/`：

```text
<workspace>/gemini-selection-translator/noise-winston/
<workspace>/youtube-outlier-mvp/noise-winston/
<workspace>/video-bridge/extension/noise-winston/
```

修改其中一份後複製到另外兩份，再比對雜湊值確認相同：

```bash
md5sum ../gemini-selection-translator/noise-winston/* ../youtube-outlier-mvp/noise-winston/* extension/noise-winston/*
```

各外掛自己的版面 CSS（`popup.css`、`options.css` 等）只負責排版，顏色、字級與元件都從 kit 取用。

## 9. 版本紀錄

**2.1.0（2026-10-15）**：從 NW 2.0.0 衍生的擴充功能版本。
- 新增 fill、line、control、`-text`、`-tint` 等語意 token。
- 字體改用系統後備鏈。
- 移除格紋背景、區塊英文標籤與裝飾性編號。
- 卡片改為細線分組。
- 萊姆只保留給成果。
- 新增 signal 按鈕。
- 修正 tile 選取殘留。
