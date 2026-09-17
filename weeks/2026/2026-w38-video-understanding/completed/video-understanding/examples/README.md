# 範例

`partial-analysis/` 是全合成、沒有影片、音訊、畫格或逐字稿的最小結構範例。它示範如何在資料不完整時，以 `partial`、阻塞未知項與下一步交接，而不假裝已有視聽證據。

在技能根目錄驗證它：

```text
python scripts/validate_analysis.py examples/partial-analysis/analysis.json
```

預期輸出：

```text
VALID (partial): structure only; audiovisual and semantic quality not verified
```
