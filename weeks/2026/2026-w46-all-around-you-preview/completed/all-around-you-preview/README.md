# All Around You Preview｜下載與安裝交接

[W46 學員入口](../../README.md)提供 Release 下載連結與練習步驟。[download-manifest.json](download-manifest.json)記錄版本、檔名、大小與 SHA-256。

本目錄為教材及安裝交接資料，不包含 EXE／`_internal`。請從 W46 Release 下載具完整產品名稱的 Windows x64 ZIP，保留原包的所有檔案。ZIP 內的 AGENTS.md 是學員解壓後的安裝入口，不在本教材目錄另放一份。

- [AGENT_INSTALL.md](AGENT_INSTALL.md)：完整安裝、備份、命令、驗收與還原手冊。
- [README-FIRST.md](README-FIRST.md)及[使用指南](使用指南.md)。
- [profile.example.json](profile.example.json)：佔位範例，不能直接套用。
- [LICENSE.txt](LICENSE.txt)與[VB-CABLE-NOTICE.md](VB-CABLE-NOTICE.md)：來源與第三方歸屬。

`package.json`／`tests/` 只供 Toolspack 的離線分發契約檢查，不是程式執行依賴。執行 macOS／Linux 不在目標內；Windows 學員不需安裝 Node.js 或 Python。
