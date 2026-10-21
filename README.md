# ManimToolkit (`mtk`)

A manim toolkit and Claude Code skill for narrated, 3Blue1Brown-style explainer videos, built to cut the
tokens and wall-clock time the old `manim-explainer` skill spent, without changing what the videos look like.

```bash
./install.sh   # editable install into ~/.venvs/manim, `mtk` on PATH, plugin/ deployed as the manim-explainer skill
```

## What's here

| Path | What |
|---|---|
| `mtk/core.py` | The look, Gemini TTS narration (`say`, `beat`), lint, storyboard stills, `VScene`/`VScene3D` (successor of the per-project `vid.py`) |
| `mtk/kit.py` | Pieces past videos kept rewriting: `E` (concept-colored math), `morph`, cards, MC choices, write-up sheets, `ArrayRow`, `CodeBlock`, `GraphMob`, `rec_tree` |
| `mtk/view3d.py` | Fast fake 3D: `SurfaceImage` (shaded surfaces) and `Cloud` (point clouds) as numpy rasters |
| `mtk/pde.py`, `mtk/recipes.py` | PDE kit and the recipe gallery (26: R01-R14, P01-P11, W01) |
| `mtk/site/player.html` | The study-page template `mtk site` fills: player, chapters, captions, transcript, shelves, checkpoints |
| `mtk/site/guide.tex`, `mtk/site/mtkguide.sty` | The study-guide template and its checkpoint macros (`mtk guide`) |
| `mtk_serve.py` | `mtk serve`: the study site on localhost, plus the chat endpoint that answers with your API key |
| `mtk_cli.py` | The `mtk` command: `new`, `voice`, `brief`, `script`, `check`, `render`, `episodes`, `guide`, `site`, `serve`, `frames`, `recipe` |
| `plugin/` | The skill: `SKILL.md` (coordinator), `API.md` (the one page scene writers read), problem-set and mind-blow docs |
| `tests/` | `python tests/test_check.py`: every lint rule fires, storyboards, briefs, captions and the site build (offline voice, no API cost); `tests/serve.py`: a local server without range support, like the artifact file server; `tests/mock_anthropic.py`: a stand-in Messages API for the chat tests |

Scene files start `from mtk import *`; nothing is copied into projects any more.

## Why it's shaped this way

The 179 scene-writing agents behind the past videos produced little output but re-read huge contexts: the
median agent made 62 API calls with context peaking at 325K tokens, 14.2M input tokens in all. Context was
filled by contact-sheet images (median 21 per agent), `cat`/`sed` re-reads of kit and scene files, source PDFs
(76 of 179 agents read them), and waits on 480p draft renders. So:

- **`mtk check`** replaces dry-run plus 480p draft plus contact sheets. It steps every frame (updaters and traced
  paths stay exact) but draws only one still per narration beat. A scene checks in ~3 s, and the 23 recipes
  (3:40 of video) in 16 s. Output is one line per scene; a crash prints the line in your file and the exception.
- **Storyboards** are one image per scene: a still at the end of every beat, captioned with time and narration.
  The reader can judge picture/narration sync without opening code. Unchanged boards are marked `[same]` and skipped.
- **More lint, fewer looks**: hidden-under-a-shape text, narration over a frozen picture, and per-scene word
  budgets join the old cut-off, overlap, tiny-text and math-in-narration checks.
- **`beat()`** (`self.beat("text", anim, [a, b], .2, anim)`) and the kit shrink scene code. A port of a real scene
  renders pixel-identical to the original.
- **One reference page** (`API.md`, ~2.5K tokens) replaces `STANDARD.md`, `vid.py` docstrings and recipe spelunking.
  Agents get facts from the brief, never the source PDFs.
- Folded in from project copies: TTS fallback to macOS `say` on 402/403 (`MTK_TTS=say` forces it), the predict
  card's z-index, and machine-wide render slots (the old `slot-manim`) for parallel agents on 8 GB.

## Measured

