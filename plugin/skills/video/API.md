# mtk: everything a scene writer needs

This page and your brief are all you read. Target: a polished 3Blue1Brown explainer. Visual first, then the
math that explains it. Dense, warm, no filler.

**Your job is one scene.** `mtk brief BRIEF.md S03` prints the shared facts and colors, what the scenes around
yours open with, and your scene: numbered beats, each a quoted narration line plus `→` what the screen does.
The narration is final and already voiced. Your work is the picture: turn each `→` into animation on that beat.
Plan briefly, write the scene in one go, then let `mtk check` and the storyboard tell you what to fix.

## The loop (this exact loop, nothing else)

```bash
mtk check s03_squares.py   # dry run, no video, a few seconds: LINT/REPORT lines + the scene's storyboard PNG
mtk check v2_x.py -s S03   # one scene of a multi-scene file (prefixes, comma-separated)
```
- One line per scene: length, words/budget, beats, warnings, storyboard path, `[NEW ]` or `[same]`. A crash
  prints `FAILED`, the line in your file and the exception, so you never need to open a log.
- A **storyboard** is one image per scene: a still at the end of every beat, captioned with its time and narration.
  Read it to judge the picture: overlap, clutter, a beat whose picture doesn't match its words, wrong colors,
  LaTeX glitches. Read only `[NEW ]` boards; `[same]` means nothing visible changed.
- Fix every `LINT` (or keep it on purpose and say why in your report). Then look. Then fix. Repeat.
- Write the whole file before the first check. Run `mtk check` in the foreground with a long Bash timeout
  (600000 ms); a voice missing from the cache is generated on the spot. Never background it or poll it.
- Done when lint is clean and every tile of the storyboard shows what its beat says, judged on the board of your
  final version (re-read it after your last change). Usually 1-3 rounds.
- Never render video (`manim -ql`, `mtk render`): the coordinator does the final pass.

## Skeleton

```python
"""S03: the remainder as a height (BRIEF.md S03)."""
from mtk import *                 # manim + numpy + everything below (PDE topics: from mtk.pde import *)
colors(p=SKY, s=EMBER, q=MINT)    # the video's concept -> hue map (same line in every file; E() reads it)

# facts: assert every number the narration says and every formula you plot, before any animation
assert np.isclose(2 ** 10, 1024)

class S03_Remainder(VScene):      # S## names, rendered in sorted order; 30-120 s each
    budget = 120                  # the [N] in the brief's heading: LINT if off by > 20%
    def construct(self):
        eq = E(r"p|=|s|\cdot|q|+|r", size=56)
        self.beat("Here's the whole idea in one line.", Write(eq))   # beat 1, quoted verbatim from the brief
        self.beat("Steps play in order and share the clip: a list plays together, a number pauses.",
                  Indicate(eq[2]), [FadeIn(a), FadeIn(b)], .2, Create(c), w=(.2, .3, .3))
        with self.say("For choreography beat() can't express, size run_times as fractions of d.") as d:
            self.play(eq.animate.shift(UP), run_time=.3 * d)
            self.play(Circumscribe(eq[4]), run_time=.4 * d)
        self.wipe()               # every scene starts empty and ends with wipe()
```

## API

**Text and math** (Avenir words, LaTeX math; never put symbols in `T`)
- `T(s, size=30, color=INK, weight=NORMAL)` words · `M(*tex, size=40, color=INK)` MathTex · `C(s, size=26)` monospace
- `E("a|b|c", size=44, cmap=None)` MathTex split at `|`; parts whose TeX is a key of `colors(...)`/`cmap` get that
  hue; `e[i]` is part i. Each part must compile alone (`\Big(`, not `\left(` split across parts).
- `TX(r"sentence with $x^2$ inline", size=30)` · `paint(m, {i: color})` · `tint(m, [((a, b), color)])` glyph ranges
- `morph(old, new, [(i, j), ...])` -> animations: old[i] glides into new[j], the rest fade. (Not TransformMatchingTex key_map: it crashes.)

