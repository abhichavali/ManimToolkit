"""Fast fake 3D: surfaces and point clouds drawn by numpy into one ImageMobject, inside a plain VScene.
Cairo's real 3D (VScene3D) renders ~10x slower than real time; these redraw in milliseconds, so a sphere can spin,
ring or heat up under a ValueTracker. Camera: elev/azim in degrees (azim turns about the vertical z axis).
Ported from the Laplace-Beltrami series (surfaces) and the diffusion-maps video (point clouds).

  SurfaceImage(grid, vals=None, width=4, elev=20, azim=-60, cmap="signed"|"heat"|stops, vmax=1, base=SKY,
               marks=[(mask, "#hex"), ...], lines=(n_u, n_v), extent=None, px=560)
        .redraw(**changes) (in an updater)  .at(xyz) scene point of a 3D point  .facing(xyz)
  sphere_grid(n), torus_grid(R, r, n), param_grid(f, u_range, v_range, nu, nv)  -> Grid: U, V, P (3,nu,nv), N
  Cloud(P (N,3), vals=None, height=5, elev=20, azim=-60, cmap="signed", color=SKY, r_px=3.2, normals=None)
        .draw(**changes)  .screen_xy(idx);  normals=pca_normals(P) dims the far side of a closed cloud
"""
from .core import *

CMAP_SIGNED = [(0, "#2a6fdb"), (0.25, SKY), (0.5, "#4a4f5e"), (0.75, EMBER), (1, GOLD)]  # zero = slate, not BG
CMAP_HEAT = [(0, "#2f3652"), (0.35, "#5b3fa8"), (0.7, EMBER), (1, "#fff1b8")]

# the painter's algorithms below rely on numpy writing repeated fancy indices in order (last one wins)
_t = np.zeros(1, int)
_t[np.zeros(1000, int)] = np.arange(1000)
assert _t[0] == 999


def _cmap(c):
    return {"signed": CMAP_SIGNED, "heat": CMAP_HEAT}[c] if isinstance(c, str) else c


def _rgb(c):
    c = ManimColor(c).to_hex()
    return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], float)


def _cam(elev, azim):
    """(toward viewer, screen right, screen up) unit vectors."""
    e, a = np.radians(elev), np.radians(azim)
    d = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    e1 = np.array([-np.sin(a), np.cos(a), 0.0])
    return d, e1, np.cross(d, e1)


# ---------- surfaces ----------
class Grid:
    """A surface sampled on (u, v): U, V (nu, nv); P (3, nu, nv) points; N (3, nu, nv) unit normals.
    closed=True (spheres, tori) culls back faces; open surfaces are lit on both sides."""

    def __init__(self, U, V, P, N=None, closed=False):
        self.U, self.V, self.P, self.closed = U, V, np.asarray(P, float), closed
        if N is None:
            du, dv = np.gradient(self.P, axis=1), np.gradient(self.P, axis=2)
            N = np.cross(du, dv, axis=0)
            N = N / (np.linalg.norm(N, axis=0) + 1e-12)
        self.N = N


def sphere_grid(n=300):
    U, V = np.meshgrid(np.linspace(0, PI, n), np.linspace(0, TAU, 2 * n), indexing="ij")
    P = np.array([np.sin(U) * np.cos(V), np.sin(U) * np.sin(V), np.cos(U)])
    return Grid(U, V, P, P.copy(), closed=True)


def torus_grid(R=1.0, r=0.42, n=300):
    U, V = np.meshgrid(np.linspace(0, TAU, 2 * n), np.linspace(0, TAU, n), indexing="ij")
    P = np.array([(R + r * np.cos(V)) * np.cos(U), (R + r * np.cos(V)) * np.sin(U), r * np.sin(V)])
    N = np.array([np.cos(V) * np.cos(U), np.cos(V) * np.sin(U), np.sin(V)])
    return Grid(U, V, P, N, closed=True)


def param_grid(f, u_range, v_range, nu=240, nv=240, closed=False):
    """Grid of f(U, V) -> (x, y, z) arrays, e.g. a graph: param_grid(lambda u, v: (u, v, h(u, v)), (-2, 2), (-2, 2))."""
    U, V = np.meshgrid(np.linspace(*u_range, nu), np.linspace(*v_range, nv), indexing="ij")
    return Grid(U, V, np.array(f(U, V), float), closed=closed)


