"""Reusable pieces that past videos kept rewriting: cards, marks, equation surgery, arrays, code, graphs, trees.
`python -m mtk.kit` self-checks the pure-python parts."""
from .core import *

MONO = "Menlo"
EDGE_KIND = {"tree": (MINT, False), "back": (ROSE, True), "forward": (GOLD, True), "cross": (LILAC, True)}


# ---------- small pieces ----------
def C(s, size=26, color=INK, **kw):
    """Monospace text (code, arrays printed as text). Words only; math goes in M()."""
    return Text(s, font=MONO, font_size=size, color=color, **kw)


def fit(m, w=None, h=None):
    """Shrink m (never grow) to at most width w / height h."""
    k = min(w / m.width if w and m.width > w else 1, h / m.height if h and m.height > h else 1)
    return m.scale(k) if k < 1 else m


def paint(m, cols):
    """Color parts of a multi-part MathTex: cols = {part index: color}."""
    for i, c in cols.items():
        m[i].set_color(c)
    return m


def tint(m, spans):
    """Color glyph ranges of a single-string MathTex: spans = [((a, b), color), ...] over m[0]'s glyphs."""
    for (a, b), c in spans:
        m[0][a:b].set_color(c)
    return m


def morph(old, new, pairs):
    """Animations taking MathTex old -> new: old[i] glides into new[j] for (i, j) in pairs, the rest fade.
    Use it instead of TransformMatchingTex(key_map=...), which crashes in manim 0.21."""
    ii, jj = {i for i, _ in pairs}, {j for _, j in pairs}
    return ([ReplacementTransform(old[i], new[j]) for i, j in pairs]
            + [FadeOut(old[i]) for i in range(len(old)) if i not in ii]
            + [FadeIn(new[j]) for j in range(len(new)) if j not in jj])


def panel(m, color=HAIR, buff=0.35):
    """m on a rounded SURFACE card. panel(...)[1] is m."""
    return VGroup(SurroundingRectangle(m, buff=buff, corner_radius=0.2, color=color, stroke_width=2,
                                       fill_color=SURFACE, fill_opacity=1), m)


def badge(n, color=ACCENT, r=0.22):
    """Numbered circle (step numbers, list markers)."""
    c = Circle(radius=r, stroke_color=color, stroke_width=2.5, fill_color=color, fill_opacity=0.2)
    return VGroup(c, T(str(n), 24, color, weight=BOLD).move_to(c))


def qcard(tag, *lines, color=EMBER, buff=0.28):
    """Question card: a colored TAG over the given mobjects (lines[k] is card[1][k + 1])."""
    return panel(VGroup(T(tag, 24, color, weight=BOLD), *lines).arrange(DOWN, buff=buff), buff=0.4)


def strike(m, color=BAD, width=4):
    """A line through m, left to right (Create it). For an X over m use manim's Cross(m)."""
    return Line(m.get_left() + 0.1 * LEFT, m.get_right() + 0.1 * RIGHT, color=color, stroke_width=width)


def span(a, b, label="", side=DOWN, off=0.5, color=INK2, size=30):
    """Dimension marker: double arrow parallel to a->b, offset to `side`, end ticks, MathTex label."""
    a, b = np.array(a, float), np.array(b, float)
    n = normalize(np.array(side, float))
    a2, b2 = a + n * off, b + n * off
    arr = DoubleArrow(a2, b2, buff=0, color=color, stroke_width=2.5, tip_length=0.15,
                      max_tip_length_to_length_ratio=0.3)
    ticks = VGroup(*[Line(p - n * 0.13, p + n * 0.13) for p in (a2, b2)]).set_stroke(color, 2)
    g = VGroup(arr, ticks)
    if label:
        g.add(M(label, size=size, color=color).next_to((a2 + b2) / 2, n, buff=0.1))
    return g


def choices(items, size=32, buff=0.22):
    """Multiple-choice rows: lettered ring + MathTex (wrap words in \\text{}). row[0] = ring+letter, row[1] = math."""
    rows = VGroup()
    for i, s in enumerate(items):
        ring = Circle(radius=0.22, stroke_color=INK2, stroke_width=2.5)
        letter = T("ABCDEFGH"[i], 22, INK2, weight=BOLD).move_to(ring)
        rows.add(VGroup(VGroup(ring, letter), M(s, size=size)).arrange(RIGHT, buff=0.3))
    return rows.arrange(DOWN, buff=buff, aligned_edge=LEFT)


