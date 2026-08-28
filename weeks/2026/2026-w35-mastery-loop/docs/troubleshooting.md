# 疑難排解

## Skill 沒有出現在清單

確認安裝結構為：

```text
mastery-loop/
├── SKILL.md
├── agents/openai.yaml
├── references/
├── scripts/
└── tests/
```

不要多包一層同名資料夾。重新啟動 Agent 工具，再用 `$mastery-loop` 明確呼叫。

## Agent 沒有先顯示三個目標

新循環應先提供恰好三個可點擊成果。若環境沒有原生按鈕，Agent 可使用 `click_choice_ui.py` 提供本機點擊頁面。不要以自由輸入或「請回覆 A/B/C」取代可用的點擊路徑。

## `validate` 顯示 spec 錯誤

先保留錯誤訊息，讓 Agent 對照對應 reference 修正 spec。常見原因：

- Assessment 少於 10 題、領域少於 3 個，或重複 kernel。
- 選項描述洩漏正解、解析或 stable ID。
- Learning slice 數量不符合 gap 公式，或缺少 Assessment lineage。
- Review 重複既有 scenario、題型、選項或正解位置。
- 目錄、report、response 或 event 指向 cycle 外部。

## 瀏覽器沒有開啟

1. 確認 Python 3.10 以上可執行。
2. 先執行 phase 的 `validate`。
3. 再讓 Agent 執行 `serve --port 0`。
4. 將 terminal 顯示的 `http://127.0.0.1:<port>/` 貼到本機瀏覽器。

## 出現 phase lock

同一 cycle 同一時間只允許一個 writer。先關閉舊頁面與舊程序，再從既有 checkpoint 重開。請勿刪除 responses、events、reports 或 lock 來重置成績。

## 提交後斷線或 timeout

保留 cycle，重新開啟相同 phase。相同 `request_id` 的 retry 會回傳既有紀錄；若同題改送另一答案，runtime 會以 conflict 拒絕，避免雙重成績。

## Review 無法開始

Review gate 需要：

- 完整 `assessment/report.json`。
- 所有 Learning slices 的 completion events。
- 每個領域一份 checkpoint response。
- 完整 `learning/report.json`。
- 沒有另一個活躍 phase writer。

讓 Agent 執行 Learning phase `validate`，依錯誤指出的缺件補齊；不要手動偽造空白 event。

## Windows 測試跳過 symlink 案例

Windows 未授予「建立符號連結」權限時，該測試會顯示 `skipped`。可以在允許 symlink 的隔離環境重跑；路徑 traversal、contained directory 與非法 evidence surface 仍由其他測試覆蓋。

## 回報問題時提供

- 作業系統、Python 與 Agent 版本。
- cycle version、phase 與完整錯誤訊息。
- 執行到哪個畫面，以及重新整理後看到什麼。
- 最小且已匿名化的 spec 或檔案結構。
- 是否曾同時啟動兩個 serve 程序。

公開回報前移除姓名、組織、客戶、專案內容、作答紀錄、API Key、Cookie、私有來源與完整 `mastery-sessions/`。
