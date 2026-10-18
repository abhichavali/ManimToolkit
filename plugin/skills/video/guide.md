# Study guide (--guide)

Watching a clear explanation feels like understanding, and that feeling is mostly fluency: recognizing each step
as it goes by is not the same as being able to produce it. The guide turns the video into practice. At each
checkpoint the study site pauses the video until the viewer has worked a problem from the guide (a compact PDF
handout), and the video then shows the answer, so every attempt gets immediate feedback.

## Checkpoints

- **How many**: one every 3 to 4 minutes of video (2 to 4 in a 10-minute video), each 3 to 8 minutes of real
  pencil work.
- **Where**: right before the video reveals a result. The attempt comes first and the reveal is its feedback, so
  the brief puts three things in a row:
  1. a cue beat, e.g. "Your turn: pause and do checkpoint 1.2 in your guide.";
  2. its `→` line, `self.checkpoint("1.2", "Compute x_2 from x_1 = 1.5")`;
  3. the reveal beat, which works it on screen and names the tempting wrong answer.
- **Kinds** (vary them across a video):
  - predict what the animation is about to show;
  - compute the next step of the worked example;
  - finish a derivation the video started;
  - explain why in one or two sentences;
  - spot the error in a plausible wrong argument;
  - retrieve an earlier idea (in episode 3, a checkpoint that needs episode 1's identity).
- **Each one**:
  - is doable with only what the video has shown so far;
  - has one clear task and a checkable answer (a number, an expression, a yes or no with a reason);
  - is no trick question.

  Its prompt (one line, at most ~60 characters, plain words) is what the video's card and the site show.
- **IDs**: `<episode>.<k>` (`1.1`, `1.2`, `2.1`), identical in the brief, the scene code and `guide.tex`.

## The guide: guide.tex, a compact handout

- `mtk guide` writes the template the first time. BasicTeX only: amsmath, amssymb, geometry, hyperref, xcolor,
  enumitem (no tcolorbox). Figures go next to guide.tex.
- **Structure**:
  1. a title, and the template's three sentences on how to use it;
  2. one `\section*{Episode N: Title}` per episode, with its checkpoints in video order;
  3. optional "After the video" problems (problem-set.md's shape);
  4. Hints, then Solutions.
- **`\checkpoint[box height]{1.2}{Short title}{statement}`**: the statement must stand alone, because the site
  shows exactly this block when the video pauses. Size the answer box (default 3 cm) to the work: 2 cm for a
  number, 5 cm for a derivation. Use the video's notation exactly.
- **`\hintfor{1.2}`**: one nudge toward the idea, never the step itself.
- **`\solutionfor{1.2}{Title}`**: why this approach, then the work, then a check (plug it back in, a limiting
  case, a number).
- **Verify every answer** with numpy or sympy (a `check_guide.py` that asserts them) before writing it: the
  video's reveal beat and the guide's solution must agree.
- **Then a cold solve**: a fresh agent works the checkpoints from the PDF with hints and solutions removed. Any
  confusion, ambiguity or "this needed something the video didn't show" means fixing the statement or the video.

## Build and ship

1. `mtk episodes BRIEF.md` records each checkpoint's time.
2. `mtk guide` compiles the handout, fills in each checkpoint's "video m:ss", and crops every checkpoint for the
   site. It warns about IDs that are in the video but not the guide (or the reverse) and checkpoints without a
   solution.
3. `mtk site`, then publish with `capabilities: {"downloads": true}`, so viewers can save the PDF from the page.

Read every page of `out/guide.pdf` before delivering it.
