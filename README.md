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
| `mtk/pde.py`, `mtk/recipes.py` | PDE kit and the 23-recipe gallery, ported unchanged |
| `mtk_cli.py` | The `mtk` command: `check`, `render`, `frames`, `recipe` |
| `plugin/` | The skill: `SKILL.md` (coordinator), `API.md` (the one page scene writers read), problem-set and mind-blow docs |
| `tests/` | `python tests/test_check.py`: every lint rule fires, storyboards build (offline voice, no API cost) |

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