Trial on 2026-10-14: one agent wrote a 3:21 video (4 scenes, Newton's method) from a brief, using only `API.md`
and `mtk check`. It finished with 0 lint, caught a rounding error in the brief, and rendered at 1080p30 in 48 s.

| per agent | past median | trial |
|---|---|---|
| API calls | 62 | 22 |
| peak context | 325K | 145K |
| input tokens (summed over calls) | 14.2M | 2.5M |
| images read | 21 | 8 |

Past parts were usually 4-7 min against this trial's 3.4 min, so per minute of video the saving is roughly 3-4x,
not the raw 6x. Wall-clock time was dominated by model generation, not tooling: a first `mtk check` of a new
file takes ~25 s (voices are prefetched in parallel), and later checks take ~3 s per scene.

## Speed: script first, one agent per scene

Generation, not rendering, is what makes a video slow: the single-agent trial above spent ~38K output tokens
planning four scenes and their narration in its head before writing a line, then finished review and fixes in
3 minutes. So the skill now has the coordinator write the exact narration and the picture for every beat into
`BRIEF.md` (where the story's quality is decided anyway); `mtk voice BRIEF.md` voices it in parallel and prints
each scene's real length before any code exists; and one agent per scene, all in parallel, writes only the
picture, starting from `mtk brief BRIEF.md S03`.

Race on the same script (4 scenes, 3:20), scene-writing phase:

| | wall time (slowest agent) | input tokens | quality |
|---|---|---|---|
| Opus 5.5, one agent per scene | 9.3 min | 3.7M | best: extra steps, annotations, a careful zoom |
| Sonnet, one agent per scene | 2.0 min | 2.4M | correct and clean, plainer |
| Opus, one agent for all 4 (old shape) | 2 h 46 min (a slow-API day) | 2.5M | baseline |

The skill uses Opus 5.5 at high effort for every scene (extra-high for the hook and the mind-blow reveal), and
overlaps the final render with the coordinator's review.

## v0.3: the machinery around the scenes

Past series kept rebuilding the same things by hand: `episodes.py` was written 7 times, walkthrough helpers sat in
39 files, and two projects each wrote a numpy rasterizer to dodge Cairo's slow 3D. Those are now library pieces:

- **`mtk episodes BRIEF.md`**: `# Episode N: Title | sub` (or `# Problem N:`) headings group scenes into videos.
  Each gets a full-quality join, a web copy under the artifact's 15 MB cap, a poster, WebVTT captions (from the
  narration, logged at render time) and an entry in `web/episodes.json` with chapters. On the Newton test, 3:34 at
  1080p became a 6.2 MB web copy in 29 s; caption cues land a median 0.26 s ahead of the speech, with no drift.
- **Walkthrough mode** (`mtk new <slug> --walk`): one agent per exam problem with the Read, Solve, Trap shape, plus
  `try_it`, `answer_box`, `marked`, `rubric`, `check` (relative tolerance only) and `sci` in the kit; recipe W01.
- **Fake 3D**: `SurfaceImage`/`Cloud` redraw in ~16 ms. A spinning shaded sphere renders at 1.3x real time at
  1080p, against 3.4x for a coarse `VScene3D` surface. **`zoom_to(p, factor, keep=[...])`**: an exponential zoom
  that keeps curves thin and dots and labels screen-sized and beside their anchors (recipe R14).
- **Guardrails for one agent per scene**: `DRIFT` lines when a declared concept changes color between scenes;
  lints for unnarrated stretches and for animation that overruns its narration (it caught an 8 s silent stretch
  from a race agent who passed `1.0` meaning one second to `beat()`); `mtk voice` lints the brief's shape;
  `mtk brief` hands every agent the shared kits' docstrings; `mtk new` scaffolds a brief in the exact format.

## Websites around the videos, with seeking that works on Chromium

`mtk site` (after `mtk episodes`) writes `index.html`, a study page: the player, a chapter timeline in the video's
concept colors, a chapter list, captions and a clickable transcript (both embedded, since the artifact server won't
serve `.vtt`), resume where you left off, episode and problem shelves, and the keys j k l n p c. It also prints an
artifact publish plan, with files batched under the 64 MB per-publish limit.

Seeking is the hard part. A server that ignores HTTP Range requests (the claude.ai artifact file server, and
`python3 tests/serve.py`) makes Chromium report the video as unseekable (`video.seekable` is `[0, 0]`). Chromium
then clamps every seek to 0 *before* any event fires: a rewind restarts the video, even into the part already
buffered, and the page can't learn where the viewer meant to go. The networking site's earlier fix only caught seeks
outside the buffer, which is why rewinding still failed sometimes. The player now:

- keeps the native controls hidden until the video is actually seekable (immediately on a server with ranges);
- otherwise downloads the whole file as soon as the stream proves unseekable, and switches to the in-memory copy,
  keeping position and play state;
- routes every seek the page makes (chapters, timeline, transcript, keys, resume, `#ep01.83` links) through one
  `jump()`, which waits for the copy instead of letting Chromium snap to 0.

Checked in the desktop app's Chromium pane against `tests/serve.py` at 800 KB/s. With the fix off: `seekable`
`[0, 0]`, and jumps to 100 s and rewinds to 20 s both restarted at 0. With it on: chapter jumps made during the
download landed on the latest one once the copy arrived (9.6 s); native rewinds and the keys worked after that. On
a server with range support, controls showed at once, every seek was native, and nothing extra downloaded.

## Study guides the video pauses for

Watching a clear explanation feels like learning, but recognizing each step as it goes by is not the same as
producing it. With `--guide`, every video gets a compact PDF handout, and the study site pauses the video at each
checkpoint until the viewer has worked it. Checkpoints sit just before the video reveals the answer, so resuming
gives immediate feedback.

- **In the video**: `self.checkpoint("1.2", "Factor what's inside the brackets")` shows a "Your turn" card and
  logs its time at render (`media/subs/*.marks.json`); `mtk episodes` carries the times into `episodes.json`.
- **The guide**: `guide.tex` (template from `mtk guide`) uses `\checkpoint{1.2}{Title}{problem}`, an unbreakable
  block with an answer box. `mtk guide` fills in each checkpoint's video time, compiles, and crops exactly that
  block out of the rendered page for the site, using `\pdfsavepos` marks LaTeX writes to the aux. It warns when
  the video and the guide disagree on checkpoint ids, or a checkpoint has no solution.
- **On the site**: playing across a checkpoint pauses the video (seeking past one never does) and opens a panel
  with that problem as printed in the guide, and Done (marks it, then plays the reveal), Skip, and Save the guide
  (the artifact `downloads` capability). Diamonds on the chapter timeline, checkpoint rows in the chapter list, a
  progress count and a "Pause at checkpoints" switch; done checkpoints play through on a rewatch.

Checked end to end on the Newton demo, in the desktop app's Chromium pane against `tests/serve.py` without range
support: two checkpoints (at 1:24 and 2:09) paused within 0.3 s of their times with the right crops; Done, Skip,
rewatch, the switch, jumping over a checkpoint and clicking a checkpoint row all behaved; a chapter jump made while
the full video was still downloading landed and then paused at the next checkpoint. That test also caught a bug:
a pending "resume where you left off" used to override such a jump.

## Ask about the video

Once a study page exists, the next question is usually "wait, why?" With an Anthropic API key around, `mtk site`
puts a chat box under the video. Claude (`claude-sonnet-5-5`) answers from that video's transcript, chapters and
checkpoints, and cites moments as `[1:23]` links that jump the video there. Each question carries where the viewer
is in the video and which checkpoints they have done, so a checkpoint not yet worked gets a hint, not the answer.
Conversations are per video and per viewer (localStorage), with Stop and Clear.

- **The key** is `$ANTHROPIC_API_KEY`, else `.anthropic_api_key` in the project folder, else `~/.anthropic_api_key`.
  With no key, there is no chat box. A key that isn't scoped to a workspace also needs `$ANTHROPIC_WORKSPACE_ID` or
  `.anthropic_workspace_id`.
- **Locally**, `mtk serve` (in the project) serves `web/` on http://127.0.0.1:8000, with range support. Its
  `/api/chat` adds the key server-side and streams the answer back. The transcript is a cached system block, and
  `fallbacks="default"` retries a declined answer on the recommended model. The key never reaches the browser,
  dotfiles are never served, and the server listens on localhost only.
- **Published** as an artifact (the plan says to pass `capabilities: {"sample": {}}`), the same box asks Claude
  through each viewer's own claude.ai account, so no key is involved at all.

Checked with `python3 tests/test_check.py`, against `tests/mock_anthropic.py`:
- `site()` turns chat on only when there is a key, and keeps the key out of the page.
- `mtk serve` sends the model, workspace header, fallback beta and `cache_control`, and streams the answer.
- Malformed history gets 400, no key gets 403, and the key file gets 404.

In the desktop app's Chromium pane against the mock:
- answers streamed in;
- the `[2:09]` link jumped the video;
- follow-ups carried the history and the viewer's position;
- the conversation survived a reload;
- Stop kept the partial answer and Clear emptied it;
- at 375 px wide nothing overflowed.

## Explaining, not summarizing

Past scripts were often correct but compressed: they named an idea, stated the result and moved on, leaving the
viewer to infer the step in between. The skill now treats explanation as its own stage:

- **A teaching plan opens every brief.**
  - **Viewer** and **Knows**: what the narration may use without explaining. Everything else gets explained before
    it's used.
  - **Crux**: the one or two steps where understanding is won or lost, and the misconception each must defeat.
  - **Ladder**: the ideas in order, each tagged core, support or aside, with a time for each. Core gets at least
    half the runtime, and asides are cut.
- **Teacher's rules for the script.** Why before what. Nothing used before it's explained. Every "so" comes with
  its reason. Introduce an idea, use it on the example, then sum it up. At the crux, slow down to ~105 words per
  minute and say it more than once. Hold the picture after a reveal.
- **A cold read before voicing.** A fresh agent plays the viewer. It reads only `mtk script BRIEF.md`, which shows
  who the viewer is and every beat's words and picture, with no facts, plan or insight line. It logs every gap, skipped step,
  unexplained "why", overloaded beat and aside, and says where the main idea is won or lost.
- **`mtk voice` flags** hand-waves ("clearly", "it turns out", "it's easy to see"), beats over 50 words, and a
  missing Knows or Crux line.

**Tested on Koopman episode 1** (an older script), the cold read found 17 problems:
- the central linearity argument was one dense spoken equation;
- the rule that builds the matrix was never said;
- "operator", "dynamical system" and "eigenfunction" were used before they were explained;
- the step from φ(F(x)) = λφ(x) to λⁿ was asserted;
- a side fact (the eigenvalue of φ²) took time the core needed.

Each finding came with the sentence or picture that fixes it.

**Taught like 3Blue1Brown.** The narration rules now cover:
- **Setup:** the question stated precisely, and where the video is headed.
- **Discovery:** the natural first guess, why it fails, then the fix.
- **Talking to the viewer:** second person, thinking out loud together.
- **Landing:** stepping back at the end of each section.

Two to four key moments per video are flagged out loud ("pay close attention here", "this is the key step") and
slowed down in three ways:
- **The voice:** a per-line delivery note.
- **The picture:** `self.spotlight(*mobs)` dims everything else and haloes the one thing, then holds;
  `self.unspot()` lifts it.
- **The words:** the next beat says it again another way.

The default voice is now a calm, unhurried teacher instead of a "brisk" one. On the same line, the old style read
161 words a minute, the new one 138, and the new one with a key-moment note 122. A line's `(style: ...)` now adds to
the default instead of replacing it. Because of that, re-rendering an older project voices its narration again.
`mtk voice` flags a script with no spotlighted key moment, and the cold read flags key points that go by "flat".
