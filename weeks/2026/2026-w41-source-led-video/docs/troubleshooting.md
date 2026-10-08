# 疑難排解

| 症狀 | 檢查與重試 |
|---|---|
| 找不到技能 | 第一層須直接有 SKILL.md；整個 source-led-video 放入技能目錄後重開對話 |
| init 拒絕既有目錄 | 建立新的 episode；續作讀取原集資料，不重新 init |
| 分數為 null／候選不合格 | 檢查缺失分數、證據與理由，以及三個門檻；補證據後重跑 score，勿用 0 代替未知 |
| plan 拒絕既有 rundown | 保留已填編排並直接修訂；plan 只建立空白骨架 |
| 首題檢查未過 | 比較所有問題、補門檻與分數、確認選中問題及第一段導讀／原音一致 |
| doctor 找不到套件或路徑 | 檢查每集 environment.json 的 Python、FFmpeg／FFprobe、GSAP、TTF、fontTools／brotli；Pillow 用於 smoke 與部分影格輔助 |
| 旁白文字不一致 | 檢查非 source rows 的確切文本與雙換行串接；重新核准後再錄音／生成 |
| 核聽 hash 失效 | WAV 已變更；重新聽目前音檔並記錄範圍，不能複用舊紀錄 |
| cut 失敗 | 確認原片有視訊與音軌、切點合法、FFmpeg 可執行；已有輸出先備份，再在新集測試 |
| resolve／build 指出資料過期 | 完成 WAV、字幕、旁白計畫後重新 resolve；來源若改動，另外重切，不能只更新計畫 |
| profile.brand 缺少 | 填自己的頻道／作者名稱，重新 resolve 後建片 |
| HTML 已有但沒有 MP4 | 繼續外部 HyperFrames 瀏覽器檢查與渲染，參見原始 quickstart；勿將 HTML 稱為成片 |
| 字幕、人物或重點卡被遮住 | 檢查實際影格與動態，修文案／素材／版型；保留未驗狀態直到重新驗收 |

回報問題時附上作業系統、Python／FFmpeg／HyperFrames 版本、已遮蔽路徑的錯誤摘要與最小合成輸入。不要貼私有原片、金鑰或完整環境設定。
