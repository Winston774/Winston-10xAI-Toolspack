---
name: "迅剪 Local Studio"
description: "石墨工作桌、品牌紫操作色與來源素材驅動的本地剪輯介面"
colors:
  primary: "#8550ff"
  primary-ink: "#ffffff"
  primary-hover: "#7432e8"
  action-text: "#b092ff"
  focus: "#5da9ff"
  success: "#46d6a0"
  result: "#dff813"
  border-strong: "#4a5261"
  control-border: "#626b7a"
  bg: "#0d0f12"
  surface: "#16191e"
  raised: "#1d2128"
  control: "#242933"
  line: "#353b47"
  text: "#f4f1e8"
  muted: "#b4b5b9"
  subtle: "#b4b5b9"
  video: "#7863ad"
  video-soft: "#45375c"
  audio: "#438b77"
  caption: "#a98847"
  error: "#ff7272"
  button: "#242933"
  button-hover: "#353b47"
  video-fill: "#4c4068"
  video-border: "#8a79ba"
  audio-fill: "#245344"
  audio-border: "#53967f"
  caption-fill: "#63502d"
  caption-border: "#ae925b"
typography:
  display:
    fontFamily: '"Segoe UI", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif'
    fontSize: "clamp(36px, 4vw, 56px)"
    fontWeight: 580
    lineHeight: 1.35
    letterSpacing: "0.015em"
  title:
    fontFamily: '"Segoe UI", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif'
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.55
  panel-title:
    fontFamily: '"Segoe UI", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif'
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.55
  body:
    fontFamily: '"Segoe UI", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: '"Segoe UI", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif'
    fontSize: "11px"
    lineHeight: 1.55
  button:
    fontFamily: '"Segoe UI", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif'
    fontSize: "12px"
    fontWeight: 550
    lineHeight: 1.55
  button-primary:
    fontFamily: '"Segoe UI", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif'
    fontSize: "12px"
    fontWeight: 650
    lineHeight: 1.55
  timecode:
    fontFamily: 'Consolas, "SFMono-Regular", monospace'
    fontSize: "10px"
rounded:
  tight: "3px"
  control: "4px"
  button: "5px"
  panel: "6px"
  notification: "7px"
  dialog: "10px"
spacing:
  tight: "4px"
  small: "8px"
  regular: "12px"
  panel: "16px"
  wide: "20px"
  dialog: "22px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-ink}"
    typography: "{typography.button-primary}"
    rounded: "{rounded.button}"
    padding: "7px 13px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "#ffffff"
  button-secondary:
    backgroundColor: "{colors.button}"
    textColor: "{colors.text}"
    typography: "{typography.button}"
    rounded: "{rounded.button}"
    padding: "7px 13px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.button}"
    rounded: "{rounded.button}"
    padding: "7px 13px"
  input:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
  rail-navigation:
    backgroundColor: "{colors.surface}"
    padding: "10px 5px"
  badge:
    textColor: "{colors.muted}"
    rounded: "{rounded.control}"
    padding: "2px 5px"
  media-card:
    rounded: "{rounded.control}"
  timeline-video:
    backgroundColor: "{colors.video-fill}"
    textColor: "#efeafa"
    rounded: "{rounded.control}"
    padding: "4px 6px"
    height: "35px"
---

# Design System: 迅剪 Local Studio

> **W37 歷史記錄註記**：本檔是來源 UI 設計與歷史驗證紀錄；它所提到的素材、測試環境與結果沒有隨學員 ZIP 附上。請以[W37 驗證紀錄](../../docs/verification.md)判定本輪可採信的測試與限制。

## Overview

**Creative North Star: "石墨剪輯桌"**

石墨色面板包住影片、逐字稿與時間軸，紫色標出可執行動作與選取狀態。密集但分區清楚的控制項、系統中文字體與細邊界，構成迅剪既有的本地工作桌。

本文件沿用已核准 A＋B 剪輯桌的配置與密度。2026-09-10 依品牌配色調整要求導入 Noise Winston v2.0.0 深色語意映射；執行期色彩以 local_editor/web/noise-winston.tokens.css 為準，元件由 style.css 消費，Canvas 波形由 waveform.js 讀取同一份 CSS 變數。

**Key Characteristics:**

- 石墨面層、品牌紫操作色與可識別的軌道色。
- 小字級、短圓角、清楚的表單與工具列。
- 本機影片與真實字幕資料構成主要內容。

## Colors

Primary 為品牌紫操作色；Secondary 是紫色影片、綠色音訊與琥珀字幕的功能配色；Neutral 以背景、面板、抬高面層、控制項與細線建立深度。frontmatter 列出常用色；完整色彩與角色以 noise-winston.tokens.css 為準。

**The Action Accent Rule.** 紫色用於主要動作；淡紫用於文字、選取與播放頭，藍色用於鍵盤焦點，綠色用於成功／連線，Signal Lime 用於匯出完成。影片、音訊與字幕以各自軌道色保持辨識。