**Layout and cards**
- `place(m, "full"|"left"|"right"|"top"|"bottom")` shrink-to-fit a slot clear of the header · `fit(m, w, h)` shrink only
- `backed(m)` text on a BG plate (over grids/fields) · `panel(m, color=HAIR)` SURFACE card, `[1]` is m
- `key_box(*lines, label="KEY IDEA")` end-of-section summary; lines are TeX strings or mobjects (`E(...)` keeps colors) · `qcard(tag, *mobs)` question card
- `sheet(head, [(label, color, [mobs]), ...])` worked write-up rows (`.rows[k]`, `.head`), already placed
- `chip(name, color)` tag · `badge(n)` numbered circle · `choices([tex, ...])` A-D rows + `mark(row, good)` -> anims
- `glow(m, color)` soft halo for a reveal, text or shapes (FadeIn it under m) · `strike(m)` line through · `Cross(m)` (manim) X over
- `span(a, b, label, side=DOWN)` dimension marker · frame is 14.2 x 8, header at top-left

**Plots and fields**
- `axes(xr, yr, width=6, height=3, xlabel="x", ylabel="y", pi_ticks=False, boxed=False)`
- `live(ax, f(x, t), tracker, color=SKY, n=240)` curve redrawn as `tracker` (a ValueTracker) moves · `dashed(curve)`
- `field_image(f(X, Y), ax, xr, yr, cmap="seq"|"div", vmax)` one image, far cheaper than many squares
- `readout(tex, fn, digits=3)` live number (drop()/wipe() clear its updater before fading)

**Structures**
- `ArrayRow(values, index_from=1)`: `.cell(i) .val(i) .mark(i, color) .unmark(i) .set(i, v) .swap(i, j) .pointer(i, label)`
- `CodeBlock(lines)`: `.focus(i) .unfocus()` (indent with spaces; fixed line pitch)
- `rec_tree(a, depth, label=lambda k: tex)`: `.levels[k] .edges`
- `GraphMob(pos, edges, directed=True, bend={})`: `.v(n) .e(u, v) .fill(n, color) .unfill(n)`
  `.kind(u, v, "tree"|"back"|"forward"|"cross"|color) .path(names) .tag(n, text)`; edges follow live node centers

**Scene** (`VScene`: 2D with a movable camera; `VScene3D`: pin text with `self.add_fixed_in_frame_mobjects`)
- `self.beat(text, *steps, w=None, style=None)` · `with self.say(text, style=None) as d:` (d = clip seconds)
- `self.title_card(kicker, title, sub)` -> mobject · `self.section(text)` plays + returns the header
- `self.predict(question, narration, seconds=3)` pause-and-ponder card · `self.wipe()` · `self.drop(*mobs)`
- `self.snap(label)` an extra storyboard still mid-beat · `self.lint_on = False` around a deliberate overlap
- camera: `self.play(self.camera.frame.animate.scale(.4).move_to(p))`

**Colors**: text `INK INK2 MUTED`; chrome `SURFACE HAIR AXIS BG`; `ACCENT GOOD BAD`; concept hues
`SKY EMBER MINT LILAC LIME ROSE GOLD`. Reference/initial curves: `MUTED` dashed. Never manim's `BLUE`, `RED`, ...

**PDE kit** (`from mtk.pde import *`): `derivs`/`sample` residual checks, `gauss_heat heat_modes sine_coeffs dalembert
odd_periodic burgers_curve t_break laplace_hot_lid`, `rd_solve` + `as_field` (stable explicit solver), `front_position
xt_diagram st_mask now_line char_curves`, family colors `TRANSPORT HEAT WAVE BURGERS REACTION ELLIPTIC`.

**Recipes**: 23 tested patterns. `mtk recipe` lists them, `mtk recipe R04` prints one. R01 linear map, R02 complex
map, R03 parameter tracker, R04 morphing derivation, R05 camera zoom, R06 epicycles, R07 flow field, R08 3D surface,
R09 Riemann sums, R10 reveal choreography, R11 graph algorithm, R12 histogram to bell curve; P01 heat modes, P02
masked x-t reveal, P03 characteristics, P04 d'Alembert, P05 Burgers breaking, P06 standing waves, P07 Laplace +
mean value, P08 Gibbs, P09 Fisher front, P10 heat kernel, P11 drum mode 3D. Copy the technique, not the scene.

