"""Look, narration and self-checks. Successor of the per-project vid.py (same look, same API, plus beat()).

Narration: `with self.say("text") as d:` adds a Gemini TTS clip (cached in <scene dir>/audio) at the current
time; animations inside the block take run_time fractions of d, and the block waits out the rest of the clip.
`self.beat("text", anim1, [anim2, anim3], 0.1, anim4)` is the one-liner form: steps play in order and share the clip.
Key: OPENROUTER_API_KEY, else the file named by OPENROUTER_KEY_FILE, else ~/.config/manim-explainer/openrouter_key.
"""
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import wave
from contextlib import contextmanager
from pathlib import Path

import numpy as np
from manim import *
from manim.utils.family import extract_mobject_family_members

# ---------- look ----------
BG = "#0f1116"
SURFACE = "#15171c"
INK = "#eef0f4"
INK2 = "#b4b9c6"
MUTED = "#7d8394"
HAIR = "#262a33"
AXIS = "#3a3f4b"
ACCENT = "#95a2ff"
GOOD = "#35c46a"
BAD = "#ff6b6b"
# concept hues: give each recurring idea one hue and keep it for the whole video
# (named so they don't shadow manim's BLUE, ORANGE, ...)
SKY = "#4a95ff"
EMBER = "#ff7a3d"
MINT = "#22c58b"
LILAC = "#a497ff"
LIME = "#3fcf3f"
ROSE = "#f06ea0"
GOLD = "#ffd27a"
PALETTE = [SKY, EMBER, MINT, LILAC, LIME, ROSE]

FONT = "Avenir Next"
config.background_color = BG
config.no_latex_cleanup = True  # parallel renders share media/Tex; cleanup deletes files another render needs

tpl = TexTemplate(documentclass=r"\documentclass{article}")  # BasicTeX has no standalone.cls
tpl.preamble = r"\usepackage{amsmath}\usepackage{amssymb}\pagestyle{empty}"
config.tex_template = tpl

# concept -> color, used by E(); set once per video with colors(p=SKY, q=MINT, ...) or COLORS.update({...})
COLORS = {}


def colors(**kw):
    COLORS.update(kw)


def T(s, size=30, color=INK, weight=NORMAL, **kw):
    """Words (Pango). Never put math symbols here; use M or E."""
    return Text(s, font=FONT, font_size=size, color=color, weight=weight, **kw)


def M(*s, size=40, color=INK, **kw):
    return MathTex(*s, font_size=size, color=color, **kw)


def E(tex, size=44, color=INK, cmap=None, **kw):
    """MathTex from 'a|b|c' parts; a part whose TeX equals a key of COLORS (or cmap) gets that color.
    E(r"p|=|s|\\cdot|q|+|r") with colors(p=SKY, s=EMBER, q=MINT, r=LILAC). Index parts as e[0], e[2], ..."""
    m = MathTex(*tex.split("|"), font_size=size, color=color, **kw)
    cm = {**COLORS, **(cmap or {})}
    for part in m:
        c = cm.get(part.tex_string.strip())
        if c:
            part.set_color(c)
    return m


def TX(s, size=30, color=INK, **kw):
    """A sentence with inline math: TX(r"for every $x \\in A$, ..."). LaTeX text font, not Avenir."""
    return Tex(s, font_size=size, color=color, **kw)


