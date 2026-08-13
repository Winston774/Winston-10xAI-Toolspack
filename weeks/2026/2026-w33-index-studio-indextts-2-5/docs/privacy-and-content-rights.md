# 隱私、聲音權利與授權

## 本機資料

| 資料 | 預設位置 | 發行包／Git |
|---|---|---|
| 聲紋與情緒暫存 | `outputs/htmlui/uploads/` | 否；工作後刪除 |
| WAV 與 JSON | `outputs/htmlui/` | 否 |
| 模型權重 | `checkpoints/` | 否，只有上游的 `pinyin.vocab` 隨程式提供 |
| Python 環境 | `.venv/` | 否 |
| 程式與教材 | Repository | 是 |

服務預設監聽 loopback；首次安裝與缺少模型時會連線下載依賴及權重。生成在本機 GPU 執行，無 API Key。

## 聲音權利

- 使用自己的聲音，或有書面授權且用途相符的聲音。
- 不使用政治人物、公眾人物、未授權個人或未成年人的聲音。
- 不進行冒用、詐欺、誤導、身分驗證規避、騷擾或假訊息。
- 公開內容時揭露 AI 生成，遵守所在地的同意、個資與深偽標示規則。

## 授權

completed 專案使用 `bilibili Model Use License Agreement`，需保留原授權與衍生作品聲明。它對大型商業使用、下游散布、模型改進與高風險用途設有限制。根倉庫 MIT License 不會改寫 completed 專案的原授權。

此文件是工程風險清單，不構成法律意見。