## Craft

- **Open on a question**, a concrete puzzle or surprising picture in the first 20 s, not a definition.
- **Discover, don't declare**: the naive attempt, why it fails, the fix. The viewer should feel they could have invented it.
- **Concrete before abstract**: one example fully worked, then the general statement.
- **The picture is the argument.** Animate changes (a parameter sweeping, a grid deforming, a term morphing), not
  slides. If a visual could be deleted without loss, delete it.
- **One idea per beat, one focus on screen.** Dim or remove what the narration isn't about; highlight the term being
  discussed (`Indicate`, `Circumscribe`, color). A beat whose words point at nothing on screen is a bug.
- **Color is meaning**: one hue per concept, the same in every equation and figure, the whole video.
- **Rigor is the payoff**: derive, don't quote; say what's assumed, name the rule used, say where intuition breaks.
- **Let the viewer think**: `predict` before the animation that answers it (as the brief places them);
  end each major section with a `key_box`. **Close the loop**: the ending answers the opening question.

## Narration

- **In a script-first brief the narration is final**: one quoted line = one `beat`/`say`, copied verbatim (a changed
  character costs a new voice call and drifts from the script). You may split a line at a sentence boundary when
  the picture needs two steps; never reword, add or drop words. Narration that seems wrong: say so in your report.
- Writing narration (the coordinator, in the brief): ~125 words per finished minute (the voice reads ~150 wpm;
  pauses and motion fill the rest); 1-3 sentences per beat (4-20 s); write for the ear ("u-t equals u-x-x",
  "e to the minus n squared t", "two pi"), no `= + ^ _ \` or Unicode math; American spelling; conversational,
  confident, a little playful ("watch this", "here's the punchline"), never padded, no hype words.
- Plain string literals in code, no f-strings: the audio cache keys on the exact text.

## Visual rules

- Main equations `size=40..56`, labels `>= 28` (ticks 24), `T` text `>= 26`. At most ~3 equation lines plus a
  figure at once. Clear old material before adding new.
- Animated math must be exact: closed forms through `ValueTracker` + `live`/`always_redraw`. Numerics are
  precomputed with a stable step (comment the rule) and say "computed numerically" on screen.
- A wrong number on screen is the worst bug an explainer can have: every stated number is asserted in the file.

## Performance

- Dense fields: one `field_image`. Surfaces: resolution <= (24, 24); stretch a prebuilt surface instead of rebuilding.
- `always_redraw` rebuilds every frame: keep what it builds small; static parts stay static. Precompute solvers/FFTs.
- 3D and `StreamLines` render ~10x slower than real time at 1080p: keep them short.

## Gotchas (each one cost a past video time)

- A helper that swaps a VGroup's `submobjects` mid-play leaves ghosts for the rest of that play: update children in place.
- `LaggedStart` / `.animate` re-add mobjects on top: labels that must stay above need `set_z_index`.
- `TransformMatchingTex(key_map=...)` crashes in 0.21: use `morph`. `substrings_to_isolate` on single letters breaks `\frac`.
- A DecimalNumber that gains a glyph (a minus sign) during a fade crashes: `drop`/`wipe` clear updaters first.
- Don't name a color `UP`, `DOWN`, `LEFT`, `RIGHT`: it shadows manim's directions.
- A highlight box spanning `matrix | vector | rhs` strokes through a centered `=`: box the pieces separately.

## Token discipline (agents)

- Read nothing else: not manim's or mtk's source, not other parts' scene files, not source PDFs (the brief has
  every fact). A pattern you need is a `mtk recipe` away. A shared project kit (`<topic>.py`): read its docstring only.
- Write your file in pieces of at most ~250 lines (Write the first, then append with Edit). Don't re-read what you
  just wrote; to find your own code later, `grep -n` then Read with offset/limit, never `cat` a whole file.
- Iterate only with `mtk check` (one scene with `-s` while fixing it). Read only `[NEW ]` storyboards.
- Think in the file, not before it: plan scenes briefly, write, and let `mtk check` tell you what's wrong.
- Report in at most 15 lines: the `mtk check` scene lines + TOTAL, and anything you couldn't get right.