class SurfaceImage(ImageMobject):
    """A shaded surface as one image. vals (array on the grid) colors it through cmap ('signed' maps -vmax..vmax,
    'heat' 0..vmax); vals=None paints `base`. marks override colors on masks (rings, caps, dots); lines draws a
    (n_u, n_v) coordinate grid. Animate with an updater: s.add_updater(lambda m: m.redraw(azim=tt.get_value()))."""

    def __init__(self, grid, vals=None, width=4, **kw):
        P = grid.P.reshape(3, -1)
        self.c = (P.min(1) + P.max(1)) / 2  # the view centers on the surface's bounding box
        self.kw = dict(grid=grid, vals=vals, vmax=1.0, elev=20, azim=-60, marks=(), lines=None, px=560,
                       cmap="signed", base=SKY)
        self.kw["extent"] = kw.pop("extent", None) or 1.05 * np.linalg.norm(P - self.c[:, None], axis=0).max()
        super().__init__(self._raster(**kw))
        self.set_resampling_algorithm(RESAMPLING_ALGORITHMS["linear"])
        self.scale_to_fit_width(width)

    def redraw(self, **kw):
        self.pixel_array = self._raster(**kw)
        return self

    def _raster(self, **kw):
        self.kw.update(kw)
        k = self.kw
        g, px, ext = k["grid"], k["px"], k["extent"]
        d, e1, e2 = _cam(k["elev"], k["azim"])
        P, N = g.P.reshape(3, -1) - self.c[:, None], g.N.reshape(3, -1)
        if k["vals"] is None:
            rgb = np.tile(_rgb(k["base"]), (P.shape[1], 1))
        else:
            v = np.asarray(k["vals"], float).reshape(-1) / k["vmax"]
            cm = _cmap(k["cmap"])
            rgb = ramp(cm, np.clip(v, 0, 1)) if cm is CMAP_HEAT else ramp(cm, np.clip(.5 + .5 * v, 0, 1))
        if k["lines"]:
            a, b = k["lines"]
            U = (g.U - g.U.min()) / (np.ptp(g.U) or 1)
            V = (g.V - g.V.min()) / (np.ptp(g.V) or 1)
            on = (np.abs((U * a + .5) % 1 - .5) < .02 * a / 6) | (np.abs((V * b + .5) % 1 - .5) < .02 * b / 12)
            rgb[on.reshape(-1)] *= 0.35
        for mask, col in k["marks"]:
            rgb[np.asarray(mask).reshape(-1)] = _rgb(col)
        facing = d @ N
        if g.closed:
            keep = facing > -0.05  # back faces never show (holes would leak them); depth order does the rest
        else:
            N = N * np.where(facing < 0, -1, 1)  # open surface: light whichever side faces us
            keep = np.ones(P.shape[1], bool)
        light = 0.5 * d + 0.6 * e2 - 0.35 * e1
        light /= np.linalg.norm(light)
        shade = 0.42 + 0.58 * np.clip(light @ N, 0, 1) + 0.25 * np.clip(d @ N, 0, 1) ** 24
        rgb = np.clip(rgb * shade[:, None], 0, 255)
        P, rgb = P[:, keep], rgb[keep]
        ix = ((e1 @ P / ext + 1) * px / 2).astype(int)
        iy = ((1 - e2 @ P / ext) * px / 2).astype(int)
        o = np.argsort(d @ P)  # far to near: nearest written last wins
        ix, iy, rgb = ix[o], iy[o], rgb[o]
        gap = max(np.median(np.linalg.norm(np.diff(g.P, axis=a), axis=0)) for a in (1, 2)) * px / (2 * ext)
        b = 2 if gap < 1.4 else int(np.ceil(gap)) + 1  # each sample covers a block sized to the grid spacing
        n = len(ix)
        pal = np.zeros((n + 1, 4), np.float32)  # sample colors; the last row is "empty"
        pal[:n, :3], pal[:n, 3] = rgb, 255
        ix, iy = np.clip(ix, 0, px - b), np.clip(iy, 0, px - b)
        offs = (np.arange(b)[:, None] * px + np.arange(b)[None, :]).ravel()
        buf = np.full(px * px, n, np.int32)  # one write for every block: nearer samples come later and win
        buf[((iy * px + ix)[:, None] + offs).ravel()] = np.repeat(np.arange(n, dtype=np.int32), b * b)
        img = pal[buf]
        img = img.reshape(px, px, 4)
        nb = ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1))
        for _ in range(2):  # fill pinholes from their 8 neighbors (silhouettes don't grow: needs >= 5)
            has = img[..., 3] > 0
            cnt = sum(np.roll(has, sh, axis=(0, 1)).astype(np.uint8) for sh in nb)
            ys, xs = np.nonzero(~has & (cnt >= 5))
            if not len(ys):
                break
            acc, n = np.zeros((len(ys), 4), np.float32), np.zeros(len(ys), np.float32)
            for dy, dx in nb:  # work on the holes only, not the whole image
                yy, xx = (ys - dy) % px, (xs - dx) % px
                h = has[yy, xx]
                acc += img[yy, xx] * h[:, None]
                n += h
            img[ys, xs] = acc / n[:, None]
        return img.astype(np.uint8)

    def at(self, xyz):
        """Scene point of the 3D point xyz under the current view."""
        _, e1, e2 = _cam(self.kw["elev"], self.kw["azim"])
        q = np.asarray(xyz, float) - self.c
        s = self.width / (2 * self.kw["extent"])
        return self.get_center() + s * (np.dot(e1, q) * RIGHT + np.dot(e2, q) * UP)

    def facing(self, xyz):
        """Is the point on the side facing the viewer (for labels on a closed surface)?"""
        return np.dot(_cam(self.kw["elev"], self.kw["azim"])[0], np.asarray(xyz, float) - self.c) > 0


