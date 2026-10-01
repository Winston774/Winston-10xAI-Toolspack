# 架構與資料流

本週收錄獨立技能，無伺服器、UI、發布帳號或相鄰技能依賴。

| 元件 | 責任 | 不會替你完成的判斷 |
| --- | --- | --- |
| highlights.py | doctor、CLI 指令分派與 validate | 內容重要性與實際觀看 |
| vh_prepare.py | 媒體檢查、字幕匯入、分塊、抽圖、分析音訊；選配 ASR | 判斷空白字幕是否無重要內容 |
| vh_evidence.py | 候選區段預覽、幀圖、音訊、時間映射 | 保證媒體已被閱讀／聆聽 |
| vh_plan.py | 引用與證據路徑檢查、門檻、加權評分、去重及報告 | 校準流量預測或證明語意正確 |
| vh_render.py | 來源 hash 重驗、固定構圖、字幕重定位、MP4 匯出與規格驗證 | 人類發布品質簽核 |

執行順序：本機影片＋同步字幕 → project/chunks → Agent 全片閱讀與候選核對 → candidates → selection/plan → MP4/SRT/render.json。

時間以與原片同步的 zero_based_media 為座標。prepare 會拒絕超出容許範圍的非零音視訊起點；來源含旋轉或非方形像素時依顯示尺寸正規化。抽圖的 requested_time 只是 seek 請求值，無法代表精確解碼 PTS。

select 重新計算八項分數，不直接相信已存總分；render 重新驗證計畫、來源 hash、時長、音軌與尺寸。輸出目錄必須新建；prepare 失敗保留 .incomplete，render 失敗保留 render.failed.json。

reviewed 需要已記錄 watched、listened（或 no_audio）且無 unresolved；整體 coverage 尚有未檢視區域時仍為 partial。這些欄位是檢視聲明，工具無法證明人或 Agent 真正看聽。render 的 human_audiovisual_signoff 固定為 false。

完整欄位見 [資料契約](../completed/video-highlights/references/contract.md)。
