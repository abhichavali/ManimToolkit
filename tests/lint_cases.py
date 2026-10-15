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


class S05_Zoom(VScene):
    def construct(self):
        dot, lab = Dot(RIGHT, radius=0.08), M("x_3", size=32).next_to(RIGHT, UP, buff=0.1)
        line = Line(LEFT, 2 * RIGHT, stroke_width=4)
        self.add(line, dot, lab)
        w0, off0 = dot.width, lab.get_center() - dot.get_center()
        self.play(self.zoom_to(dot.get_center(), 100, keep=[line, dot, (lab, dot)]), run_time=1)
        z = config.frame_width / self.camera.frame.width
        assert abs(z - 100) < 1e-6, z
        assert abs(dot.width * z - w0) < 1e-6, (dot.width * z, w0)  # same size on screen
        assert np.allclose((lab.get_center() - dot.get_center()) * z, off0)  # still beside its dot on screen
        assert abs(line.get_stroke_width() * z - 4) < 1e-6
        self.wipe()


class S06_DriftA(VScene):
    def construct(self):
        colors(q=SKY)
        self.play(FadeIn(E("q|=|1")))
        self.wipe()


class S07_DriftB(VScene):
    def construct(self):
        colors(q=SKY)
        self.play(FadeIn(M("q", color=EMBER).shift(UP)))
        self.wipe()


class S08_Overrun(VScene):
    def construct(self):
        self.beat("Short line.", FadeIn(Circle()), 8.0)  # meant 8 seconds; it's 8 clips
        self.wipe()
