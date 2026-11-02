# mtk: everything a scene writer needs

This page and your brief are all you read. Target: a polished 3Blue1Brown explainer. Visual first, then the
math that explains it. Dense, warm, no filler.

**Your job is one scene.** `mtk brief BRIEF.md S03` prints the shared facts and colors, what the scenes around
yours open with, and your scene: numbered beats, each a quoted narration line plus `→` what the screen does.
The narration is final, voiced, and read from the brief by beat number. Your work is the picture: each `→` as animation.
Plan briefly, write the scene in one go, then let `mtk check` and the storyboard tell you what to fix.

## The loop (this exact loop, nothing else)

```bash
mtk check s03_squares.py   # dry run, no video, a few seconds: LINT/REPORT lines + the scene's storyboard PNG
mtk check v2_x.py -s S03   # one scene of a multi-scene file (prefixes, comma-separated)
mtk check s03.py --agent   # after the first look: only the beats that changed, what moved, and a sheet of just those
mtk check s03.py -s S03 --at 12.4,15   # full-size stills mid-animation, without rendering any video
```
- From your second check on use `--agent`. `beat 3 ...: ~'x^2' (0,1)->(0,2)` often confirms a fix without an image;
  otherwise read the `.diff.png` it names, never the whole board again. Use `--at` when motion is the question.
- One line per scene: length, words/budget, beats, warnings, storyboard path, `[NEW ]` or `[same]`. A crash
  prints `FAILED`, the line in your file and the exception, so you never need to open a log.
- A **storyboard** is one image per scene: a still at the end of every beat, captioned with its time and narration.
  Read it to judge the picture: overlap, clutter, a beat whose picture doesn't match its words, wrong colors,
  LaTeX glitches. Read only `[NEW ]` boards; `[same]` means nothing visible changed.
- Fix every `LINT` (or keep it on purpose and say why in your report). Then look. Then fix. Repeat.
- `DRIFT x_n: SKY in S01,S02; INK in S04` (checking several scenes) means a concept shows in different colors
  in different scenes: use `E(...)` so `colors(...)` applies, or say why it differs.
- Write the whole file before the first check. Run `mtk check` in the foreground with a long Bash timeout
  (600000 ms); a voice missing from the cache is generated on the spot. Never background it or poll it.
- **Two rounds.** Check and read the board, fix everything you saw in one edit pass, check again with `--agent`. Clean
  lint and a right picture: stop and report; a reviewer reads every board after you. A third round is only for a visible defect.
- Never render video (`manim -ql`, `mtk render`): the coordinator does the final pass.

## Skeleton

```python
"""S03: the remainder as a height (BRIEF.md S03)."""
from mtk import *                 # manim + numpy + everything below (PDE topics: from mtk.pde import *)
colors(p=SKY, s=EMBER, q=MINT)    # the video's concept -> hue map (same line in every file; EQ reads it)

# facts: assert every number the narration says and every formula you plot, before any animation
assert np.isclose(2 ** 10, 1024)

class S03_Remainder(Doc):         # the class is the brief's scene heading; rendered in sorted order
    def construct(self):
        eq, plot, note = EQ(r"p = s \cdot q + r"), axes([0, 1], [0, 1]), mix("the height is $r$")
        dot = Dot(plot.c2p(0, .5), color=SKY)
        self.follow(T("here", 28), dot)
        self.line(1, {"whole": self.stage(top=eq, center=plot, later=note),
                      "height": [Indicate(part(eq, "r")), FadeIn(dot)],
                      "grows": (dot.animate.move_to(plot.c2p(1, .5)), 2)})
        self.line(2, {"So": self.stage(left=eq, right=(plot, note))})
        self.wipe()
```

## Scene docs: this is how you write a scene

You say what's on screen and on which word. Never write narration, coordinates or fractions of a clip.
- `self.line(n, {phrase: cue, ...})` plays beat `n` of the brief, using its words and delivery. Each cue starts as the
  voice says its phrase and runs until the next cue, at most 1.2 s. A cue is an animation, a list that plays together,
  or `(cue, seconds)` when it should take longer. Phrases go in spoken order; a phrase not in the line is an error that
  shows you the line. Every beat of your scene plays, in order. No cues: it just talks.
- `self.stage(top=, center=, left=, right=, bottom=, later=, keep=)` is the next picture, usable as a cue or in
  `self.play`. Slots can't overlap and fit themselves. A slot takes a mobject or a tuple stacked downward. What's already
  on screen and listed glides over, what's new fades in, and **everything else on screen fades out**, so you never list
  what leaves. `later=x` holds x's place in a slot until a later cue brings it in (`FadeIn(x)`); list it in its slot too.
  `keep=x` leaves x as it is. Build composite figures with VGroup and `.arrange`, and hand the group to a slot.