def axes(x_range, y_range, width=6, height=3, xlabel="x", ylabel="y", pi_ticks=False, boxed=False, **kw):
    """Plain dark-theme axes. pi_ticks labels 0, pi, 2pi on a [0, 2pi] x-axis.
    boxed=True frames the plot region instead of crossing axes at the origin (use under heat maps)."""
    if boxed:
        ax = axes(x_range, y_range, width, height, "", "", pi_ticks, **kw)
        ax.y_axis.set_stroke(opacity=0)  # the frame replaces it (moving axes would break c2p)
        if y_range[0] != 0:
            ax.x_axis.set_stroke(opacity=0)
        lo, hi = ax.c2p(x_range[0], y_range[0]), ax.c2p(x_range[1], y_range[1])
        frame = Rectangle(width=hi[0] - lo[0], height=hi[1] - lo[1], stroke_color=AXIS, stroke_width=2)
        ax.add(frame.move_to((lo + hi) / 2))
        if xlabel:
            ax.add(M(xlabel, size=28, color=MUTED).next_to(frame.get_corner(DR), RIGHT, buff=0.15))
        if ylabel:
            ax.add(M(ylabel, size=28, color=MUTED).next_to(frame, LEFT, buff=0.15).align_to(frame, UP))
        return ax
    ax = Axes(
        x_range=x_range, y_range=y_range, x_length=width, y_length=height,
        axis_config={"color": AXIS, "stroke_width": 2, "include_ticks": not pi_ticks, "tick_size": 0.05,
                     "include_tip": False},
        **kw,
    )
    if pi_ticks:
        for v, lab in [(0, "0"), (PI, r"\pi"), (TAU, r"2\pi")]:
            if x_range[0] <= v <= x_range[1]:
                ax.add(M(lab, size=24, color=MUTED).next_to(ax.c2p(v, y_range[0]), DOWN, buff=0.15))
    if xlabel:
        ax.add(M(xlabel, size=28, color=MUTED).next_to(ax.x_axis.get_right(), RIGHT, buff=0.12))
    if ylabel:
        ax.add(M(ylabel, size=28, color=MUTED).next_to(ax.y_axis.get_top(), UP, buff=0.12))
    return ax


def ramp(stops, v):
    """Piecewise-linear colormap; stops = [(pos, '#rrggbb'), ...], v in [0, 1] (array ok)."""
    pos = np.array([p for p, _ in stops])
    rgb = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for _, c in stops], float)
    return np.stack([np.interp(v, pos, rgb[:, j]) for j in range(3)], -1)


CMAP_DIV = [(0, "#2a6fdb"), (0.25, SKY), (0.5, BG), (0.75, EMBER), (1, GOLD)]
CMAP_SEQ = [(0, BG), (0.35, "#3b2a7a"), (0.7, EMBER), (1, "#fff1b8")]


def field_image(f, ax, x_range, y_range, cmap="seq", vmax=1.0, nx=480, ny=360, opacity=1.0):
    """Heat map of f(X, Y) (vectorized numpy) fitted to axes ax; y increases upward. Signed fields: cmap='div'."""
    xs = np.linspace(*x_range, nx)
    ys = np.linspace(*y_range, ny)[::-1]  # image row 0 = top = largest y
    X, Y = np.meshgrid(xs, ys)
    F = f(X, Y)
    if cmap == "div":
        rgb = ramp(CMAP_DIV, np.clip(0.5 + 0.5 * F / vmax, 0, 1))
    else:
        rgb = ramp(CMAP_SEQ, np.clip(F / vmax, 0, 1))
    a = np.full(F.shape + (1,), 255 * opacity)
    img = ImageMobject(np.concatenate([rgb, a], -1).astype(np.uint8))
    p0, p1 = ax.c2p(x_range[0], y_range[0]), ax.c2p(x_range[1], y_range[1])
    img.stretch_to_fit_width(p1[0] - p0[0]).stretch_to_fit_height(p1[1] - p0[1])
    img.move_to((p0 + p1) / 2)
    return img


def key_box(*lines, width=11, color=ACCENT, label="KEY IDEA"):
    """Summary card: lines are MathTex strings (wrap words in \\text{}) or mobjects, e.g. E(...) for concept colors."""
    body = VGroup(*[l if isinstance(l, Mobject) else M(l, size=36) for l in lines]).arrange(DOWN, buff=0.25)
    inner = VGroup(T(label, 22, color, weight=BOLD), body).arrange(DOWN, buff=0.3)
    box = RoundedRectangle(corner_radius=0.2, width=max(width, inner.width + 0.8), height=inner.height + 0.7,
                           stroke_color=color, stroke_width=2.5, fill_color=SURFACE, fill_opacity=1)
    return VGroup(box, inner.move_to(box))


