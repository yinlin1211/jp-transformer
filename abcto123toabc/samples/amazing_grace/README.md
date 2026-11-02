# Amazing Grace — 单曲渲染样例

完整歌曲，**无和弦叠音**，因此包含在 `abcto123toabc` 的“不计和弦叠音”100% 统计里。带歌词、三连音、延音/连音。

| 文件 | 说明 |
|---|---|
| `source.abc` | 原始 ABC |
| `score.123` | ABC → 123 |
| `roundtrip.abc` | ABC → 123 → ABC |
| `jianpu.png` | Dolce 渲染 123 的简谱 |
| `staff_original.png` | abcjs 渲染原始 ABC 的五线谱 |
| `staff_roundtrip.png` | abcjs 渲染往返 ABC 的五线谱 |

## 已知差异

往返后的第一个歌词前多出段号 `1.`（`staff_roundtrip.png` 可见）；原始 ABC 渲染没有这个段号。音高、时值、三连音和连音线不变。
