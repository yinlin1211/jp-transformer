# 原始简谱 → 悦谱 123 记谱方法

> 本文说明两件事：
>
> 1. **我们的原始简谱**（苍强统一简谱 DSL）长什么样、每个符号什么意思；
> 2. 它怎样映射到 **悦谱 123**，再进入 MusicXML / Dolce Mixed。
>
> 代码实现见 `scripts/jp123_bidir.py`（双向 codec）与 `scripts/build_batch.py`（批量入口）。

---

## 0. 一句话对照

| 层 | 名称 | 形态 | 谁消费 |
|---|---|---|---|
| 源 | 原始简谱（苍强 DSL） | `songdata.notation` 字符串 + `lyric` 字段 | 我们的 `website_renderer` / `playback_full` |
| 中 | 悦谱 123 | `X:1 / K:1=E / M:4/4 / Q:1/4=…` 的文本 | Dolce 的 `parse123` |
| 中 | MusicXML | 标准谱面 XML | Dolce Mixed / 其他五线谱工具 |
| 出 | PNG | 长图 | `original_jianpu.png`（原谱）、`mixed.png`（混排） |

原始简谱是**我们自己的 DSL**，不是印刷简谱的图片；悦谱 123 是 Dolce 能读懂的一种**简化 ABC 方言**。

---

## 1. 原始简谱（苍强统一简谱）

### 1.1 音高

| 写法 | 含义 |
|---|---|
| `1`–`7` | 唱名 do–si |
| `0` | 休止 |
| `8` / `9` | `jie`（有声无音高 / 节奏音）、`kong`（空音节槽），codec 内部用 |
| `1g` / `1gg` | 高八度 / 高两个八度 |
| `1d` / `1dd` | 低八度 / 低两个八度 |
| `1,` | 低八度（另一种方言写法，codec 与 `d` 等价归一） |

> 例：`6,.` = 低八度的 6 + 附点；`1g_` = 高八度的 1 + 一条减时线。

### 1.2 时值

| 写法 | 含义 |
|---|---|
| `5` | 一拍（四分音符） |
| `5_` | 一条减时线（八分音符） |
| `5__` | 两条减时线（十六分音符），也写作 `5=` |
| `5.` | 附点 |
| `5..` | 双附点 |
| `5-` | 增时线 / 延音（延长一个单位） |
| `5 - -` | 总共三拍 |

> 归一规则：`x` 视为 `_`，`d` 视为 `,`；`=` 按两条减时线计。
> 换行只是排版：`5,` 换行接 `=3,` 时，`=` 属于前一个音。codec 会先合并换行（记 `linebreaks-joined`）。

### 1.3 变音

| 写法 | 含义 |
|---|---|
| `7b` / `3#` | 后置降号 / 升号 |
| `b3` / `#4` | 前置变音号（**源 runtime 实测会忽略前置写法**；codec 会把它挪到前一个音或记 loss） |

### 1.4 连音线、圆滑线、倚音

| 写法 | 含义 |
|---|---|
| `( ... )` | 圆滑线 / 同音连音组 |
| `(t: ... )` | 强制同音连音组（`t` 标记本身不写入 123） |
| `(3: ... )` | 三连音等 tuplet |
| `( ... )@` | 左倚音：括号里的音是装饰音，后面的音是主音 |
| `@( ... )` | 右倚音：源 runtime 不发声，codec 直接丢弃（记 `right-ghost-dropped`） |

### 1.5 小节线、反复、房号

| 写法 | 含义 |
|---|---|
| `\|` | 小节线 |
| `\|\|` | 双小节线 |
| `\|]` | 终止线 |
| `\|\|\|` | 全曲终止 |
| `\|:` / `:\|` | 反复开始 / 结束 |
| `[1:` / `[2:` / `[1,2:` | 一房 / 二房 / 一二房共用 |
| `]` | 房号结束 |
| `{{ ... }}` | 段落 / 反复块（转 123 时线性化，记 `section-block-linearized`） |

### 1.6 记号与标签

**短记号**（直接写在音符旁）：