def glow(m, color=None, layers=8, width=24, opacity=0.6):
    """Soft halo behind m: stacked stroke copies, so the core is brightest. FadeIn(glow(eq)) under a reveal."""
    color = color or m.get_color()
    g = VGroup(*[m.copy().set_fill(opacity=0).set_stroke(color, width=width * i / layers, opacity=opacity / layers)
                 for i in range(layers, 0, -1)])
    for x in g.family_members_with_points():
        x.joint_type = LineJointType.ROUND  # miter joints spike out of glyph corners
    return g


# layout slots (center, width, height) in the 14.2 x 8 frame, clear of the section header
REGIONS = {"full": ((0, -0.25, 0), 13.0, 6.6), "left": ((-3.45, -0.25, 0), 6.3, 6.6),
           "right": ((3.45, -0.25, 0), 6.3, 6.6), "top": ((0, 2.15, 0), 13.0, 2.4),
           "bottom": ((0, -2.4, 0), 13.0, 2.4)}


def place(m, region="full"):
    """Shrink m (never grow) to fit a REGIONS slot and center it there. Split screens: place(a, 'left'), place(b, 'right')."""
    c, w, h = REGIONS[region]
    if m.width > w or m.height > h:
        m.scale(min(w / m.width, h / m.height))
    return m.move_to(c)


def live(ax, f, tt, x_range=None, color=SKY, width=4, n=240, **kw):
    """Curve of f(x, t) on ax that redraws as ValueTracker tt moves (t = tt.get_value()). kw go to ax.plot
    (e.g. stroke_opacity). Raise n for wiggly curves: n samples across x_range."""
    a, b = x_range or ax.x_range[:2]
    return always_redraw(lambda: ax.plot(lambda x: f(x, tt.get_value()), x_range=[a, b, (b - a) / n],
                                         color=color, stroke_width=width, **kw))


def dashed(m, n=50):
    """Dashed copy of a curve: initial data, reference curves, 'what it would have been'."""
    return DashedVMobject(m, num_dashes=n)


def backed(m, opacity=0.85):
    """m on a background-colored plate, so grid lines or fields behind it don't cut through the text."""
    return VGroup(BackgroundRectangle(m, color=BG, fill_opacity=opacity, buff=0.08), m)


def readout(tex, fn, digits=3, size=34, color=INK):
    """Live number: label (MathTex) followed by fn() to `digits` places, updated every frame.
    Clear its updaters before fading it out (drop()/wipe() do) or a sign change mid-fade crashes manim."""
    lab = M(tex, size=size, color=color)
    num = DecimalNumber(fn(), num_decimal_places=digits, font_size=size, color=color).next_to(lab, RIGHT, buff=0.15)
    num.add_updater(lambda m: m.set_value(fn()))
    return VGroup(lab, num)


def chip(name, color):
    t = T(name, 22, color, weight=BOLD)
    r = RoundedRectangle(corner_radius=0.12, width=t.width + 0.35, height=t.height + 0.22,
                         stroke_color=color, stroke_width=2, fill_color=color, fill_opacity=0.12)
    return VGroup(r, t.move_to(r))


# ---------- narration ----------
TTS_URL = "https://openrouter.ai/api/v1/audio/speech"
TTS_MODEL = "google/gemini-3.8-flash-tts"
VOICE = "Puck"
STYLE = "energetic, crystal-clear teacher; warm, curious, confident, conversational, brisk pace"
RATE = 24000  # response is raw PCM s16le, mono, 24 kHz
KEY_FILE = Path.home() / ".config/manim-explainer/openrouter_key"
_QUOTA = {"out": False}


def audio_dir():
    """<folder of the scene file manim was given>/audio, else ./audio."""
    f = config.input_file
    d = (Path(f).resolve().parent if f else Path.cwd()) / "audio"
    d.mkdir(exist_ok=True)
    return d


