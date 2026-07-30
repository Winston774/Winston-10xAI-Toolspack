# Security Policy

## Supported version

目前維護 `1.x`。

## 回報安全問題

請不要在公開 Issue 貼出有效 Token、私人圖片、SQLite、`.env`、帳號資訊或可直接利用的敏感證據。

先以不含秘密的方式說明：

- 受影響版本。
- 問題類型與影響。
- 最小重現條件。
- 是否需要私下交換細節。

Repository 維護者可再提供適合的私人回報方式。

## 安全設計

- HTTP 服務只綁定 `127.0.0.1`。
- 使用者匯入圖片不會自動傳送。
- Codex 分析需要明確按鈕操作。
- Agent 使用一次性 session 與唯讀 sandbox。
- 動態分析結果需通過本機 JSON Schema。
- Git 預設忽略本機資料與設定。

這些控制不是遠端多人服務的完整安全架構。請勿將 Stylebase 直接暴露到區域網路或公網。