- `self.follow(label, anchor, side=UP)` keeps a label beside something moving. It enters and leaves with it.
- `EQ(r"X_k = E_k + z^k O_k", size=44)` is math with every concept in `colors(...)` colored for you. `part(eq, "E_k")` is
  that piece. `mix("same speed as $z$", size=30)` is words in the video's font with math among them. Use these, never
  `\\text{}` in math or `M` for a colored concept: `LINT` flags both.
- A `Doc` is a `VScene`. When a moment needs something else, write it with anything below, in the same file:
  `self.play`, `self.spotlight`, `self.predict("question", 3)` (3 = its beat), `self.checkpoint`, updaters, a kit.

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
- `glow(m, color)` soft halo that marks one reveal (the answer, the key term, `eq[2]`): `FadeIn(glow(m))`. It
  sits behind m (raises m's z_index) so glyphs stay sharp; don't hand-roll halos · `strike(m)` line through · `Cross(m)` (manim) X over
- `span(a, b, label, side=DOWN)` dimension marker · frame is 14.2 x 8, header at top-left

**Guide checkpoints**: `self.checkpoint("1.2", "Compute x_2 from x_1 = 1.5")` shows a "Your turn" card, and the
study site pauses the video there until the viewer has worked checkpoint 1.2 in the PDF guide. Put it exactly
where the brief's `→` line says: after the cue beat, right before the beat that reveals the answer. Prompt: one
short line of plain words, no TeX.

**Worked problems** (walkthroughs): `self.try_it()` the "Try it before we solve it" pause · `answer_box(m)` ·
`marked(row, good)` a choices() row already marked · `rubric(pts, items, traps)` grading points over the common trap
(TX sentences) · `check(value, expected, rtol=2e-3)` asserts a number (relative: tiny SI values can't slip through)
and returns it · `sci(2.18e6)` -> `2.18 \times 10^{6}` (TeX; plain decimals between 0.01 and 1000)

**Plots and fields**
- `axes(xr, yr, width=6, height=3, xlabel="x", ylabel="y", pi_ticks=False, boxed=False)`
- `live(ax, f(x, t), tracker, color=SKY, n=240)` curve redrawn as `tracker` (a ValueTracker) moves · `dashed(curve)`
- `field_image(f(X, Y), ax, xr, yr, cmap="seq"|"div", vmax)` one image, far cheaper than many squares
- `readout(tex, fn, digits=3)` live number (drop()/wipe() clear its updater before fading)

**Fake 3D** (fast: a numpy raster in one image, ~2.5x faster than `VScene3D` and smooth-shaded; use `VScene3D`
only when the camera must fly through geometry). Camera `elev`/`azim` in degrees.
- `SurfaceImage(grid, vals=None, width=4, elev=20, azim=-60, cmap="signed"|"heat", vmax=1, marks=[(mask, color)],
  lines=(nu, nv))`; grids: `sphere_grid(n)`, `torus_grid(R, r, n)`, `param_grid(lambda u, v: (x, y, z), ur, vr)`;
  `.redraw(azim=...)` in an updater spins or recolors it; `.at(xyz)` pins a Dot/label to a 3D point; `.facing(xyz)`
- `Cloud(P, vals=None, height=5, elev=20, azim=-60)` point cloud; `.draw(...)` in an updater; `.screen_xy(i)`;
  `normals=pca_normals(P)` shades the far side of a closed cloud

**Structures**
- `ArrayRow(values, index_from=1)`: `.cell(i) .val(i) .mark(i, color) .unmark(i) .set(i, v) .swap(i, j) .pointer(i, label)`
- `CodeBlock(lines)`: `.focus(i) .unfocus()` (indent with spaces; fixed line pitch)
- `rec_tree(a, depth, label=lambda k: tex)`: `.levels[k] .edges`
- `GraphMob(pos, edges, directed=True, bend={})`: `.v(n) .e(u, v) .fill(n, color) .unfill(n)`
  `.kind(u, v, "tree"|"back"|"forward"|"cross"|color) .path(names) .tag(n, text)`; edges follow live node centers

**Scene** (`VScene`: 2D with a movable camera; `VScene3D`: pin text with `self.add_fixed_in_frame_mobjects`)
- `self.beat(text, *steps, w=None, style=None)`, `with self.say(text) as d:`: narration typed in the file, for walkthroughs
  with no script; a number step is a pause as a fraction of the clip
- `self.title_card(kicker, title, sub)` -> mobject · `self.section(text)` plays + returns the header
- `self.spotlight(*mobs)` -> animation: a key moment; everything else dims and mobs glow (play it in that beat,
  hold, then `self.unspot()` -> animation in the next; `wipe` also lifts it). Use it where the brief's `→` says.
- `self.predict(question, narration, seconds=3)` pause-and-ponder card · `self.wipe()` · `self.drop(*mobs)`
- `self.snap(label)` an extra storyboard still mid-beat · `self.lint_on = False` around a deliberate overlap
- camera: `self.play(self.camera.frame.animate.scale(.4).move_to(p))`; deep zooms: `self.play(self.zoom_to(p, 600,
  keep=[curve, dot, (label, dot)]), run_time=4)`: exponential, p stays put; kept curves stay thin, kept dots and
  text keep their screen size, and a (label, anchor) pair stays beside its anchor

**Colors**: text `INK INK2 MUTED`; chrome `SURFACE HAIR AXIS BG`; `ACCENT GOOD BAD`; concept hues
`SKY EMBER MINT LILAC LIME ROSE GOLD`. Reference/initial curves: `MUTED` dashed. Never manim's `BLUE`, `RED`, ...

**PDE kit** (`from mtk.pde import *`): `derivs`/`sample` residual checks, `gauss_heat heat_modes sine_coeffs dalembert
odd_periodic burgers_curve t_break laplace_hot_lid`, `rd_solve` + `as_field` (stable explicit solver), `front_position
xt_diagram st_mask now_line char_curves`, family colors `TRANSPORT HEAT WAVE BURGERS REACTION ELLIPTIC`.

**Recipes**: 26 tested patterns. `mtk recipe` lists them, `mtk recipe R04` prints one. R01 linear map, R02 complex
map, R03 parameter tracker, R04 morphing derivation, R05 camera zoom, R06 epicycles, R07 flow field, R08 3D surface,
R09 Riemann sums, R10 reveal choreography, R11 graph algorithm, R12 histogram to bell curve; P01 heat modes, P02
masked x-t reveal, P03 characteristics, P04 d'Alembert, P05 Burgers breaking, P06 standing waves, P07 Laplace +
mean value, P08 Gibbs, P09 Fisher front, P10 heat kernel, P11 drum mode 3D; R13 fake-3D sphere, R14 deep zoom;
W01 walkthrough (Read, Solve, Trap). Copy the technique, not the scene.

## Craft

- **Open on a question**, a concrete puzzle or surprising picture in the first 20 s, not a definition.
- **Discover, don't declare**: the naive attempt, why it fails, the fix. The viewer should feel they could have invented it.
- **Concrete before abstract**: one example fully worked, then the general statement.
- **One step per transform.** Each algebra or logic step the narration takes happens on screen as its own
  change, with the changed part highlighted; never morph across several steps at once. At the crux (the brief's
  **Crux** line), slow down: show it, hold, show it again on the example.
- **The picture is the argument.** Animate changes (a parameter sweeping, a grid deforming, a term morphing), not
  slides. If a visual could be deleted without loss, delete it.
- **One idea per beat, one focus on screen.** Dim or remove what the narration isn't about; highlight the term being
  discussed (`Indicate`, `Circumscribe`, color). A beat whose words point at nothing on screen is a bug.
- **Color is meaning**: one hue per concept, the same in every equation and figure, the whole video.
- **Rigor is the payoff**: derive, don't quote; say what's assumed, name the rule used, say where intuition breaks.
- **Let the viewer think**: `predict` before the animation that answers it (as the brief places them);
  end each major section with a `key_box`. **Close the loop**: the ending answers the opening question.

## Narration

- **In a script-first brief the narration is final**: `self.line(n)` reads it, and you never retype it. Narration that
  seems wrong: say so in your report.
- Writing narration (the coordinator, in the brief): ~110 words per finished minute (the voice reads ~140 wpm;
  pauses and motion fill the rest); 1-3 sentences per beat (4-20 s); write for the ear ("u-t equals u-x-x",
  "e to the minus n squared t", "two pi"), no `= + ^ _ \` or Unicode math; American spelling; conversational,
  confident, a little playful ("watch this", "here's the punchline"), never padded, no hype words.
- Explain like a teacher talking a student through it, 3Blue1Brown style: set up the question and where it's
  headed, why before what, nothing used before it's explained, every "so" with its reason. Flag the 2-4 key
  moments out loud ("pay close attention here", "this is the key step"), slow them down (`style="slower and
  deliberate"`), and say each one again another way. Never "clearly", "obviously", "it turns out" or "it's easy
  to see": each one marks a step the viewer was asked to take on trust.

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