def _key():
    k = os.environ.get("OPENROUTER_API_KEY")
    if not k:
        f = Path(os.environ.get("OPENROUTER_KEY_FILE", KEY_FILE))
        k = f.read_text().strip() if f.exists() else None
    if not k:
        raise RuntimeError(f"set OPENROUTER_API_KEY or put the key in {KEY_FILE} to render narration")
    return k


def _say_fallback(text, h):
    """Draft-only stand-in when the key is over its spending limit: macOS `say`, cached as <hash>.say.wav,
    so the real voice replaces it automatically once the API works again. Never ship these."""
    out = audio_dir() / f"{h}.say.wav"
    if not out.exists():
        tmp = out.with_suffix(".tmp.wav")
        subprocess.run(["say", "-v", "Samantha", "-r", "185", "--file-format=WAVE", "--data-format=LEI16@24000",
                        "-o", str(tmp), text], check=True)
        tmp.rename(out)
    if not _QUOTA.get("warned"):
        _QUOTA["warned"] = True
        why = "MTK_TTS=say" if os.environ.get("MTK_TTS") == "say" else "OpenRouter key limit reached"
        print(f"LINT TTS: {why}; using the macOS draft voice (re-render with the real voice before shipping)",
              flush=True)
    return out


def tts(text, voice=None, style=None):
    """Return (wav_path, seconds) for text, calling the API only on a cache miss."""
    voice, style = voice or VOICE, style or STYLE
    h = hashlib.sha1(f"{TTS_MODEL}|{voice}|{style}|{text}".encode()).hexdigest()[:16]
    path = audio_dir() / f"{h}.wav"
    if os.environ.get("MTK_TTS") == "say":  # offline/free draft voice (tests); never ship it
        _QUOTA["out"] = True
    if not path.exists() and _QUOTA["out"]:
        path = _say_fallback(text, h)
    if not path.exists():
        # Gemini TTS speaks `input` verbatim; delivery style must go in speech_metadata.
        body = json.dumps({"model": TTS_MODEL, "voice": voice, "input": text, "provider": {"options": {
            "google-ai-studio": {"speech_metadata": {"style": style}}}}}).encode()
        req = urllib.request.Request(TTS_URL, body, {"Authorization": f"Bearer {_key()}",
                                                     "Content-Type": "application/json"})
        pcm = None
        for attempt in range(4):
            try:
                pcm = urllib.request.urlopen(req, timeout=180).read()
                break
            except urllib.error.HTTPError as e:
                if e.code in (402, 403):  # key or account spending limit: retrying won't help
                    _QUOTA["out"] = True
                    break
                if attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))
        if pcm is None:
            path = _say_fallback(text, h)
        else:
            tmp = path.with_suffix(".tmp")
            with wave.open(str(tmp), "wb") as w:
                w.setnchannels(1), w.setsampwidth(2), w.setframerate(RATE)
                w.writeframes(pcm)
            tmp.rename(path)
    with wave.open(str(path)) as w:
        return path, w.getnframes() / w.getframerate()


# ---------- self-checks ----------
TEXTY = (Text, MarkupText, SingleStringMathTex, DecimalNumber)  # MathTex and Tex subclass SingleStringMathTex
SYMBOLS = re.compile(r"[=+^_\\]|[Ͱ-Ͽ←-⋿]")
FROZEN = 6.0  # seconds of narration over an unchanging picture before lint complains
SNAP = os.environ.get("MTK_SNAP")  # `mtk check` sets it: a folder for one still per beat (the storyboard)


def _texts(m):
    """Outermost text-like mobjects in m's family (a MathTex counts once, not per part)."""
    return [m] if isinstance(m, TEXTY) else [t for s in m.submobjects for t in _texts(s)]


def _label(t):
    s = getattr(t, "original_text", None) or getattr(t, "tex_string", None) or type(t).__name__
    return repr(s[:28])


