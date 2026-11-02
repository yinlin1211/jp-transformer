# jp-transformer

简谱 / ABC / 123 转换与渲染实验仓库。

## abcto123toabc

ABC → 123 → ABC 往返实验，测试集为 30 个 ABC。

- 数据：`abcto123toabc/data/abc/`
- 准确率：**不计和弦叠音，6795 / 6795 个非和弦音符完全一致（100%）**；29/29 个含非和弦音符的文件通过
- 画廊：`abcto123toabc/index.html`
- 详细说明：`abcto123toabc/README.md`

### 数据构成

- 15 个语法夹具（`accents`、`accidentals`、`bar-lines`、`beams`、`broken-rhythm-markers`、`chords`、`chord-symbols`、`grace-notes`、`keys-and-modes`、`lyrics`、`note-lengths`、`notes-pitches`、`ties-and-slurs`、`tuplets`、`unit-note-length`）
- 14 个真实曲目文件（11 首；Amazing Grace 2 版、Jericho 3 版）
- 1 个 SATB 测试谱（`satb-absolute-pitching`）

数据来自 Alex 的 `abc2kern/data/abc/`，原始出处为 abcnotation.com examples 等示例。

### 统计口径

- 比较 `(onset, duration, MIDI pitch)`
- **不计和弦叠音**：简谱不显示和弦堆，123 只保留最高音
- 歌词文本不在该口径内
- `chords.abc` 全是和弦堆，没有非和弦音符，因此没有统计对象

### 已知限制

- 具名多声部（`V:P1` / `V:S`）会被合并/顺序化；数字声部（`V:1` / `V:2`）可保留
- 和弦叠音、歌词分段、段号 `1.` 属于简谱/文本层的预期差异
- abcjs 会忽略部分 ABC 装饰；Dolce 五线谱保留跳音点

## 复现

```bash
cd abcto123toabc
node scripts/make_cases.mjs
node scripts/check_accuracy.mjs
```
