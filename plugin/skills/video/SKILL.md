---
name: video
description: Make a 3Blue1Brown-style narrated explainer video (manim animation + Gemini TTS voice, 1080p30) on any topic, with deep intuition and full rigor. Optional post-watch problem set (--problems), a PDF study guide the video pauses for (--guide), and an optional "blow your mind" moment (--mind-blow). Use when the user asks for an explainer, animated, manim or 3b1b-style video ("make me a video on X", "explain X in a video"), a problem set to go with a video, or "blow my mind mode".
argument-hint: <topic, or a path to notes/paper> [--guide] [--problems] [--mind-blow] [--minutes N] [--out DIR]
---

# Explainer video

Request: `$ARGUMENTS`

Parse the topic and flags; plain-language equivalents count ("with a problem set", "blow my mind").
- `--problems`: also make a post-watch problem set. Read `problem-set.md` in this skill's folder.
- `--mind-blow`: build in one genuine "whoa" moment, only if one fits honestly. Read `mind-blow.md`.
- `--guide`: a PDF study guide the video pauses for, so the viewer works problems instead of only watching
  ("with a guide", "workbook", "make it active"). Read `guide.md`.
- `--minutes N`: target length, default 10. `--out DIR`: project folder, default `~/Movies/Explainers/<topic-slug>`.
The final render is always 1080p30.

The toolkit is the `mtk` Python package (source `~/Code/ManimToolkit`, installed in `~/.venvs/manim`) and the
`mtk` command. **`API.md` in this skill's folder is the complete scene-writing reference**: read it before
writing the brief (narration rules, what the toolkit draws) and before reviewing scenes. Nothing is copied into
projects.

## How this stays fast

Model generation is the bottleneck, not rendering: an agent asked for a whole part spends most of its time
planning the part and its narration in its head before writing a line. So the story is written once, by you,
as an exact script; `mtk voice` times it before any code exists; then one agent per scene writes only the
picture for its beats, all in parallel, checking with `mtk check` storyboards instead of draft renders. Wall
time is your brief plus the slowest single scene plus review, and the final render overlaps the review.

## 0. Preflight

```bash
mtk recipe >/dev/null && ffmpeg -version | head -1 && which pdflatex && (test -s ~/.config/manim-explainer/openrouter_key || test -n "$OPENROUTER_API_KEY") && echo ok
```
- No `mtk`: `uv pip install --python ~/.venvs/manim/bin/python -e ~/Code/ManimToolkit && ln -sf ~/.venvs/manim/bin/mtk ~/.local/bin/mtk`
  (no venv: `python3 -m venv ~/.venvs/manim && uv pip install --python ~/.venvs/manim/bin/python manim` first).
- No key: ask the user for an OpenRouter key and store it with
  `mkdir -p ~/.config/manim-explainer && (umask 077; printf '%s\n' "<key>" > ~/.config/manim-explainer/openrouter_key)`.
  Never print the key or copy it into a project.

## 1. Understand the topic

- If the user gave a source (notes, paper, lecture, homework), read all of it, once, yourself. Otherwise work
  from what you know and look up anything you're unsure of.
- Assume a curious, mathematically literate viewer unless told otherwise. Default anything you can.
- Do the math before planning: derivations, the worked example, every number, checked with throwaway
  numpy/sympy. Find where the intuition breaks and what the rigorous version needs.

## 2. Set up the project

`mtk new <slug>` creates `~/Movies/Explainers/<slug>/` (or `--dir <--out>`) with a BRIEF.md skeleton in the
exact format below (`--walk` for exam walkthroughs, see Walkthrough mode); call that folder `P` and fill the brief
in place.
Voice: only if the user asks (`import mtk.core as core; core.VOICE = "Charon"` in every file, and
`mtk voice BRIEF.md --voice Charon`).

## 3. Write BRIEF.md: the script

A video is one idea told as a story, and the brief is where its quality is decided: the hook, the order of
ideas, every word spoken, and the picture that makes each idea obvious. `mtk voice` and `mtk brief` parse this
format, so keep it exact:

````markdown
# <Title>  (~N min)

