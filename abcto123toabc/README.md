# ABC → 123 → ABC 转换与渲染对比

测试集：`data/abc/` 下 30 个 ABC（15 个语法夹具 + 14 个真实曲目文件 + 1 个 SATB 测试谱）。
转换链路：`ABC → parseAbc → emit123 → parse123 → emitAbc → parseAbc`（Dolce `out/cli/j123.js`）。

## 数据

`data/abc/` 的 30 个文件来自 Alex 的 `abc2kern/data/abc/`，原始出处为 abcnotation.com examples 等示例。

- **15 个语法夹具**：`accents`、`accidentals`、`bar-lines`、`beams`、`broken-rhythm-markers`、`chords`、`chord-symbols`、`grace-notes`、`keys-and-modes`、`lyrics`、`note-lengths`、`notes-pitches`、`ties-and-slurs`、`tuplets`、`unit-note-length`
- **14 个真实曲目文件（11 首）**：Amazing Grace（2 版）、Bad Apple、Ding Dong、Dusty Miller、Jericho（3 版）、Kesh、Kitchen Girl、Morning Star、Old Sir Simon、Paddy O'Rafferty、Speed the Plough
- **1 个 SATB 测试谱**：`satb-absolute-pitching`（标题为 `TEST: Vocal SATB score.`）

## 目录

| 目录 | 内容 |
|---|---|
| `data/abc/` | 30 个 ABC 源文件 |
| `alex123/` | 从原始 ABC 生成的 123（Dolce `emit123`） |
| `rt_abc/` | ABC→123→ABC 往返后的 ABC（表头已调整为 `K:` 最后，供 abcjs 渲染） |
| `direct_abc/` | 原始 ABC 副本 |
| `jianpu/` | Dolce 直接渲染 123 的简谱截图（6 个代表例） |
| `staff_dolce/` | Dolce 由 123 投影的五线谱截图 |
| `mixed_dolce/` | Dolce 混排截图（部分样例） |
| `direct_abcjs/` | abcjs 渲染原始 ABC 的五线谱 SVG/PNG |
| `staff_abcjs/` | abcjs 渲染往返 ABC 的五线谱 SVG/PNG |
| `index.html` | 6 个代表例的四联对比页 |
| `scripts/` | 批量生成与统计脚本 |

## 准确率（不计和弦叠音）

统计口径：`(onset, duration, MIDI pitch)`，原始 ABC vs ABC→123→ABC；**不计和弦叠音**（简谱不显示和弦堆，123 只保留最高音）。歌词文本不在该口径内。

| 口径 | 音符事件 | 文件级 |
|---|---:|---:|
| 非和弦音符 | **6795 / 6795 = 100.00%** | **29/29（含非和弦音符的文件）** |

结论：**不计和弦叠音时，ABC↔123 的音符和时值无损。**

> `chords.abc` 全部是和弦堆，没有非和弦音符，因此在该口径下没有统计对象。

## 已知限制

- **具名多声部会被合并/顺序化**：`V:P1`、`V:S` 这类具名声部在当前 ABC 解析中不会保留为并行声部；`V:1` / `V:2` 数字声部可以保留（Amazing Grace 双声部正常）。
- `ding-dong` 是具名 4 声部，ABC→123→ABC 后不再有 `V:`，abcjs 渲染出的 4 行是顺序系统，不是 4 个同时声部。
- **和弦叠音**不参与统计：123 没有和弦堆，只保留最高音，这是简谱显示口径下的预期行为。
- 歌词文本仍有差异：`lyrics.abc` 的 `syl-la-ble` 会被拆成三个歌词事件；`amazing_grace` 的段号 `1.` 会被当成第一个歌词。
- abcjs 会忽略 `!staccato!` 等部分装饰；Dolce 五线谱会保留跳音点。

## 渲染结论（6 个代表例）

代表例：`accents`、`ties-and-slurs`、`amazing_grace`、`ding-dong`、`bad_apple`、`jericho-(chord-symbols)`。

- abcjs 直出 vs 往返的音符数全部一致：8/8、17/17、43/43、242/242、737/737、73/73。
- Dolce 五线谱对单声部/带和弦符号的谱效果良好：Jericho 正确显示 `Dm/A7`、`Fine`；Bad Apple 连音/三连音正常；Amazing Grace 歌词和三连音正常。
- 简谱视图不显示和弦符号（Dolce 五线谱视图会显示）。
- `ding-dong`（具名 4 声部、`M:none`）的 Dolce Staff 按钮未切换，仍停留在简谱；abcjs 能出 4 行，但它们是顺序系统，且歌词重叠。
- 图片中红色框是自动化点击留下的选中态，不是渲染错误。

## 环境与复现

- Dolce: `TENOR/vendor/dolce/out/cli/j123.js`
- abcjs 6.7.1 + jsdom 29.1.1: `local_jianpu_abc_demo/scripts/render_abc.js`
- 简谱/五线谱截图：Dolce Vite app（`npx vite --port 5180`）+ Playwright Chromium

```bash
# 1. 生成全部 30 个 123 与往返 ABC
node scripts/make_cases.mjs

# 2. 统计不计和弦叠音的音符准确率
node scripts/check_accuracy.mjs

# 3. 渲染 abcjs 五线谱（需要 local_jianpu_abc_demo 的 abcjs 环境）
ABC_RENDERER=/path/to/local_jianpu_abc_demo/scripts/render_abc.js \
  bash scripts/render_abcjs.sh
```
