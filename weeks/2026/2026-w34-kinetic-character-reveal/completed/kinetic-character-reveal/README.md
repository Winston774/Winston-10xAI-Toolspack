# Kinetic Character Reveal Skill

把高密度的 motion-graphics 角色登場提示詞轉成可重複利用的視覺系統。

## 它能做什麼

- 從參考提示詞抽取 Style DNA
- 分離 HARD／CONTROLLED／FREE 約束
- 產生極貼近原作的 Faithful 版本
- 產生同系列但換角色、色盤與動作家族的 Series 版本
- 產生較大幅度的 Remix 版本
- 驗證 cut 數、時間軸、角色一致性、色盤與風格漂移

## 安裝到 Codex

### Codex 個人技能目錄

Windows：

```text
%USERPROFILE%\.codex\skills\kinetic-character-reveal\
```

macOS / Linux：

```text
~/.codex/skills/kinetic-character-reveal/
```

使用共用 Agent Skills 目錄的環境，也可以放到 `%USERPROFILE%\.agents\skills\kinetic-character-reveal\` 或 `~/.agents/skills/kinetic-character-reveal/`。

### 單一專案技能

把整個資料夾放到：

```text
<repo>/.agents/skills/kinetic-character-reveal/
```

確認 `SKILL.md` 位於技能資料夾根目錄。若 Codex 尚未顯示技能，重新啟動 Codex。

## 呼叫方式

```text
$kinetic-character-reveal
請分析下面的參考影片提示詞，先輸出 Style DNA 與 HARD／CONTROLLED／FREE 約束，再產生一個同系列的新版本。
```

```text
$kinetic-character-reveal
模式：SERIES
角色：冷靜的女性 roller-skater
品牌字：RX
色盤：ultraviolet / magenta / white / silver / black
保留：13 cuts、15 秒、24fps、80/20、角色一致性
```

```text
$kinetic-character-reveal
模式：AUDIT
檢查 prompt.md，修正所有時間軸、角色漂移、重複構圖與風格稀釋問題。
```

## 驗證腳本

```bash
python scripts/validate_prompt.py examples/original-ao-prompt.txt
```

可調整規格：

```bash
python scripts/validate_prompt.py prompt.txt --cuts 12 --duration 18 --fps 24 --aspect 9:16
```

此腳本使用 Python 標準函式庫，不需要額外安裝套件。
