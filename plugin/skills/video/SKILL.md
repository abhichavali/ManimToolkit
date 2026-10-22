---
name: video
description: Make a 3Blue1Brown-style narrated explainer video (manim animation + Gemini TTS voice, 1080p30) on any topic, with deep intuition and full rigor, taught like a teacher: it sets the question up, builds from a concrete case, and flags and slows the key moments. Optional post-watch problem set (--problems), a PDF study guide the video pauses for (--guide), and an optional "blow your mind" moment (--mind-blow). Use when the user asks for an explainer, animated, manim or 3b1b-style video ("make me a video on X", "explain X in a video"), a problem set to go with a video, or "blow my mind mode".
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
- Pin down the viewer literally: what they already know (courses, tools, notation) and what they don't. When
  unsure, assume one level less: anything taught in the topic's own course is new to them and gets explained.
  Default anything else you can.
- Do the math before planning: derivations, the worked example, every number, checked with throwaway
  numpy/sympy. Find where the intuition breaks and what the rigorous version needs.
- Find the crux: the one or two steps where understanding is actually won or lost. That's the step students get
  wrong, the move that makes the whole thing work, the "but why?" an expert has stopped noticing. Write down the
  misconception each one has to defeat. The video spends its time there.

## 2. Set up the project

`mtk new <slug>` creates `~/Movies/Explainers/<slug>/` (or `--dir <--out>`) with a BRIEF.md skeleton in the
exact format below (`--walk` for exam walkthroughs, see Walkthrough mode); call that folder `P` and fill the brief
in place.
Voice: only if the user asks (`import mtk.core as core; core.VOICE = "Charon"` in every file, and
`mtk voice BRIEF.md --voice Charon`).

## 3. Write BRIEF.md: the script

A video is one idea told as a story, and the brief is where its quality is decided: the hook, the order of
ideas, every word spoken, and the picture that makes each idea obvious. It opens with a teaching plan (Viewer,
Knows, Crux, Ladder): who's watching, what they already know, where the idea is hard, and where the time goes. Write
that before any beat. `mtk voice`, `mtk brief` and `mtk script` parse this format, so keep it exact:

````markdown
# <Title>  (~N min)