# ---------- point clouds ----------
def colors_for(vals, cmap="signed", vrange=None):
    """(N,) values -> (N, 3) rgb 0..255. vrange defaults to symmetric for 'signed', min..max otherwise."""
    v, cm = np.asarray(vals, float), _cmap(cmap)
    if vrange is None:
        m = np.abs(v).max() or 1
        vrange = (-m, m) if cm is CMAP_SIGNED else (v.min(), v.max() if v.max() > v.min() else v.min() + 1)
    return ramp(cm, np.clip((v - vrange[0]) / (vrange[1] - vrange[0]), 0, 1))


def pca_normals(X, k=16):
    """Unit normals from the points alone: smallest principal direction of each point's k nearest neighbors,
    oriented away from the centroid (fine for closed, star-shaped clouds). Only used to shade the far side."""
    from scipy.spatial import cKDTree
    _, nb = cKDTree(X).query(X, k)
    Y = X[nb] - X[nb].mean(1, keepdims=True)
    n = np.linalg.eigh(np.einsum("nki,nkj->nij", Y, Y))[1][:, :, 0]
    return n * np.sign(((X - X.mean(0)) * n).sum(1))[:, None]


def render_cloud(P, rgb, elev=20, azim=-60, res=720, r_px=3.2, radius=None, center=None, depth_shade=0.45,
                 rim=True, alpha=None, aspect=1.0, normals=None, back=0.3):
    """Points as shaded discs, far to near, 2x supersampled -> (res, res*aspect, 4) uint8 RGBA, transparent
    background. radius: world half-extent mapped to the image half-height (fix it so rotation doesn't rescale)."""
    P = np.asarray(P, float)
    n = len(P)
    center = P.mean(0) if center is None else np.asarray(center, float)
    d, e1, e2 = _cam(elev, azim)
    Q = (P - center) @ np.stack([e1, e2, d]).T  # columns: screen x, screen y, depth toward the viewer
    radius = radius or np.linalg.norm(P - center, axis=1).max() * 1.05
    ss = 2
    H, W = res * ss, int(round(res * aspect)) * ss
    px = W / 2 + Q[:, 0] / radius * (H / 2)
    py = H / 2 - Q[:, 1] / radius * (H / 2)
    rgb = np.broadcast_to(np.asarray(rgb, np.float32), (n, 3))
    zn = (Q[:, 2] - Q[:, 2].min()) / (np.ptp(Q[:, 2]) + 1e-12)
    shade = (1 - depth_shade) + depth_shade * zn
    if normals is not None:
        shade = np.where(np.asarray(normals) @ d < 0, back * shade, shade)
    a = np.ones(n) if alpha is None else np.broadcast_to(np.asarray(alpha, float), (n,))
    pal = np.zeros((n + 2, 4), np.float32)  # rows: the points (premultiplied), the dark rim, empty
    pal[:n, 3] = a
    pal[:n, :3] = rgb * shade[:, None] * a[:, None]
    pal[n] = (15, 17, 22, 1)
    rf = r_px * ss
    g = np.arange(-int(rf) - 2, int(rf) + 3)
    DX, DY = np.meshgrid(g, g)
    R2 = DX ** 2 + DY ** 2
    ring = (R2 > rf ** 2) & (R2 <= (rf + 1.6) ** 2) if rim else np.zeros_like(R2, bool)
    disc = R2 <= rf ** 2
    off = np.concatenate([DY[ring] * W + DX[ring], DY[disc] * W + DX[disc]]).astype(np.int32)
    isfill = np.r_[np.zeros(ring.sum(), bool), np.ones(disc.sum(), bool)]
    order = np.argsort(Q[:, 2])
    cx, cy = np.round(px[order]).astype(np.int32), np.round(py[order]).astype(np.int32)
    m = 2 * (int(rf) + 3)
    vis = (cx > m) & (cx < W - m) & (cy > m) & (cy < H - m)  # whole disc inside: no per-pixel bounds checks
    o = order[vis]
    flat = ((cy[vis] * W + cx[vis])[:, None] + off[None, :]).ravel()
    buf = np.full(H * W, n + 1, np.int32)
    buf[flat] = np.where(isfill[None, :], o[:, None].astype(np.int32), np.int32(n)).ravel()
    img = pal[buf].reshape(H, W, 4)
    img = (img[0::2, 0::2] + img[1::2, 0::2] + img[0::2, 1::2] + img[1::2, 1::2]) / 4
    al = img[..., 3:]
    img[..., :3] /= np.maximum(al, 1e-6)
    img[..., 3:] *= 255
    return np.clip(img, 0, 255).astype(np.uint8)