def _box(m):
    return m.get_left()[0], m.get_right()[0], m.get_bottom()[1], m.get_top()[1]


class Narrated:
    """Narration, cards, self-checks and storyboard stills shared by VScene (2D, movable camera) and VScene3D.

    After every play() it lints the frame and prints `LINT <scene> t=..s: ...`: text cut off by the frame edge,
    text on text, text too small, text hidden under a filled shape drawn after it, narration with math symbols,
    narration over a frozen picture. tear_down prints `REPORT <scene> <s> <words>w[/<budget>] <beats> beats <n> warnings`.
    Set a class attribute `budget = <words>` to get a LINT when the scene's narration misses it by over 20%.
    Turn the check off around a deliberate overlap with `self.lint_on = False`.
    """
    GAP = 0.3  # breath after each line
    lint_on = True
    budget = None

    def setup(self):
        super().setup()
        if SNAP:  # storyboard pass: step every frame (updaters, traced paths stay exact) but draw only the stills
            r = self.renderer

            def tick(*a, **k):  # what CairoRenderer.render does, minus drawing and writing the frame
                r.time += 1 / r.camera.frame_rate
            r.render = tick

    def _frame(self):
        f = getattr(self.camera, "frame", None)
        if f is None:
            return ORIGIN, config.frame_width, config.frame_height
        return f.get_center(), f.width, f.height

    def _warn(self, key, msg):
        seen = self.__dict__.setdefault("_seen", set())
        if key not in seen:
            seen.add(key)
            self._nwarn = getattr(self, "_nwarn", 0) + 1
            print(f"LINT {type(self).__name__} t={self.time:.1f}s: {msg}", flush=True)

    def _lint_roots(self):
        return self.mobjects

    def _lint(self):
        c, w, h = self._frame()
        zoom = config.frame_width / w
        L, R, B, U = c[0] - w / 2, c[0] + w / 2, c[1] - h / 2, c[1] + h / 2
        roots = self._lint_roots()
        texts = [t for m in roots for t in _texts(m)
                 if max((x.get_fill_opacity() for x in t.family_members_with_points()), default=0) > 0.05]
        boxes = [_box(t) for t in texts]
        for t, (l, r, b, tp) in zip(texts, boxes):
            inside = l < R and r > L and b < U and tp > B  # wholly off-screen (e.g. after a zoom) is fine
            if inside and (l < L or r > R or b < B or tp > U):
                self._warn((id(t), "edge"), f"{_label(t)} is cut off by the frame edge")
            fs = getattr(t, "font_size", None)
            if fs and fs * zoom < 20:
                self._warn((id(t), "small"), f"{_label(t)} renders at font size {fs * zoom:.0f} (< 20, unreadable)")
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                (l1, r1, b1, t1), (l2, r2, b2, t2) = boxes[i], boxes[j]
                ix, iy = min(r1, r2) - max(l1, l2), min(t1, t2) - max(b1, b2)
                small = min((r1 - l1) * (t1 - b1), (r2 - l2) * (t2 - b2))
                if ix > 0 and iy > 0 and ix * iy > 0.2 * small:
                    self._warn((id(texts[i]), id(texts[j]), "overlap"),
                               f"{_label(texts[i])} overlaps {_label(texts[j])}")
        if texts:
            self._lint_covered(roots, texts, w * h)

    def _lint_covered(self, roots, texts, area):
        """Text whose center sits under an opaque shape (or image) drawn after it: z-order bugs, cards drawn
        under nodes, labels buried by a later fill. Shapes over half the frame (deliberate dims) are skipped."""
        order = extract_mobject_family_members(roots, use_z_index=True, only_those_with_points=True)
        pos = {id(m): i for i, m in enumerate(order)}
        in_text = {id(x) for t in texts for x in t.get_family()}
        covers = []
        for i, m in enumerate(order):
            if id(m) in in_text:
                continue
            solid = isinstance(m, ImageMobject) or (isinstance(m, VMobject) and m.get_fill_opacity() > 0.5)
            if solid and m.width * m.height < 0.5 * area:
                covers.append((i, _box(m), m))
        for t in texts:
            last = max((pos.get(id(x), -1) for x in t.family_members_with_points()), default=-1)
            x, y = t.get_center()[:2]
            for i, (l, r, b, tp), m in covers:
                if i > last and l < x < r and b < y < tp:
                    self._warn((id(t), "covered"), f"{_label(t)} is hidden under a {type(m).__name__} drawn after it "
                                                   "(add it later or raise its z_index)")
                    break

    def play(self, *args, **kw):
        super().play(*args, **kw)
        if not all(isinstance(a, Wait) for a in args):
            self._dirty = True  # the picture changed since the last storyboard still
        if self.lint_on:
            self._lint()

    def snap(self, label=""):
        """Save a storyboard still now (only under `mtk check`). say()/beat() and wipe() call it for you."""
        if not SNAP:
            return
        shots = self.__dict__.setdefault("_snaps", [])
        if shots and not getattr(self, "_dirty", True):
            return
        self._dirty = False
        from PIL import Image
        r = self.renderer
        keep, r.static_image = r.static_image, None  # else static mobjects get painted twice
        r.update_frame(self, ignore_skipping=True)
        r.static_image = keep
        d = Path(SNAP)
        d.mkdir(parents=True, exist_ok=True)
        Image.fromarray(r.get_frame()).convert("RGB").save(d / f"{len(shots):02d}.png")
        shots.append({"t": round(self.time, 2), "text": label})

    def tear_down(self):
        super().tear_down()
        words, beats = getattr(self, "_words", 0), getattr(self, "_beats", 0)
        if self.budget and abs(words - self.budget) > 0.2 * self.budget:
            self._warn("budget", f"narration is {words} words; budget {self.budget} (keep within 20%)")
        if SNAP:
            if self.mobjects:
                self.snap("(end)")  # scenes that don't finish with wipe()
            Path(SNAP).mkdir(parents=True, exist_ok=True)
            (Path(SNAP) / "beats.json").write_text(json.dumps(getattr(self, "_snaps", [])))
        b = f"/{self.budget}" if self.budget else ""
        print(f"REPORT {type(self).__name__} {self.time:.1f}s {words}w{b} {beats} beats "
              f"{getattr(self, '_nwarn', 0)} warnings", flush=True)

    @contextmanager
    def say(self, text, style=None):
        """style overrides the delivery for this line only (e.g. 'slow, quiet, awed' for a reveal)."""
        n = len(text.split())
        self._words = getattr(self, "_words", 0) + n
        self._beats = getattr(self, "_beats", 0) + 1
        bad = sorted(set(SYMBOLS.findall(text)))
        if bad:
            self._warn(("say", text), f"narration contains {' '.join(bad)}; spell math out: {text[:40]!r}")
        if n > 60:
            self._warn(("long", text), f"narration line is {n} words; split it into beats: {text[:40]!r}")
        path, dur = tts(text, style=style)
        # straight to the file writer: Scene.add_sound is a no-op right after a cached animation
        self.renderer.file_writer.add_sound(str(path), self.time)
        t0 = self.time
        yield dur
        left = dur - (self.time - t0)
        if left > 0:
            if left > FROZEN and self.lint_on:
                self._warn(("frozen", t0), f"picture frozen for {left:.1f}s while narrating {text[:30]!r}: "
                                           "highlight what's being said, or split the beat")
            self.wait(left)
        self.snap(text)
        self.wait(self.GAP)

    def beat(self, text, *steps, w=None, style=None):
        """Narrate text while the steps play in order. A step is an animation, a list/tuple of animations played
        together, or a number = a pause, as a fraction of the clip. Animation steps share what the pauses leave,
        equally, unless w gives each one's fraction of the clip. self.beat("Here's the trick.") just talks."""
        anims = [s for s in steps if not isinstance(s, (int, float))]
        rest = 1 - sum(s for s in steps if isinstance(s, (int, float)))
        ws = iter(w if w is not None else [rest / max(1, len(anims))] * len(anims))
        if w is not None and len(w) != len(anims):
            raise ValueError(f"beat(): {len(anims)} animation steps but {len(w)} weights")
        with self.say(text, style=style) as d:
            for s in steps:
                if isinstance(s, (int, float)):
                    self.wait(s * d)
                else:
                    self.play(*(s if isinstance(s, (list, tuple)) else [s]), run_time=max(next(ws) * d, 1 / 30))

    def wipe(self, run_time=0.6):
        """Fade out everything on screen (updaters stopped first so nothing redraws mid-fade)."""
        if self.mobjects:
            self.snap()
            self.drop(*self.mobjects, run_time=run_time)

    def drop(self, *mobs, run_time=0.6):
        for m in mobs:
            m.clear_updaters()
        self.play(*[FadeOut(m) for m in mobs], run_time=run_time)

    def title_card(self, kicker, title, sub=None):
        g = VGroup(T(kicker.upper(), 22, ACCENT, weight=BOLD), T(title, 54, INK, weight=BOLD))
        if sub:
            g.add(T(sub, 28, INK2))
        g.arrange(DOWN, buff=0.35)
        if g.width > 12.5:
            g.scale_to_fit_width(12.5)
        bar = VGroup(*[Rectangle(width=1.2, height=0.08, stroke_width=0, fill_color=c, fill_opacity=1)
                       for c in PALETTE]).arrange(RIGHT, buff=0.08)
        bar.next_to(g, DOWN, buff=0.6)
        return VGroup(g, bar)

    def section(self, text):
        """Small persistent header at top-left; returns it so the caller can fade it out."""
        h = T(text.upper(), 22, MUTED, weight=BOLD).to_corner(UL, buff=0.4)
        self.play(FadeIn(h, shift=0.2 * RIGHT), run_time=0.5)
        return h

    def predict(self, question, narration, seconds=3.0):
        """'Pause and ponder' card: narration asks, then a ring drains for `seconds`, then it clears."""
        lab = T("PAUSE AND PONDER", 24, EMBER, weight=BOLD)
        q = T(question, 30, INK, line_spacing=1.2)
        if q.width > 11:
            q.scale_to_fit_width(11)
        ring = Circle(radius=0.32, color=EMBER, stroke_width=6).rotate(PI / 2)
        g = VGroup(lab, q, ring).arrange(DOWN, buff=0.4)
        box = SurroundingRectangle(g, buff=0.45, corner_radius=0.2, color=EMBER, stroke_width=2,
                                   fill_color=SURFACE, fill_opacity=1)
        dim = FullScreenRectangle(stroke_width=0, fill_color=BG, fill_opacity=0.8)
        card = Group(dim, box, g)
        card.set_z_index(100)  # above any z-indexed mobjects in the scene
        c, w, _ = self._frame()  # follow a moved or zoomed camera
        card.scale(w / config.frame_width).move_to(c)
        if isinstance(self, ThreeDScene):
            self.add_fixed_in_frame_mobjects(card)
        self.lint_on = False  # the card sits over the scene on purpose
        with self.say(narration):
            self.play(FadeIn(card, scale=0.95), run_time=0.6)
        self.play(Uncreate(ring), run_time=seconds, rate_func=linear)
        self.play(FadeOut(card), run_time=0.4)
        self.lint_on = True


class VScene(Narrated, MovingCameraScene):
    """2D scene; self.camera.frame can pan and zoom (self.play(self.camera.frame.animate.scale(0.4).move_to(p)))."""


class VScene3D(Narrated, ThreeDScene):
    """3D scene. Pin 2D text to the screen with self.add_fixed_in_frame_mobjects(...) before animating it in.
    Cairo 3D is slow: keep surface resolution modest and 3D stretches short."""

    def _lint_roots(self):
        return list(self.renderer.camera.fixed_in_frame_mobjects)  # free 3D text can't be checked in 2D
