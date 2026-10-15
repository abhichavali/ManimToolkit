"""PDE kit on top of mtk.core: exact solutions, stable solvers, space-time diagrams, and residual checks.
`from mtk.pde import *` gives everything in mtk too. `python -m mtk.pde` self-checks every formula here.

Conventions: functions of (x, t) are vectorized numpy; x is horizontal, t increases upward in x-t diagrams.
Color = equation family, kept for the whole video.
"""
from .core import *

TRANSPORT, HEAT, WAVE, BURGERS, REACTION, ELLIPTIC = SKY, EMBER, MINT, LILAC, LIME, ROSE


# ---------- checks: assert every formula you plot satisfies its PDE ----------

def derivs(u, x, t, h=1e-4):
    """Centered differences of u(x, t) at arrays x, t -> dict u, ut, ux, uxx, utt (truncation ~ h^2, roundoff ~ 1e-16/h^2)."""
    u0 = u(x, t)
    return {"u": u0, "ut": (u(x, t + h) - u(x, t - h)) / (2 * h), "ux": (u(x + h, t) - u(x - h, t)) / (2 * h),
            "uxx": (u(x + h, t) - 2 * u0 + u(x - h, t)) / h ** 2, "utt": (u(x, t + h) - 2 * u0 + u(x, t - h)) / h ** 2}


def sample(xr, tr, n=300, seed=0):
    """n random points (x, t) inside the box xr x tr, for derivs()."""
    r = np.random.default_rng(seed)
    return r.uniform(*xr, n), r.uniform(*tr, n)


# ---------- exact solutions ----------

def gauss_heat(A, alpha, x0, nu):
    """u_t = nu u_xx with u(x, 0) = A exp(-alpha (x - x0)^2): stays Gaussian, widens, height drops as 1/sqrt(1 + 4 alpha nu t)."""
    return lambda x, t: A / np.sqrt(1 + 4 * alpha * nu * t) * np.exp(-alpha * (x - x0) ** 2 / (1 + 4 * alpha * nu * t))


def heat_modes(b, nu=1.0, L=np.pi):
    """u_t = nu u_xx on [0, L], u = 0 at both ends: sum of b[n-1] e^{-nu (n pi / L)^2 t} sin(n pi x / L)."""
    def u(x, t):
        x, t = np.asarray(x, float), np.asarray(t, float)
        return sum(bn * np.exp(-nu * (n * np.pi / L) ** 2 * t) * np.sin(n * np.pi * x / L)
                   for n, bn in enumerate(b, 1) if bn)
    return u


def sine_coeffs(f, N, L=np.pi, m=4000):
    """b_n = (2/L) * integral_0^L f(x) sin(n pi x / L) dx for n = 1..N (midpoint rule, m cells)."""
    x = (np.arange(m) + 0.5) * L / m
    return [2 / m * np.sum(f(x) * np.sin(n * np.pi * x / L)) for n in range(1, N + 1)]


def odd_periodic(f, L):
    """Odd, 2L-periodic extension of f from [0, L]: the trick that makes d'Alembert respect fixed ends."""
    def g(x):
        y = np.mod(x, 2 * L)
        return np.where(y <= L, f(np.minimum(y, L)), -f(np.clip(2 * L - y, 0, L)))
    return g


def dalembert(f, c=1.0):
    """u_tt = c^2 u_xx released from rest with u(x, 0) = f: half travels left, half travels right."""
    return lambda x, t: 0.5 * (f(x - c * t) + f(x + c * t))


def burgers_curve(u0, t, xi):
    """Inviscid Burgers u_t + u u_x = 0 by characteristics: points (xi + u0(xi) t, u0(xi)).
    Plot them as a parametric curve: after breaking it folds over (multivalued), which is the cue for a shock."""
    return xi + u0(xi) * t, u0(xi)


def t_break(u0, xr, n=20001):
    """First crossing of Burgers characteristics: -1 / min u0'(xi) (inf if u0 never decreases)."""
    xi = np.linspace(*xr, n)
    m = np.min(np.gradient(u0(xi), xi))
    return -1 / m if m < 0 else np.inf


