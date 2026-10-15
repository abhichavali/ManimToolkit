"""Scenes that each break one rule; tests/test_check.py asserts `mtk check` reports every one."""
from mtk import *


class S01_Covered(VScene):
    def construct(self):
        self.play(FadeIn(T("buried label", 30)))
        self.play(FadeIn(Square(1.5, fill_color=SKY, fill_opacity=1)))


class S02_Overlap_Edge_Small(VScene):
    def construct(self):
        self.play(FadeIn(M("x^2", size=60)), FadeIn(M("y^2", size=60).shift(0.1 * RIGHT)))
        self.play(FadeIn(T("off the edge", 40).move_to(7 * RIGHT)), FadeIn(T("tiny", 12).move_to(3 * DOWN)))


class S03_Narration(VScene):
    budget = 20

    def construct(self):
        self.play(FadeIn(Circle()))
        self.beat("Hold still while this sentence keeps going and going, long enough that the picture just sits "
                  "there frozen, with nothing at all changing on the screen for many seconds, x = 2.")
        self.wipe()


class S04_Clean(VScene):
    def construct(self):
        eq = E(r"a|=|b", size=48)
        self.beat("A clean beat.", Write(eq), Indicate(eq[0]))
        self.wipe()