時間軸片段實際使用專用 fill／border 配對；track-video-fill、track-audio-fill、track-caption-fill 等角色集中在 token 檔，數值沿用原分類色。

## Typography

介面使用 Windows／繁中系統字體堆疊，不載入外部 webfont。首頁 display 是獨立用途；工具面板依 panel-title、body、label 收斂密度。提示文字通常採 label 字級，行高放寬至 1.7；逐字稿 textarea 使用 body 字級，行高 1.65。

**The Numeric Alignment Rule.** 時間碼與程式片段使用等寬字體；候選時長使用 tabular-nums，避免數字更新造成橫向跳動。

## Layout

可重用語法為常駐工具列、可獨立捲動面板、置中且 contain 的預覽、底部水平時間軸。此表面的模式與核准 A＋B 配置由 docs/editor-surface.md 管理。

目前 CSS 的實際配置：

| 條件 | 工作區欄寬：工具／側欄／預覽／屬性 | 外框列高：頂列／工作區／時間軸／狀態 |
| --- | --- | --- |
| 預設 | 66／300／minmax(260,1fr)／265 px；口播側欄 340 px | 56／minmax(340,1fr)／265／28 px |
| ≥1700 px | 70／340／minmax(400,1fr)／300 px；口播側欄 380 px | 60／minmax(370,1fr)／290／28 px |
| ≤1250 px | 61／270／minmax(250,1fr)／235 px；口播側欄 310 px、預覽最小 230 px | 沿用預設 |
| ≤1080 px | 60／295／minmax(250,1fr) px；屬性改 270 px 浮出面板 | 56／minmax(340,1fr)／257／28 px |
| ≤760 px | 54 px 工具列＋內容；預覽 340 px、側欄 430 px 垂直排列 | 54／auto／257／30 px |

面板內距以 panel spacing 為主；屬性面板 15 px、≤1250 px 一般面板 13 px。時間軸固定標籤寬 118 px；一般軌列最小高 46 px，≥1700 px 為 52 px，字幕軌 37 px。頁面最小寬 360 px；桌面外框最小高 660 px。

首頁另採最大寬 min(1140px,92vw)、1:1.25 雙欄與 7vw 間距；≤760 px 轉單欄。這些尺寸記錄目前實作，不要求其他表面套用。

## Elevation & Depth

**The Quiet Surface Rule.** 常駐面板以色階與細線分隔；陰影限於對話框、浮出屬性與通知。

對話框投影為 0 18px 65px #0006，通知為 0 7px 20px #0003，浮出屬性為 -6px 8px 22px #0003。預覽標題使用 1px 2px 3px #0009 text-shadow。沒有常駐面板玻璃模糊。

## Shapes

表單、素材縮圖、軌道片段採 control 圓角，按鈕採 button 圓角；字幕片段更緊，對話框更大。SVG 為既有線性圖示。播放頭以細直線搭配 10 px 五邊形標記，保持時間定位清楚。

## Components

- **按鈕**：主要、一般、ghost 三種已有變體；主要字重 650，其餘以 button token 為準。最小高度 34 px，圖示按鈕 30×30 px。停用透明度 .4；hover 使用現有面色，鍵盤焦點為 2 px 焦點藍 outline、偏移 3 px。
- **欄位**：實線邊界由 --nw-control-border 管理；focus 改焦點藍邊界。搜尋欄以 focus-within 顯示 2 px 焦點藍 outline。checkbox 保留原生外觀，range 使用紫色 accent-color。
- **導覽**：工具按鈕高 56 px，圖示 22 px、文字 10 px；選取顯示深紫底、淡紫文字、左側 2 px 指示線與 aria-pressed。
- **素材卡**：雙欄縮圖網格，欄間 10 px、列間 15 px；縮圖高 78 px，素材名省略。≤760 px 改三欄與 72 px 縮圖。
- **軌道片段**：紫／綠／琥珀分類、可見文字與時間碼；選取使用 2 px 淡紫外框。分割手把位於兩端，各 5 px。標準影片片段高度見 token，≥1700 px 為 41 px。
- **候選／逐字稿**：分隔列表承載時間、原因、checkbox、試聽與明確套用動作；逐字稿保留可編輯 textarea。不要僅以底色表達是否已選取。
- **對話框／通知**：原生 dialog 最大寬 min(460px,92vw)，媒體預覽 min(780px,94vw)；通知最多寬 490 px，以文字與圖示區分成功／錯誤。按鈕背景轉場 .15s ease、通知進入 .18s ease-out；reduced-motion 關閉動畫與轉場。

既有 .impeccable/design.json 為本次遷移前的樣式展示快照，含舊名稱與薄荷 fallback，尚未重建；不作執行期配色來源。圖示沿用內嵌 SVG。

