# 來源與授權｜W38 v0.1.1

## 本次採用的輸入

- 使用者更正的原始檔：`video-understanding2.rar`
- 原始檔大小：85,426 bytes
- SHA-256：`a9c388a03cfdab6e4f341be599d5ddbfd0b3d1b46d405225d3f007b4e94aa260`
- RAR 根路徑：`video-understanding/video-understanding/`
- 日期：2026-09-17

本次重新核對全部 17 個檔案：13 個文字來源，以及 4 個 Python 編譯快取。文字內容已閱讀；快取僅做檔案盤點與雜湊，未執行，未納入分發。原始 RAR 保持不變。

## 發布對應

| RAR 檔案 | v0.1.1 處理 |
| --- | --- |
| SKILL.md | 保留功能內容，移除文末對未附授權檔的引用 |
| agents/openai.yaml | 保留內容 |
| assets/ 下 2 個模板 | 保留內容 |
| references/ 下 3 個方法文件 | 保留內容 |
| scripts/ 下 2 支 Python 程式 | 保留程式 |
| tests/ 下 2 支 Python 測試 | 保留測試 |
| .gitignore | 保留內容 |
| VALIDATION.md | 依本次可重跑結果重新編寫；原始歷史敘述不充當本次驗證 |
| scripts／tests 的 4 個 .pyc | 排除可再生快取 |

其中 11 個檔案以換行正規化後的完整文字比對 RAR，內容一致。SKILL.md 僅移除文末授權檔引用，其餘內容一致。發布過程可能將 CRLF 轉成 LF，因此原檔 byte hash 與發布 hash 可不同。

W38 的 README、lesson、metadata、docs 與技能 README 是本次重新編寫的學員文件。依使用者指定，本版刪除 LICENSE／NOTICE，下載包也不附根目錄 LICENSE。上一版額外引入的兩份 Hypit 研究文件、安全附加指令與合成示例已從目前版本移除，歷史版本仍可查閱。

## 原始文字檔 SHA-256

以下數值屬 RAR 解出的原始 bytes：

```text
ef09dc3e481e25e36a09fb2ff57699e7ac6b4704710a21fb1e74782c199ebaf8  .gitignore
4cfff180a12a53b3c56302dff9f6f24a49b8daae415776e87308af117a20e3dd  SKILL.md
0d7b5d2777f9777e6fe1e5bfc55133d351aebab40803180a9b5e2ddc8a915b85  VALIDATION.md
c8eb64b1d9e363ab99fbcb954a3bd935f2eb2aac31c8078ed99905450f160006  agents/openai.yaml
d07960707409c46ffbb6eb968e6491e6cfe8bb04a3126c7ca1d229db4c9065a4  assets/analysis.template.json
cbf8f6452a8d1d2dc6eff9d219928bb3789cf30fb333165d8b09837559ebd3a7  assets/VIDEO_UNDERSTANDING.template.md
f7491b3b42012ba35d631802d0711b2a29fd0dfec631e59d8402ad1e7ae6497b  references/handoff-contract.md
bd5c6d9a07aac94ca7a956aa01e1da322fb277a14d9c5581941005f679bd08dd  references/observation-method.md
25b545ce8302fbfca95e59f64daa9cf861f4087bb4653c528d773faf486307eb  references/tooling.md
b23e24cf0e62571b8270bc8f13bbfa89429a2feec2a1ca86f126b176413a27d2  scripts/prepare_video.py
4142074b7ef826a5bd25b89fadb3c130989a2814a17272afcbc7a53ba436d967  scripts/validate_analysis.py
736769c0504ba313e1093df12a2ed2b6be4dfb7bc2f001af45a7654c5898360e  tests/test_prepare_video.py
a86617ade841d3e35c439dd9cea39473ddcc064174ad51fef0f051711aa13105  tests/test_validate_analysis.py
```

## 來源紀錄與授權欄位

RAR 未附 LICENSE／NOTICE；依使用者後續指示，本次包裝也不保留前版補入的兩個檔案，並同步清除對這些檔案的連結。

既有通知記錄的方法來源為 Hypit，曾研究的 revision 為 `d68fe605c7eecbdadbfa7fa8df0a8dee59d6db66`。此資訊來自既有版本；本次未重新查核上游網站，也沒有加入上游 runtime 或生成程式。

本版 metadata 的 license 設為 unspecified，include_root_license 設為 false；沒有在此套用 MIT、Apache 或宣告新的使用授權。授權檔的刪除屬包裝變更，原始來源紀錄保留於上段。
