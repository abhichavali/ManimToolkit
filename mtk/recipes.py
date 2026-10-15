"""Recipe gallery: tested 3Blue1Brown-style patterns in the mtk look (manim CE 0.21).

Each R## scene is a short, silent, self-contained demo of one visual idea. Copy the pattern into your
own scene, then narrate it with self.beat(...) / `with self.say(...) as d:`.
R## are general; P## are PDE patterns built on mtk.pde (exact solutions, solvers, x-t diagrams); W## walkthroughs.
List: mtk recipe      Print one: mtk recipe P02      Storyboard one: mtk check -s P02_SpaceTime <this file>
"""
from mtk import *
from mtk.pde import *


class R01_LinearMap(VScene):
    """Linear algebra: a matrix moves the whole grid. Basis vectors ride along; the unit square's area becomes |det|.
    Pattern: one VGroup (plane + vectors + square) through ApplyMatrix, a faint static copy of the grid behind."""

    def construct(self):
        A = [[1, 1], [-0.5, 1.5]]  # det = 2
        assert abs(np.linalg.det(A) - 2) < 1e-12
        ghost = NumberPlane(background_line_style={"stroke_color": HAIR, "stroke_width": 1}, axis_config={"stroke_color": HAIR})
        plane = NumberPlane(x_range=[-10, 10], y_range=[-8, 8],
                            background_line_style={"stroke_color": SKY, "stroke_width": 1.5, "stroke_opacity": 0.5})
        i_hat = Arrow(ORIGIN, RIGHT, buff=0, color=MINT, stroke_width=6)
        j_hat = Arrow(ORIGIN, UP, buff=0, color=EMBER, stroke_width=6)
        sq = Square(1, stroke_width=0, fill_color=GOLD, fill_opacity=0.45).move_to([0.5, 0.5, 0])
        mat = M(r"\begin{bmatrix} 1 & 1 \\ -0.5 & 1.5 \end{bmatrix}", size=40)
        det = M(r"\text{area} \times", r"2", size=36, color=GOLD)
        hud = VGroup(mat, det).arrange(DOWN, buff=0.3).to_corner(UL, buff=0.5)
        bg = BackgroundRectangle(hud, color=BG, fill_opacity=0.85, buff=0.2)  # keeps the HUD readable over the grid
        self.add(ghost)
        self.play(Create(plane), run_time=1.5)
        self.play(GrowArrow(i_hat), GrowArrow(j_hat), FadeIn(sq), FadeIn(bg), Write(mat))
        self.play(ApplyMatrix(A, VGroup(plane, i_hat, j_hat, sq)), run_time=3)
        self.play(Write(det))
        self.wait()


class R02_ComplexMap(VScene):
    """Complex functions as motion of the plane. prepare_for_nonlinear_transform() first, or lines bend in steps."""

    def construct(self):
        plane = ComplexPlane(x_range=[-3, 3], y_range=[-3, 3],
                             background_line_style={"stroke_color": LILAC, "stroke_width": 2, "stroke_opacity": 0.7})
        plane.prepare_for_nonlinear_transform()
        circle = Circle(radius=1, color=GOLD, stroke_width=5)
        lab = M(r"z \mapsto z^2", size=44).to_corner(UL, buff=0.5)
        self.play(Create(plane), Create(circle), Write(lab), run_time=1.5)
        self.play(ApplyComplexFunction(lambda z: z ** 2, VGroup(plane, circle)), run_time=4)
        self.wait()


class R03_Tracker(VScene):
    """A parameter you can watch: ValueTracker drives the curve, a riding dot and a live readout.
    Pattern: always_redraw for things rebuilt from the tracker, add_updater for things that just move."""

    def construct(self):
        k = ValueTracker(1)
        ax = axes([0, TAU, PI / 2], [-1.5, 1.5, 1], width=10, height=4, xlabel="x", ylabel="y", pi_ticks=True)
        curve = always_redraw(lambda: ax.plot(lambda x: np.sin(k.get_value() * x), color=SKY, stroke_width=5))
        dot = always_redraw(lambda: Dot(ax.c2p(2, np.sin(2 * k.get_value())), color=GOLD, radius=0.09))
        readout = Variable(1, M("k"), num_decimal_places=2).scale(0.9).to_corner(UR, buff=0.6)
        readout.add_updater(lambda v: v.tracker.set_value(k.get_value()))
        formula = M(r"y = \sin(kx)", color=SKY).to_corner(UL, buff=0.6)
        self.play(Create(ax), Write(formula), FadeIn(readout))
        self.play(Create(curve), FadeIn(dot))
        self.play(k.animate.set_value(3), run_time=4, rate_func=there_and_back_with_pause)
        self.wait()


class R04_Derivation(VScene):
    """Algebra that moves: each step morphs from the last, and pieces with identical TeX glide instead of redrawing.
    Pattern: pass each line as several strings (each must compile alone: use \\Big( not \\left( ), color the
    tracked symbol the same in every line, TransformMatchingTex between lines, then box the result and brace it.
    Don't use substrings_to_isolate on single letters: it splits \\frac and \\sqrt and LaTeX fails."""

    def construct(self):
        steps = [["a", "x^2", "+", "b", "x", "+", "c", "=", "0"],
                 ["x^2", "+", r"\frac{b}{a}", "x", "=", r"-\frac{c}{a}"],
                 [r"\Big(", "x", "+", r"\frac{b}{2a}", r"\Big)^2", "=", r"\frac{b^2 - 4ac}{4a^2}"],
                 ["x", "=", r"\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}"]]
        eqs = [M(*p, size=52).set_color_by_tex("x", SKY) for p in steps]
        why = ["divide by a", "complete the square", "square root, solve for x"]
        cur = eqs[0]
        self.play(Write(cur))
        for nxt, w in zip(eqs[1:], why):
            w = T(w, 28, INK2).next_to(nxt, DOWN, buff=0.6)
            self.play(TransformMatchingTex(cur, nxt), FadeIn(w, shift=0.2 * UP), run_time=1.8)
            self.wait(0.6)
            self.play(FadeOut(w))
            cur = nxt
        box = SurroundingRectangle(cur, color=GOLD, buff=0.25, corner_radius=0.1)
        brace = Brace(cur[2], DOWN, color=MUTED)
        lab = T("every root of every quadratic", 28, INK2).next_to(brace, DOWN, buff=0.2)
        self.play(Create(box), GrowFromCenter(brace), FadeIn(lab))
        self.wait()