## Do's and Don'ts

### Do:

- Do 沿用現有石墨面層、品牌紫操作色與三類軌道配色。
- Do 用語意按鈕、label、原生 dialog 與可見焦點；動態結果同時提供文字。
- Do 讓長素材名稱省略、字幕換行，時間軸可水平捲動。
- Do 從本機素材取得縮圖與波形；示例與合成測試資料需明確標示。

### Don't:

- Don't 將專案首頁的大標題字級套用至剪輯工具面板。
- Don't 用裝飾性漸層、玻璃模糊或通篇投影取代現有平面分區。
- Don't 僅靠顏色表達選取、錯誤或工作完成。
- Don't 把這次工作台配置提升為所有未來頁面的固定欄寬。

## Noise Winston 採用契約

- 基準：Noise Winston Design System v2.0.0，Calm structure. Loud signal.
- 深度：品牌色與語意狀態映射；保留字體、字級、間距、路由及編輯流程。
- 色彩來源：`local_editor/web/noise-winston.tokens.css`；由 `index.html` 在 `style.css` 前載入。
- 元件來源：`local_editor/web/style.css`。既有 `--bg / --surface / --accent` 等為相容別名；新增元件優先使用語意角色。
- 波形來源：`waveform.js` 每次 paint 讀取 `--waveform-color / --waveform-muted`，不在繪圖迴圈讀取 computed style。
- 套用表面：專案首頁、工作台、側欄、時間軸、對話框、工作回饋。

| 範圍 | 原始來源 | 目標角色 | 決策 |
| --- | --- | --- | --- |
| 面板與文字 | 分散色碼、舊 CSS 變數 | nw-canvas / surface / text | map |
| 按鈕與導覽 | 薄荷操作色 | nw-action / action-text / action-surface | map |
| 焦點與成功 | 共用 accent | nw-focus / success / result | extend |
| 媒體與軌道 | 原本分類／內容色 | track-* / waveform-* / media-* / filter-* | preserve |
| 字體與配置 | 系統繁中字體、A＋B 工作台 | 現有規格 | preserve |

### 刻意保留的例外

- 固定深色：沿用目前剪輯工作台的長時間觀看情境，尚無淺色或系統主題切換。本次未新增主題控制；暖白作文字色，Ivory 淺色 canvas 待未來另行設計。
- 主要按鈕用純白字：#8550ff 背景搭 #ffffff 對比 4.58:1；標準暖白 #f4f1e8 只有 4.05:1。可及性優先。
- 軌道、音訊波形、剪輯建議、濾鏡示意保留原色值並集中為語意變數；影片畫布、字幕與標題的實際內容色仍由專案資料決定。
- 密集工具列沿用 30–34px 控制項及現有小字級，未宣稱符合全部 44px 觸控要求。
- 既有 sidecar 不隨本次色彩映射重建；後續 Agent 以本文件及 token 檔為準。

### 稽核與驗證

修改前的 Impeccable 原始碼稽核：A11y 2、效能 3、響應式 2、主題 2、實作一致性 3，共 12/20。屬本次抽查評估，並非 WCAG 全面認證。

- P1：次要色 #858d98 在 raised #25282d 上為 4.41:1；改用 nw-text-muted。
- P2：操作、焦點與成功共用 accent；已分成各自角色。
- P2：CSS 分散色碼、Canvas 硬編碼；已集中到 token 層。
- 保留：原生 dialog、label、按鈕、aria-pressed、可見狀態文字及 reduced-motion。
- 延後：既有窄螢幕密集工具列、44px 觸控尺寸、字級與 sidecar 更新，均超出本次配色範圍。
- 掃描器請對 `local_editor/web` 執行；根目錄掃描會納入本機 ASR runtime，造成與產品 UI 無關的結果。

可重跑：
```powershell
git diff --check
node --check local_editor/web/waveform.js
node --test tests/*.test.mjs
node <skill-root>/scripts/inspect-project.mjs local_editor/web --json
```

2026-09-10 驗證結果：23 項既有前端測試、JavaScript 語法與 diff whitespace 檢查通過。元件 CSS 無硬編碼色值、無未定義變數；掃描色值由 174 降至 80，剩餘值集中於 token 層。Impeccable 剩餘 21 項字級與 1 項圓角 advisory，未新增超出配色範圍的修正。

瀏覽器驗證涵蓋桌面與 390px 工作台、真實素材波形、首頁、對話框及可見焦點；原專案版本保持 v14。主要按鈕文字對比 4.58:1、hover 6.24:1、次要文字對 grouped surface 7.12:1。無 npm／TypeScript／前端打包程序；lint、typecheck、production build 不適用。固定深色未測淺色；200% 文字放大、完整空白／錯誤／完成狀態互動、實際媒體匯出與完整 Python 媒體回歸未執行，本次以配色及讀取既有素材的 UI 檢查為限。
