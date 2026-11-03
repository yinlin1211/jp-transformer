# 棠梨煎雪 · 简谱 + 五线谱混排

> 2026-11-03。输入：`raw_jianpu/<song>/source_原始简谱.json`。
> 链路：苍强统一简谱 → 悦谱 123 → MusicXML → 悦谱 Dolce Mixed（五线谱上叠简谱层）→ 单页长图 PNG。

## 成品

| 文件 | 说明 |
|---|---|
| `original_jianpu.png` | 原谱简谱长图 |
| `mixed.png` | 悦谱混排长图（只保留 PNG） |
| `score.123` | 苍强简谱转出的悦谱 123 |
| `score.musicxml` | 五线谱侧 MusicXML |
| `preview.html` | 本地预览 |

## 谱面事实

| 项目 | 值 |
|---|---|
| 调号 / 拍号 / 速度 | 1=C / 4/4 / ♩=72 |
| **写谱** | **44 小节** |
| 发声音符 | 221（其中 3 个连音在 MusicXML 里合并，XML 218） |
| 歌词 | 205 个字 + 16 个空槽 = 221 |
| 反复 | `|:` 第 10 小节，`:|` 第 34 小节，反复段 10–34 |
| **演奏展开** | **69 小节**（1–34 + 10–34 + 35–44） |
| 与官方 playback 对照 | 官方 `playback_full.json` 也是 69 小节、♩=72 |

## 本轮修的三处

1. **反复记号不再被吃掉**  
   旧 codec 把 `|:`/`:|` 拆成 `|` + raw `:`，记成 loss。本目录 `jp123_bidir_tangli.py` 增加了 `|:`、`:|`、`]:|`、`]|||` 的识别，123 与 MusicXML 都能带 `<repeat>`。

2. **`{hot}` 不是 Coda**  
   源 runtime 里 `{hot}` 是配置开关（`case "hot": config[t]=1`），不是反复记号。旧 codec 映射成 `!coda!`，会在谱首画一个 Coda。本轮改为丢弃并记 `tag-dropped:hot`。

3. **歌词空槽用 `/`，不是字面空格**  
   源歌词里的 `_` 是“这个词空着但占一个音符槽”。123 的 `w:` 里：
   - `_` = melisma（延长前一个字）；
   - `/` = 跳过一个音符、不配字（**空白且占槽**）；
   - 字面空格 = 分词，**不占槽**，会把后面的字整体前移。  
   所以本轮把歌词里的 `_` 统一转成 `/`。谱面渲染同样是空白，且 205 字 + 16 空槽 = 221 音，逐槽对齐。

## 已知边界

- 本曲没有 `{play}` / 段落标签，所以不涉及 `I:playorder`。混排是**写谱 44 小节**，反复用 `|:` / `:|` 表示；不是展开后的 69 小节。
- 若需要“按演奏顺序展开的 69 小节混排”，需要先按 `playItems` 展开再排一版。
- 源 JSON 无 bpm；本谱取官方 `playback_full.json` 的 ♩=72。
- `jp123_bidir_tangli.py` 是任务内副本，尚未回灌共享 codec；回灌前需重跑 10,965 段回归。

## 复现

```bash
python3 make_score.py          # 原始 JSON → .123
node to_xml_tangli.mjs         # .123 → .musicxml + timeline
python3 render_mixed.py        # MusicXML → 混排 SVG（Dolce Mixed，长图）
python3 ../scripts/export_png.py .        # → mixed.png（只保留 PNG）
```
