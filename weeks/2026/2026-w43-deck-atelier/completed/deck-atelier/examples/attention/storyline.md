# Attention Is All You Need — 論文導讀
Audience: 對 AI 有興趣、但不一定是機器學習專家的聽眾（教師、學生、工程師、主管）
Occasion: 15–20 分鐘的論文導讀 · Length: 15 slides · Language: 繁體中文（保留英文技術名詞）
Source: Vaswani et al. (2017), arXiv:1706.03762 v7 — `source/source.md`

Governing thought: 只靠注意力，Transformer 做到了更快、更準，也更能擴展。

SCQA:
- S — 2017 年，翻譯等序列任務由 RNN／LSTM 主導。
- C — 它們逐字計算：無法平行（慢），遠距離資訊要層層轉手（健忘）。
- Q — 能不能完全拿掉循環，只靠注意力？
- A — 可以：Transformer 更快、更準，而且簡單到能一路擴展成今日的 LLM。

Key lines (chapters): 01 困境 · 02 機制 · 03 成果 · 04 影響

| # | Chapter | Action title | Layout | Exhibit / visual | Source |
|---|---|---|---|---|---|
| 1 | — | (cover) Attention Is All You Need：拿掉循環，只留注意力 | cover | attention arcs, its → Law (foreshadows slide 7) | — |
| 2 | 摘要 | 只靠注意力，Transformer 做到了更快、更準，也更能擴展 | points ×3 | — | Abstract, §6.1, Table 2 |
| 3 | 目錄 | 四個問題，帶你讀懂這篇論文 | agenda 2×2 | — | — |
| 4 | 01 困境 | 2017 年的主流模型，必須一個字、一個字地讀 | split | RNN chain h1…h6 over "The Law will never be perfect" | §1 |
| 5 | 01 困境 | 逐字計算帶來兩個瓶頸：慢，而且健忘 | exhibit ×2 + takeaway | sequential ops O(n)→O(1); path length O(n)→O(1) | Table 1 |
| 6 | 02 機制 | 如果每個字，都能直接看見句子裡的每一個字？ | statement (invert) | all-to-all arcs | — |
| 7 | 02 機制 | 模型讀到 its 時，會自己回頭看向 Law | exhibit | arcs from its; weights 59% / 17% (illustrative) | Figure 4 |
| 8 | 02 機制 | 注意力是一次檢索：用 Query 比對每個 Key，取回 Value | three columns | scores → softmax → mix (illustrative) | §3.2.1 |
| 9 | 02 機制 | 整個機制，濃縮成一行公式 | formula + 4 annotations | softmax(QKᵀ/√dₖ)V | Eq. (1) |
| 10 | 02 機制 | 八個注意力頭，同時從八個角度閱讀同一句話 | split | 8 heatmaps → concat → linear; −0.9 BLEU with one head | §3.2.2, Table 3(A) |
| 11 | 02 機制 | 沒有循環就沒有順序，於是用波形替每個位置蓋上印記 | split | 5 sinusoids, reading line at pos 26 | §3.5 |
| 12 | 02 機制 | 把積木疊起來：6 層編碼器，加上 6 層解碼器 | notes + figure + notes | Figure 1 redrawn; builds: encoder → decoder → cross-attention | Fig. 1, §3.1, Table 3 |
| 13 | 03 成果 | 更準，也更省：以一小部分的訓練成本，刷新翻譯紀錄 | chart + stats | cost (log FLOPs) vs BLEU EN→DE; 28.4 / 41.8 / 3.5 days | Table 2, §5.2, §6.1 |
| 14 | 04 影響 | 一篇翻譯論文，成了今日 AI 的共同骨架 | timeline + stat | 2017 → GPT·BERT → GPT-3 → ViT → ChatGPT → LLMs; 29 萬次引用 | model papers; Google Scholar (2026-10); Nature 2025 |
| 15 | 結語 | Attention is all you need.（三個帶得走的觀點） | closing (invert) | — | — |

Notes on facts
- EN→FR: the abstract and Table 2 report 41.8; §6.1 still says 41.0 (left over from v1). The deck uses 41.8.
- "Base model beats all previous models" holds for EN→DE only (27.3 vs 26.36); EN→FR base is 38.1.
- Slides 7–8 use illustrative weights (59/17/5/4/3/12 %), consistent with softmax of the shown scores; both slides say so.
- Citations: 291,810 on Google Scholar (Vaswani profile, fetched 2026-10-18) → 「29 萬」; Nature (2025) ranks it #7 most cited of the 21st century.
