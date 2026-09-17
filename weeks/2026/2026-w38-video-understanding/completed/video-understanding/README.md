# Video Understanding｜影片理解

將參考短片整理為有時間證據的敘事、視聽系統與製作交接文件。W38 學員包版本：v0.1.1 Preview。

## 使用入口

安裝整個資料夾至 Agent 的 Skills 目錄，重新啟動後呼叫：

```text
使用 $video-understanding 分析這支短影音。
交付 VIDEO_UNDERSTANDING.md、analysis.json 與必要證據；
區分觀察、推論及製作建議，明列未檢視範圍。
```

輸出放在自己的工作目錄。未有改編目標時先理解原片，替換內容留待下一階段。能力不足時以 partial 交付，保留 PROGRESS.md 以便續跑。

## 內容導覽

- [SKILL.md](SKILL.md)：Agent 執行入口，保留本次 RAR 的功能指令。
- [觀察方法](references/observation-method.md)：整體與局部閱讀、系統生命週期、空間、文字、聲音。
- [交接契約](references/handoff-contract.md)：索引欄位、引用、證據、狀態與下游接手。
- [工具操作](references/tooling.md)：本機準備、時間映射與索引驗證。
- [主文件模板](assets/VIDEO_UNDERSTANDING.template.md)／[JSON 模板](assets/analysis.template.json)：填入實際影片資料後使用。
- [驗證紀錄](VALIDATION.md)：本次測試方式及範圍。

本次發布包不附授權檔，metadata 的授權欄位為未指定。

Python 3.10+；證據 helper 另需 FFmpeg／FFprobe。Python 程式只使用標準函式庫。實際觀看與聆聽由 Agent 可用工具提供，生成與渲染留給下一階段。
