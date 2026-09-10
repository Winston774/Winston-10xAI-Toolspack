# 迅剪 Local Studio

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

需要在 Windows 本機完成影片剪輯、口播精剪與繁體中文字幕的創作者，以及透過 MCP 操作相同專案的 Codex / Claude Code Agent。

## Product Purpose

提供接近剪映操作習慣的本地剪輯工作台，優先完成素材匯入、智能剪口播、字幕校正、時間軸調整、真實影片匯出與 Agent 操作閉環。

v0.2 將 Agent 的理解依據納入正式產品契約：每項判斷可取得來源／合成聲畫、逐字稿、圖層與時間映射；每項修改有提案快照、差異及驗證；未知、估算與實際審閱分開記錄。剪輯方向由使用者或已明確取得需求的 Agent 保存，不從素材名稱推測。

## Operating Context

使用者已確認先完成瀏覽器本地工作台與 MCP。Python 在本機提供服務，FFmpeg 處理媒體；既有 agent-video 與 Seedance CLI 保留。資料保存在專案本機目錄。

## Capabilities and Constraints

智能剪口播、字幕工具與 MCP 為必備。全功能剪輯器是長期產品範圍，交付以功能矩陣記錄已驗證能力與擴充項目。所有畫面、錯誤與操作說明以繁體中文為主。自動語音辨識依賴本機可用模型；預設不下載模型或呼叫雲端服務。修改可復原，Agent 使用版本檢查避免覆蓋其他操作。

## Brand Commitments

沿用使用者要求的剪映類型工作配置；採用獨立工作名稱「迅剪」，不使用剪映商標與專有素材。

## Evidence on Hand

既有 Python 管線、FFmpeg / FFprobe 工具與智能剪輯原始碼。尚無使用者提供的測試口播素材，驗證素材必須明確標示為合成測試。

v0.2 依使用者提供的實際 Agent 剪輯回報修正資訊缺口；自動化與修改驗收使用明確標示的合成素材。原有實際專案僅驗證讀取與新版相容性。

## Product Principles

- 本機資料與可檢查的專案狀態。
- UI 與 MCP 共用同一個剪輯核心。
- 智能建議可逐項確認，套用後可復原。
- 真實操作與匯出驗證優先於功能數量宣稱。

## Open Decisions

預設以單人口播作初次驗證；長期素材類型及 Windows 安裝包列為後續確認項目。
