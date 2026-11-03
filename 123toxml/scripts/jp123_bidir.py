#!/usr/bin/env python3
"""苍强简谱 DSL ⇄ Dolce 123 双向编解码器。

方向一（fwd）：我们的 songdata（notation + lyric）→ 123 文本
方向二（rev）：123 文本 → 我们的 songdata

设计原则
--------
1. **语义优先**：所有映射都以「官方 runtime 解出的发声事件」为准，不追求文本逐字一致。
2. **不静默丢构造**：任何无法表达的构造都写进 losses，调用方必须可见。
3. **双向对称**：fwd 与 rev 使用同一张表；rev(fwd(x)) 应在发声层回到 x。

已实测的双方差异（2026-10-23，见 docs/映射矩阵.md）：
    八度      g / ,          ↔  ' / ,
    减时线    _ 的个数         ↔  _ 的个数（我们 _ = 1 条，_= = 3 条）
    双附点    ..               ↔  附点音 + 连音线（123 只认一个附点）
    倚音      (...)@           ↔  {...}（123 的倚音不发声、不占拍）
    右倚音    @(...)（我们不发声）↔  不表达（丢弃，记 loss）
    节奏音符  8 (jie) / 9 (kong) ↔  X / x
    变音      后缀 7b / 3g#      ↔  前缀 b7 / #3'
    和弦      {cn:Am7}         ↔  "Am7"
    力度      {tip:mf}         ↔  !mf!
    术语      {tip:渐慢}        ↔  "^渐慢."
    曲中转调  {comment:转[1=E]}  ↔  "^转[1=E]"（不转调，保留文字）
    跨小节延音 -  - | -  -     ↔  合并成一个长音的 `-`（123 的 - 不能跨小节）
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from fractions import Fraction

# --------------------------------------------------------------------------- #
# 记号表
# --------------------------------------------------------------------------- #

MARK_OURS_TO_123 = {
    "v": "!breath!",
    "tr": "!trill!",
    "mu": "!uppermordent!",
    "sd": "!falloff!",
    "st": "!staccato!",
    "fe": "!fermata!",
    ">": "!accent!",
    # 123 记号表里没有 da / su：§8.3 允许原样保留
    "da": "!da!",
    "su": "!su!",
}
MARK_123_TO_OURS = {v.strip("!"): k for k, v in MARK_OURS_TO_123.items()}
MARK_123_TO_OURS.update({
    "呼吸": "v", "呼吸记号": "v",
    "延长": "fe", "延长记号": "fe",
    "重音": ">", "strong-accent": ">", "emphasis": ">",
    "顿音": "st", "staccatissimo": "st",
    "颤音": "tr", "trill-mark": "tr",
    "上波音": "mu", "pralltriller": "mu", "inverted-mordent": "mu",
    "下滑音": "sd", "scoop": "sd",
    "breath-mark": "v",
})
DYNAMICS = {"p", "pp", "ppp", "mp", "mf", "f", "ff", "fff", "sf", "sfz",
            "crescendo", "diminuendo"}

# 苍强标签里的记号短名 → 123 记号（源 runtime 多数不发声，但保留记号更利于展示）
TAG_MARK = {
    "dun": "!staccato!",
    "yc": "!fermata!",
    "xh": "!breath!",
    "br": "!breath!",
    "hx": "!breath!",
    "ds": "!D.S.!",
    "DS": "!D.S.!",
    "dc": "!D.C.!",
    "jump": "!segno!",
}
# 已知但本轮不承载的标签：结构化播放/段落/样式
# `hot` 在源 runtime 里是配置开关（`case "hot": config[t]=1`），不是 Coda 记号。
TAG_DROP = {"play", "section", "mark", "omit", "ms", "text", "lyric", "hint",
            "graph", "f", "auto", "t", "bo", "sus", "hot"}

DEFAULT_BPM = 90
DEFAULT_RHYTHM = "4/4"

BEAM_CHARS = "_="


# --------------------------------------------------------------------------- #
# 我们方言的扫描
# --------------------------------------------------------------------------- #

@dataclass
class Note:
    deg: int                    # 0 = 休止；8 = jie；9 = kong
    octv: int = 0
    acc: str = ""               # "b" / "#" / ""
    beams: int = 0
    dots: int = 0
    raw_suffix: str = ""
    acc_prefix: bool = False    # 源写法是前置变音号（官方 runtime 会忽略它）


@dataclass
class Atom:
    kind: str                   # note/rest/prolong/open/close/tuplet/ghost/bar/
                                # mark/tag/chord/tilde/house/inline/raw
    value: object = None
    extra: dict = field(default_factory=dict)


def _scan_ours(text: str):
    """我们的 notation → Atom 列表。括号组保留结构，`(...)@` 收成 ghost。"""
    atoms: list[Atom] = []
    i, n = 0, len(text)

    def close_ghost():
        """把最近一个未闭合的 open 到末尾收成 ghost；调用处保证存在。"""
        depth, j = 0, len(atoms) - 1
        while j >= 0:
            if atoms[j].kind == "close":
                depth += 1
            elif atoms[j].kind == "open":
                if depth == 0:
                    inner = atoms[j + 1:]
                    del atoms[j:]
                    atoms.append(Atom("ghost", inner, {"side": "left"}))
                    return
                depth -= 1
            j -= 1
        atoms.append(Atom("raw", ")@"))

    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == "{":
            if i + 1 < n and text[i + 1] == "{":
                atoms.append(Atom("section_begin"))
                i += 2
                continue
            if i + 1 < n and text[i + 1] == "~":
                # {~ … ~} 是「带 ~ 的花括号音乐块」，内部仍是普通音符
                j = text.find("~}", i + 2)
                if j > 0:
                    inner = text[i + 2:j].strip(" ~")
                    atoms.extend(_scan_ours(inner))
                    i = j + 2
                    continue
            j = text.find("}", i + 1)
            if j < 0:
                atoms.append(Atom("raw", text[i:]))
                break
            body = text[i + 1:j]
            if ":" in body:
                k, v = body.split(":", 1)
                atoms.append(Atom("tag", (k.strip(), v)))
            else:
                atoms.append(Atom("tag", ("", body)))
            i = j + 1
            continue
        if c == "}" and i + 1 < n and text[i + 1] == "}":
            atoms.append(Atom("section_end"))
            i += 2
            continue
        if c == "@":
            if i + 1 < n and text[i + 1] == "(":
                depth, j = 0, i + 1
                while j < n:
                    if text[j] == "(":
                        depth += 1
                    elif text[j] == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                inner = _scan_ours(text[i + 2:j])
                atoms.append(Atom("ghost", inner, {"side": "right"}))
                i = j + 1
                continue
            atoms.append(Atom("raw", c))
            i += 1
            continue
        if c == "(":
            if text.startswith("(t:", i):
                # (t: … ) 强制同音连音组；Dolce 的 ( … ) 对同音本来就会合并，
                # 所以 123 里保留括号即可，t 标记本身不写。
                atoms.append(Atom("open_tie"))
                i += 3
                continue
            m = re.match(r"\((\d+):(?:(\d+):)?", text[i:])
            if m:
                atoms.append(Atom("tuplet", m.group(0)))
                i += len(m.group(0))
                continue
            atoms.append(Atom("open"))
            i += 1
            continue
        if c == ")":
            if i + 1 < n and text[i + 1] == "@":
                close_ghost()
                i += 2
                continue
            atoms.append(Atom("close"))
            i += 1
            continue
        if c == "|":
            # 反复记号：`|:` / `:|`。之前被拆成 `|` + raw `:`，结构在 codec 里丢掉。
            if text.startswith("|:", i):
                atoms.append(Atom("bar", "|:"))
                i += 2
                continue
            j = i
            while j < n and text[j] == "|":
                j += 1
            if i > 0 and text[i - 1] == "[":
                atoms.append(Atom("house_bar", text[i - 1:j]))
                i = j
                continue
            atoms.append(Atom("bar", text[i:j]))
            i = j
            continue
        # 房号收尾：`]` 只是房号的右括号，不是音乐记号。按后面的小节线归一。
        if text.startswith("] :|", i):
            atoms.append(Atom("bar", ":|"))
            i += 4
            continue
        if text.startswith("]:|", i):
            atoms.append(Atom("bar", ":|"))
            i += 3
            continue
        if text.startswith("] |||", i):
            atoms.append(Atom("bar", "|]"))
            i += 5
            continue
        if text.startswith("]|||", i):
            atoms.append(Atom("bar", "|]"))
            i += 4
            continue
        if text.startswith("] ||", i):
            atoms.append(Atom("bar", "||"))
            i += 4
            continue
        if text.startswith("]||", i):
            atoms.append(Atom("bar", "||"))
            i += 3
            continue
        if text.startswith("] |", i) or text.startswith("]|", i):
            j = i + (3 if text.startswith("] |", i) else 2)
            while j < n and text[j].isspace():
                j += 1
            # 一房结束、后面紧跟二房 → `:|`；否则最后一房 → 终止线。
            if j < n and re.match(r"\[[0-9]", text[j:]):
                atoms.append(Atom("bar", ":|"))
            else:
                atoms.append(Atom("bar", "|]"))
            i = i + (3 if text.startswith("] |", i) else 2)
            continue
        if c == "]":
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            if j < n and re.match(r"\[[0-9]", text[j:]):
                atoms.append(Atom("bar", ":|"))
            i += 1
            continue
        if text.startswith(":|", i):
            atoms.append(Atom("bar", ":|"))
            i += 2
            continue
        if c == "[":
            # 房号起始只吃到冒号，不能把后面的第一个音（如 `[1:6`）吞进房号。
            m = re.match(r"\[[\d,\-]+\s*:", text[i:])
            if m:
                atoms.append(Atom("house_start", m.group(0)))
                i += len(m.group(0))
                continue
            atoms.append(Atom("raw", c))
            i += 1
            continue
        if c == "-":
            atoms.append(Atom("prolong"))
            i += 1
            continue
        if c.isdigit():
            j = i + 1
            while j < n and (text[j] in "g,#b_=..xd"):
                j += 1
            tok = text[i:j]
            atoms.append(_parse_our_note(tok))
            i = j
            continue
        if c in "#b" and i + 1 < n and text[i + 1].isdigit():
            # 前置变音号：#4 / b3。官方 runtime 实测**忽略**前置变音号，
            # 为与发声层一致，这里标记后丢弃（不映射成 123 的 #4/b3）。
            j = i + 2                       # 跳过变音号与数字
            while j < n and (text[j] in "g,#b_=..xd"):
                j += 1
            atom = _parse_our_note(text[i + 1:j])
            atom.value.acc = c
            atom.value.acc_prefix = True
            atoms.append(atom)
            i = j
            continue
        if c == ">":
            atoms.append(Atom("mark", ">"))
            i += 1
            continue
        if c.isalpha():
            j = i
            while j < n and text[j].isalpha() and j - i < 3:
                j += 1
            word = text[i:j]
            if word in MARK_OURS_TO_123:
                atoms.append(Atom("mark", word))
                i = j
                continue
            atoms.append(Atom("raw", word))
            i = j
            continue
        atoms.append(Atom("raw", c))
        i += 1
    return atoms


def _parse_our_note(tok: str) -> Atom:
    deg = int(tok[0])
    suffix = tok[1:]
    # 统一方言归一：x = 一条减时线，d = 低八度点
    suffix = suffix.replace("x", "_").replace("d", ",")
    octv = suffix.count("g") - suffix.count(",")
    acc = ""
    if "#" in suffix:
        acc = "#"
    elif "b" in suffix:
        acc = "b"
    beams = suffix.count("_") + 2 * suffix.count("=")
    dots = suffix.count(".")
    kind = "note"
    if deg == 0:
        kind = "rest"
    elif deg == 8:
        kind = "jie"          # 有声无音高 / 节奏音符（官方 runtime 记为 jie）
    elif deg == 9:
        kind = "kong"         # 空音节槽
    return Atom(kind, Note(deg, octv, acc, beams, dots, suffix))


# --------------------------------------------------------------------------- #
# 我们 → 123
# --------------------------------------------------------------------------- #

def _our_note_to_123(n: Note, losses: list[str]) -> list[str]:
    """返回 token 列表（双附点拆成「附点音 + 连音线」）。"""
    if n.deg in (8, 9):
        base = "X" if n.deg == 8 else "x"
        return [base + "_" * n.beams + "." * min(n.dots, 1)]
    prefix = {"b": "b", "#": "#"}.get(n.acc, "")
    if n.acc_prefix:
        # 官方 runtime 忽略前置变音号；为保发声层一致，123 里也不写
        losses.append(f"prefix-accidental-dropped:{n.acc}{n.deg}")
        prefix = ""
    if n.deg == 0:
        prefix = ""
    octv = n.octv
    octs = "'" * octv if octv > 0 else "," * (-octv)
    beams, dots = n.beams, n.dots
    if dots > 2:
        losses.append(f"dots-too-many:{dots}")
        dots = 2
    if dots == 2:
        # 双附点 = 原时值 × 7/4；123 只认一个附点，直接写 `..` 会丢第二个点。
        # 不带减时线：沿用已验证的 `附点音 + -` 写法（精确，但依赖本项目的
        #   Dolce 补丁；上游 Dolce 会把它读成 1.5）。
        # 带减时线：`附点音 + ~ + 四分之一音`，例如 1_.. → 1_.~ 1___。
        #   用后置 `~` 而不是 `( … )`，它不进括号栈，不会打乱原有圆滑线分组。
        if beams == 0:
            return [f"{prefix}{n.deg}{octs}_." if n.deg else "_", "-"]
        base = "0" if n.deg == 0 else f"{prefix}{n.deg}{octs}"
        first = f"{base}{'_' * beams}."
        second = f"{base}{'_' * (beams + 2)}"
        if n.deg == 0:
            return [first, second]
        return [first + "~", second]
    return [f"{prefix}{'0' if n.deg == 0 else n.deg}{octs}{'_' * beams}{'.' * dots}"]


def _shift_octaves(atoms: list[Atom], shift: int) -> None:
    for a in atoms:
        if a.kind in ("note", "rest", "jie", "kong"):
            a.value.octv += shift
        elif a.kind == "ghost":
            _shift_octaves(a.value, shift)


def _inner_to_123(atoms: list[Atom], losses: list[str]) -> str:
    out: list[str] = []
    for a in atoms:
        out.extend(_atom_to_123(a, losses))
    return " ".join(x for x in out if x)


def _atom_to_123(a: Atom, losses: list[str]) -> list[str]:
    k = a.kind
    if k in ("note", "rest", "jie", "kong"):
        return _our_note_to_123(a.value, losses)
    if k == "prolong":
        return ["-"]
    if k == "open":
        return ["("]
    if k == "open_tie":
        losses.append("tie-group-marker-dropped")
        return ["("]
    if k == "close":
        return [")"]
    if k == "tuplet":
        return [a.value]
    if k == "bar":
        # 保留反复与终止小节线；普通 `|||` 在 123 里写作终止线 `|]`。
        return ["|]" if a.value == "|||" else a.value]
    if k == "house_bar":
        return [a.value]
    if k == "house_start":
        v = a.value.rstrip(":").strip()
        if re.fullmatch(r"\[\d+(?:,\d+)*", v):
            return [v]
        losses.append(f"house:{a.value}")
        return []
    if k == "mark":
        return [MARK_OURS_TO_123.get(a.value, f"!{a.value}!")]
    if k in ("section_begin", "section_end"):
        losses.append("section-block-linearized")
        return []
    if k == "tag":
        kind, value = a.value
        if kind == "bpm":
            return []
        if kind == "octave":
            return []                      # 已在上层把音高整体移调
        if kind == "cn":
            return [f'"{value}"']
        if kind == "tip":
            if value in DYNAMICS:
                return [f"!{value}!"]
            return [f'"^{value}."']
        if kind == "comment":
            # 源 runtime 把 {comment:转[...]} 只当文字，不改变调号；
            # 若映射成 [K:...] 会让 Dolce 单方面转调 → 发声层分叉。
            return [f'"^{value}"']
        if kind == "":
            if value.startswith("!") and value.endswith("!"):
                losses.append("pinyin-slot-dropped")
                return []
            # {1=D} / {2/4}：行内改调 / 改拍（实测源 runtime 会应用改调）
            if re.fullmatch(r"1=[#b]?[A-Ga-g]\d*", value or ""):
                return [f"[K:{value}]"]
            if re.fullmatch(r"\d+/\d+", value or ""):
                return [f"[M:{value}]"]
            if value in MARK_OURS_TO_123:
                return [MARK_OURS_TO_123[value]]
            if value in TAG_MARK:
                return [TAG_MARK[value]]
            jump = {"S": "!segno!", "Fine": "!fine!", "ds1": "!D.S.!",
                    "DS": "!D.S.!", "DC": "!D.C.!",
                    "jump": "!segno!", "bo": "!uppermordent!"}
            if value in jump:
                return [jump[value]]
            if value in TAG_DROP or value == "start":
                losses.append(f"tag-dropped:{value}")
                return []
        if kind in TAG_DROP:
            losses.append(f"tag-dropped:{kind}:{value!r}")
            return []
        losses.append(f"tag-unknown:{kind}:{value!r}")
        return []
    if k == "ghost":
        inner = _inner_to_123(a.value, losses)
        return ["{" + inner + "}"]
    if k == "tilde":
        return ["~"]
    if k == "raw":
        v = str(a.value or "")
        if v.strip():
            losses.append(f"raw-dropped:{v!r}")
        return []
    losses.append(f"atom-unknown:{k}")
    return []


def _collapse_prolong_bars(tokens: list[str]) -> list[str]:
    """123 的 `-` 不能跨小节。把「小节线后紧跟 -」的线去掉，让延音连成一片。"""
    out: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "|":
            j = i + 1
            while j < len(tokens) and tokens[j] == "":
                j += 1
            if j < len(tokens) and tokens[j] == "-":
                i += 1              # 丢掉这条小节线
                continue
        out.append(t)
        i += 1
    return out


# 理论调号 → 等音调号（Dolce 拒绝 #G/#D/#A 这类 8+ 升号的理论调）
ENHARMONIC = {"#A": "bB", "#D": "bE", "#G": "bA", "#B": "C", "#E": "F"}
# 官方 runtime 对 1=X<n> 的八度锚点（实测，n=4 为基准）
KEY_OCT_SHIFT = {1: -3, 2: -2, 3: -1, 4: 0, 5: 1, 6: 1, 7: 2, 8: 3}


def _norm_key(raw):
    """→ (123 用的调名, 源调号原样, 源调号状态, 源调号八度, 失败原因)"""
    if raw is None:
        return None, None, "missing", None, "keynote-missing"
    original = str(raw)
    s = original.strip().replace("＝", "=").replace(" ", "")
    if not s:
        return None, original, "empty", None, "keynote-empty"
    if "=" in s:
        s = s.split("=", 1)[1]
    key_oct = None
    m_oct = re.search(r"(\d+)$", s)
    if m_oct:
        key_oct = int(m_oct.group(1))
        s = s[: -len(m_oct.group(0))]
    m = re.fullmatch(r"([#bd]?)([A-Ga-g])([#bd]?)", s)
    if not m:
        return None, original, "explicit", key_oct, f"keynote-malformed:{raw!r}"
    pre, letter, post = m.groups()
    acc = pre or post
    key = f"{'b' if acc == 'd' else acc}{letter.upper()}"
    key = ENHARMONIC.get(key, key)
    return key, original, "explicit", key_oct, None


def _norm_rhythm(raw):
    if raw is None:
        return DEFAULT_RHYTHM, "rhythm-missing"
    s = " ".join(str(raw).split())
    if not s:
        return DEFAULT_RHYTHM, "rhythm-empty"
    if re.fullmatch(r"\d+", s):
        s = f"{s}/4"
    return s, None


def _norm_bpm(raw):
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_BPM, f"bpm-malformed:{raw!r}"
    if v <= 0:
        return DEFAULT_BPM, f"bpm-nonpositive:{raw!r}"
    return v, None


# 两个 runtime 对歌词标点的音节归属不一致的字符：
#   我方：各自占一个音节（部分甚至占空槽）；123：并入前一字或后一字。
# 用 {...} 把每个标点包成独立音节，强制对齐口径一致。
WRAP_PUNCT = set("；：~～…—()（）《》〈〉「」『』【】〔〕“”‘’")


def _wrap_punct(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "{":
            j = s.find("}", i + 1)
            if j >= 0:
                out.append(s[i:j + 1])
                i = j + 1
                continue
        if c in WRAP_PUNCT:
            out.append("{" + c + "}")
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _lyric_verses(raw):
    if raw is None:
        return [], "lyric-missing"
    if isinstance(raw, str):
        try:
            arr = json.loads(raw)
        except json.JSONDecodeError:
            arr = [raw]
    else:
        arr = raw
    if isinstance(arr, str):
        arr = [arr]
    if not arr:
        return [], "lyric-empty"
    # 我方歌词里的 (...) 是「多字挤一格」，123 对应 {...}
    # 我方 `_` = 这个词空着但占一个音符槽（不是延长前一个字）。
    # 123 里字面空格不占槽（会把后面的字前移）；`_` 是 melisma（延长前字）。
    # 空槽且不配字应写 `/`（跳音符），渲染同样是空白。
    out = []
    n_group = 0
    for verse in arr:
        n_group += verse.count("(")
        v = re.sub(r"\(([^()]*)\)", r"{\1}", str(verse))
        v = _wrap_punct(v).replace("_", "/")
        out.append(v)
    return out, (f"lyric-group-to-brace:{n_group}" if n_group else None)


def ours_to_123(song: dict) -> dict:
    """songdata → {"text": str, "losses": [...], "header": {...}}"""
    losses: list[str] = []
    notation = song.get("notation")
    if not notation or not str(notation).strip():
        return {"text": None, "losses": ["notation-empty"], "header": {}}
    notation = str(notation)

    # 本轮是「写谱形态」混排：{play}/{section}/{ms} 不进入 123 谱面。
    # `{play:}` 的演奏顺序不展开；`{section:}` 只是段落标记；`{ms:}` 无 123 对应。
    if re.search(r"\{play\s*:", notation):
        losses.append("play-linearized")
    if re.search(r"\{section\s*:", notation):
        losses.append("section-markers-dropped")
    if re.search(r"\{ms\s*:", notation):
        losses.append("ms-dropped")
    notation = re.sub(r"\{play\s*:[^}]*\}", "", notation)
    notation = re.sub(r"\{section\s*:[^}]*\}", "", notation)
    notation = re.sub(r"\{ms\s*:[^}]*\}", "", notation)

    # 段名行（A1:/B:/间奏:）如果留着，codec 会把标签里的数字当音符。
    if re.search(r"(?m)^[ \t]*[A-Za-z][A-Za-z0-9_]*[ \t]*:[ \t]*", notation):
        losses.append("section-labels-stripped")
    notation = re.sub(r"(?m)^[ \t]*[A-Za-z][A-Za-z0-9_]*[ \t]*:[ \t]*", "", notation)
    # 段名紧贴在标签后面（`{f:G}A1:`）。
    notation = re.sub(r"(?<=[}\n])[ \t]*[A-Za-z][A-Za-z0-9_]*[ \t]*:[ \t]*", "", notation)

    # 源方言 `5bo` / `7bo.`：`bo` 是「半拍/减时线」写法，不是降号 `b` + `o`。
    # 不先归一的话会被读成 b5（降五度）并丢掉半拍。
    # 换行只是排版：源里常见 `5,` 换行后接 `=3,`，`=` 是前一个音的减时线。
    # 保留换行会让 `=` 变成裸 token 丢掉，前一音被拉长。
    n_nl = notation.count("\n") + notation.count("\r")
    if n_nl:
        losses.append(f"linebreaks-joined:{n_nl}")
        notation = notation.replace("\r", "").replace("\n", "")

    # 源方言 `5bo_` / `7bo.` / `7bo`：`bo` 是装饰记号，不是降号 `b`。
    # 它本身不带时值；时值看它后面的 `_` / `=` / `.`。
    # 例：`5bo_` → `5_`；`7bo.` → `7.`；`7bo` → `7`。
    n_bo = len(re.findall(r"\dbo", notation))
    if n_bo:
        losses.append(f"bo-marker-dropped:{n_bo}")
        notation = re.sub(r"(\d)bo", r"\1", notation)

    # 源方言 `7./3g./7/`：`/` 是一条减时线（八分），不是分隔符。
    # 官方 runtime 把它读成 `7_.` / `3g_.` / `7_`；不归一会被读成四分音符，整首时值被拉长。
    n_slash = len(re.findall(r"[0-9][g,#b_=\.xd]*/", notation))
    if n_slash:
        losses.append(f"slash-as-beam:{n_slash}")
        notation = re.sub(r"([0-9][g,#b_=\.xd]*)/", r"\1_", notation)

    key, key_raw, key_source, key_oct, key_err = _norm_key(song.get("keynote"))
    if key_err:
        losses.append(key_err)
    rhythm, rhythm_err = _norm_rhythm(song.get("rhythm"))
    if rhythm_err:
        losses.append(rhythm_err)
    bpm, bpm_err = _norm_bpm(song.get("bpm"))
    if bpm_err:
        losses.append(bpm_err)
    verses, lyric_err = _lyric_verses(song.get("lyric"))
    if lyric_err:
        losses.append(lyric_err)

    # 正文里的 {bpm:N} 是权威速度
    m = re.search(r"\{bpm:\s*([0-9.]+)\s*\}", str(notation))
    if m:
        try:
            bpm = float(m.group(1))
        except ValueError:
            pass

    atoms = _scan_ours(str(notation))

    # 全曲级 {octave:N}：官方 runtime 会把所有音整体移 N 个八度
    m_oct = re.search(r"\{octave:\s*(-?\d+)\s*\}", str(notation))
    if m_oct:
        shift = int(m_oct.group(1))
        if shift:
            _shift_octaves(atoms, shift)
            losses.append(f"octave-tag-applied:{shift}")

    # 注意 1：不合并 (8 8) 节奏连音——合并会少一个歌词槽，反向时歌词整体前移。
    # 注意 2：不剥掉跨小节圆括号——我方 runtime 确实会把括号内同音合成一个音，
    #         剥掉会让发声层分叉（实测大量回归）。跨小节连音的分组差异归入残差。
    # 这两类都单独归入残差桶（见验收报告）。

    # 右倚音：官方 runtime 不发声；丢弃（左倚音保留为 ghost）
    cleaned: list[Atom] = []
    for a in atoms:
        if a.kind == "ghost" and a.extra.get("side") == "right":
            losses.append("right-ghost-dropped")
            continue
        cleaned.append(a)
    atoms = cleaned

    tokens: list[str] = []

    def is_note_token(t: str) -> bool:
        return bool(re.fullmatch(r"[#b]?\d[',_\.]*", t or ""))

    for a in atoms:
        if a.kind in ("note", "rest", "jie", "kong") and getattr(a.value, "acc_prefix", False):
            # 源 runtime 的实测语义：前置变音号作用于**前一个**音符，而不是后一个。
            # 因此把它挪到 123 里前一个音符的前面，当前音符保持原样。
            acc = a.value.acc
            note = a.value
            note.acc, note.acc_prefix = "", False
            cur = _atom_to_123(a, losses)
            note.acc, note.acc_prefix = acc, True
            tokens.extend(cur)
            target = None
            for j in range(len(tokens) - len(cur) - 1, -1, -1):
                if is_note_token(tokens[j]):
                    target = j
                    break
            if target is None:
                losses.append(f"prefix-accidental-unattached:{acc}")
            elif tokens[target][:1] in ("#", "b"):
                losses.append(f"prefix-accidental-conflict:{acc}:{tokens[target]}")
            else:
                tokens[target] = acc + tokens[target]
                losses.append(f"prefix-accidental-moved-to-previous:{acc}")
            continue
        tokens.extend(_atom_to_123(a, losses))
    tokens = _collapse_prolong_bars(tokens)
    body = " ".join(t for t in tokens if t)
    body = re.sub(r"\s+", " ", body).strip()

    title = str(song.get("song_name") or "Untitled").strip() or "Untitled"
    lines = ["X:1", f"T:{title}", f"K:1={key or 'C'}", f"M:{rhythm}", f"Q:1/4={bpm:g}"]

    # 谱号八度补偿：把「我方 runtime 的锚点」翻译成 Dolce 的谱面。
    #   ① 主音是 B 的调：Dolce 按《简谱通用规范》把 1 放在 B3..A4，低一个八度
    #   ② 源调号缺省：我方 runtime 兜底在 C5，Dolce 的 1=C 在 C4
    #   ③ 源调号带八度后缀（1=E6 / 1=F3）：我方按后缀移位
    clef_shift = 0
    if key is not None and key.lstrip("#b").upper() == "B":
        clef_shift += 1
        losses.append("key-b-tonic-octave-shift:+8")
    if key is None:
        clef_shift += 1
        losses.append("key-missing-octave-shift:+8")
    if key_oct:
        oct_shift = KEY_OCT_SHIFT.get(key_oct, 0)
        if oct_shift:
            clef_shift += oct_shift
            losses.append(f"key-octave-suffix:{key_oct}:{oct_shift:+d}")
    if clef_shift:
        if abs(clef_shift) > 1:
            losses.append(f"clef-shift-clamped:{clef_shift}")
            clef_shift = 1 if clef_shift > 0 else -1
        lines.append(f"V:1 clef=treble{'+8' if clef_shift > 0 else '-8'}")
    # 往返溯源：注释行不被 Dolce 消费，但 rev 能据此还原源调号（含缺失/八度后缀）
    if key_source == "missing" or key_source == "empty":
        lines.append("%JIANPU-KEYNOTE-SOURCE:missing")
    else:
        lines.append(f"%JIANPU-KEYNOTE:{key_raw}")
    if clef_shift:
        lines.append(f"%JIANPU-CLEF-SHIFT:{clef_shift:+d}")
    lines.append(body)
    for verse in verses:
        if verse is not None:
            lines.append("w:" + verse)
    lines.append("")
    return {"text": "\n".join(lines), "losses": losses,
            "header": {"key": key, "rhythm": rhythm, "bpm": bpm, "verses": verses}}


# --------------------------------------------------------------------------- #
# 123 的扫描
# --------------------------------------------------------------------------- #

CHORD_RE = re.compile(r"[#b]?[A-G](?:[A-Za-z0-9#b+\-()/.]*)")


def _scan_123_body(text: str, losses: list[str]):
    """123 音乐体 → Atom 列表（用于反向）。"""
    atoms: list[Atom] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == "%":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c == '"':
            j = text.find('"', i + 1)
            if j < 0:
                losses.append("text-mark-unclosed")
                break
            atoms.append(Atom("text_mark", text[i + 1:j]))
            i = j + 1
            continue
        if c == "!":
            j = text.find("!", i + 1)
            if j < 0:
                losses.append("mark-unclosed")
                break
            atoms.append(Atom("mark", text[i + 1:j]))
            i = j + 1
            continue
        if c == "{":
            j = text.find("}", i + 1)
            if j < 0:
                losses.append("grace-unclosed")
                break
            atoms.append(Atom("grace", text[i + 1:j]))
            i = j + 1
            continue
        if c == "(":
            m = re.match(r"\((\d+):(?:(\d+):)?", text[i:])
            if m:
                atoms.append(Atom("tuplet", m.group(0)))
                i += len(m.group(0))
                continue
            atoms.append(Atom("open"))
            i += 1
            continue
        if c == ")":
            atoms.append(Atom("close"))
            i += 1
            continue
        if c == "[":
            m = re.match(r"\[(K|M):([^\]]*)\]", text[i:])
            if m:
                atoms.append(Atom("inline", (m.group(1), m.group(2))))
                i += len(m.group(0))
                continue
            if text.startswith("[|]", i):
                atoms.append(Atom("invis_bar", "[|]"))
                i += 4
                continue
            m = re.match(r"\[\d[\d,\-]*", text[i:])
            if m:
                atoms.append(Atom("house_start", m.group(0)))
                i += len(m.group(0))
                continue
            atoms.append(Atom("raw", c))
            i += 1
            continue
        if c == "|":
            j = i
            while j < n and text[j] in "|:]":
                j += 1
            atoms.append(Atom("bar", text[i:j]))
            i = j
            continue
        if c == ":":
            if text.startswith(":|", i):
                atoms.append(Atom("bar", ":|"))
                i += 2
                continue
            atoms.append(Atom("raw", c))
            i += 1
            continue
        if c == ".":
            if text.startswith(".|", i):
                atoms.append(Atom("invis_bar", ".|"))
                i += 2
                continue
            atoms.append(Atom("raw", c))
            i += 1
            continue
        if c in "#bn" and i + 1 < n and text[i + 1].isdigit():
            j = i + 2                       # 跳过变音号与数字
            while j < n and text[j] in "',_.":
                j += 1
            atoms.append(Atom("note123", text[i:j]))
            i = j
            continue
        if c.isdigit():
            j = i + 1
            while j < n and text[j] in "',_.":
                j += 1
            atoms.append(Atom("note123", text[i:j]))
            i = j
            continue
        if c in "Xx":
            j = i + 1
            while j < n and text[j] in "',_.":
                j += 1
            atoms.append(Atom("rhythm123", text[i:j]))
            i = j
            continue
        if c == "y":
            atoms.append(Atom("spacer"))
            i += 1
            continue
        if c == "-":
            atoms.append(Atom("prolong"))
            i += 1
            continue
        if c == "~":
            atoms.append(Atom("tilde"))
            i += 1
            continue
        if c == "$":
            atoms.append(Atom("linebreak"))
            i += 1
            continue
        if c.isalpha() or c in "#b":
            # 裸和弦：A–G 开头、到空白为止、后面必须有空白（123 §8.1）
            m = CHORD_RE.match(text[i:])
            if m:
                name = m.group(0)
                end = i + len(name)
                if end < n and (text[end].isspace() or text[end] in "|"):
                    atoms.append(Atom("chord", name))
                    i = end
                    continue
            atoms.append(Atom("raw", c))
            i += 1
            continue
        atoms.append(Atom("raw", c))
        i += 1
    return atoms


def _parse_123_note(tok: str, losses: list[str]) -> Atom:
    acc = ""
    if tok[0] in "#bn":
        acc = tok[0]
        tok = tok[1:]
        if acc == "n":
            losses.append("natural-accidental-dropped")
            acc = ""
    deg = int(tok[0])
    rest = tok[1:]
    octv = rest.count("'") - rest.count(",")
    beams = rest.count("_")
    dots = rest.count(".")
    if dots > 1:
        losses.append(f"multi-dot-read-as-single:{dots}")
        dots = 1
    return Atom("note123", Note(deg, octv, acc, beams, dots, rest))


def _atom123_to_ours(a: Atom, losses: list[str]) -> list[str]:
    k = a.kind
    if k == "note123":
        n = _parse_123_note(a.value, losses).value
        return [_our_note_text(n)]
    if k == "rhythm123":
        ch = a.value[0]
        rest = a.value[1:]
        beams = rest.count("_")
        dots = min(rest.count("."), 1)
        return [("8" if ch == "X" else "9") + "_" * beams + "." * dots]
    if k == "prolong":
        return ["-"]
    if k == "open":
        return ["("]
    if k == "close":
        return [")"]
    if k == "tuplet":
        return [a.value]
    if k == "bar":
        v = a.value
        if v in ("|", "||", "|||", "|]", ":", "::"):
            return ["|"]
        if ":" in v:
            losses.append(f"repeat-bar-linearized:{v}")
            return ["|"]
        return ["|"]
    if k == "invis_bar":
        losses.append(f"invisible-bar-as-visible:{a.value}")
        return ["|"]
    if k == "house_start":
        losses.append(f"house-linearized:{a.value}")
        return []
    if k == "mark":
        v = a.value
        if v in MARK_123_TO_OURS:
            return [MARK_123_TO_OURS[v]]
        if v in DYNAMICS:
            return [f"{{tip:{v}}}"]
        if re.fullmatch(r"[A-Za-z]{1,3}", v):
            return [v]
        losses.append(f"mark-unknown:{v}")
        return [f"{{comment:!{v}!}}"]
    if k == "grace":
        inner = _scan_123_body(a.value, losses)
        text = " ".join(x for at in inner for x in _atom123_to_ours(at, losses))
        return ["(" + text + ")@"]
    if k == "chord":
        return [f"{{cn:{a.value}}}"]
    if k == "text_mark":
        v = a.value
        if v.startswith(("^", "_")):
            v = v[1:]
            if v.endswith("."):
                v = v[:-1]
            if v in DYNAMICS:
                return [f"{{tip:{v}}}"]
            return [f"{{comment:{v}}}"]
        # 不带位置前缀的引号串：和弦（"Am7"1）
        if re.fullmatch(r"[#b]?[A-G][A-Za-z0-9#b+\-()/.]*", v):
            return [f"{{cn:{v}}}"]
        if v in DYNAMICS:
            return [f"{{tip:{v}}}"]
        return [f"{{comment:{v}}}"]
    if k == "inline":
        kind, value = a.value
        if kind == "K":
            return [f"{{comment:转[{value}]}}"]
        return [f"{{comment:M:{value}}}"]
    if k == "spacer":
        losses.append("spacer-y-dropped")
        return []
    if k == "tilde":
        return ["~"]           # 后处理再配对
    if k in ("linebreak",):
        return []
    if k == "raw":
        v = str(a.value or "")
        if v.strip():
            losses.append(f"raw-dropped:{v!r}")
        return []
    losses.append(f"atom123-unknown:{k}")
    return []


def _tuplet_supported(value: str) -> bool:
    """我方 runtime 只认 (3: 与 (3:2:（默认 2/3 比例）。"""
    m = re.match(r"\((\d+):(?:(\d+):)?", value or "")
    if not m:
        return False
    n = int(m.group(1))
    p = int(m.group(2)) if m.group(2) else None
    return n == 3 and p in (None, 2)


def _atoms123_to_ours(atoms: list[Atom], losses: list[str]) -> list[str]:
    out: list[str] = []
    stack: list[bool] = []
    for a in atoms:
        if a.kind == "tuplet":
            ok = _tuplet_supported(a.value)
            stack.append(ok)
            if ok:
                out.append(a.value)
            else:
                losses.append(f"tuplet-unsupported-dropped:{a.value}")
            continue
        if a.kind == "open":
            stack.append(True)
            out.append("(")
            continue
        if a.kind == "close":
            ok = stack.pop() if stack else True
            if ok:
                out.append(")")
            continue
        out.extend(_atom123_to_ours(a, losses))
    return out


def _our_note_text(n: Note) -> str:
    octs = "g" * n.octv if n.octv > 0 else "," * (-n.octv)
    beams = "_" * n.beams
    dots = "." * n.dots
    if n.deg in (8, 9):
        return f"{n.deg}{octs}{beams}{dots}"
    return f"{n.deg}{octs}{n.acc}{beams}{dots}"


def _pair_tildes(tokens: list[str]) -> list[str]:
    """`A ~ B` → `(A B)`；多音共享的 ~ 依次成对。

    这里按「左音符 = 已输出的最后一个音符」处理，右音符从后续 token 里找，
    避免一次性 insert 改变下标。
    """
    note_re = re.compile(r"^[#b]?\d[',_\.]*$")
    out: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t != "~":
            out.append(t)
            i += 1
            continue
        # 找左音符：已输出里最后一个音符 token
        left = None
        for j in range(len(out) - 1, -1, -1):
            if note_re.fullmatch(out[j] or ""):
                left = j
                break
        # 找右音符：后续第一个音符 token（跳过空格/记号/|）
        j = i + 1
        right = None
        while j < len(tokens):
            if note_re.fullmatch(tokens[j] or ""):
                right = j
                break
            j += 1
        if left is None or right is None:
            i += 1
            continue
        out.insert(left, "(")
        out.append(tokens[right])
        out.append(")")
        i = right + 1
    return out


# --------------------------------------------------------------------------- #
# 123 文本的解析（头部 + 分行 + 歌词）
# --------------------------------------------------------------------------- #

FIELD_RE = re.compile(r"^([A-Za-z])\s*[:：](.*)$")
CN_FIELDS = {
    "曲号": "X", "标题": "T", "副标题": "T", "词曲": "C", "调": "K",
    "拍": "M", "速度": "Q", "声部": "V", "歌词": "w", "段": "w",
    "顺序": "P", "演唱": "I", "注": "N", "样式": "I",
}


def _parse_header(lines: list[str]):
    headers: dict[str, list[str]] = {}
    music_blocks: list[dict] = []
    cur_music: list[str] = []
    cur_lyrics: list[str] = []
    cur_voice: int | None = None

    def flush():
        nonlocal cur_music, cur_lyrics
        if cur_music or cur_lyrics:
            music_blocks.append({"music": " ".join(cur_music), "lyrics": list(cur_lyrics),
                                 "voice": cur_voice})
        cur_music, cur_lyrics = [], []

    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if line.lstrip().startswith("%"):
            continue
        m = FIELD_RE.match(line)
        key = None
        val = None
        if m and (m.group(1) in "XTCKMQPVINZOSRBDGHFWUIL" or m.group(1) in "wW"):
            key, val = m.group(1), m.group(2)
        else:
            for cn, k in CN_FIELDS.items():
                if line.startswith(cn + "：") or line.startswith(cn + ":"):
                    key, val = k, line[len(cn) + 1:]
                    break
        if key in ("w", "W"):
            cur_lyrics.append(val.strip())
            continue
        if key == "V":
            flush()
            m = re.match(r"(\d+)", val.strip())
            cur_voice = int(m.group(1)) if m else 1
            headers.setdefault("V", []).append(val.strip())
            continue
        if key is not None:
            # 头部字段：只有出现在第一条音乐行之前才算“头部”；
            # 之后出现的 K/M 行内改调也应保留（暂记入 headers 的多值）
            headers.setdefault(key, []).append(val.strip())
            continue
        # 音乐行
        if cur_lyrics:
            flush()
        cur_music.append(line.strip())
    flush()
    return headers, music_blocks


def rev_123(text: str) -> dict:
    """123 文本 → {"songdata": {...}, "losses": [...], "meta": {...}}"""
    losses: list[str] = []

    # fwd 写入的溯源注释（Dolce 忽略 `%` 行；外国 123 没有这些行也能用）
    meta = {}
    for line in text.splitlines():
        if line.startswith("%JIANPU-KEYNOTE-SOURCE:"):
            meta["keynote_source"] = line.split(":", 1)[1].strip()
        elif line.startswith("%JIANPU-KEYNOTE:"):
            # 原样保留（含尾随空格）：实测 `1=A  ` 与 `1=A` 在源 runtime 里落点不同
            meta["keynote_raw"] = line.split(":", 1)[1]
        elif line.startswith("%JIANPU-CLEF-SHIFT:"):
            meta["clef_shift"] = line.split(":", 1)[1].strip()

    headers, blocks = _parse_header(text.splitlines())

    body_tokens: list[str] = []
    lyric_verses: list[str] = []

    voice_ids = sorted({b["voice"] for b in blocks if b.get("voice") is not None})
    if len(voice_ids) > 1:
        first_voice = voice_ids[0]
        blocks = [b for b in blocks if b.get("voice") in (None, first_voice)]
        losses.append(f"multi-voice-first-only:{len(voice_ids)}")

    for b in blocks:
        music = b["music"]
        # 去掉行内换行符
        music = music.replace("$", " ")
        atoms = _scan_123_body(music, losses)
        toks = _atoms123_to_ours(atoms, losses)
        toks = _pair_tildes(toks)
        body_tokens.extend(t for t in toks if t)
        for idx, w in enumerate(b["lyrics"]):
            verse = _lyric_123_to_ours(w)
            while len(lyric_verses) <= idx:
                lyric_verses.append("")
            lyric_verses[idx] += verse

    notation = " ".join(body_tokens)
    notation = re.sub(r"\s+", " ", notation).strip()
    notation = notation.replace(" | | ", " | ")

    # 头部元数据
    key_raw = (headers.get("K") or [None])[0]
    keynote = None
    if key_raw:
        keynote = key_raw if key_raw.startswith("1=") else f"1={key_raw}"
    if meta.get("keynote_source") == "missing":
        keynote = ""
    elif meta.get("keynote_raw"):
        keynote = meta["keynote_raw"]
    rhythm = (headers.get("M") or [DEFAULT_RHYTHM])[0]
    rhythm = rhythm.split()[0] if rhythm.split() else DEFAULT_RHYTHM
    bpm = DEFAULT_BPM
    q = (headers.get("Q") or [None])[0]
    if q:
        m = re.search(r"=\s*([0-9.]+)", q)
        if m:
            bpm = float(m.group(1))
    title = (headers.get("T") or ["Untitled"])[0] or "Untitled"

    voices = headers.get("V") or []
    clefs = [v for v in voices if "clef=" in v]
    key_upper = (keynote or "").lstrip("1=#b").upper()
    for v in clefs:
        shift = re.search(r"clef=treble([+-]8)", v)
        if not shift:
            continue
        if meta.get("clef_shift"):
            # fwd 写入的补偿：源调号本身已携带该八度信息，原样还原即可
            continue
        if key_upper == "B" or not keynote:
            losses.append("clef-octave-shift-treated-as-our-compensation")
        else:
            losses.append(f"clef-octave-shift-unapplied:{shift.group(1)}")

    notation = "{bpm:%g} " % bpm + notation
    songdata = {
        "song_name": title,
        "keynote": keynote or "",
        "rhythm": rhythm,
        "bpm": bpm,
        "notation": notation,
        "lyric": json.dumps(lyric_verses, ensure_ascii=False) if lyric_verses else "[]",
    }
    return {"songdata": songdata, "losses": losses,
            "meta": {"verses": len(lyric_verses), "blocks": len(blocks),
                     "voices": len(voices)}}


def _lyric_123_to_ours(line: str) -> str:
    # 123 的对位符号 → 我方：/ 跳音符 = 我方 `_` 空槽；_ melisma 同样落成空槽
    s = line
    s = s.replace("\\/", "\x00SLASH\x00").replace("\\-", "\x00DASH\x00")
    s = s.replace("/", "_").replace("*", "_")
    # 123 的 {...} 是多字挤一格；我方是 (...)。
    # 单字标点的 {...} 是 fwd 用来强制占位的，还原成裸标点。
    def _brace(m):
        v = m.group(1)
        if len(v) == 1 and v in WRAP_PUNCT:
            return v
        return "(" + v + ")"
    s = re.sub(r"\{([^{}]*)\}", _brace, s)
    s = re.sub(r"<(\d+)\.>", "", s)
    s = s.replace("\x00SLASH\x00", "/").replace("\x00DASH\x00", "-")
    # 段内空格只是分词，不占位
    s = re.sub(r"\s+", "", s)
    return s


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "fwd":
        song = json.load(open(sys.argv[2], encoding="utf8"))["songdata"]
        print(ours_to_123(song)["text"])
    elif len(sys.argv) >= 3 and sys.argv[1] == "rev":
        print(json.dumps(rev_123(open(sys.argv[2], encoding="utf8").read()),
                         ensure_ascii=False, indent=2))
    else:
        print("usage: jp123_bidir.py fwd <phrase.json> | rev <file.123>", file=sys.stderr)
        sys.exit(2)