def mark(row, good=True):
    """Animations marking a choices() row right (GOOD) or wrong (BAD)."""
    col = GOOD if good else BAD
    ring, letter = row[0]
    return [ring.animate.set_fill(col, 1).set_stroke(col), letter.animate.set_color(BG), row[1].animate.set_color(col)]


def marked(row, good=True):
    """A choices() row already in mark()'s end state (a scene that opens with the answer filled in)."""
    col = GOOD if good else BAD
    row[0][0].set_fill(col, 1).set_stroke(col)
    row[0][1].set_color(BG)
    row[1].set_color(col)
    return row


def answer_box(m, color=GOLD, buff=0.15):
    """The boxed final answer of a worked problem (Create it)."""
    return SurroundingRectangle(m, color=color, buff=buff, corner_radius=0.08, stroke_width=3)


def check(value, expected, rtol=2e-3):
    """Assert a number before it goes on screen or into narration; returns value. Relative only: numpy's default
    absolute floor (1e-8) would wave through any tiny SI value (coulombs, farads)."""
    assert np.isclose(value, expected, rtol=rtol, atol=1e-12 if expected == 0 else 0), f"{value} != {expected}"
    return value


def sci(x, digits=2):
    """Scientific notation as TeX: sci(2.18e6) -> '2.18 \\times 10^{6}'; plain decimals if 0.01 <= |x| < 1000."""
    if x == 0:
        return "0"
    e = int(np.floor(np.log10(abs(x))))
    if -2 <= e < 3:
        return f"{x:.{max(digits - e, 0)}f}" if e < digits else f"{x:.0f}"
    m = x / 10 ** e
    if round(abs(m), digits) >= 10:
        m, e = m / 10, e + 1
    return rf"{m:.{digits}f} \times 10^{{{e}}}"


def rubric(pts, items, traps, size=28):
    """Grading points (MINT checklist) over the common trap (ROSE): items/traps are TX sentences ($math$ inline).
    .rows (the checklist lines), .top, .trap. Already place()d."""
    rows = VGroup(*[VGroup(M(r"\checkmark", size=30, color=MINT), TX(x, size)).arrange(RIGHT, buff=0.22)
                    for x in items]).arrange(DOWN, aligned_edge=LEFT, buff=0.17)
    top = panel(VGroup(T(f"GRADING POINTS  ·  {pts} PTS", 22, MINT, weight=BOLD), rows)
                .arrange(DOWN, aligned_edge=LEFT, buff=0.28), MINT, 0.3)
    tr = panel(VGroup(T("COMMON TRAP", 22, ROSE, weight=BOLD), *[TX(x, size) for x in traps])
               .arrange(DOWN, aligned_edge=LEFT, buff=0.14), ROSE, 0.3)
    g = place(VGroup(top, tr).arrange(DOWN, buff=0.3, aligned_edge=LEFT), "full")
    g.rows, g.top, g.trap = rows, top, tr
    return g


def sheet(head, rows, col=3.2, row_buff=0.28):
    """Worked write-up on a panel: head mobject, then rows (label, color, [body mobjects]) with bodies in one
    column. .rows[k] = VGroup(chip, body); .head. Already place()d full-frame."""
    rs = VGroup()
    for label, color, lines in rows:
        lab = chip(label, color).scale(1.12)
        body = VGroup(*lines).arrange(DOWN, aligned_edge=LEFT, buff=0.13)
        body.align_to(lab, UP).shift(RIGHT * (lab.get_left()[0] + col - body.get_left()[0]))
        rs.add(VGroup(lab, body))
    rs.arrange(DOWN, aligned_edge=LEFT, buff=row_buff)
    p = panel(VGroup(head, rs).arrange(DOWN, aligned_edge=LEFT, buff=0.32), buff=0.3)
    place(p, "full")
    p.rows, p.head = rs, head
    return p


