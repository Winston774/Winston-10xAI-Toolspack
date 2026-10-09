# 使用索引

第一次使用從 [SKILL.md](SKILL.md) 與[快速上手](references/quickstart.md)開始；只讀當下階段需要的文件。

| 要做的事情 | 文件／工具 |
|---|---|
| 安裝、使用範例、初始化 | [quickstart.md](references/quickstart.md)、[interview.py](scripts/interview.py) 的 `init` |
| 全片理解、候選與第一題比較 | [editorial.md](references/editorial.md)、[opening_selection.py](scripts/opening_selection.py) |
| 編排問題線與時間軸 | [rundown-and-data.md](references/rundown-and-data.md)、[interview.py](scripts/interview.py) 的 `plan`／`resolve` |
| 配音稿、專名與核聽 | [voice-and-terms.md](references/voice-and-terms.md)、[check_narration.py](scripts/check_narration.py) |
| 整份旁白 WAV 拆段、單次速度處理 | [prepare_voice.py](scripts/prepare_voice.py) |
| 字幕、人物、進度、重點動畫、封面 | [visual-system.md](references/visual-system.md)、[build_film.py](scripts/build_film.py) |
| 檢查紙邊、縮入、逐點與還原 | [check_style.py](scripts/check_style.py)、[visual_contract.py](scripts/visual_contract.py) |
| 工具與字型配置 | [dependencies.md](references/dependencies.md)、[configure.py](scripts/configure.py) |
| 交付與修訂 | [quality-and-delivery.md](references/quality-and-delivery.md) |
| 本機技術試跑 | [smoke_test.py](scripts/smoke_test.py)，合成靜音樣本不代表真人影片品質 |

## 新增可選製作路徑

- [製作設定](references/production-presets.md)：保存聲線試聽、同來源色系與雙語顯示規則。
- [編輯式 motion adapter](references/editorial-motion.md)：已準備媒體＋author-supplied cards/cues，CLI `build_editorial_motion.py PLAN --output NEW_WORK`；固定1080p30。不要與原rundown/schema混用。
- [聲音設定範本](templates/voice-selection.json)、[來源主題範本](templates/source-themes.json)、[編輯式計畫](templates/editorial-motion.json)。

## interview.py 子命令

| 命令 | 用途 |
|---|---|
| `init --out <新目錄>` | 建立當集工作目錄，可加入品牌、環境與片長要求 |
| `score <candidates.json> --out <報告.json>` | 檢查語意門檻、計算候選分數與未知分數區間 |
| `plan <工作目錄>` | 按已選問題建立尚未填寫的 rundown |
| `doctor <工作目錄>` | 檢查本機依賴路徑，不代表工具已實際執行 |
| `cut <工作目錄>` | 按 rundown 的原片秒數裁切來源 |
| `resolve <工作目錄>` | 依實際影音解析時間軸、字幕和章節 |
| `check <工作目錄> [--video <影片> --decode]` | 檢查時間軸；指定影片時核對格式，可完整解碼 |
| `package --out <分享.zip>` | 封裝目前技能資料夾並核對雜湊；輸出須在技能目錄外，拒絕覆蓋 |

封裝只收錄技能資料夾，不會收錄其他目錄的集數工程。分享前仍需檢查自己是否把設定、素材或私有資訊誤放進技能目錄；產生的 `.manifest.json` 位於 ZIP 旁，可用於核對版本與內容。

## 可填寫範本

| 範本 | 內容 |
|---|---|
| [profile.json](templates/profile.json) | 頻道、片長下限、旁白速度、字幕及渲染基準 |
| [environment.json](templates/environment.json) | 本機可執行工具、GSAP 與字型路徑 |
| [opening-selection.json](templates/opening-selection.json) | 標題承諾、候選首題、比較證據及選擇 |
| [narration-plan.json](templates/narration-plan.json) | 主持／講者、來賓、議題時機、原文術語及核聽紀錄 |
| [thumbnail-brief.json](templates/thumbnail-brief.json) | 當集縮圖方向、人物來源、標題層級及實看紀錄 |
| [film-scorecard.json](templates/film-scorecard.json) | 成片品質評估，與來源候選分數分開 |

初始化會將當集所需設定複製至自己的工作目錄。修改新集的設定，不需把本機路徑、素材或聲音放回技能目錄。