**Viewer**: who's watching and why.
**Knows**: what the narration may use without explaining, listed literally ("derivatives, matrix times vector,
eigenvalues of a 2×2"). Everything else is explained on screen before it's used.
**Hook**: the concrete question or picture of the first 20 s. **Insight**: the one sentence the viewer keeps.
**Payoff**: how the ending answers the hook.
**Crux**: the one or two steps where understanding is won or lost, and the misconception each must defeat.
**Ladder**: the ideas in teaching order, each resting only on Knows and earlier rungs, tagged and timed:
1. (support, 0:45) why the naive approach fails
2. (core, 2:30) <the crux step>
3. (aside, cut) <the history, the generalization, the side result>

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
3. "Pay close attention here, because this is the whole trick: ..." (style: slower and deliberate, stressing the key words)
   → self.spotlight(eq[2]); hold 2 s

## S02_<Name> [<words>] <chapter label>
...
````

A series: put `# Episode N: Title | subtitle` above each episode's scenes; `mtk episodes` builds one video per
episode from these headings. Text after `[budget]` becomes the scene's chapter label.

- Draft straight into the file (teaching plan, then scene list and budgets, then the beats), not in your head
  first: the brief is the one long sequential step, and writing it twice (once in thinking, once in the file)
  doubles it.
- `[N]` in a scene heading is its narration word budget. Scenes of 30 to 90 s, each one idea; a scene is one
  agent's job, so more scenes means more parallelism.
- Budget ~110 narration words per finished minute, ~95 in crux scenes: the voice reads ~140 wpm (~120 on a key
  line), and pictures, holds and spotlights fill the rest. Follow API.md's narration rules. A beat can carry
  `(style: ...)` after the quote, a delivery note for that line ("slower and deliberate, stressing the key
  words"; "quieter, a little awed" for a reveal).
- 2 to 4 key moments (see Emphasis below), each with a `→ self.spotlight(...)` line.
- For each key idea, ask "what picture makes this obvious?" before "what equation states it?", and say it in
  the `→` lines: concrete enough that the scene agent doesn't have to invent the explanation, loose enough to
  leave it the layout.

- 2 to 4 predict beats (`→ self.predict("question", <this line>)`); end major sections with a key_box.
- With `--guide`: a checkpoint every 3 to 4 minutes, just before a reveal: the cue beat, its
  `→ self.checkpoint("1.2", "short prompt")` line, then the reveal beat (`guide.md`). Write `guide.tex` alongside
  the brief, with every answer verified.
- With `--mind-blow`: candidates, the chosen moment (or why none fits), and its plant and reveal beats.
- Scene writers never open the source: every fact they need is in the brief.

**Teach it like 3Blue1Brown: a teacher talking one student through it.** The failure to avoid is narration that
is correct but compressed: it names an idea, states the result and moves on, every beat at the same speed and
weight, and leaves the viewer to infer the steps and to guess what mattered. A viewer who knows only the Knows line
must follow every beat without stopping to rebuild a step, and must always know which moments matter most.

*Setup.*
- Open on the hook, then set it up properly: the question stated precisely, what we're given, and where we're
  headed ("here's the plan: first ..., then ..., and that will explain ..."). If the crux leans on something in
  Knows, remind them of it in a sentence or two, right before it's needed.
- Why before what: before any definition, operation or step, the viewer knows what it's for ("we want Y; the
  obvious try fails because ...; so here's X"). Let them discover it, with the natural first guess, why it fails,
  and the fix, so they feel they could have invented it.

*Exposition.*
- **Time goes where the difficulty is.** Core rungs get at least half the runtime, and each crux step gets its own
  scene. Support gets what the core needs. Asides get a sentence or are cut: history, side results,
  generalizations. The Ladder's times add up to the target before you write a beat; if they don't fit, cut rungs,
  never squeeze them.
- **Concrete first, all the way through.** Trace one example with real numbers through every step before the
  general symbols, and keep it on screen as the anchor.
- **Nothing used before it's explained.** Each term, symbol or fact not in Knows is said in plain words and shown
  on the example, and only then named. One new term per beat at most.
- **Show every step.** Each "so", "which means" or "therefore" has its reason in the words or on screen. Name the
  rule a step uses. Wherever a viewer could ask "wait, why?", the next beat answers it. Don't read an equation
  aloud as its explanation: say what it means, then build it piece by piece, each symbol tied to the picture.
- **Introduce, use, land.** After a new idea, use it once on the example, then say in a sentence what we now have.
  Open each section with where we are and what's missing ("we can do X; what we can't do yet is Y").
- **Talk to them.** Use the second person, and think out loud together: "you might be wondering ...", "let's just
  try it", "if this feels strange, good: it should". Say where it's genuinely hard. When you skip something, say
  so plainly ("I'll skip the proof; the idea is ...").

*Emphasis and pacing.*
- **Tell the viewer what matters.** Mark the 2 to 4 key moments out loud: "pay close attention here", "this is
  the key step", "this part is subtle, so let's go slowly", "if you remember one thing from this video, make it
  this". Reserve these phrases for the crux, so they keep their force. Elsewhere, plain signposts ("next",
  "here's the catch").
- **A key moment slows down in three ways at once:**
  - the voice: the line carries `(style: slower and deliberate, stressing the key words)`;
  - the picture: it spotlights the one thing, then holds (`→ self.spotlight(eq[2]); hold 2 s`);
  - the words: the next beat says it again another way ("in other words, ...").

  Show the tempting wrong intuition failing right there.
- **Vary the pace.** Move briskly through what they already know and slow down at the crux. Put a breather (an
  example or a recap) between two hard ideas, and silence after a reveal. Predict beats go before the answers they
  set up.

*Landing.* At the end of each section and of the video, step back ("so, stepping back: ..."). Give the key idea in
one sentence, answer the hook, and say why it matters.

**Read it as the viewer, before any scene exists.** You know the topic too well to see the gaps yourself. When the
brief is drafted, spawn one fresh general-purpose agent (`model: "opus"`, `effort: "medium"`) with this prompt,
verbatim:
> You're about to watch an explainer video, and you are exactly the viewer its brief describes: you know what
> its Knows line lists and nothing more about this topic. Run `cd <P> && mtk script BRIEF.md` and read only that
> output (the narration, with what's on screen under each line); open no other file. Go beat by beat and note
> every place where you would: meet a term, symbol or fact you don't know that hasn't been explained yet (gap);
> be told a conclusion without seeing why (why); have to fill in a step the video skipped (jump); get two new
> ideas at once, or a new one before the last was used (dense); lose track of why the video is doing what it's
> doing, or where it's headed (lost); want it to slow down, show it again or give an example (slow); see a key
> point go by without being flagged as important or given time to land (flat); or sit through something that
> doesn't serve the main idea (cut). Don't fill gaps from your own expertise: if the viewer would be confused,
> say so. Then, as a teacher: state the video's main idea in one sentence from the script alone, name the beats
> where it's won or lost, whether they get enough time and are flagged as the key moments, and say what you'd cut
> to pay for it. Judge it against a great 3Blue1Brown lesson: does it set up the question, build it from a
> concrete case, and land it? Report at most
> 30 lines, most important first, each `S03.2 [jump] what's missing → the sentence or picture that fixes it`.

Meanwhile run `cd "$P" && mtk voice BRIEF.md`. It voices every line in parallel (the scene checks later find them
cached) and prints each scene's length against its `[budget]`. It also flags:
- beats with no `→` line, and scenes with no budget;
- a missing `colors(`, `**Knows**` or `**Crux**` line, or no `self.spotlight` key moment;
- hand-waves ("clearly", "it turns out", "it's easy to see");
- beats too dense to follow.

Then fix the brief in one pass:
- every gap, why and jump the review found, and the rest by judgment;
- every hand-wave, and the timing.

Fixing usually means more beats at the crux and fewer elsewhere, so rebalance the budgets. Run `mtk voice` once
more (only changed lines are re-voiced). Series over ~30 minutes: one reviewer per episode, each told that it has
watched the earlier episodes.

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
  Does each algebra step happen on screen one at a time, rather than several in one morph? Do the key moments
  spotlight the one thing and hold?
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
publish it with `capabilities: {"downloads": true}` so viewers can save the guide.
**Chat under each video** comes on by itself when an Anthropic API key is found (`$ANTHROPIC_API_KEY`, else a
`.anthropic_api_key` file in the project folder, else `~/.anthropic_api_key`; `mtk site` prints `chat: on` or
`off`; no key, no chat box). Viewers ask a question and Claude (Sonnet) answers from that video's transcript,
chapters and checkpoints, with `[m:ss]` links that jump the video, and only hints for checkpoints not yet done. To
use it locally, run `mtk serve` in the project: it serves `web/` on http://127.0.0.1:8000 and answers with the key,
server-side. A key that isn't scoped to a workspace (`sk-ant-usr…`) also needs `$ANTHROPIC_WORKSPACE_ID` or a
`.anthropic_workspace_id` file in the same places. Published, the page uses each viewer's own claude.ai account:
pass the capabilities the plan prints (`"sample": {}`). Never print, Read or publish a key file. `mtk site` never
puts the key in the page and `mtk serve` never serves dotfiles; keep `.anthropic_*` files out of `files`. Its
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
you published one (and `mtk serve` for the local site with chat, if chat is on), and the timestamp of the mind-blow moment if there is one (or one line on why none fit). Share the files (SendUserFile if available).
Say plainly anything that isn't right yet.