class R05_Zoom(VScene):
    """Zoom in until a curve looks straight (local linearity). Pattern: animate self.camera.frame;
    counter-scale anything that should keep its on-screen size (labels, dots) by the same factor."""

    def construct(self):
        ax = axes([-1, 3, 1], [-1, 5, 1], width=8, height=6, xlabel="x", ylabel="y")
        f = lambda x: 0.6 * x ** 2 - 0.2 * x + 0.5
        g = ax.plot(f, color=SKY, stroke_width=4, x_range=[-1, 2.9])
        x0 = 1.6
        p = ax.c2p(x0, f(x0))
        dot = Dot(p, color=GOLD, radius=0.08)
        tan = ax.plot(lambda x: f(x0) + (1.2 * x0 - 0.2) * (x - x0), color=GOLD, stroke_width=3, x_range=[0.6, 2.6])
        self.play(Create(ax), Create(g))
        self.play(FadeIn(dot), Create(tan))
        frame = self.camera.frame
        frame.save_state()
        s = 0.06
        self.play(frame.animate.scale(s).move_to(p), dot.animate.scale(s), g.animate.set_stroke(width=4 * s),
                  tan.animate.set_stroke(width=3 * s), run_time=4)
        self.wait()
        self.play(Restore(frame),
                  dot.animate.scale(1 / s), g.animate.set_stroke(width=4), tan.animate.set_stroke(width=3), run_time=2)
        self.wait()


class R06_Epicycles(VScene):
    """Fourier epicycles: spinning circles, tip to tail, trace a closed curve.
    Pattern: FFT the sampled path once with numpy, then one ValueTracker t drives every arrow (always_redraw)."""

    def construct(self):
        n, terms = 512, 40
        s = np.linspace(0, 2 * np.pi, n, endpoint=False)
        # heart curve as complex numbers, scaled into the frame
        path = (16 * np.sin(s) ** 3 + 1j * (13 * np.cos(s) - 5 * np.cos(2 * s) - 2 * np.cos(3 * s) - np.cos(4 * s))) / 6
        c = np.fft.fft(path) / n
        freqs = np.fft.fftfreq(n, 1 / n).astype(int)
        order = sorted(range(n), key=lambda i: -abs(c[i]))[:terms]
        recon = sum(c[i] * np.exp(1j * freqs[i] * s) for i in order)
        assert np.max(np.abs(recon - path)) < 0.25  # 40 terms land within a quarter unit everywhere
        t = ValueTracker(0)
        tip = [ORIGIN]

        def chain():
            z, g = 0j, VGroup()
            for i in order:
                r, nz = abs(c[i]), z + c[i] * np.exp(1j * freqs[i] * t.get_value())
                g.add(Circle(radius=r, stroke_color=INK2, stroke_width=1, stroke_opacity=0.35).move_to([z.real, z.imag, 0]))
                g.add(Line([z.real, z.imag, 0], [nz.real, nz.imag, 0], color=SKY, stroke_width=2))
                z = nz
            tip[0] = np.array([z.real, z.imag, 0])
            return g

        arms = always_redraw(chain)
        pen = Dot(tip[0], radius=0.04, color=GOLD).add_updater(lambda d: d.move_to(tip[0]))  # added after arms
        trace = TracedPath(pen.get_center, stroke_color=GOLD, stroke_width=4)
        self.add(arms, pen, trace)
        self.play(t.animate.set_value(2 * np.pi), run_time=8, rate_func=linear)
        self.wait()


class R07_Flow(VScene):
    """Vector field + flow: streamlines that keep moving, for ODEs, fluids, gradients.
    Pattern: StreamLines(...).start_animation(); the motion continues through every wait()."""

    def construct(self):
        f = lambda p: np.array([p[1], -np.sin(p[0]) - 0.25 * p[1], 0])  # damped pendulum phase plane
        lines = StreamLines(f, x_range=[-7, 7, 0.5], y_range=[-4, 4, 0.5], stroke_width=2, padding=1,
                            colors=[SKY, MINT, GOLD, EMBER], max_anchors_per_line=40, virtual_time=6)
        lab = M(r"\ddot\theta = -\sin\theta - 0.25\,\dot\theta", size=40)
        lab.add_background_rectangle(color=BG, opacity=0.85, buff=0.15).to_corner(UL, buff=0.4)
        self.add(lines)
        lines.start_animation(warm_up=True, flow_speed=1.5)
        self.play(FadeIn(lab))
        self.wait(5)
        self.play(lines.end_animation())


class R08_Surface(VScene3D):
    """3D surface with a slow orbit. Pattern: Surface over ThreeDAxes, fill by height, fixed-in-frame title.
    Cairo 3D is slow: resolution (24, 24) and a few seconds of orbit is plenty."""

    def construct(self):
        ax = ThreeDAxes(x_range=[-3, 3], y_range=[-3, 3], z_range=[-1, 1.5], x_length=6, y_length=6, z_length=3,
                        axis_config={"color": AXIS})
        surf = Surface(lambda u, v: ax.c2p(u, v, np.exp(-(u * u + v * v) / 2) * np.cos(2 * u)),
                       u_range=[-3, 3], v_range=[-3, 3], resolution=(24, 24), stroke_width=0.4, stroke_color=BG)
        surf.set_fill_by_value(axes=ax, colorscale=[(SKY, -0.6), (BG, 0), (EMBER, 0.6), (GOLD, 1)], axis=2)
        title = M(r"z = e^{-(x^2 + y^2)/2} \cos 2x", size=36).to_corner(UL, buff=0.5)
        self.set_camera_orientation(phi=65 * DEGREES, theta=-50 * DEGREES)
        self.add_fixed_in_frame_mobjects(title)
        self.play(Create(ax), Write(title))
        self.play(Create(surf), run_time=2)
        self.begin_ambient_camera_rotation(rate=0.25)
        self.wait(4)
        self.stop_ambient_camera_rotation()