# ---------- data structures ----------
class ArrayRow(VGroup):
    """Cells left to right. values: list of numbers/strings. index_from: label under cell i is i + index_from
    (None hides indices). Positions are 0-based in every method."""

    def __init__(self, values, cell=0.8, size=30, index_from=1, color=INK2, fill=SURFACE, idx_size=20):
        super().__init__()
        self.cell_size, self.size = cell, size
        self.boxes = VGroup(*[Square(cell, stroke_color=color, stroke_width=2, fill_color=fill, fill_opacity=1)
                              for _ in values]).arrange(RIGHT, buff=0)
        self.vals = VGroup(*[self._num(v).move_to(b) for v, b in zip(values, self.boxes)])
        self.add(self.boxes, self.vals)
        self.idx = VGroup()
        if index_from is not None:
            self.idx = VGroup(*[T(str(i + index_from), idx_size, MUTED).next_to(b, DOWN, buff=0.1)
                                for i, b in enumerate(self.boxes)])
            self.add(self.idx)
        self.values = list(values)

    def _num(self, v, color=INK):
        return T(str(v), self.size, color)

    def cell(self, i):
        return self.boxes[i]

    def val(self, i):
        return self.vals[i]

    def mark(self, i, color, opacity=0.35):
        """Animation: tint cell i."""
        return self.boxes[i].animate.set_fill(color, opacity=opacity).set_stroke(color)

    def unmark(self, i):
        return self.boxes[i].animate.set_fill(SURFACE, opacity=1).set_stroke(INK2)

    def set(self, i, v, color=INK):
        """Animation: replace the value shown in cell i."""
        new = self._num(v, color).move_to(self.boxes[i])
        self.values[i] = v
        return Transform(self.vals[i], new)  # the old mobject stays in the row, so nothing is left loose on screen

    def swap(self, i, j, arc=PI / 2):
        """Animation: values i and j trade places along arcs (cells stay put)."""
        a, b = self.vals[i], self.vals[j]
        pa, pb = self.boxes[i].get_center(), self.boxes[j].get_center()
        self.vals.submobjects[i], self.vals.submobjects[j] = b, a
        self.values[i], self.values[j] = self.values[j], self.values[i]
        return AnimationGroup(a.animate(path_arc=arc).move_to(pb), b.animate(path_arc=arc).move_to(pa))

    def pointer(self, i, label="", color=EMBER, up=False):
        """A small arrow (with optional label) under (or over) cell i; move it with .animate.next_to(...)."""
        d = UP if up else DOWN
        arr = Arrow(ORIGIN, -d * 0.6, buff=0, color=color, stroke_width=5, max_tip_length_to_length_ratio=0.35)
        g = VGroup(arr)
        if label:
            g.add(T(label, 24, color).next_to(arr, d, buff=0.08))
        g.next_to(self.boxes[i], d, buff=0.35 if self.idx and not up else 0.12)
        return g


class CodeBlock(VGroup):
    """Pseudocode lines (indent with leading spaces), fixed line pitch. .focus(i) slides a highlight bar to line i."""

    def __init__(self, lines, size=24, color=INK, width=None, line_gap=0.42):
        super().__init__()
        rows = VGroup()
        cw = C("MMMMMMMMMM", size).width / 10  # monospace advance per character
        for k, s in enumerate(lines):
            t = C(s.strip() or ".", size, color)
            if not s.strip():
                t.set_opacity(0)
            indent = (len(s) - len(s.lstrip(" "))) * cw
            t.move_to(DOWN * k * line_gap + RIGHT * indent, aligned_edge=LEFT)
            rows.add(t)
        self.rows = rows
        w = width or rows.width + 0.6
        self.panel = RoundedRectangle(corner_radius=0.15, width=w, height=rows.height + 0.5, stroke_color=HAIR,
                                      stroke_width=2, fill_color=SURFACE, fill_opacity=1).move_to(rows)
        self.panel.align_to(rows, LEFT).shift(0.3 * LEFT)
        self.bar = Rectangle(width=w - 0.1, height=line_gap * 0.95, stroke_width=0, fill_color=EMBER,
                             fill_opacity=0.0)
        self.add(self.panel, self.bar, rows)
        self.bar.move_to(rows[0]).align_to(self.panel, LEFT).shift(0.05 * RIGHT)

    def focus(self, i, color=EMBER):
        return self.bar.animate.set_fill(color, opacity=0.22).move_to(
            [self.bar.get_center()[0], self.rows[i].get_center()[1], 0])

    def unfocus(self):
        return self.bar.animate.set_fill(opacity=0)