def laplace_hot_lid(x, y, terms=80):
    """Laplace on the square [0, pi]^2 with u = 1 on the top edge, 0 on the other three (separation of variables)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    return sum(4 / (n * np.pi) * np.sinh(n * y) / np.sinh(n * np.pi) * np.sin(n * x) for n in range(1, 2 * terms, 2))


# ---------- numerical solvers (label them "computed numerically" on screen) ----------

def rd_solve(u0, xr, D, T, every, f=None, bc="neumann", dx=0.05):
    """u_t = D u_xx + f(u) on xr by explicit Euler; returns (x, ts, U) with a snapshot U[k] at ts[k] = k * every.
    bc: 'neumann' (no flux), 'dirichlet' (ends held at their initial values) or 'periodic'.
    Stability: explicit diffusion needs dt <= dx^2 / (2D); we use dt = 0.4 dx^2 / D or less."""
    x = np.arange(xr[0], xr[1] + dx / 2, dx)
    u = np.asarray(u0(x), float).copy()
    nsub = int(np.ceil(every / (0.4 * dx * dx / D)))
    dt = every / nsub
    snaps = [u.copy()]
    for _ in range(int(round(T / every))):
        for _ in range(nsub):
            lap = np.roll(u, 1) - 2 * u + np.roll(u, -1)
            if bc == "neumann":
                lap[0], lap[-1] = 2 * (u[1] - u[0]), 2 * (u[-2] - u[-1])  # mirror ghost cells
            elif bc == "dirichlet":
                lap[0] = lap[-1] = 0
            u = u + dt * (D * lap / dx ** 2 + (f(u) if f else 0))
        snaps.append(u.copy())
    return x, np.arange(len(snaps)) * every, np.array(snaps)


def as_field(x, ts, U):
    """Bilinear interpolant f(X, T) of snapshot data, vectorized: feed it to live() and field_image()."""
    def f(X, Tq):
        X, Tq = np.broadcast_arrays(np.asarray(X, float), np.asarray(Tq, float))
        i = np.clip((X - x[0]) / (x[1] - x[0]), 0, len(x) - 1.000001)
        j = np.clip((Tq - ts[0]) / (ts[1] - ts[0]), 0, len(ts) - 1.000001)
        i0, j0 = i.astype(int), j.astype(int)
        a, b = i - i0, j - j0
        return ((1 - b) * ((1 - a) * U[j0, i0] + a * U[j0, i0 + 1]) + b * ((1 - a) * U[j0 + 1, i0] + a * U[j0 + 1, i0 + 1]))
    return f


def front_position(x, u, level=0.5):
    """x where a decreasing front u first drops through `level` (linear interpolation)."""
    i = np.argmax(u < level)
    return x[i - 1] + (u[i - 1] - level) / (u[i - 1] - u[i]) * (x[i] - x[i - 1])


# ---------- space-time diagrams ----------

def xt_diagram(f, xr, tr, width=8, height=3.4, cmap="seq", vmax=1.0, xlabel="x", ylabel="t"):
    """Boxed x-t axes plus a heat map of f(x, t) under them. Returns (ax, img); add img before ax."""
    ax = axes([xr[0], xr[1], 1], [tr[0], tr[1], 1], width, height, xlabel=xlabel, ylabel=ylabel, boxed=True)
    return ax, field_image(f, ax, xr, tr, cmap=cmap, vmax=vmax)


def st_mask(ax, xr, tr, tt):
    """BG-colored cover over the not-yet-reached part (t > tt) of an x-t diagram: the diagram fills in as tt grows."""
    def mk():
        lo, hi = ax.c2p(xr[0], tt.get_value()), ax.c2p(xr[1], tr[1])
        h = max(hi[1] - lo[1], 1e-3)
        return Rectangle(width=hi[0] - lo[0] + 0.04, height=h, stroke_width=0, fill_color=BG,
                         fill_opacity=1).move_to([(lo[0] + hi[0]) / 2, lo[1] + h / 2, 0])
    return always_redraw(mk)


def now_line(ax, xr, tt, color=INK2):
    """Dashed horizontal line at t = tt in an x-t diagram."""
    return always_redraw(lambda: DashedLine(ax.c2p(xr[0], tt.get_value()), ax.c2p(xr[1], tt.get_value()),
                                            color=color, stroke_width=2, dash_length=0.08))


def char_curves(ax, X, xis, xr, tr, color=INK, width=2, n=120):
    """Characteristic curves x = X(xi, t) for each foot xi, drawn in the x-t box and clipped at its sides."""
    ts = np.linspace(*tr, n)
    g = VGroup()
    for xi in xis:
        xs = X(xi, ts)
        keep = (xs >= xr[0]) & (xs <= xr[1])
        a = np.argmax(keep)  # first contiguous run inside the box
        b = a + (np.argmin(keep[a:]) if not keep[a:].all() else keep.size - a)
        if b - a >= 2:
            g.add(VMobject(stroke_color=color, stroke_width=width).set_points_smoothly(
                [ax.c2p(xs[k], ts[k]) for k in range(a, b)]))
    return g


if __name__ == "__main__":  # self-check: python -m mtk.pde
    x, t = sample([0.2, 2.9], [0.05, 1])
    u = heat_modes([1, 0, 0.5, 0, 0.3])
    d = derivs(u, x, t)
    assert np.max(abs(d["ut"] - d["uxx"])) < 1e-4
    g = gauss_heat(0.8, 3, 0.5, 0.4)
    d = derivs(g, x, t)
    assert np.max(abs(d["ut"] - 0.4 * d["uxx"])) < 1e-4
    w = dalembert(lambda s: np.exp(-s * s), c=2)
    d = derivs(w, x, t)
    assert np.max(abs(d["utt"] - 4 * d["uxx"])) < 1e-3
    tri = lambda s: np.minimum(s, np.pi - s)
    b = sine_coeffs(tri, 5)
    assert abs(b[0] - 4 / np.pi) < 1e-5 and abs(b[1]) < 1e-9 and abs(b[2] + 4 / (9 * np.pi)) < 1e-5
    ext = odd_periodic(tri, np.pi)
    assert abs(ext(-1.0) + tri(1.0)) < 1e-12 and abs(ext(2 * np.pi + 1) - tri(1.0)) < 1e-12
    assert abs(t_break(lambda s: np.exp(-s * s), [-4, 4]) - np.sqrt(np.e / 2)) < 1e-4
    xs, ys = sample([0.3, 2.8], [0.3, 2.6])
    h = 1e-3
    lap = (laplace_hot_lid(xs + h, ys) + laplace_hot_lid(xs - h, ys) + laplace_hot_lid(xs, ys + h)
           + laplace_hot_lid(xs, ys - h) - 4 * laplace_hot_lid(xs, ys)) / h ** 2
    assert np.max(abs(lap)) < 1e-3 and abs(laplace_hot_lid(np.pi / 2, np.pi / 2) - 0.25) < 1e-6  # symmetry: 1/4
    xg, ts, U = rd_solve(lambda s: np.exp(-s * s), [-10, 10], 0.5, 1.0, 0.1, dx=0.05)
    ex = gauss_heat(1, 1, 0, 0.5)
    assert np.max(abs(U[-1] - ex(xg, 1.0))) < 2e-3
    F = as_field(xg, ts, U)
    assert abs(F(0.0, 0.55) - ex(0.0, 0.55)) < 5e-3
    print("pde ok")