| 原谱 | 123 | 含义 |
|---|---|---|
| `v` | `!breath!` | 呼吸 |
| `tr` | `!trill!` | 颤音 |
| `mu` | `!uppermordent!` | 上波音 |
| `sd` | `!falloff!` | 下滑音 |
| `st` | `!staccato!` | 顿音 |
| `fe` | `!fermata!` | 延长 |
| `>` | `!accent!` | 重音 |

**花括号标签**：

| 原谱 | 123 | 说明 |
|---|---|---|
| `{bpm:72}` | `Q:1/4=72` | 速度；正文里的 `{bpm}` 是权威值 |
| `{1=E}` / `{2/4}` | `[K:1=E]` / `[M:2/4]` | 行内转调 / 变拍 |
| `{cn:Am7}` | `"Am7"` | 和弦名 |
| `{tip:mf}` | `!mf!` | 力度 |
| `{tip:渐慢}` | `"^渐慢."` | 术语 |
| `{comment:转[1=E]}` | `"^转[1=E]"` | 只作文字，不真的转调 |
| `{octave:N}` | 音高整体移 N 个八度 | 记 `octave-tag-applied` |
| `{dun}` / `{yc}` / `{xh}` | `!staccato!` / `!fermata!` / `!breath!` | 短标签 |
| `{ds}` / `{DS}` | `!D.S.!` | 跳转 |
| `{play:...}` | 不进入写谱 123 | 本轮只做非 `{play}` 歌曲 |
| `{section:...}` / `{ms:...}` | 丢弃 | 段落 / 多段标记 |
| `{hot}` | 丢弃 | 源 runtime 的配置开关，不是 Coda |

### 1.7 歌词

歌词在 `songdata.lyric` 字段，通常是 JSON 数组（一个元素 = 一段歌词）。

| 写法 | 含义 |
|---|---|
| `_` | melisma / 空槽：这个音符不配新字 |
| `/` | 槽位分隔（排版用） |
| `(...)` | 分组（codec 转成 `{...}`） |
| 字面空格 | 分词，不占音符槽 |

> 转 123 时 `_` 统一写成 `/`；`/` 表示“跳过一个音符、不配字，但占一个槽”。

---

## 2. 悦谱 123

悦谱 123 是 Dolce 的输入方言，外形接近 ABC，但用 `1=E` 这种简谱调号。

### 2.1 文件头

```
X:1
T:寄明月
K:1=E
M:4/4
Q:1/4=72
%JIANPU-KEYNOTE:1=E
V:1 clef=treble+8        # 仅 B 主音 / 缺省调号 / 调号带八度后缀时出现
```

| 行 | 含义 |
|---|---|
| `X:1` | 曲目编号 |
| `T:` | 曲名 |
| `K:1=E` | 简谱调号（不是 ABC 的 `K:E`） |
| `M:` | 拍号 |
| `Q:1/4=72` | 速度（四分音符 = 72） |
| `%JIANPU-KEYNOTE:` | 保留原谱调号写法，供反向还原 |
| `%JIANPU-CLEF-SHIFT:` | 谱号八度补偿（往返溯源用） |
| `V:1 clef=treble+8` | Dolce 的谱号八度 |

### 2.2 音符与时值

| 123 | 含义 |
|---|---|
| `1`–`7` | 唱名 |
| `0` / `z` | 休止 |
| `X` / `x` | `jie` / `kong`（节奏音、空槽） |
| `1'` / `1''` | 高八度 / 高两个八度 |
| `1,` / `1,,` | 低八度 / 低两个八度 |
| `1_` | 一条减时线 |
| `1__` | 两条减时线（原谱的 `=` 到这里变成 `__`） |
| `1.` | 附点 |
| `-` | 增时线 / 延音 |
| `~` | 连音 / 延音连接（双附点拆分时会用到） |

> 关键差异：**原谱用 `=` 表示两条减时线，123 用 `__`**。codec 会把 `5=` 写成 `5__`。

### 2.3 变音

| 123 | 含义 |
|---|---|
| `#4` / `b7` | 前置升号 / 降号 |
| `n5` | 还原号（Dolce 侧解析后丢弃，记 `natural-accidental-dropped`） |

### 2.4 连音、倚音、tuplet