class R09_Riemann(VScene):
    """Limits you can see: rectangles refine, the sum converges, a readout tracks it.
    Pattern: rebuild rectangles per dx and ReplacementTransform between them; numbers are computed, not typed."""

    def construct(self):
        ax = axes([0, 2, 0.5], [0, 4.5, 1], width=7, height=5, xlabel="x", ylabel="y").shift(1.8 * LEFT)
        f = lambda x: x ** 2
        g = ax.plot(f, color=SKY, stroke_width=4)
        exact = 8 / 3
        rects, sums = None, []
        for dx in [0.5, 0.25, 0.1, 0.04]:
            xs = np.arange(0, 2, dx)
            sums.append(float(np.sum(f(xs) * dx)))  # left sum
            new = ax.get_riemann_rectangles(g, x_range=[0, 2], dx=dx, input_sample_type="left",
                                            color=(SKY, MINT), fill_opacity=0.6, stroke_width=0.5, stroke_color=BG)
            val = VGroup(M(r"\Delta x =", f"{dx}", size=34), M(r"\text{sum} =", f"{sums[-1]:.3f}", size=34))
            val.arrange(DOWN, aligned_edge=LEFT).to_edge(RIGHT, buff=1)
            if rects is None:
                self.play(Create(ax), Create(g))
                self.play(Create(new), Write(val))
            else:
                self.play(ReplacementTransform(rects, new), ReplacementTransform(readout, val), run_time=1.5)
            rects, readout = new, val
            self.wait(0.5)
        assert abs(sums[-1] - exact) < 0.1 and sums == sorted(sums)  # left sums of an increasing f climb to 8/3
        target = M(r"\to \frac{8}{3}", size=40, color=GOLD).next_to(readout, DOWN, buff=0.4, aligned_edge=LEFT)
        self.play(Write(target))
        self.wait()


class R10_Reveal(VScene):
    """The 'blow your mind' choreography (Basel problem): plant a mystery early, build toward it, then reveal slowly.
    Beats: (1) a dashed target marked '?' (2) the build, partial sums creeping up (3) stillness: one line,
    `with self.say(..., style="slower, quieter, a little awed")` (4) the reveal with glow + Flash
    (5) immediately start explaining WHY; a reveal without the why is a magic trick."""

    def construct(self):
        target = np.pi ** 2 / 6
        partial = np.cumsum(1 / np.arange(1, 2001) ** 2)
        assert abs(partial[-1] - target) < 1e-3 and abs(target - 1.644934) < 1e-6
        ax = axes([0, 2, 0.5], [0, 1, 1], width=11, height=1.2, xlabel="", ylabel="").shift(0.6 * DOWN)
        ax.y_axis.set_opacity(0)
        line_x = ax.c2p(target, 0)[0]
        mystery = DashedLine([line_x, -2.2, 0], [line_x, 1.3, 0], color=MUTED)
        q = M("?", size=56, color=MUTED).next_to(mystery, UP, buff=0.15)
        series = M(r"1 + \tfrac14 + \tfrac19 + \tfrac1{16} + \cdots", size=44).to_edge(UP, buff=1.0)
        self.play(Write(series), Create(ax))
        self.play(Create(mystery), FadeIn(q, shift=0.2 * DOWN))
        n = ValueTracker(1)
        bar = always_redraw(lambda: Rectangle(width=ax.c2p(partial[int(n.get_value()) - 1], 0)[0] - ax.c2p(0, 0)[0],
                                              height=0.5, stroke_width=0, fill_color=SKY, fill_opacity=0.8)
                            .move_to(ax.c2p(0, 0), aligned_edge=LEFT))
        self.add(bar)
        self.play(n.animate.set_value(2000), run_time=5, rate_func=lambda t: t ** 3)
        self.wait(1)  # the stillness before the reveal is part of the effect
        ans = M(r"\frac{\pi^2}{6}", size=72, color=GOLD).move_to(q).shift(0.3 * UP)
        halo = glow(ans, GOLD)
        self.play(ReplacementTransform(q, ans), FadeIn(halo), mystery.animate.set_color(GOLD), run_time=1.5)
        self.play(Flash(ans, color=GOLD, line_length=0.4, num_lines=16, flash_radius=1.0))
        circ = Circle(radius=0.7, color=GOLD).next_to(ans, RIGHT, buff=0.6)
        why = T("where is the circle?", 30, INK2).next_to(ax, DOWN, buff=0.9)
        self.play(Create(circ), FadeIn(why))  # (5): turn the shock into a question the video answers
        self.wait()


class R11_Graph(VScene):
    """Algorithms on graphs: a manim Graph, then a BFS wave colours vertices layer by layer.
    Pattern: compute the algorithm's order in plain Python first, then animate that order."""

    def construct(self):
        V = list(range(10))
        E = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6), (3, 7), (4, 7), (5, 8), (6, 8), (7, 9), (8, 9)]
        g = Graph(V, E, layout="kamada_kawai", layout_scale=3.2, labels=True,
                  vertex_config={"fill_color": SURFACE, "stroke_color": INK2, "stroke_width": 2, "radius": 0.3},
                  edge_config={"stroke_color": AXIS, "stroke_width": 3})
        adj = {v: [] for v in V}
        for a, b in E:
            adj[a].append(b), adj[b].append(a)
        dist, layers = {0: 0}, [[0]]
        while True:
            nxt = []
            for v in layers[-1]:
                for w in adj[v]:
                    if w not in dist:
                        dist[w] = len(layers)
                        nxt.append(w)
            if not nxt:
                break
            layers.append(nxt)
        assert dist[9] == 4 and sum(map(len, layers)) == 10
        self.play(Create(g), run_time=2)
        for i, layer in enumerate(layers):
            col = PALETTE[i % len(PALETTE)]
            self.play(*[g.vertices[v].animate.set_fill(col, opacity=0.9, family=False) for v in layer],
                      *[g.edges[e].animate.set_stroke(col) for e in E if {dist[e[0]], dist[e[1]]} == {i - 1, i}],
                      run_time=0.8)
        self.wait()


class R12_Histogram(VScene):
    """Probability: binomial bars settle onto the bell curve as n grows (CLT).
    Pattern: standardize, so each bar's area is its probability; Transform one bar set into the next."""

    def construct(self):
        from math import comb
        ax = axes([-4, 4, 1], [0, 0.5, 0.1], width=10, height=4.5, xlabel="z", ylabel="").shift(0.4 * DOWN)
        bell = ax.plot(lambda z: np.exp(-z * z / 2) / np.sqrt(2 * np.pi), color=GOLD, stroke_width=4)

        def bars(n):
            mu, sd = n / 2, np.sqrt(n) / 2
            g = VGroup()
            for k in range(n + 1):
                z0, z1 = (k - 0.5 - mu) / sd, (k + 0.5 - mu) / sd
                h = comb(n, k) / 2 ** n * sd  # density height: probability / bar width (1/sd)
                if z1 < -4 or z0 > 4:
                    continue
                g.add(Polygon(ax.c2p(z0, 0), ax.c2p(z1, 0), ax.c2p(z1, h), ax.c2p(z0, h),
                              stroke_width=1, stroke_color=BG, fill_color=SKY, fill_opacity=0.7))
            return g

        assert abs(sum(comb(40, k) for k in range(41)) / 2 ** 40 - 1) < 1e-12
        label = lambda n: M(r"n =", str(n), size=40).to_corner(UR, buff=0.6)
        cur, lab = bars(1), label(1)
        self.play(Create(ax), FadeIn(cur), Write(lab))
        for n in [2, 4, 8, 16, 40]:
            self.play(Transform(cur, bars(n)), Transform(lab, label(n)), run_time=1.2)
        self.play(Create(bell), run_time=1.5)
        self.wait()


