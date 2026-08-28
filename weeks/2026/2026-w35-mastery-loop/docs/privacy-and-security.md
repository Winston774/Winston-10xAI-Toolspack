# 資料、隱私與安全

## 資料位置

Mastery Loop 的 Python runtime 不需要外部 API，也不含 telemetry。新循環的規格、回答、報告、checkpoint 與 delayed review 排程都保存在學員指定 workspace 的 `mastery-sessions/<cycle-id>/`。

本週公開包不含任何講師或測試者的 `mastery-sessions/`。發行內容只收錄 Git commit 中的正式技能檔案。

## 分享與版本控制

`mastery-sessions/` 可能包含：

- 學習目標與能力缺口。
- 每題選擇、錯誤類型與回饋時間。
- 個人工作情境、組織名稱或專案細節。
- 來源連結與評估依據。

將工作目錄加入 Git、雲端同步、Issue、聊天室或課程成果前，先排除 `mastery-sessions/`，或逐檔匿名化。公開問題回報只提供最小 spec、錯誤訊息與可重現步驟。

## 本機介面邊界

- HTTP server 綁定 `127.0.0.1`，不對區域網路公開。
- 狀態變更使用 CSRF 與 opaque tokens。
- 伺服器驗證 phase、順序、request ID、路徑 containment 與內容格式。
- 回應採 atomic write-once；重送相同請求不會建立第二份成績。
- CSP、frame protection、HTML escaping 與 body limits 降低瀏覽器攻擊面。

請勿自行把綁定位址改成 `0.0.0.0`，也不要透過反向代理、port forwarding 或公開 tunnel 暴露學習頁面。

## 來源與高風險主題

當主題涉及即時、醫療、法律、金融、安全或其他高風險判斷：

- 使用當前的第一方或權威來源。
- 將未查證 benchmark 標為 provisional。
- 找不到可辯護答案時暫停 scoring。
- 不把學習結果當成正式資格、診斷、許可或專業意見。

## 授權

本週技能、教材與程式碼依 Toolspack 根目錄 [MIT License](../../../../LICENSE) 發布。學習時引用的第三方文章、規範、題庫或教材仍受各自條款約束；保留連結與必要摘要，不要將完整受保護內容複製進 cycle 或公開成果。
