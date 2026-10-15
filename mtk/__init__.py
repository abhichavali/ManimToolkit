"""mtk: manim toolkit for narrated 3Blue1Brown-style explainers. Scene files: `from mtk import *`
(PDE topics: `from mtk.pde import *`). Reference: API.md in the manim-explainer skill."""
import importlib

from .core import *
from .kit import *
from .view3d import *

# the star imports re-export manim's own `core` module under that name; point mtk.core back at ours
core = importlib.import_module(".core", __name__)