# ====================================== PDE recipes ======================================


class P01_HeatModes(VScene):
    """Heat equation as decaying sine modes (separation of variables on [0, pi], u = 0 at both ends).
    Pattern: profile left, mode amplitudes as bars right, one tracker t driving both. Mode n decays like
    e^{-n^2 t}, so the wiggles die first: the profile smooths before it shrinks."""

    def construct(self):
        b = [1.0, 0, 0.45, 0, 0.3, 0, 0.22]
        u = heat_modes(b)
        d = derivs(u, *sample([0.1, 3.0], [0.0, 1.0]))
        assert np.max(abs(d["ut"] - d["uxx"])) < 1e-4 and abs(u(np.pi, 0.3)) < 1e-12
        t = ValueTracker(0)
        ax = axes([0, PI, PI / 2], [-0.2, 1.4, 0.5], width=6, height=3.6, xlabel="x", ylabel="u", pi_ticks=True)
        bx = axes([0, 8, 1], [0, 1.1, 0.5], width=4.6, height=3.6, xlabel="n", ylabel="")
        VGroup(ax, bx).arrange(RIGHT, buff=1.4).shift(0.5 * DOWN)
        init = dashed(ax.plot(lambda s: u(s, 0), color=MUTED, stroke_width=3))
        modes = VGroup(*[live(ax, lambda s, tt, n=n, bn=bn: bn * np.exp(-n * n * tt) * np.sin(n * s), t,
                              color=HEAT, width=1.5, stroke_opacity=0.4) for n, bn in enumerate(b, 1) if bn])
        prof = live(ax, u, t, color=HEAT, width=5)

        def bars():
            g = VGroup()
            for n, bn in enumerate(b, 1):
                if bn:
                    lo, hi = bx.c2p(n - 0.35, 0), bx.c2p(n + 0.35, bn * np.exp(-n * n * t.get_value()))
                    g.add(Rectangle(width=hi[0] - lo[0], height=max(hi[1] - lo[1], 1e-3), stroke_width=0,
                                    fill_color=HEAT, fill_opacity=0.8).move_to(lo, aligned_edge=DL))
            return g

        nlab = VGroup(*[M(str(n), size=26, color=MUTED).next_to(bx.c2p(n, 0), DOWN, buff=0.15)
                        for n, bn in enumerate(b, 1) if bn])
        eq = M(r"u = \sum_n b_n\, e^{-n^2 t} \sin nx", size=44, color=HEAT).to_edge(UP, buff=0.5)
        clock = readout("t =", t.get_value, digits=2, size=32).to_corner(UR, buff=0.5)
        self.play(Write(eq), Create(ax), Create(bx), FadeIn(nlab))
        self.play(Create(init), FadeIn(modes), Create(prof), FadeIn(always_redraw(bars)), FadeIn(clock))
        self.play(t.animate.set_value(0.8), run_time=6, rate_func=linear)
        self.wait()


class P02_SpaceTime(VScene):
    """The x-t diagram filling in under a live profile: the signature view of any 1D evolution.
    Pattern: profile panel on top, xt_diagram below on the same x scale; st_mask uncovers t <= tt, now_line marks tt.
    Layer order: image, mask, axes frame, then anything that rides on top."""

    def construct(self):
        nu = 0.5
        parts = [gauss_heat(0.7, 0.5, 0, nu), gauss_heat(0.5, 12, 1.8, nu), gauss_heat(0.5, 12, -1.8, nu)]
        u = lambda x, t: sum(p(x, t) for p in parts)
        d = derivs(u, *sample([-4, 4], [0.01, 2]))
        assert np.max(abs(d["ut"] - nu * d["uxx"])) < 1e-4
        xr, tr = [-4, 4], [0, 2]
        t = ValueTracker(0)
        top = axes([-4, 4, 1], [0, 1.2, 0.5], width=9, height=2.2, xlabel="x", ylabel="u", boxed=True)
        top.move_to(1.9 * UP + 0.8 * RIGHT)
        ax, img = xt_diagram(u, xr, tr, width=9, height=3.4)
        Group(img, ax).move_to(1.75 * DOWN + 0.8 * RIGHT)
        init = dashed(top.plot(lambda s: u(s, 0), color=MUTED, stroke_width=3))
        prof = live(top, u, t, color=HEAT, width=5)
        eq = M(r"u_t = \tfrac12 u_{xx}", size=44, color=HEAT).to_corner(UL, buff=0.5)
        self.play(Write(eq), Create(top), Create(init))
        self.add(img, st_mask(ax, xr, tr, t), ax, now_line(ax, xr, t), prof)
        self.play(t.animate.set_value(2), run_time=6, rate_func=linear)
        self.wait()


class P03_Characteristics(VScene):
    """Transport with variable speed, u_t + x u_x = 0: values ride along curved characteristics X = xi e^t.
    Pattern: field under char_curves, both revealed by the mask; dots ride X(xi, t) carrying their (constant) value."""

    def construct(self):
        u0 = lambda s: np.exp(-4 * (s - 1) ** 2) + 0.7 * np.exp(-6 * (s + 1.2) ** 2)
        u = lambda x, t: u0(x * np.exp(-t))
        X = lambda xi, t: xi * np.exp(t)
        x, tt0 = sample([-4, 4], [0, 1.4])
        d = derivs(u, x, tt0)
        assert np.max(abs(d["ut"] + x * d["ux"])) < 1e-5
        xr, tr = [-4, 4], [0, 1.4]
        t = ValueTracker(0)
        ax, img = xt_diagram(u, xr, tr, width=10, height=5.2)
        Group(img, ax).shift(0.5 * DOWN)
        chars = char_curves(ax, X, np.linspace(-3.5, 3.5, 15), xr, tr, color=INK2, width=1.5)
        feet = [0.8, -0.9, 0.25]  # X(xi, 1.4) = 4.06 xi must stay inside [-4, 4]
        dots = VGroup(*[Dot(radius=0.08, color=GOLD).add_updater(
            lambda m, xi=xi: m.move_to(ax.c2p(X(xi, t.get_value()), t.get_value()))) for xi in feet])
        vals = VGroup(*[backed(M(f"{u0(xi):.2f}", size=26, color=GOLD)).add_updater(
            lambda m, i=i: m.next_to(dots[i], RIGHT, buff=0.1)) for i, xi in enumerate(feet)])
        eq = backed(M(r"u_t + x\,u_x = 0", size=44, color=TRANSPORT)).to_corner(UL, buff=0.4)
        self.add(img, chars, st_mask(ax, xr, tr, t), ax)
        self.play(Write(eq), FadeIn(dots), FadeIn(vals))
        self.play(t.animate.set_value(1.4), run_time=5, rate_func=linear)
        self.wait()