| 123 | 含义 |
|---|---|
| `( ... )` | 圆滑线 / 同音连音组 |
| `{ ... }` | 倚音（不发声） |
| `(3: ... )` | 三连音 |

### 2.5 小节线与反复

| 123 | 含义 |
|---|---|
| `\|` | 小节线 |
| `\|\|` / `\|]` | 双线 / 终止线 |
| `\|:` / `:\|` | 反复开始 / 结束 |
| `[1` / `[2` / `[1,2` | 房号 |
| `[\|]` / `.\|` | 不可见小节线 |

### 2.6 记号、和弦、文字

| 123 | 含义 |
|---|---|
| `!trill!` / `!accent!` / `!mf!` | 记号 / 力度 |
| `"Am7"` | 和弦名 |
| `"^渐慢."` | 术语文字 |
| `[K:1=D]` / `[M:2/4]` | 行内转调 / 变拍 |

### 2.7 歌词 `w:`

```
w:穿过了小巷后的/古/街  青墙旁你遥望夕阳斜 / 只因是不经意/的一/瞥…
```

| 写法 | 含义 |
|---|---|
| `字` | 配一个音符 |
| `_` | melisma：延长前一个字 |
| `/` | 跳过一个音符槽（句首前奏常用连续 `/`） |
| 字面空格 | 分词，不占槽 |

---

## 3. 同一段谱的对照

以 `cases/寄明月/score.123` 开头为例：

**原始简谱（节选）**

```
|||00_5__6__5_3_2_1_|6,.(3_3)5,|
 6,.(3_3)2_1_|23_5(3_3_)3_|
 |:2_2__3__2_1_2_3_5_3_|
```

**悦谱 123（节选）**

```
K:1=E
M:4/4
Q:1/4=72
%JIANPU-KEYNOTE:1=E
|] 0 0_ 5__ 6__ 5_ 3_ 2_ 1_ | 6,. ( 3_ 3 ) 5, | 6,. ( 3_ 3 ) 2_ 1_ | 2 3_ 5 ( 3_ 3_ ) 3_ | ... |: 2_ 2__ 3__ 2_ 1_ 2_ 3_ 5_ 3_ | ...
```

可以看到：

- 原谱的 `=3`（两条减时线）在 123 里成了 `3_` / `3__` 这种**重复 `_`** 的写法；
- 原谱 `(...)` 圆滑线在 123 里保持不变；
- 原谱的 `|:` 反复在 123 里同样是 `|:`；
- 原谱的 `6,.`（低八度 + 附点）在 123 里同样是 `6,.`。

---

## 4. 转换管线

```
原始简谱 JSON
  songdata: notation / lyric / keynote / rhythm / bpm
        │
        │  scripts/build_batch.py
        │  scripts/jp123_bidir.py: ours_to_123()
        │    - 换行合并
        │    - bo / slash-as-beam / prefix-accidental 归一
        │    - {play}/{section}/{ms} 过滤
        │    - losses 逐条记录
        ▼
   score.123
        │
        │  scripts/to_xml.mjs  (Dolce j123: parse123)
        ▼
   score.musicxml  +  timeline_123.json
        │
        │  scripts/render_mixed.py  (Dolce Mixed: 五线谱 + 简谱层)
        ▼
   mixed.svg
        │
        │  scripts/export_png.py  (Chrome 1400 px, 2×)
        ▼
   mixed.png          ← 混排成品

原始简谱 JSON
        │  website_renderer/render_svg.js
        ▼
   original_jianpu.png ← 原谱成品
```

批量口径见 `README.md`：

- 58 首基准里排除 36 首含 `{play:}` 的，剩 **22 首非 play**；
- 每首的转换损失在 `report_convert.json` 的 `losses` 里逐条可见。

---

## 5. 有损边界（losses）

转换是**语义优先**，不追求文本逐字一致。常见损失：

