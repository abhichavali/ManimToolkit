# Post-watch problem set

Problems a viewer can start right after watching. Each needs one genuine idea from the video. They should be
easy to understand and not doable without thinking: no plug-and-chug, no grinding.

## Shape: 5 to 7 problems, gentle ramp

1. **Warm-up (1 to 2)**: the core idea in its simplest form, e.g. the video's worked example with one thing changed.
2. **Think a little (3 to 4)**: the same idea in a slightly new setting, with one "aha" step reachable in 5 to 15
   minutes. Good moves: predict, then verify; run the question backwards; change a parameter and ask what changes
   and why; find the flaw in a plausible wrong argument; estimate before computing.
3. **Stretch (1, marked optional)**: follows the thread the video pointed to at the end.
4. With `--mind-blow`: one problem where the viewer re-derives the surprise themselves in a small case.

Every problem:
- A short, self-contained statement, with notation exactly as in the video.
- Points to the moment it builds on, `\see{4:12}`, using the chapter list `mtk render` prints.
- Has a numeric or otherwise checkable answer wherever possible.

## Hints and solutions

- **Hints** (own page): one nudge per problem. Point at the idea; don't do the step.
- **Solutions** (own pages, at the end): the reasoning first (why this approach), then the work, then a check
  (plug back in, a limiting case, a numeric sanity value).

## Verify (required)

- `check_problems.py` in the project computes every answer with numpy or sympy and asserts it matches the
  solution text.
- Spawn a fresh agent to solve the problems cold from `problems.tex` with the hints and solutions removed.
  Any mismatch, ambiguity, or "this was a slog" means fix the statement or the difficulty.

## Format

Copy `problem-set.tex` from the skill folder to `<project>/problems.tex` and fill it in. Packages: BasicTeX only
(amsmath, amssymb, amsthm, geometry, hyperref, xcolor); enumitem, tcolorbox and mdframed are not installed.
Build with `pdflatex -interaction=nonstopmode problems.tex` twice (page references), then look at every page of
`problems.pdf` with the Read tool before delivering.
