# Deck Atelier｜技能目錄

完整學員入口與安裝方式見 [W43 README](../../README.md)。此資料夾可整包複製到宿主的技能目錄；請保留所有相對路徑。

- [SKILL.md](SKILL.md)：Agent 的技能入口。
- `references/`：匯入、敘事、版型、圖解、動態與 QA 六份參考資料。
- `assets/engine/`：HTML 簡報 CSS／JavaScript 引擎。
- `assets/templates/`：新建簡報的模板。
- [Attention 範例](examples/attention/deck.html)與[故事線](examples/attention/storyline.md)：15 頁圖解簡報。
- `scripts/`：來源匯入、簡報新建、風格切換、CJK 分詞、單檔建置與瀏覽器截圖／PDF。
- `tests/`、`package.json`：本週額外加入的離線分發契約測試。

不必執行 `npm install`。離線契約測試使用 Node.js 22+ 與 Python 3.10+，在此目錄執行 `node --test tests/distribution.test.mjs`；CI 使用 `npm run validate`。這些測試不會驗證所有來源格式、安裝宿主或呼叫模型。

建置與 QA 的完整依賴、範例指令、外部連線及覆寫行為請先閱讀[安裝說明](../../docs/setup-and-dependencies.md)和[隱私說明](../../docs/privacy-and-content-rights.md)。來源未附授權檔，不因放進 Toolspack 而取得新的授權。