**Hook**: the concrete question or picture of the first 20 s. **Insight**: the one sentence the viewer keeps.
**Payoff**: how the ending answers the hook.

Every file starts:
```python
from mtk import *
colors(**{"x_n": SKY, "e_n": EMBER, r"\sqrt{2}": GOLD})
```
<what each hue means; anything else every scene must share (notation, a shared kit and its API)>

## Facts (assert the ones your scene shows)
- every number, formula, notation choice and source detail the scenes need, and how it's checked; errata here

## S01_Hook [79]
Picture: one or two lines: the layout and what's on screen overall; recipes to borrow (`mtk recipe`).
1. "The exact narration for this beat: one to three sentences, written for the ear."
   → what the screen does during this beat
2. "Next beat."
   → ...

## S02_<Name> [<words>] <chapter label>
...
````

A series: put `# Episode N: Title | subtitle` above each episode's scenes; `mtk episodes` builds one video per
episode from these headings. Text after `[budget]` becomes the scene's chapter label.

- Draft straight into the file (scene list and budgets first, then the beats), not in your head first: the
  brief is the one long sequential step, and writing it twice (once in thinking, once in the file) doubles it.
- `[N]` in a scene heading is its narration word budget. Scenes of 30 to 90 s, each one idea; a scene is one
  agent's job, so more scenes means more parallelism.
- Budget ~125 narration words per finished minute; follow API.md's narration rules. Beats can carry
  `(style: slower, quieter, a little awed)` after the quote for a reveal.
- For each key idea, ask "what picture makes this obvious?" before "what equation states it?", and say it in
  the `→` lines: concrete enough that the scene agent doesn't have to invent the explanation, loose enough to
  leave it the layout.
- 2 to 4 predict beats (`→ self.predict("question", <this line>)`); end major sections with a key_box.
- With `--guide`: a checkpoint every 3 to 4 minutes, just before a reveal: the cue beat, its
  `→ self.checkpoint("1.2", "short prompt")` line, then the reveal beat (`guide.md`). Write `guide.tex` alongside
  the brief, with every answer verified.
- With `--mind-blow`: candidates, the chosen moment (or why none fits), and its plant and reveal beats.
- Scene writers never open the source: every fact they need is in the brief.

Then `cd "$P" && mtk voice BRIEF.md`: it voices every line in parallel (the scene checks later find them cached),
prints each scene's length against its `[budget]`, and flags beats with no `→` line, scenes with no budget and a
missing `colors(` line. Edit the prose until the total fits the target; only changed lines get re-voiced.

Shared objects: if a visual appears in more than one scene (a graph, a figure, a solver, the hook's table that
returns at the end), write `$P/<topic>.py` before spawning: `from mtk import *`, the builders, the asserted facts,
a docstring listing its API, under ~150 lines. `mtk brief` prints every shared module's docstring to each scene
agent, so they all build from the same pieces.

## 4. Write the scenes: one agent per scene, all at once

Spawn one general-purpose agent per scene, all in one message, on Opus 5.5 with extended thinking: pass
`model: "opus"` and `effort: "high"` to every scene agent, and `effort: "xhigh"` to the hook scene and the
mind-blow reveal (the scenes that make or break the video). This skill asks for those settings explicitly.
Prompt, verbatim:
> Write scene S0k of the video in `<P>` as `<P>/s0k_<name>.py`. First read `<skill dir>/API.md` (the complete
> reference; its loop and token rules are mandatory), then run `cd <P> && mtk brief BRIEF.md S0k` for your
> brief. Read nothing else. Report in at most 8 lines.

Keep the scene to agent map: fixes go back to the agent that wrote the scene. More than ~12 scenes: spawn in
waves of ~10 to stay clear of usage limits.

## 5. Review as the viewer, with the render running

- When every agent has reported, start `cd "$P" && mtk render` in the background (1080p30, every scene in
  parallel on global render slots), and review while it runs.
- `mtk check` (fast: everything is cached) for the lint lines and lengths, then read every storyboard once,
  all in one message with parallel Reads (`media/board/*.png`: a still per beat, captioned with its narration). Is each idea obvious from the picture?
  Does every beat show what its words say? Anything cluttered, static, off-palette? Is the rigor all there?
  Continuity across scenes (notation, colors, callbacks)? A `DRIFT` line means a concept changes color between
  scenes: send it to the scenes' agents.