class Cloud(ImageMobject):
    """A 3D point cloud as one image. Spin it: c.add_updater(lambda m: m.draw(azim=tt.get_value())).
    draw() takes vals, rgb, vrange or any render setting (elev, azim, alpha, r_px, back); the rest is kept."""

    def __init__(self, P, vals=None, height=5.0, cmap="signed", vrange=None, color=SKY, elev=20, azim=-60,
                 res=None, r_px=3.2, radius=None, alpha=None, aspect=1.0, normals=None, back=0.3, **kw):
        self.P = np.asarray(P, float)
        res = res or max(120, int(round(config.pixel_height * height / config.frame_height)))  # 1 px per px
        self.c0 = self.P.mean(0)
        self.rad = radius or np.linalg.norm(self.P - self.c0, axis=1).max() * 1.05
        self.st = dict(elev=elev, azim=azim, alpha=alpha, r_px=r_px * res / 720, normals=normals, back=back)
        self.cmap, self.vrange, self.res, self.aspect = cmap, vrange, res, aspect
        self.rgb = colors_for(vals, cmap, vrange) if vals is not None else _rgb(color)
        super().__init__(self._raster(), **kw)
        self.height = height

    def _raster(self):
        return render_cloud(self.P, self.rgb, res=self.res, radius=self.rad, center=self.c0, aspect=self.aspect,
                            **self.st)

    def draw(self, vals=None, rgb=None, vrange=None, **st):
        if "r_px" in st:
            st["r_px"] *= self.res / 720
        if vrange is not None:
            self.vrange = vrange
        if vals is not None:
            self.rgb = colors_for(vals, self.cmap, self.vrange)
        if rgb is not None:
            self.rgb = rgb
        self.st.update(st)
        self.pixel_array = self._raster()
        return self

    def screen_xy(self, idx):
        """Scene coordinates of point(s) idx under the current view (to pin labels or arrows to a point)."""
        _, e1, e2 = _cam(self.st["elev"], self.st["azim"])
        Q = self.P[np.atleast_1d(idx)] - self.c0
        s = self.height / 2 / self.rad
        c = self.get_center()
        return np.c_[c[0] + Q @ e1 * s, c[1] + Q @ e2 * s, np.zeros(len(Q))]


def demo():
    import time
    t = time.time()
    s = SurfaceImage(sphere_grid(200), width=4)
    a = s.pixel_array[..., 3] > 0
    assert abs(a.mean() - np.pi * (1 / 1.05) ** 2 / 4) < 0.05 * np.pi / 4, a.mean()  # disc of radius 1/1.05
    x, y = s.at([0, 0, 1]), s.get_center()
    assert x[1] > y[1] and s.facing([0, 0, 1])  # the north pole is up and visible at elev 20
    h = param_grid(lambda u, v: (u, v, np.exp(-u * u - v * v)), (-2, 2), (-2, 2), 80, 80)
    SurfaceImage(h, vals=h.P[2], cmap="heat")
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2000, 3))
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    c = Cloud(X, vals=X[:, 2], height=4)
    assert c.pixel_array[..., 3].mean() > 10
    c.draw(azim=30)
    print(f"view3d ok ({time.time() - t:.2f}s)")


if __name__ == "__main__":
    demo()