class P04_Dalembert(VScene):
    """Wave equation released from rest: the bump splits in two (d'Alembert), information moves along x = +-ct,
    and a point (x0, t0) only feels data in [x0 - c t0, x0 + c t0]: the domain of dependence."""

    def construct(self):
        f = lambda s: np.exp(-3 * s * s)
        u = dalembert(f)
        d = derivs(u, *sample([-5, 5], [0, 3]))
        assert np.max(abs(d["utt"] - d["uxx"])) < 1e-4
        xr, tr = [-5, 5], [0, 3]
        t = ValueTracker(0)
        top = axes([-5, 5, 1], [-0.1, 1.1, 0.5], width=9, height=2.2, xlabel="x", ylabel="u", boxed=True)
        top.move_to(1.9 * UP + 0.8 * RIGHT)
        ax, img = xt_diagram(u, xr, tr, width=9, height=3.4)
        Group(img, ax).move_to(1.75 * DOWN + 0.8 * RIGHT)
        cone = VGroup(*[DashedLine(ax.c2p(0, 0), ax.c2p(s * 3, 3), color=WAVE, stroke_width=2) for s in (-1, 1)])
        eq = M(r"u_{tt} = u_{xx}", size=44, color=WAVE).to_corner(UL, buff=0.5)
        self.play(Write(eq), Create(top), Create(dashed(top.plot(f, color=MUTED, stroke_width=3))))
        self.add(img, cone, st_mask(ax, xr, tr, t), ax, now_line(ax, xr, t), live(top, u, t, color=WAVE, width=5))
        self.play(t.animate.set_value(3), run_time=5, rate_func=linear)
        x0, t0 = 1.5, 2.0
        tri = Polygon(ax.c2p(x0, t0), ax.c2p(x0 - t0, 0), ax.c2p(x0 + t0, 0), stroke_color=GOLD, stroke_width=3,
                      fill_color=GOLD, fill_opacity=0.2)
        lab = backed(T("domain of dependence", 26, GOLD)).next_to(ax.c2p(x0, t0), UP, buff=0.15)
        self.play(Create(tri), FadeIn(Dot(ax.c2p(x0, t0), color=GOLD)), FadeIn(lab))
        self.wait()


class P05_BurgersBreaking(VScene):
    """Inviscid Burgers: tall parts move faster, characteristics cross at t_b = -1/min u0', the profile turns
    vertical and then folds over (multivalued), which is exactly where a shock has to be inserted."""

    def construct(self):
        u0 = lambda s: np.exp(-s * s)
        tb = t_break(u0, [-4, 4])
        assert abs(tb - np.sqrt(np.e / 2)) < 1e-4
        xb = 1 / np.sqrt(2) + u0(1 / np.sqrt(2)) * tb  # first crossing: foot where u0' is most negative
        xr, tr = [-3, 5], [0, 2]
        t = ValueTracker(0)
        top = axes([-3, 5, 1], [-0.1, 1.2, 0.5], width=9, height=2.2, xlabel="x", ylabel="u", boxed=True)
        top.move_to(1.9 * UP + 0.8 * RIGHT)
        ax = axes([-3, 5, 1], [0, 2, 1], width=9, height=3.4, xlabel="x", ylabel="t", boxed=True)
        ax.move_to(1.75 * DOWN + 0.8 * RIGHT)
        xi = np.linspace(-3, 4.9, 500)  # feet across the whole box, so the profile spans it

        def profile():
            x, v = burgers_curve(u0, t.get_value(), xi)
            return VMobject(stroke_color=BURGERS if t.get_value() <= tb else BAD, stroke_width=5).set_points_smoothly(
                [top.c2p(a, b) for a, b in zip(x, v)])

        chars = char_curves(ax, lambda s, tt: s + u0(s) * tt, np.linspace(-2.5, 2.5, 25), xr, tr, color=BURGERS, width=1.5)
        tline = DashedLine(ax.c2p(-3, tb), ax.c2p(5, tb), color=GOLD, stroke_width=2)
        tlab = backed(M(r"t_b = \sqrt{e/2}", size=30, color=GOLD)).next_to(tline, LEFT, buff=0.1).shift(0.25 * UP)
        eq = M(r"u_t + u\,u_x = 0", size=44, color=BURGERS).to_corner(UL, buff=0.5)
        self.play(Write(eq), Create(top), Create(ax))
        self.add(chars, st_mask(ax, xr, tr, t), ax, now_line(ax, xr, t), always_redraw(profile))
        self.play(t.animate.set_value(tb), run_time=4, rate_func=linear)
        self.play(Create(tline), FadeIn(tlab), Flash(ax.c2p(xb, tb), color=GOLD))
        fold = backed(T("multivalued: a shock must form", 26, BAD)).next_to(top, DOWN, buff=0.12).shift(2 * RIGHT)
        self.play(t.animate.set_value(1.9), FadeIn(fold), run_time=2.5, rate_func=linear)
        self.wait()


