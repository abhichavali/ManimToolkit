"""Scene docs: say what's on screen and on which word, not where and for how long. Same manim, same Cairo pixels.

class S03_Split(Doc):
    def construct(self):
        eq, plot = EQ(r"X_k = E_k + z^k O_k"), axes([0, 1], [0, 1])
        self.line(1, {"Here": self.stage(top=eq, center=plot), "split": Indicate(part(eq, "E_k"))})

Narration and budget come from BRIEF.md by beat number, cues fire on the words the voice actually says, and stage()
lays out the next picture so it can't overlap: what it doesn't list leaves, what it lists again glides, the rest enters.
A Doc is a VScene, so anything else manim or mtk can do still works, in the same file.
"""
import re
import wave
from pathlib import Path

import numpy as np
from manim import DOWN, FadeIn, FadeOut, MathTex, MoveToTarget, RIGHT, UP, VGroup, config

from .core import COLORS, INK, T, VScene, _texts

MARGIN, GAP, MIN_SIZE, MOVE = 0.45, 0.35, 22, 0.8
TOKEN = r"(?<![A-Za-z\\])({})(?![A-Za-z_^])"


def word_times(path, text):
    """Start time of each word of text in its wav. Clause breaks snap to the pauses in the audio, and words inside a
    clause share its time by length."""
    # ponytail: no forced alignment, so a word mid-clause is an estimate; use a Whisper alignment if cues land visibly late
    with wave.open(str(path)) as w:
        rate, pcm = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
    hop = max(1, rate // 100)
    env = np.sqrt(np.convolve(pcm ** 2, np.ones(hop) / hop, "same"))[::hop]
    on = env > 0.05 * (env.max() or 1)
    if not on.any():
        return [0.0] * len(text.split())
    a, b = np.argmax(on), len(on) - np.argmax(on[::-1])
    gaps, i = [], a
    while i < b:  # the middles of the silent runs
        if not on[i]:
            j = i
            while j < b and not on[j]:
                j += 1
            if j - i >= 6:
                gaps.append((i + j) / 2)
            i = j
        i += 1
    words = text.split()
    size = np.array([sum(c.isalnum() for c in w) + 1 for w in words], float)
    at = (np.r_[0, np.cumsum(size)] / size.sum() * (b - a) + a)[:-1]
    breaks = [k + 1 for k, w in enumerate(words[:-1]) if w[-1] in ",.;:?!"]
    start, last, knots = 0, a, [(0, a)]
    for k in breaks:  # each break takes the nearest later pause within reach
        near = [g for g in gaps if g > last and abs(g - at[k]) < 0.15 * (b - a)]
        if near:
            last = min(near, key=lambda g: abs(g - at[k]))
            knots.append((k, last))
    knots.append((len(words), b))
    out = np.zeros(len(words))
    for (k0, t0), (k1, t1) in zip(knots, knots[1:]):
        share = np.r_[0, np.cumsum(size[k0:k1])][:-1] / size[k0:k1].sum()
        out[k0:k1] = t0 + share * (t1 - t0)
    return [float(x) / (rate / hop) for x in out]


def find_phrase(phrase, text, after=0):
    """Index of the word where phrase starts, at or after word `after`."""
    norm = lambda s: re.sub(r"\W", "", s).lower()
    words, want = [norm(w) for w in text.split()], [norm(w) for w in phrase.split()]
    for i in range(after, len(words) - len(want) + 1):
        if words[i:i + len(want)] == want:
            return i
    raise ValueError(f"cue {phrase!r} isn't in the rest of the line: {' '.join(text.split()[after:])!r}")


def tex_parts(tex, keys):
    """Split TeX around concept tokens that stand alone at brace depth 0, so each gets its color. Never inside a
    \\left...\\right, where the pieces wouldn't compile."""
    if not keys or r"\left" in tex:
        return [tex]
    pat = re.compile(TOKEN.format("|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))))
    parts, i, depth = [], 0, [0]
    for ch in tex:
        depth.append(depth[-1] + (ch == "{") - (ch == "}"))
    for m in pat.finditer(tex):
        if depth[m.start()] == 0 and depth[m.end()] == 0:
            parts += [tex[i:m.start()], m.group(1)]
            i = m.end()
    return [p for p in (x.strip() for x in parts + [tex[i:]]) if p]


def EQ(tex, size=44, color=INK, cmap=None, **kw):
    """Math with every concept in colors(...) colored for you. part(eq, "E_k") gets one of them."""
    cm = {**COLORS, **(cmap or {})}
    m = MathTex(*tex_parts(tex, cm), font_size=size, color=color, **kw)
    for p in m:
        if p.tex_string.strip() in cm:
            p.set_color(cm[p.tex_string.strip()])
    return m


def part(eq, tex):
    """The piece of an EQ whose TeX is exactly tex."""
    for p in eq:
        if p.tex_string.strip() == tex:
            return p
    raise ValueError(f"no part {tex!r} in {[p.tex_string for p in eq]}")


def mix(s, size=30, color=INK):
    """Words in the video's font with $math$ among them: mix("same speed as $z$")."""
    bits = [EQ(x, size=size * 4 // 3, color=color) if i % 2 else T(x.strip(), size, color)
            for i, x in enumerate(s.split("$")) if x.strip()]
    return VGroup(*bits).arrange(RIGHT, buff=0.14)


def _stack(item):
    return list(item) if isinstance(item, (list, tuple)) else [] if item is None else [item]


def solve(slots, width, height, margin=MARGIN, gap=GAP):
    """Boxes that can't overlap, for {slot: [(w, h), ...]}. Bands top and bottom take their height and the columns left,
    center, right share the rest, each by its need. Returns ({slot: scale}, {slot: (x, y, w, h)})."""
    # ponytail: a five-slot grid, not a general constraint solver; add slots when real scenes can't say what they need
    W, H = width - 2 * margin, height - 2 * margin
    need = {s: (max(w for w, _ in v), sum(h for _, h in v) + gap * (len(v) - 1)) for s, v in slots.items() if v}
    bands = [s for s in ("top", "bottom") if s in need]
    cols = [s for s in ("left", "center", "right") if s in need]
    keep = H - gap * (len(bands) - (not cols)) - (2.5 if cols else 0)  # columns keep some room to breathe
    want = sum(need[s][1] for s in bands)
    band = {s: need[s][1] * min(1, keep / want) for s in bands} if bands else {}
    mid_h = H - sum(band.values()) - gap * len(bands)
    box = {}
    if "top" in band:
        box["top"] = (0, H / 2 - band["top"] / 2, W, band["top"])
    if "bottom" in band:
        box["bottom"] = (0, -H / 2 + band["bottom"] / 2, W, band["bottom"])
    y = (band.get("bottom", 0) + gap * ("bottom" in band) - band.get("top", 0) - gap * ("top" in band)) / 2
    if cols:
        free = W - gap * (len(cols) - 1)
        total = sum(need[s][0] for s in cols)
        widths = [need[s][0] * free / total if total > free else need[s][0] + (free - total) / len(cols) for s in cols]
        x = -W / 2
        for s, w in zip(cols, widths):
            box[s] = (x + w / 2, y, w, mid_h)
            x += w + gap
    return {s: min(1, box[s][2] / need[s][0], box[s][3] / need[s][1]) for s in need}, box


class Stage:
    """The next picture. It's placed when you call stage(), and what enters or leaves is settled when it plays."""

    def __init__(self, scene, listed, later, keep):
        self.scene, self.listed, self.later, self.keep = scene, listed, later, keep

    def anims(self):
        sc = self.scene
        now = {id(x) for m in sc.mobjects for x in m.get_family()}
        ids = {id(x) for m in [*self.listed, *self.later, *self.keep] for x in m.get_family()}
        spot = getattr(sc, "_spot", None)
        ids |= {id(x) for m in ((spot[0], *spot[1]) if spot else ()) for x in m.get_family()}
        stays = lambda m: any(id(x) in ids for x in m.get_family()) or (
            id(m) in sc._follows and any(id(x) in ids for x in sc._follows[id(m)][1].get_family()))
        out = []
        for m in sc.mobjects:
            if not stays(m):
                m.clear_updaters()
                out.append(FadeOut(m))
        for m in self.listed:
            if any(id(x) in now for x in m.get_family()):
                if getattr(m, "_stage_to", None) is not None:  # not .target: .animate uses that for its own move
                    m.target, m._stage_to = m._stage_to, None
                    out.append(MoveToTarget(m))
            elif not any(m is x for x in self.later):
                out.append(FadeIn(m))
        return out


class Doc(VScene):
    """A scene written against BRIEF.md: self.line(n, {word: animation}), self.stage(...), self.follow(...)."""

    def setup(self):
        super().setup()
        from mtk_cli import script
        name = type(self).__name__
        path = Path(config.input_file).resolve().parent / "BRIEF.md"
        got = script(path) if path.exists() else {}
        if name not in got:
            raise ValueError(f"{name} isn't a scene in {path}; its heading there must match the class name")
        budget, self.lines = got[name]
        self.budget, self._played, self._follows = self.budget or budget, [], {}

    def play(self, *args, **kw):
        args = [a for x in args for a in (x.anims() if isinstance(x, Stage) else [x])]
        now = {id(x) for m in self.mobjects for x in m.get_family()}
        moving = {id(a.mobject): a for a in args if hasattr(a, "mobject")}
        for label, anchor in self._follows.values():  # a label enters and leaves with its anchor
            a = moving.get(id(anchor))
            if a is not None and id(label) not in moving:
                if isinstance(a, FadeOut) and id(label) in now:
                    args.append(FadeOut(label))
                elif not isinstance(a, FadeOut) and id(label) not in now:
                    args.append(FadeIn(label))
        if args:
            super().play(*args, **kw)

    def line(self, n, cues=None, style=None):
        """Say beat n of the brief. cues: {phrase: animation, list of them, or (animation(s), seconds)}, in spoken order.
        Each starts on its phrase and takes until the next cue, at most 1.2 s, unless it says how long."""
        text, st = self._take(n)
        from .core import tts
        path = tts(text, style=style or st)[0]
        times = word_times(path, text)
        plan, after = [], 0
        for phrase, item in (cues or {}).items():
            after = find_phrase(phrase, text, after)
            secs = item[1] if isinstance(item, tuple) else None
            anim = item[0] if isinstance(item, tuple) else item
            plan.append((times[after], anim if isinstance(anim, list) else [anim], secs))
        with self.say(text, style=style or st) as d:
            t0 = self.time
            for k, (at, anims, secs) in enumerate(plan):
                if t0 + at > self.time + 0.02:
                    self.wait(t0 + at - self.time)
                until = t0 + (plan[k + 1][0] if k + 1 < len(plan) else d)
                self.play(*anims, run_time=secs or float(np.clip(until - self.time, 0.25, 1.2)))

    def predict(self, question, narration, seconds=3.0):
        """Pause and ponder. narration: a beat number of the brief."""
        return super().predict(question, self._take(narration)[0] if isinstance(narration, int) else narration, seconds)

    def _take(self, n):
        if not 1 <= n <= len(self.lines):
            raise ValueError(f"beat {n}: {type(self).__name__} has beats 1 to {len(self.lines)} in BRIEF.md")
        if self._played and n <= self._played[-1]:
            self._warn(("order", n), f"beat {n} plays after beat {self._played[-1]}: the brief's order is the story")
        self._played.append(n)
        return self.lines[n - 1]

    def stage(self, top=None, bottom=None, left=None, right=None, center=None, later=(), keep=()):
        """Lay out the next picture. A slot takes a mobject or a tuple to stack downward. later: placed, but you bring it in
        with a cue. keep: stays where it is. Whatever else is on screen leaves. Play it as a cue, or with self.play."""
        slots = {s: _stack(v) for s, v in dict(top=top, bottom=bottom, left=left, right=right, center=center).items() if v is not None}
        later, keep = _stack(later), _stack(keep)
        for m in [m for v in slots.values() for m in v]:  # undo the last stage's shrink, so a roomier slot grows it back
            m._was = getattr(m, "_shrunk", 1.0)
        sizes = {s: [(m.width / m._was, m.height / m._was) for m in v] for s, v in slots.items()}
        scale, box = solve(sizes, config.frame_width, config.frame_height)
        now = {id(x) for m in self.mobjects for x in m.get_family()}
        for s, v in slots.items():
            k, (x, y, _, h) = scale[s], box[s]
            total = sum(hh * k for _, hh in sizes[s]) + GAP * (len(v) - 1)
            top_y = y + total / 2
            for m, (_, hh) in zip(v, sizes[s]):
                small = [t.font_size * k / m._was for t in _texts(m) if getattr(t, "font_size", None)]
                if small and min(small) < MIN_SIZE:
                    self._warn(("fit", id(m)), f"stage {s}: no room, its text shrinks to size {min(small):.0f}; "
                                               "move something to another slot or take it off this picture")
                on = any(id(q) in now for q in m.get_family())
                t = m.copy() if on else m
                t.scale(k / m._was)
                t.move_to([x, top_y - hh * k / 2, 0])
                m._shrunk, m._stage_to = k, t if on else None
                top_y -= hh * k + GAP
        return Stage(self, [m for v in slots.values() for m in v], later, keep)

    def follow(self, label, anchor, side=UP, buff=0.2):
        """Keep label beside anchor, wherever anchor goes; it leaves when anchor does."""
        label.add_updater(lambda m: m.next_to(anchor, side, buff=buff))
        label.next_to(anchor, side, buff=buff)
        self._follows[id(label)] = (label, anchor)
        return label

    def tear_down(self):
        missing = [i + 1 for i in range(len(self.lines)) if i + 1 not in self._played]
        if missing:
            self._warn("beats", f"beats {missing} of the brief never play")
        super().tear_down()
