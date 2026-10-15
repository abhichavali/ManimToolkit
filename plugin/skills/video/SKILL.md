---
name: video
description: Make a 3Blue1Brown-style narrated explainer video (manim animation + Gemini TTS voice, 1080p30) on any topic, with deep intuition and full rigor. Optional post-watch problem set (--problems) and an optional "blow your mind" moment (--mind-blow). Use when the user asks for an explainer, animated, manim or 3b1b-style video ("make me a video on X", "explain X in a video"), a problem set to go with a video, or "blow my mind mode".
argument-hint: <topic, or a path to notes/paper> [--problems] [--mind-blow] [--minutes N] [--out DIR]
---

# Explainer video

Request: `$ARGUMENTS`

Parse the topic and flags; plain-language equivalents count ("with a problem set", "blow my mind").
- `--problems`: also make a post-watch problem set. Read `problem-set.md` in this skill's folder.
- `--mind-blow`: build in one genuine "whoa" moment, only if one fits honestly. Read `mind-blow.md`.
- `--minutes N`: target length, default 10. `--out DIR`: project folder, default `~/Movies/Explainers/<topic-slug>`.
The final render is always 1080p30.

The toolkit is the `mtk` Python package (source `~/Code/ManimToolkit`, installed in `~/.venvs/manim`) and the
`mtk` command. **`API.md` in this skill's folder is the complete scene-writing reference**: read it before
writing or reviewing any scene. Nothing is copied into projects.

## Where tokens go (why this skill is shaped this way)

Past videos spent >95% of their tokens re-reading context, not writing: agents averaged ~130 turns at up to
300K tokens of context, mostly images, re-read files and source PDFs. So: agents get a brief with every fact
(never the PDFs), one reference page (API.md), one command (`mtk check`) whose text lint and per-beat storyboards
replace video drafts, and they read only storyboards that changed. Keep your own context small the same way.

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

## 2. Find the story: write BRIEF.md

A video is one idea told as a story. `BRIEF.md` is the only thing scene writers get, so it carries every fact.
- **Hook**: the concrete question or picture of the first 20 s. **Insight**: the one sentence the viewer keeps.
  **Payoff**: how the ending answers the hook.
- **Arc**: parts, then scenes (`S01_...`), each with a word budget `[N]` (~125 narration words per finished
  minute), what's on screen beat by beat, what's said, and the recipe it borrows from (`mtk recipe`).
- For each key idea, ask "what picture makes this obvious?" before "what equation states it?"
- **Colors**: the `colors(...)` line every file starts with (concept to hue, fixed for the whole video).
- **Facts**: every number, formula, notation choice and source detail the scenes need, with how it's checked.
  Errata in the source go here too. Scene writers never open the source.
- 2 to 4 predict / quick-check placements. With `--mind-blow`: candidates, the chosen moment (or why none fits),
  where it is planted and revealed.

## 3. Set up the project

`P=~/Movies/Explainers/<slug>` (or `--out`): `mkdir -p "$P"`, put BRIEF.md there. If several parts share a cast
(a graph, a figure, a solver, a data set), write `$P/<topic>.py` first: `from mtk import *`, the pieces, the
asserted facts, and a docstring listing its API, under ~150 lines, so agents don't each reinvent it.
Voice: only if the user asks (`import mtk.core as core; core.VOICE = "Charon"` at the top of each file).

## 4. Write the scenes

- Up to ~6 minutes: write `v1_<slug>.py` yourself, following API.md.
- Longer: parts of 4 to 7 minutes (`v1_...`, `v2_...`), one general-purpose agent per part, all spawned in one
  message so they run in parallel. Prompt each with:
  > Write `<P>/v<k>_<name>.py`: part <k> of the video in `<P>` (scenes S<a>-S<b>; your brief section is below,
  > the full brief is `<P>/BRIEF.md`). Read `<skill dir>/API.md` first: it is the complete reference, and its loop
  > and token rules are mandatory. [Shared kit: read only the docstring of `<P>/<topic>.py`.] Every fact you need
  > is in the brief; don't open source documents or other parts' files. Use American spelling.
  > Report in at most 15 lines.
  >
  > <the brief section>
- Write or personally review the hook and the mind-blow scene: they make or break the video.

## 5. Review as the viewer

- `cd "$P" && mtk check`: zero `LINT` lines (or ones you accept on purpose); lengths match the brief.
- Read each storyboard once (`media/board/*.png`: one image per scene, a still per beat, captioned with the
  narration). Is each idea obvious from the picture? Does every beat show what its words say? Anything cluttered,
  static, off-palette? Is every step of the rigor there? Continuity across parts (notation, colors, callbacks)?
- Send fixes to the agent that wrote the part (SendMessage: scene, beat number, what's wrong), not a fresh agent.
  After fixes, `mtk check` again and read only the `[NEW ]` boards.
- Series over ~30 minutes: give each episode's board review to a fresh agent that returns notes, so your own
  context doesn't fill with images.

## 6. Final render

`cd "$P" && mtk render` renders every scene at 1080p30 in parallel (global render slots, so parallel jobs on this
machine queue instead of swapping) and joins all parts into `out/<folder>.mp4` with gap-free audio. It prints a
chapter list (keep it for the problem set and the summary) and every silence over 3 s (each must be deliberate).
Storyboards show beat ends; check motion and full resolution with one image:
`mtk frames out/<name>.mp4 <4-6 seconds mid-animation in the busiest scenes>`, then Read it.

## 7. Problem set (only with --problems)

Follow `problem-set.md`. An agent can draft it while the scenes are being written; finalize it after the final
render so its timestamps match.

## 8. Deliver

Tell the user the video path and length, the chapter list, the problem-set PDF path, and the timestamp of the
mind-blow moment if there is one (or one line on why none fit). Share the files (SendUserFile if available).
Say plainly anything that isn't right yet.