class P06_StandingWaves(VScene):
    """Separation of variables for the string: modes sin(nx) cos(nt) (nodes never move), and their sum.
    Pattern: stacked small panels for the building blocks, one big panel for the superposition, one tracker."""

    def construct(self):
        w = [1.0, 0.5, 0.3]
        mode = lambda n: (lambda x, t: np.sin(n * x) * np.cos(n * t))
        u = lambda x, t: sum(c * mode(n)(x, t) for n, c in enumerate(w, 1))
        d = derivs(u, *sample([0, np.pi], [0, 6]))
        assert np.max(abs(d["utt"] - d["uxx"])) < 1e-4
        t = ValueTracker(0)
        small = VGroup(*[axes([0, PI, PI], [-1.1, 1.1, 1], width=4.6, height=1.3, xlabel="", ylabel="")
                         for _ in w]).arrange(DOWN, buff=0.55).move_to(3.3 * LEFT + 0.4 * DOWN)
        big = axes([0, PI, PI / 2], [-1.9, 1.9, 1], width=5.6, height=4, xlabel="x", ylabel="u", pi_ticks=True)
        big.move_to(3.6 * RIGHT + 0.4 * DOWN)
        labs = VGroup(*[M(f"n = {n}", size=30, color=MUTED).next_to(a, LEFT, buff=0.3) for n, a in enumerate(small, 1)])
        nodes = VGroup(*[Dot(a.c2p(k * np.pi / n, 0), radius=0.06, color=GOLD)
                         for n, a in enumerate(small, 1) for k in range(n + 1)])
        curves = VGroup(*[live(a, lambda x, tt, n=n, c=c: c * mode(n)(x, tt), t, color=WAVE, width=3)
                          for n, (a, c) in enumerate(zip(small, w), 1)])
        eq = M(r"u = \sum_n c_n \sin(nx)\cos(nt)", size=40, color=WAVE).to_edge(UP, buff=0.5)
        self.play(Write(eq), Create(small), Create(big), FadeIn(labs))
        self.add(curves, nodes, live(big, u, t, color=WAVE, width=5))
        self.play(t.animate.set_value(2 * PI), run_time=7, rate_func=linear)
        self.wait()


class P07_Laplace(VScene):
    """Steady state (Laplace) on a square with a hot lid: heat-map field, level curves, and the mean value property:
    the average over any circle equals the value at its center, however the circle grows.
    Pattern: field_image + ImplicitFunction level sets mapped through ax.c2p; a live numeric average as proof-by-watching."""

    def construct(self):
        u = laplace_hot_lid
        c = (np.pi / 2, 1.2)
        ring = lambda r: np.mean(u(c[0] + r * np.cos(np.linspace(0, TAU, 2000, endpoint=False)),
                                   c[1] + r * np.sin(np.linspace(0, TAU, 2000, endpoint=False))))
        assert all(abs(ring(r) - u(*c)) < 1e-4 for r in (0.3, 0.6, 0.9))
        ax = axes([0, PI, PI / 2], [0, PI, PI / 2], width=5.6, height=5.6, xlabel="x", ylabel="y", boxed=True)
        ax.move_to(3 * LEFT + 0.4 * DOWN)
        img = field_image(lambda X, Y: u(X, Y), ax, [0, PI], [0, PI], nx=300, ny=300)
        levels = VGroup(*[ImplicitFunction(lambda x, y, v=v: laplace_hot_lid(x, y, 30) - v, x_range=[0.02, PI - 0.02],
                                           y_range=[0.02, PI - 0.02], color=INK2, stroke_width=1.5, stroke_opacity=0.6)
                          .apply_function(lambda p: ax.c2p(p[0], p[1])) for v in (0.1, 0.2, 0.35, 0.5, 0.7)])
        lid = M("u = 1", size=30, color=GOLD).next_to(ax, UP, buff=0.15)
        r = ValueTracker(0.2)
        unit = ax.c2p(1, 0)[0] - ax.c2p(0, 0)[0]
        circ = always_redraw(lambda: Circle(radius=r.get_value() * unit, color=GOLD, stroke_width=4).move_to(ax.c2p(*c)))
        eq = M(r"u_{xx} + u_{yy} = 0", size=44, color=ELLIPTIC)
        center = readout(r"u(\text{center}) =", lambda: u(*c), digits=4, size=34)
        avg = readout(r"\text{circle average} =", lambda: ring(r.get_value()), digits=4, size=34, color=GOLD)
        VGroup(eq, center, avg).arrange(DOWN, buff=0.6, aligned_edge=LEFT).move_to(3.6 * RIGHT + 0.4 * DOWN)
        self.play(FadeIn(img), Create(ax), Write(lid), Write(eq))
        self.play(Create(levels), run_time=2)
        self.play(Create(circ), FadeIn(Dot(ax.c2p(*c), color=GOLD, radius=0.06)), FadeIn(center), FadeIn(avg))
        self.play(r.animate.set_value(1.1), run_time=3)
        self.play(r.animate.set_value(0.4), run_time=2)
        self.wait()


class P08_Gibbs(VScene):
    """Fourier partial sums of a square wave converge, except for an overshoot near the jump that never shrinks:
    it tends to (2/pi) Si(pi) = 1.1790 (Gibbs). Pattern: integer ValueTracker N, dense sampling, live max readout."""

    def construct(self):
        S = lambda x, N: 4 / np.pi * sum(np.sin(k * x) / k for k in range(1, int(N) + 1, 2))
        xs = np.linspace(1e-4, np.pi / 2, 20000)
        assert abs(S(xs, 401).max() - 1.178979744) < 1e-3
        ax = axes([-PI, PI, PI / 2], [-1.5, 1.5, 0.5], width=11, height=4.4, xlabel="x", ylabel="")
        ax.shift(0.5 * DOWN)
        N = ValueTracker(1)
        n_odd = lambda: 2 * int(round((N.get_value() - 1) / 2)) + 1
        sq = VGroup(*[dashed(ax.plot(lambda x, v=v: v, x_range=r, color=MUTED), n=30)  # dash each piece: not a VGroup
                      for v, r in ((-1, [-PI, 0]), (1, [0, PI]))])
        curve = always_redraw(lambda: ax.plot(lambda x: S(x, n_odd()), x_range=[-PI, PI, TAU / 1500],
                                              color=SKY, stroke_width=4))
        gib = DashedLine(ax.c2p(-PI, 1.179), ax.c2p(PI, 1.179), color=GOLD, stroke_width=2)
        glab = M("1.179", size=28, color=GOLD).next_to(gib, RIGHT, buff=0.1)
        eq = M(r"S_N(x) = \frac{4}{\pi}\sum_{k \text{ odd} \le N} \frac{\sin kx}{k}", size=40).to_corner(UL, buff=0.4)
        nlab = readout("N =", n_odd, digits=0, size=34).to_corner(UR, buff=0.5)
        peak = readout(r"\max S_N =", lambda: S(xs[::20], n_odd()).max(), digits=3, size=34, color=GOLD)
        peak.next_to(nlab, DOWN, buff=0.3, aligned_edge=RIGHT)
        self.play(Write(eq), Create(ax), Create(sq), FadeIn(nlab))
        self.play(Create(curve), FadeIn(peak))
        self.play(N.animate.set_value(61), run_time=6, rate_func=rate_functions.ease_in_quad)
        self.play(Create(gib), FadeIn(glab))
        self.wait()


