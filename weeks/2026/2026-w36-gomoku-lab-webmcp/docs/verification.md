# 驗證紀錄與證據邊界

## 來源

- 來源目錄：`D:\Codex\WebMCP_Gomoku`
- 打包 commit：`7541bf1d09d85c5f34f095cb070ea277d748cf7d`
- 來源追蹤檔：80 個
- 匯入方式：`git archive HEAD`，未包含 `.git`、`node_modules`、`.next`、`.vinext`、`.wrangler`、`dist` 或 QA 暫存資料。
- Toolspack 分享副本另加入 README、MIT LICENSE、`scripts/validate-gomoku.mjs`，並在 `package.json` 加入 `test`、`typecheck`、`validate` scripts；其餘來源檔應維持 blob 相同。

## 2026-09-03 本機結果

| 檢查 | 結果 | 證據邊界 |
|---|---|---|
| Source Git status / fsck / diff-check | PASS | 來源 clean；Git 物件與 whitespace 檢查通過 |
| 祕密與私鑰樣式掃描 | PASS | 未發現 API key、GitHub token 或 private key pattern |
| `npm ci` | PASS | Node `24.12.0`、npm `11.6.2`，安裝 558 packages |
| `tsc --noEmit --incremental false` | PASS | TypeScript 無錯誤 |
| `npm run build` | PASS | Vinext production build 完成；有非阻斷 route classification warning |
| `npm run lint` | FAIL | 19 項；集中在未使用 UI scaffold，詳見 known limitations |
| `npm test` / `npm run validate` | PASS | Toolspack 副本新增零依賴靜態契約測試；可在 CI 未安裝套件時執行 |
| Inline script syntax / tool contract | PASS | script 可解析；辨識 8 個工具與必要 workflow |
| Source canonical blob parity | PASS | 原 80 個 Git 追蹤檔中 79 個相同；只有 `package.json` 新增 release scripts |
| Desktop / mobile / light / dark | PASS | Chromium headless 視覺與可及性 snapshot；console/page errors 為空 |
| 人類按鈕「開始新棋局」 | PASS | 實際 scroll + pointer click 後 boardVersion 增加 |
| 公開 helper 決策後落子 | PASS | `publish_agent_decision → place_stone` 成功，棋盤增加 1 子 |
| stale approval 回歸 | FAIL / 已知 P1 | v1 建立核准、v2 落子、舊核准使 v3 清盤 |
| 原生 ChatGPT WebMCP | NOT RUN | QA Chromium 沒有 `document.modelContext`，不可宣稱 8 工具實機註冊成功 |
| 外部部署網址 | NOT RUN | 沒有把本機 build 推論成線上內容已更新 |

## Release 前重跑

```powershell
npm ci
npm test
npm run typecheck
npm run build
npm run lint
```

前四項必須通過。lint 的已知失敗與原生 WebMCP `NOT RUN` 是本版維持 Preview 的原因，不能省略或改寫為成功。
