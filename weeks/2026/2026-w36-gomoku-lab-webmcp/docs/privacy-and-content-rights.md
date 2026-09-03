# 資料、隱私與內容權利

## 資料流

棋盤、歷史、決策、核准與 Audit Log 保存在目前分頁的 JavaScript 記憶體。重新載入頁面會建立新狀態。成品程式碼沒有 `fetch`、XHR、WebSocket、sendBeacon、localStorage、sessionStorage 或 IndexedDB 資料傳輸／保存流程。

ChatGPT 與頁面之間的工具呼叫仍受你使用的瀏覽器、ChatGPT 帳號與服務條款約束。分享畫面前，請自行移除私人對話、帳號資訊與其他分頁內容。

## 憑證與專案 ID

- 成品不需要 API Key。
- `.openai/hosting.json` 的 `project_id` 是來源專案綁定識別，不是密碼。
- 不要把自己的 token、Cookie、`.env` 或私鑰加入 Repo、ZIP、Issue 或 Audit 範例。
- 部署前請建立自己的 Sites 專案並更新綁定，避免影響來源專案。

## 決策內容

只保存對使用者有用的策略摘要、棋盤證據、候選方案與信心。不要要求、記錄或公開模型私人 chain-of-thought。若需要除錯，使用工具輸入輸出、版本、錯誤碼與 Audit Log。

## 內容與授權

本週自行創作的程式碼、教材與隨附素材依 Repo 根目錄 MIT License 發布；completed 內另附相同授權。`package.json` 與 lockfile 只描述／鎖定相依套件，沒有把 `node_modules` 打入 ZIP。React、Vinext、Cloudflare、OpenAI Sites plugin、shadcn 及其他第三方套件仍各自依其授權條款使用，根目錄 MIT 不會覆蓋它們。

五子棋規則屬通用遊戲機制；若你替換圖片、字型、音效、品牌或教學範例，需自行確認素材權利。