| loss | 原因 |
|---|---|
| `play-linearized` | `{play:}` 演奏顺序不展开；本批直接排除含 `{play}` 的歌 |
| `section-markers-dropped` / `section-labels-stripped` | `{section:}`、`A:`/`B:` 段名不进 123 谱面 |
| `linebreaks-joined` | 原谱换行只是排版，codec 合并后 `=` 才能正确归属 |
| `bo-marker-dropped` | `5bo` 的 `bo` 是装饰/半拍写法，不是降号 `b` |
| `slash-as-beam` | `7./` 的 `/` 是一条减时线，不是分隔符 |
| `prefix-accidental-dropped/moved` | 源 runtime 忽略前置变音号，codec 保持发声层一致 |
| `right-ghost-dropped` | 右倚音源 runtime 不发声 |
| `tie-group-marker-dropped` | `(t:` 只用于强制同音连音组，123 保留括号即可 |
| `dots-too-many` | 超过双附点的写法降级 |
| `natural-accidental-dropped` | 123 的 `n` 还原号在 Dolce 侧不承载 |
| `key-b-tonic-octave-shift` / `key-missing-octave-shift` / `key-octave-suffix` | Dolce 与源 runtime 的谱号八度锚点不同 |
| `lyric-group-to-brace` | 歌词 `(...)` 分组转成 123 的 `{...}` |
| `tag-dropped:*` | 123 没有对应构造的标签 |
| `section-block-linearized` | `{{ ... }}` 段落块在 123 里线性化 |

**跨小节延音**：源谱可以写 `5 - - | - -`，123 的 `-` 不能跨小节；codec 会按 123 的限制合并/重排，可能造成逐小节时值偏移，但总时值和音符不丢。

---

## 6. 目录

```
123toxml/
├── README.md              # 批量说明（22 首非 play）
├── NOTATION.md            # 本文：原始简谱 ↔ 悦谱 123
├── index.html             # 逐首状态、原谱/混排缩略图
├── cases/<曲名>/
│   ├── original_jianpu.png
│   ├── mixed.png
│   ├── score.123
│   ├── score.musicxml
│   └── timeline_123.json
├── report_convert.json    # 转换损失 / 头部信息
├── report_durations.json  # 与 playback_full 的逐小节时值核对
├── report_xml.json        # 123 → MusicXML 统计
├── report_lines.json      # 逐首来源与行数
├── render_status.json     # 混排渲染状态
└── scripts/
    ├── jp123_bidir.py     # 苍强 DSL ⇄ 悦谱 123
    ├── build_batch.py     # 批量 源 JSON → score.123
    ├── to_xml.mjs         # score.123 → score.musicxml
    ├── render_mixed.py    # MusicXML → Dolce Mixed → mixed.svg
    ├── export_png.py      # mixed.svg → mixed.png
    └── make_index.py      # 生成 index.html
```

---

## 7. 复现

```bash
# 1) 原始简谱 → 悦谱 123（22 首非 play）
python3 scripts/build_batch.py

# 2) 123 → MusicXML + timeline
node scripts/to_xml.mjs .

# 3) MusicXML → Dolce Mixed
python3 scripts/render_mixed.py cases/<曲名>

# 4) 混排 SVG → PNG（只保留 PNG）
python3 scripts/export_png.py cases/<曲名>
rm -f cases/<曲名>/mixed.svg

# 5) 原谱简谱 → PNG
#    由 website_renderer 渲染 `00_统一简谱全曲.svg` 后栅格化

# 6) 重新生成索引
python3 scripts/make_index.py
```

---

## 8. 记谱方法的一句话总结

- **原始简谱**：数字 + 后缀（`g`/`d` 八度、`_`/`=` 减时线、`.` 附点、`#`/`b` 变音、`-` 增时线），配 `(...)` 连音、`{...}` 标签、`{{...}}` 段落、`|:`/`:|`/`[1:` 反复与房号；歌词单独放 `lyric`。
- **悦谱 123**：同样的数字体系，但八度改用 `'`/`,`，减时线改成重复 `_`，变音改成前置 `#`/`b`，连音仍是 `(...)`，倚音是 `{...}`，反复仍是 `|:`/`:|`/`[1`；文件头用 `K:1=E`、`M:`、`Q:`，歌词用 `w:`。
- **转换核心**：只做“原谱 token → 123 token”的语义映射；凡是 123 承载不了的构造，写进 `losses`，不静默丢弃。