- Send fixes to the scene's agent (SendMessage: beat number, what's wrong). When they're done, run `mtk render`
  again: manim's cache skips every unchanged animation, so only the fixed scenes re-render.
- Series over ~30 minutes: give each episode's board review to a fresh agent that returns notes, so your own
  context doesn't fill with images.

## 6. Final checks

`mtk render` joins everything into `out/<folder>.mp4` with gap-free audio and captions (`out/<folder>.vtt`, from the
narration) and prints a chapter list (keep it for the problem set and the summary) and every silence over 3 s
(each must be deliberate). For a series, a site or an artifact page: `mtk episodes BRIEF.md` builds per episode (or
per problem) `out/<stem>.mp4`, a web copy under the artifact's 15 MB per-file cap (`--mb-per-min` for a site-wide
budget), a poster, captions and `web/episodes.json` (titles, durations, chapters) for the page to read.

**A website around the videos**: `mtk site --kicker "<course>" --blurb "<one or two sentences>" --out <a folder in
your scratchpad>` (after `mtk episodes`) writes `index.html` (a study page: player, chapter timeline and list,
captions and a clickable transcript built in, resume where you left off, episode and problem shelves, keys
j k l n p c) next to copies of the videos, and prints the publish plan: Artifact publish with `file_path` that
`index.html` and `files` = batch 1, then each later batch to the same url (64 MB per publish, 15 MB per file).
With a guide, the page pauses the video at every checkpoint and shows that checkpoint's problem from the PDF;
publish it with `capabilities: {"downloads": true}` so viewers can save the guide. Its
player is the one to use for any video page: Chromium can't seek videos served without byte ranges (the artifact
file server), and the player works around it (it fetches the full file and switches to it, with every seek waiting
for it instead of snapping to 0). Test it locally with `python3 <repo>/tests/serve.py <folder> 8765 --kbps 800`
(no range support, like the artifact server; add `--ranges` for a normal host). With `--guide`: `mtk episodes BRIEF.md`,
then `mtk guide` (it fills in each checkpoint's video time, compiles and crops; fix every GUIDE line), then read
every page of `out/guide.pdf`. Storyboards show beat ends; check motion and full resolution with one image: `mtk frames out/<name>.mp4 <4-6 seconds mid-animation in
the busiest scenes>`, then Read it.

## Walkthrough mode (exam problems)

When the user wants practice problems or an exam walked through ("walk me through this practice midterm"), each
problem gets its own ~2 to 2.5 minute video. Problems are independent, so their agents write their own narration.
- `mtk new <slug> --walk` gives the brief: shared viewer, tone and colors, then per problem `# Problem N: Title |
  Ch. · topic · review: Episode K`, a facts block (statement, choices, answer, every solution number, the tempting
  wrong choice and the mistake behind it), and three scenes `S{NN}1_Read`, `S{NN}2_Solve`, `S{NN}3_Trap` with
  word budgets. Check every answer yourself first (numpy/sympy, or the course's key: keys have been wrong).
- One agent per problem, all at once (`model: "opus"`, `effort: "high"`), prompted: "Write problem N of the
  walkthroughs in `<P>` as `<P>/pNN.py`. First read `<skill dir>/API.md` (mandatory rules), then run `cd <P> &&
  mtk brief BRIEF.md pNN`. Read nothing else. Write the narration yourself under API.md's rules. Report in at most
  8 lines." (`mtk recipe W01` shows the Read/Solve/Trap pieces.)
- Review as above, then `mtk render` and `mtk episodes BRIEF.md` (one web video per problem, `pNN.mp4`).

## 7. Problem set (only with --problems)

Follow `problem-set.md`. An agent can draft it while the scenes are being written; finalize it after the final
render so its timestamps match.

## 8. Deliver

Tell the user the video path and length, the chapter list, the problem-set or guide PDF path, the site's link if
you published one, and the timestamp of the mind-blow moment if there is one (or one line on why none fit). Share the files (SendUserFile if available).
Say plainly anything that isn't right yet.
