#!/bin/bash
# Install mtk into the manim venv (editable, so edits here are live) and deploy plugin/ as the Claude Code skill
# plugin manim-explainer. Re-run after editing anything in plugin/.
set -euo pipefail
cd "$(dirname "$0")"
V=~/.venvs/manim
[ -x $V/bin/python ] || { python3 -m venv $V && uv pip install --python $V/bin/python manim; }
uv pip install --python $V/bin/python -q -e .
mkdir -p ~/.local/bin && ln -sf $V/bin/mtk ~/.local/bin/mtk
S=~/.claude/skills/manim-explainer
if [ -e $S/skills/video/vid.py ]; then  # the old copy-the-toolkit version: keep it, out of the way
  mkdir -p ~/.claude/skills/.trash && mv $S ~/.claude/skills/.trash/manim-explainer-0.1.0-$(date +%Y%m%d-%H%M%S)
fi
mkdir -p $S && rsync -a --delete --exclude .git plugin/ $S/
echo "mtk -> $(command -v mtk); skill -> $S"