class P09_FisherFront(VScene):
    """Reaction-diffusion (Fisher-KPP): a front invades at speed 2 sqrt(D r). Numerical, so it says so on screen.
    Pattern: rd_solve once, as_field to interpolate between snapshots, readouts measured from the data."""

    def construct(self):
        x, ts, U = rd_solve(lambda s: 1 / (1 + np.exp(4 * (s - 4))), [0, 60], 1.0, 20, 0.1, f=lambda v: v * (1 - v), dx=0.1)
        F = as_field(x, ts, U)
        pos = np.array([front_position(x, Ui) for Ui in U])
        speed = (pos[200] - pos[100]) / 10
        assert 1.8 < speed < 2.05, speed  # approaches 2 from below (the pulled-front correction is slow)
        t = ValueTracker(0)
        ax = axes([0, 60, 10], [0, 1.1, 0.5], width=11.5, height=3.6, xlabel="x", ylabel="u").shift(0.6 * DOWN)
        eq = M(r"u_t = u_{xx} + u(1 - u)", size=44, color=REACTION).to_corner(UL, buff=0.5)
        where = readout(r"\text{front at } x =", lambda: np.interp(t.get_value(), ts, pos), digits=1, size=32)
        vel = readout(r"\text{speed} =", lambda: (np.interp(t.get_value(), ts, pos) - np.interp(t.get_value() - 2, ts, pos)) / 2
                      if t.get_value() > 2 else 0, digits=2, size=32, color=GOLD)
        theory = M(r"\to 2\sqrt{Dr} = 2", size=32, color=GOLD)
        hud = VGroup(where, VGroup(vel, theory).arrange(RIGHT, buff=0.3)).arrange(DOWN, aligned_edge=LEFT, buff=0.25)
        hud.to_corner(UR, buff=0.5)
        note = T("computed numerically", 24, MUTED).to_corner(DR, buff=0.4)
        self.play(Write(eq), Create(ax), FadeIn(hud), FadeIn(note))
        self.add(live(ax, F, t, color=REACTION, width=5, n=600))
        self.play(t.animate.set_value(20), run_time=7, rate_func=linear)
        self.wait()


class P10_HeatKernel(VScene):
    """Superposition: rough data = a few spikes; each spike spreads as its own Gaussian (the heat kernel),
    and the solution is their sum. Pattern: faint per-piece curves in palette colors under one bold sum."""

    def construct(self):
        nu = 0.5
        spikes = [(-2.6, 0.6), (-1.2, 1.0), (0.3, 0.5), (1.4, 0.9), (2.7, 0.45)]
        parts = [gauss_heat(A, 30, x0, nu) for x0, A in spikes]
        u = lambda x, t: sum(p(x, t) for p in parts)
        d = derivs(u, *sample([-4, 4], [0.02, 1.5]))
        assert np.max(abs(d["ut"] - nu * d["uxx"])) < 1e-4
        t = ValueTracker(0)
        ax = axes([-4, 4, 1], [0, 1.1, 0.5], width=11, height=4.2, xlabel="x", ylabel="u").shift(0.7 * DOWN)
        pieces = VGroup(*[live(ax, p, t, color=PALETTE[i], width=2, stroke_opacity=0.7) for i, p in enumerate(parts)])
        eq = M(r"u(x,t) = \int \Phi(x - y, t)\, u_0(y)\, dy", size=40, color=HEAT).to_edge(UP, buff=0.5)
        sub = T("each spike spreads on its own; the solution is their sum", 28, INK2).next_to(eq, DOWN, buff=0.3)
        self.play(Write(eq), FadeIn(sub), Create(ax))
        self.play(FadeIn(pieces))
        total = live(ax, u, t, color=INK, width=5)
        self.play(Create(total))
        self.play(t.animate.set_value(1.5), run_time=6, rate_func=linear)
        self.wait()


class P11_DrumMode(VScene3D):
    """A square drum's (2, 1) mode, u = sin 2x sin y cos(sqrt5 t), as a 3D surface.
    Pattern: build the surface once, then each frame stretch a copy in z by the time factor (no re-tessellation),
    which keeps 3D cheap enough to render. Title pinned with add_fixed_in_frame_mobjects."""

    def construct(self):
        w = np.sqrt(5)
        h = 1e-4
        r = np.random.default_rng(1)
        x, y, tt = r.uniform(0, np.pi, 200), r.uniform(0, np.pi, 200), r.uniform(0, 3, 200)
        U = lambda x, y, t: np.sin(2 * x) * np.sin(y) * np.cos(w * t)
        utt = (U(x, y, tt + h) - 2 * U(x, y, tt) + U(x, y, tt - h)) / h ** 2
        lap = (U(x + h, y, tt) + U(x - h, y, tt) + U(x, y + h, tt) + U(x, y - h, tt) - 4 * U(x, y, tt)) / h ** 2
        assert np.max(abs(utt - lap)) < 1e-3
        ax = ThreeDAxes(x_range=[0, PI], y_range=[0, PI], z_range=[-1, 1], x_length=5, y_length=5, z_length=2.4,
                        axis_config={"color": AXIS})
        base = Surface(lambda a, b: ax.c2p(a, b, np.sin(2 * a) * np.sin(b)), u_range=[0, PI], v_range=[0, PI],
                       resolution=(24, 24), stroke_width=0.4, stroke_color=BG)
        base.set_fill_by_value(axes=ax, colorscale=[(SKY, -1), (BG, 0), (EMBER, 1)], axis=2)
        t = ValueTracker(0)
        zero = ax.c2p(0, 0, 0)
        surf = base.copy().add_updater(lambda m: m.become(base.copy().stretch(
            np.cos(w * t.get_value()) or 1e-3, 2, about_point=zero)))
        title = M(r"u = \sin 2x\, \sin y\, \cos(\sqrt5\, t)", size=36, color=WAVE).to_corner(UL, buff=0.5)
        self.set_camera_orientation(phi=62 * DEGREES, theta=-50 * DEGREES)
        self.add_fixed_in_frame_mobjects(title)
        self.play(Create(ax), Write(title))
        self.add(surf)
        self.play(t.animate.set_value(2 * TAU / w), run_time=6, rate_func=linear)
        self.wait()


