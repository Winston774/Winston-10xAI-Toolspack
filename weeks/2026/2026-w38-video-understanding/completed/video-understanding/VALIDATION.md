# 驗證紀錄：來源與本週 Release

## 來源範圍

本週收到的 `video-understanding.zip` SHA-256 為：

```text
2E2BA1EF39F202B717CF5F2279FC882E4342F87244AC4B1E6C31DE68E20F9CEB
```

其中有 10 個檔案：技能入口、agent metadata、兩份 templates、三份 reference 與兩支 Python script。它未含 `LICENSE`、`NOTICE`、兩份 Hypit 研究 reference、tests 或 `.gitignore`，使技能連結、授權與原始驗證敘述無法在原 ZIP 內完整重現。

本週公開包以同名來源工作樹 commit `f5ea07ee11b005e6628b5a7f73718ce230b945a3` 的可追溯補充檔為基礎，加入：

- `LICENSE`、`NOTICE`。
- `references/hypit-architecture.md`、`references/hypit-method.md`。
- `tests/test_prepare_video.py`、`tests/test_validate_analysis.py`。
- `README.md`、安全／隱私說明、合成範例與本週教學文件。

本週也在 `SKILL.md` 補上本機輸入、外部傳輸確認、公開分享與未信任資料邊界。它沒有加入 Hypit runtime、生成程式、真實影片、畫格、WAV、逐字稿或作者私有輸出。

## 來源端歷史紀錄

來源作者在 2026-09-17 的 Windows、Python 3.11、FFmpeg／FFprobe 7.1.1 環境記錄：30 個測試通過，含 7 個真正執行 FFmpeg／FFprobe 的媒體整合案例。這是歷史開發結果，不能直接視為每位學員電腦的驗證結果。

來源作者端另記錄過 112 個固定 Hypit commit 引用與 12 個本地研究連結的檢查。該檢查使用作者的私有 `.work/upstream` 快取，快取未隨 Release 發布；學員可閱讀已收錄的兩份研究筆記與其固定連結，卻無法在本包內重跑同一個快取檢查。

## 本週可重跑的驗證

在本技能根目錄執行：

```powershell
python -B -X utf8 -m unittest discover -s tests -v
python -B -X utf8 -c "from pathlib import Path; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in [Path('scripts/prepare_video.py'), Path('scripts/validate_analysis.py')]]; print('AST_COMPILE_OK')"
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .
python -X utf8 scripts/validate_analysis.py examples/partial-analysis/analysis.json
```

若要啟用媒體整合測試，先設定兩個指向受信任本機工具的環境變數：

```powershell
$env:VIDEO_TEST_FFMPEG = '<absolute-path-to-ffmpeg>'
$env:VIDEO_TEST_FFPROBE = '<absolute-path-to-ffprobe>'
python -B -X utf8 -m unittest discover -s tests -v
```

未設定變數時，test discovery 仍會發現 30 個測試，但 7 個媒體整合案例會標示 `skipped`。只有 23 個純 Python tests 的結果可被視為已通過；`skipped` 必須保留在報告中。

## 本週發布前實測

2026-09-17 在 Windows、Python 3.11.15、FFmpeg／FFprobe 8.0.1 的本機環境完成下列檢查：

| 檢查 | 結果 | 範圍 |
| --- | --- | --- |
| `python -B -X utf8 -m unittest discover -s tests -v` | 30 passed，0 skipped | 7 個 FFmpeg／FFprobe 合成媒體整合案例、7 個 helper unit tests、16 個交接索引 validator tests |
| Python AST compile | `AST_COMPILE_OK` | `scripts/prepare_video.py`、`scripts/validate_analysis.py`；不寫入 `__pycache__` |
| skill-creator quick validator | `Skill is valid!` | `SKILL.md` frontmatter、名稱與 scaffold 檢查 |
| 合成 partial 範例 | `VALID (partial)` | JSON 結構、時間、引用與 handoff 規則 |
| Toolspack repository validator | `Repository validation passed.` | 週次結構、metadata、Catalog、skill reference、禁止檔案與常見 secret pattern |

整合測試只使用 `testsrc2` 與 `sine` 產生的暫存合成媒體，沒有使用或上傳真實影片。上述測試也沒有驗證跨平台相容性、真實影片的視聽品質、來源權利或任何外部服務。

## 結構與視聽的界線

`examples/partial-analysis/analysis.json` 可通過結構驗證，但它沒有真實影片或 evidence。這個設計用來演示 JSON 形狀與 `partial` handoff；它不構成視覺、音訊、語義或生成品質證據。

同樣地，`validate_analysis.py` 的成功輸出只檢查資料結構、時間、引用、檔案與狀態規則。真正的畫面、聲音、抽樣密度、敘事理解、權利和發布決策仍需由使用者與執行 Agent 覆核。