def rec_tree(a, depth, label=lambda k: f"n/2^{k}", width=12.0, level_gap=1.3, r=0.36, size=26, color=LILAC,
             show=None):
    """Recursion tree, branching a, `depth` levels below the root (keep a**depth <= ~27). label(k): MathTex in
    every node at depth k. show(k): nodes drawn at depth k (default all). .levels[k] (VGroup), .edges."""
    levels, edges = [], VGroup()
    for k in range(depth + 1):
        cnt = a ** k if show is None else show(k)
        xs = np.linspace(-width / 2, width / 2, cnt + 2)[1:-1] if cnt > 1 else [0.0]
        row = VGroup()
        for x in xs:
            c = Circle(r, color=color, stroke_width=2.5, fill_color=SURFACE, fill_opacity=1)
            lab = M(label(k), size=size)
            if lab.width > 2 * r * 0.85:
                lab.scale_to_fit_width(2 * r * 0.85)
            row.add(VGroup(c, lab.move_to(c)).move_to([x, -k * level_gap, 0]))
        levels.append(row)
    for k in range(1, depth + 1):
        parents, kids = levels[k - 1], levels[k]
        per = max(1, len(kids) // max(1, len(parents)))
        for j, kid in enumerate(kids):
            p = parents[min(j // per, len(parents) - 1)]
            edges.add(Line(p.get_bottom(), kid.get_top(), color=AXIS, stroke_width=2))
    g = VGroup(edges, *levels)
    g.levels, g.edges = levels, edges
    return g.move_to(ORIGIN)


class GraphMob(VGroup):
    """pos: {name: (x, y)}; edges: [(u, v)] or [(u, v, w)] (w = weight label). directed: arrows.
    Edges are (re)built from the nodes' CURRENT centers, so move the graph freely before kind()/path().
    bend: {(u, v): angle} curves an edge (use for 2-cycles u->v, v->u)."""

    def __init__(self, pos, edges, directed=True, r=0.34, size=28, bend=None, weight_size=26, scale=1.0):
        super().__init__()
        self.directed, self.r, self.bend = directed, r * scale, dict(bend or {})
        self.nodes = {}
        for name, (x, y) in pos.items():
            c = Circle(self.r, color=INK2, stroke_width=2.5, fill_color=SURFACE, fill_opacity=1)
            lab = T(str(name), size, INK)
            self.nodes[name] = VGroup(c, lab.move_to(c)).move_to([x * scale, y * scale, 0])
        self.weights, self.edge_list, self.edges = {}, [], {}
        for e in edges:
            u, v = e[0], e[1]
            self.edge_list.append((u, v))
            self.edges[(u, v)] = self._edge(u, v, AXIS, False)
            if len(e) > 2:
                self.weights[(u, v)] = self._wlabel(u, v, e[2], weight_size)
        self.edge_group = VGroup(*self.edges.values())
        self.weight_group = VGroup(*self.weights.values())
        self.node_group = VGroup(*self.nodes.values())
        self.tags = {}
        self.add(self.edge_group, self.weight_group, self.node_group)

    def v(self, name):
        return self.nodes[name]

    def e(self, u, v):
        return self.edges[(u, v)] if (u, v) in self.edges else self.edges[(v, u)]

    def _ends(self, u, v):
        a, b = self.nodes[u].get_center(), self.nodes[v].get_center()
        d = (b - a) / np.linalg.norm(b - a)
        return a + d * self.r, b - d * self.r

    def _edge(self, u, v, color, dashed, width=3):
        a, b = self._ends(u, v)
        ang = self.bend.get((u, v), 0)
        n = max(6, int(np.linalg.norm(b - a) / 0.18))
        if self.directed:
            m = Arrow(a, b, buff=0, color=color, stroke_width=width, path_arc=ang, tip_length=0.2,
                      max_stroke_width_to_length_ratio=20, max_tip_length_to_length_ratio=0.3)
            if dashed:
                tip = m.pop_tips()
                m = VGroup(DashedVMobject(m, num_dashes=n, dashed_ratio=0.55), tip)
            return m
        m = ArcBetweenPoints(a, b, angle=ang, color=color, stroke_width=width) if ang else \
            Line(a, b, color=color, stroke_width=width)
        return DashedVMobject(m, num_dashes=n, dashed_ratio=0.55) if dashed else m

    def _wlabel(self, u, v, w, size):
        a, b = self._ends(u, v)
        mid, d = (a + b) / 2, (b - a) / np.linalg.norm(b - a)
        nrm = np.array([-d[1], d[0], 0])
        ang = self.bend.get((u, v), 0)
        off = 0.28 + (abs(ang) * np.linalg.norm(b - a) / 4 if ang else 0)
        lab = T(str(w), size, GOLD if not str(w).startswith("-") else ROSE)
        return backed(lab.move_to(mid + nrm * off * (1 if ang >= 0 else -1)))

    def fill(self, name, color, opacity=0.85, text=None):
        """Animation: fill vertex `name`; text recolors its label (BG reads well on bright fills)."""
        c, lab = self.nodes[name]
        return AnimationGroup(c.animate.set_fill(color, opacity=opacity).set_stroke(color),
                              lab.animate.set_color(text if text is not None else lab.get_color()))

    def unfill(self, name):
        c, lab = self.nodes[name]
        return AnimationGroup(c.animate.set_fill(SURFACE, opacity=1).set_stroke(INK2), lab.animate.set_color(INK))

    def kind(self, u, v, k, width=4):
        """Animation: restyle edge (u, v) as 'tree' | 'back' | 'forward' | 'cross' | a color."""
        color, dashed = EDGE_KIND.get(k, (k, False))
        key = (u, v) if (u, v) in self.edges else (v, u)
        old = self.edges[key]
        new = self._edge(*key, color, dashed, width)
        self.edges[key] = new
        self.edge_group.submobjects[self.edge_group.submobjects.index(old)] = new
        return ReplacementTransform(old, new)

    def path(self, names, color=EMBER, width=6):
        """Mobject: a bright overlay along consecutive vertices (Create it to trace a route)."""
        return VGroup(*[self._edge(a, b, color, False, width) for a, b in zip(names, names[1:])])

    def tag(self, name, text, color=INK2, size=22, direction=UP):
        """Mobject: small label by a vertex (pre/post times, dist values). Keeps one per vertex in .tags."""
        t = backed(T(text, size, color)).next_to(self.nodes[name], direction, buff=0.08)
        self.tags[name] = t
        return t


def demo():
    t = rec_tree(3, 2, label=lambda k: "n")
    assert len(t.levels[2]) == 9 and len(t.edges) == 12
    a = ArrayRow([5, 3, 8])
    a.swap(0, 2)
    assert a.values == [8, 3, 5]
    g = GraphMob({"A": (0, 0), "B": (2, 0), "C": (1, 1.5)}, [("A", "B", 4), ("B", "C"), ("C", "A")])
    assert len(g.edges) == 3 and ("A", "B") in g.weights
    g.kind("A", "B", "back")
    colors(p=SKY)
    e = E(r"p|=|s|+|r", cmap={"r": MINT})
    assert e[0].get_color().to_hex().lower() == SKY and e[4].get_color().to_hex().lower() == MINT
    assert len(morph(e, E(r"p|=|r"), [(0, 0), (1, 1), (4, 2)])) == 5
    m = fit(Square(4), w=2)
    assert abs(m.width - 2) < 1e-9
    assert sci(2.18e6) == r"2.18 \times 10^{6}" and sci(9.996e-5) == r"1.00 \times 10^{-4}" and sci(0.5) == "0.500"
    assert check(1.6e-19, 1.602e-19) and not _raises(lambda: check(1.6e-19, 1.5e-19))
    r = choices([r"1", r"2"])
    assert marked(r[0])[1].get_color().to_hex().lower() == GOOD
    assert len(rubric(4, ["base case"], ["off by one"]).rows) == 1
    print("kit ok")


def _raises(fn):
    try:
        fn()
        return True
    except AssertionError:
        return False


if __name__ == "__main__":
    demo()