class R13_FakeSurface(VScene):
    """Fake 3D that renders fast: a shaded sphere colored by a spherical harmonic, spinning in a plain VScene.
    Pattern: SurfaceImage + a ValueTracker for azim, redrawn in an updater (milliseconds per frame); pin labels
    and dots to 3D points with .at(xyz). Prefer this to VScene3D (~10x slower) unless the camera flies through."""

    def construct(self):
        g = sphere_grid(200)
        Y = 3 * np.cos(g.U) ** 2 - 1  # the l = 2, m = 0 harmonic up to scale: +2 at the poles, -1 on the equator
        assert np.isclose(Y.max(), 2) and np.isclose(Y.min(), -1, atol=1e-3)
        s = SurfaceImage(g, vals=Y / 2, width=5).shift(2 * LEFT)
        az = ValueTracker(-60)
        s.add_updater(lambda m: m.redraw(azim=az.get_value()))
        pole = Dot(color=GOLD, radius=0.07).add_updater(lambda d: d.move_to(s.at([0, 0, 1])))
        lab = VGroup(M(r"Y_2^0 \propto 3\cos^2\theta - 1", size=40),
                     T("orange: positive · blue: negative", 26, INK2)).arrange(DOWN, buff=0.3).shift(3.6 * RIGHT)
        self.add(s, pole)
        self.play(FadeIn(lab), az.animate.set_value(300), run_time=6, rate_func=linear)
        self.wipe()


class R14_DeepZoom(VScene):
    """Zoom hundreds of times toward a point while curves stay thin and dots and labels stay readable:
    self.zoom_to(p, factor, keep=[...]). (label, dot) pairs keep a label beside its dot. Here: Newton's third
    tangent for x^2 - 2, from x2 = 17/12, lands 0.000002 from sqrt 2; at 600x they still look like one point."""

    def construct(self):
        r2, x2 = np.sqrt(2), 17 / 12
        x3 = (x2 + 2 / x2) / 2
        assert np.isclose(x3 - r2, 2.124e-6, rtol=1e-3)
        ax = axes([0, 2.5, 0.5], [-2, 4, 1], width=7, height=5)
        f = ax.plot(lambda x: x * x - 2, x_range=[0, 2.1, 0.0005], color=LILAC, stroke_width=4)
        # the tangent at x2 crosses zero exactly at x3: y = f(x2) + 2 x2 (x - x2)
        tan = Line(ax.c2p(x2 + 0.4, x2 * x2 - 2 + 2 * x2 * 0.4), ax.c2p(x3 - 0.4, -2 * x2 * 0.4), color=MINT,
                   stroke_width=3)
        root, d3 = Dot(ax.c2p(r2, 0), color=GOLD, radius=0.06), Dot(ax.c2p(x3, 0), color=SKY, radius=0.05)
        lr = M(r"\sqrt{2}", size=32, color=GOLD).next_to(root, UP + LEFT, buff=0.1)
        l3 = M("x_3", size=32, color=SKY).next_to(d3, DOWN + RIGHT, buff=0.1)
        self.play(Create(ax), Create(f), run_time=1.2)
        self.play(Create(tan), FadeIn(root, d3, lr, l3), run_time=0.8)
        self.play(self.zoom_to(root.get_center(), 600, keep=[f, tan, ax, root, d3, (lr, root), (l3, d3)]),
                  run_time=4)
        self.wait(1)
        self.wipe()


class W01_Walkthrough(VScene):
    """An exam-problem walkthrough's pieces in their usual order, compressed into one silent scene. In a real
    walkthrough they are three narrated scenes (mtk new --walk): S{NN}1_Read (title_card, the problem as a
    picture or qcard, self.try_it()), S{NN}2_Solve (steps, answer_box, choices + mark), S{NN}3_Trap (mark(row,
    False) on the tempting wrong choice, the one-line mistake, a key_box takeaway). Numbers go through check()."""

    def construct(self):
        k, q1, q2, r = 8.99e9, 3e-6, 4e-6, 0.30
        F = check(k * q1 * q2 / r ** 2, 1.20)
        trap = check(k * q1 * q2 / r, 0.36)  # forgot to square the distance
        card = self.title_card("Practice midterm · Problem 2", "Two charges, one force", "Ch. 18 · Coulomb's law")
        self.play(FadeIn(card, shift=0.2 * UP), run_time=0.8)
        self.wait(1)
        self.play(FadeOut(card), run_time=0.5)
        q = qcard("PROBLEM 2", TX(r"Charges $q_1 = 3\,\mu$C and $q_2 = 4\,\mu$C sit $0.30$ m apart."),
                  TX(r"How strong is the force between them?"))
        self.play(FadeIn(q, shift=0.2 * UP), run_time=0.6)
        self.wait(1)
        self.play(q.animate.scale(0.85).to_edge(UP, buff=0.3), run_time=0.6)
        steps = VGroup(E(r"F|=|k\frac{q_1 q_2}{r^2}", size=42),
                       E(r"F|=|\frac{(8.99 \times 10^9)(3 \times 10^{-6})(4 \times 10^{-6})}{(0.30)^2}", size=38),
                       E(r"F|=|" + sci(F) + r"\ \text{N}", size=42)).arrange(DOWN, buff=0.35, aligned_edge=LEFT)
        steps.next_to(q, DOWN, buff=0.45).to_edge(LEFT, buff=1.0)
        for st in steps:
            self.play(Write(st), run_time=0.8)
        box = answer_box(steps[2])
        self.play(Create(box), run_time=0.5)
        rows = choices([r"0.36\ \text{N}", r"1.20\ \text{N}", r"3.60\ \text{N}", r"12.0\ \text{N}"])
        rows.next_to(steps, RIGHT, buff=1.4).align_to(steps, UP)
        self.play(FadeIn(rows, lag_ratio=0.2), run_time=0.8)
        self.play(*mark(rows[1]), run_time=0.6)
        self.play(*mark(rows[0], good=False), run_time=0.6)
        self.wait(0.5)
        kb = key_box(r"F \propto \frac{1}{r^2}", sci(trap) + r"\ \text{N} \;=\; \text{forgot to square } r",
                     label="THE TRAP")
        self.play(FadeOut(VGroup(q, steps, box, rows)), FadeIn(place(kb, "full")), run_time=0.8)
        self.wait(1)
        self.wipe()
