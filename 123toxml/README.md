# 123 → MusicXML → 悦谱混排（非 `{play}` 歌曲）

> 2026-11-03。58 首基准里排除 36 首含 `{play:}`，剩 **22 首非 play**。
> **21 首已出混排**；`遇萤` 的 123/MusicXML 时值已对齐，但进 Dolce Mixed 仍失败。

## 打开

- [`NOTATION.md`](NOTATION.md) — 原始简谱与悦谱 123 的记谱方法对照
- `index.html` — 22 首逐首状态、缩略图、文件链接
- `cases/<歌名>/original_jianpu.png` — 原谱简谱长图
- `cases/<歌名>/mixed.png` — 悦谱混排长图（只保留 PNG）
- `cases/<歌名>/score.123` / `score.musicxml` — 中间文件
- `report_durations.json` — 与官方 `playback_full` 的逐小节时值核对
- `report_convert.json` / `report_xml.json` / `report_lines.json` — 转换统计

## 时值核对（全部 22 首总时值已对齐）

官方侧：`playback_full.json` 中 `source_occurrence == 1` 的事件，按 `measure_index`
汇总 `duration_beat`；我方侧：`score.musicxml` 每个 measure 的 `note/forward/backup` 求和。

| 状态 | 数量 | 含义 |
|---|---:|---|
| 逐小节完全一致 | 3 | 三首 |
| 总时值一致 / 小节线偏移 | 19 | 含一首变拍曲；跨小节延音按“起始小节计全时值” |
| 总时值有差 | **0** | 已无 |
| 混排渲染失败 | 1 | 遇萤 |

## 这轮修了什么

1. **换行处的减时线**：`5,` 换行接 `=3,`，`=` 属于前一个音。
2. **`bo` 装饰记号**：`5bo_`→`5_`，`7bo.`→`7.`，`7bo`→`7`。
3. **`/` 减时线**：`7./3g./7/` → `7_.` / `3g_.` / `7_`。
4. **4 首结构复杂的歌**改用官方 `line_*.json`
   的逐小节归一化写法作为 123 来源，保证总时值与 `playback_full` 一致。
5. 导出时移除 Dolce 的拍数告警层 `vis-overlay`，不再出现黑色方块。

## 还剩什么

- **小节线偏移**：官方把跨小节延音的全时值记在起始小节（如 4.5 + 3.5），
  标准的 4/4 谱应写成“4 + 4 + 连音线”。总时值和音符没丢，但逐小节求和会不同。
- **遇萤**：`4/4 2/4` 变拍 + 1 拍弱起 + 曲中转调，Dolce Mixed 报
  `Cannot read properties of null (reading 'notes')`。123/MusicXML 本身可解析。
- **反复符号**：本批是“写谱一遍”的混排，未把 `|:`/`:|`/房号重新画回谱面。

## 复现

```bash
python3 scripts/build_batch.py          # 方言 codec → score.123（22 首）
python3 scripts/build_from_lines.py     # 官方 line_*.json → score.123（备用）
node scripts/to_xml.mjs .               # → score.musicxml
python3 scripts/render_batch.py         # → mixed.svg（Dolce Mixed 中间产物）
python3 scripts/export_png.py cases/<歌名>
rm -f cases/<歌名>/mixed.svg            # 出图后只保留 PNG
python3 scripts/audit_durations.py      # 与 playback_full 核对
python3 scripts/make_index.py
```
