# Shift PM｜從 MVP 到 Production 的產品化助手

Chrome 外掛有了點子或原型，接下來要怎麼選架構、拆工、驗收、上架，甚至開始收費？**Shift PM** 讓 AI Agent 擔任專案總管（Chief PM），先依你的產品階段、資料與成本結構做診斷，再決定此刻該推進哪一段。

這週分享完整原版技能，呼叫名稱是 **`chrome-extension-saas-architect`**。學員包保留原本的 `SKILL.md`、六份參考文件及三份範本；本頁提供安裝與使用入口。

## 安裝到你的 Codex 專案

1. 下載並解壓本週教材 ZIP。若下載的是 GitHub 整個分支的 ZIP，先進到 `weeks/2026/2026-w48-shift-pm/`。
2. 將 `completed/` 下的整個 `chrome-extension-saas-architect` 資料夾複製到**你的 Chrome 外掛專案根目錄**的 `.agents/skills/`。安裝後應看到 `.agents/skills/chrome-extension-saas-architect/SKILL.md`；`references/` 和 `templates/` 也要一起複製。若已有同名技能，先備份並比較版本。
3. 用 Codex 開啟該專案，在新對話輸入 `$chrome-extension-saas-architect`。如果清單未顯示，先核對開啟的專案和資料夾層級，再重開 Codex。參考 [Codex 技能指南](https://developers.openai.com/codex/skills)。

想先試用或使用其他能讀文件的 Agent，可以直接交給它完整技能資料夾，請它從 [SKILL.md](completed/chrome-extension-saas-architect/SKILL.md) 開始，按目前階段讀取對應參考。安裝技能不需要 API 金鑰、付費帳號或額外安裝 Chrome 外掛；後續實作依你的專案選擇工具。

## 什麼時候用？

| 手上的情況 | 交給 Agent 的任務 | 可以先拿到的成果 |
|---|---|---|
| 只有點子或本機 MVP | 做 Phase 0 診斷，比較本機、同步、用量計費或共享快取需求 | 一頁架構與商業決策，列出必做、可選及暫緩項 |
| 已在開發，事情太多 | 按里程碑拆工單與依賴，安排實作和獨立審查 | 工單、Owner 待辦、規格／獨立審查／沙盒／Git 與 CI 四道閘門 |
| 準備封測、送審或上架 | 用 25 個避坑案例和送審清單核對現況 | 需補的證據、環境隔離、核准事項和發布前檢核 |
| 要收費、估成本或找首批客戶 | 試算單位經濟、比較定價模式、規劃第一批使用者的啟用路徑 | 成本與毛利試算、收費取捨和市場驗證計畫 |

第一次可以直接貼：

> 用 $chrome-extension-saas-architect 幫我做 Phase 0。我的外掛目前能＿＿，預計先給＿＿使用，每次操作的成本是＿＿（不確定就先標示）。請先唯讀盤點，給我一頁決策、要我核准的事項，以及下一張可驗收的工單。這一輪先不要改檔、部署、扣款或送審。

## 原版內容索引

- [四維診斷與架構決策](completed/chrome-extension-saas-architect/references/01-discovery-and-architecture.md) · [雲端服務選型](completed/chrome-extension-saas-architect/references/02-service-stack-guide.md)
- [專案管理與多 Agent 協作](completed/chrome-extension-saas-architect/references/03-multi-agent-pm-workflow.md) · [25 個避坑案例](completed/chrome-extension-saas-architect/references/04-pitfalls-and-postmortems.md)
- [上架、合規與正式切換](completed/chrome-extension-saas-architect/references/05-launch-compliance-runbook.md) · [成本、定價與成長](completed/chrome-extension-saas-architect/references/06-monetization-and-growth.md)
- [專案治理範本](completed/chrome-extension-saas-architect/templates/AGENTS-starter.md) · [任務清單範本](completed/chrome-extension-saas-architect/templates/tasks-starter.json) · [送審自檢表](completed/chrome-extension-saas-architect/templates/pre-approval-checklist.md)

參考文件中的平台政策、費用及審核條件，執行前以當前官方資料核對。正式帳號、憑證、定價、收款、部署與送審由專案擁有者決定並授權；技能不保證審核結果。若技能找不到，先檢查是否複製了完整的原名資料夾；若輸出過廣，把目標縮小到下一個里程碑和一張工單。
