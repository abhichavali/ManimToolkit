"""mtk command line. Run from the video's project folder.

  mtk check  [files] [-s SCENE..] [-j N]   dry run (no video): LINT/REPORT lines + one storyboard per scene
                                           (a still at the end of every beat, captioned with its narration)
  mtk render [files] [-q l|m|h|k] [-o NAME] [-j N]   render (default h = 1080p30) and join into out/NAME.mp4
  mtk frames VIDEO SEC [SEC..]             one captioned sheet of full-quality frames, for spot checks
  mtk recipe [NAME]                        list the recipe gallery, or print one recipe's source

files default to every *.py here that defines S## scene classes. -s S03,S04 picks scenes by name prefix (any class, e.g. recipes).
All manim runs share global render slots (SLOTS env, default ~ RAM/1.3 GB, capped at the core count),
so parallel agents on one machine queue instead of swapping.
"""
import argparse
import concurrent.futures as cf
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MANIM = str(Path(sys.executable).parent / "manim")
SCENE = re.compile(r"^class (S\d\w*)\(", re.M)
ANY = re.compile(r"^class (\w+)\(", re.M)
QUAL = {"l": (["-ql"], "480p15"), "m": (["-qm"], "720p30"), "h": (["-qh", "--frame_rate", "30"], "1080p30"),
        "k": (["-qk"], "2160p60")}
TILE, COLS, PER_SHEET = (400, 225), 3, 15


def slots():
    if os.environ.get("SLOTS"):
        return int(os.environ["SLOTS"])
    ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30
    return max(1, min(os.cpu_count() or 1, int(ram * 0.75)))


def grab_slot():
    """Block until one of the machine-wide render slots is free; returns the fd holding it."""
    d = Path.home() / ".cache/mtk/slots"
    d.mkdir(parents=True, exist_ok=True)
    n = slots()
    while True:
        for i in range(n):
            fd = os.open(d / f"{i}.lock", os.O_CREAT | os.O_RDWR)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                os.close(fd)
        time.sleep(0.5)


def find(files, picks):
    picks = [x for p in picks or [] for x in p.split(",") if x]
    if not files:
        files = sorted(str(p) for p in Path(".").glob("*.py") if SCENE.search(p.read_text(errors="ignore")))
    out = []
    for f in files:
        src = Path(f).read_text()
        names = ANY.findall(src) if picks else SCENE.findall(src)
        out += [(f, n) for n in sorted(names) if not picks or any(n.startswith(p) for p in picks)]
    if not out:
        sys.exit(f"no scenes found in {files or 'this folder'}" + (f" matching {picks}" if picks else ""))
    return out


def manim(f, s, flags, env=None):
    """Run one scene (one retry: parallel renders can race on the shared LaTeX cache). Returns (ok, log lines).
    A failed scene's log is kept at media/logs/<file>.<scene>.log."""
    tmp = Path("media/logs") / f"{Path(f).stem}.{s}.{os.getpid()}.log"  # concurrent checks don't share logs
    tmp.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        fd = grab_slot()
        try:
            with open(tmp, "w") as out:
                ok = subprocess.run([MANIM, *flags, f, s], stdout=out, stderr=subprocess.STDOUT,
                                    env={**os.environ, "PYTHONWARNINGS": "ignore", "COLUMNS": "200", **(env or {})}
                                    ).returncode == 0
        finally:
            os.close(fd)
        if ok:
            break
    ls = [ln.strip() for ln in re.split(r"[\r\n]", tmp.read_text(errors="ignore"))]
    if ok:
        tmp.unlink()
    else:
        tmp.rename(tmp.with_name(f"{Path(f).stem}.{s}.log"))
    return ok, ls


def marks(ls):
    """REPORT/LINT lines a scene printed."""
    return [m.group(0) for ln in ls for m in [re.search(r"(REPORT|LINT) .*", ln)] if m]


def failure(f, s, ls):
    """Where it broke (frames in the user's files) and the exception line, from manim's rich traceback."""
    here = {p.name for p in Path(".").glob("*.py")} | {Path(f).name}
    where = []
    for ln in ls:
        m = re.search(r"([\w./-]+\.py):(\d+) in (\w+)", ln)
        if m and Path(m.group(1)).name in here:
            where.append(f"{Path(m.group(1)).name}:{m.group(2)} in {m.group(3)}")
    exc = [ln.strip("│ ") for ln in ls if re.match(r"^[│ ]*\w*(Error|Exception|Exit)\b", ln)]
    print(f"FAILED {Path(f).stem} {s}  (media/logs/{Path(f).stem}.{s}.log)")
    for ln in where[-3:] + (exc[-1:] or [x for x in ls if x][-1:]):
        print("   ", ln)


def prefetch(pairs):
    """Synthesize every literal narration line of the files in parallel before any scene runs. Scenes fetch
    their lines one by one as they play, so a first check of a new file otherwise waits minutes on TTS."""
    import ast
    import warnings
    warnings.filterwarnings("ignore", category=SyntaxWarning)  # pydub's, on import
    import mtk.core as core
    for f in dict.fromkeys(f for f, _ in pairs):
        tree = ast.parse(Path(f).read_text())
        voice = style = None
        for node in tree.body:  # module-level `core.VOICE = "..."` / `core.STYLE = "..."` overrides
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for t in node.targets:
                    if isinstance(t, ast.Attribute) and t.attr in ("VOICE", "STYLE"):
                        voice, style = (node.value.value, style) if t.attr == "VOICE" else (voice, node.value.value)
        lines = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("say", "beat", "predict"):
                k = 1 if n.func.attr == "predict" else 0
                kw = {x.arg: x.value for x in n.keywords}
                arg = n.args[k] if len(n.args) > k else kw.get("narration" if k else "text")
                st = kw.get("style")
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    lines.append((arg.value, st.value if isinstance(st, ast.Constant) else style))
        core.config.input_file = str(Path(f).resolve())  # tts() caches next to the scene file
        with cf.ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda ls: _quiet(core.tts, ls[0], voice, ls[1]), lines))


def _quiet(fn, *a):
    try:
        return fn(*a)
    except Exception:  # the scene run retries and reports it properly
        return None


def board(snapdir, out):
    """Tile a scene's beat stills into captioned storyboard sheet(s). Returns (paths, changed?)."""
    from PIL import Image, ImageDraw, ImageFont
    beats = json.loads((snapdir / "beats.json").read_text()) if (snapdir / "beats.json").exists() else []
    pngs = sorted(snapdir.glob("[0-9][0-9].png"))
    if not pngs:
        return [], False
    digest = hashlib.sha1(b"".join(p.read_bytes() for p in pngs) + json.dumps(beats).encode()).hexdigest()
    sha = out.with_suffix(".sha")
    changed = not sha.exists() or sha.read_text() != digest
    font = ImageFont.load_default(size=15)
    w, h = TILE
    cap = 24
    paths = []
    for k in range(0, len(pngs), PER_SHEET):
        chunk = pngs[k:k + PER_SHEET]
        rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * w + (COLS - 1) * 4, rows * (h + cap + 4)), "#05060a")
        d = ImageDraw.Draw(sheet)
        for i, p in enumerate(chunk):
            x, y = (i % COLS) * (w + 4), (i // COLS) * (h + cap + 4)
            sheet.paste(Image.open(p).convert("RGB").resize(TILE), (x, y))
            b = beats[k + i] if k + i < len(beats) else {"t": 0, "text": ""}
            txt = f"{k + i + 1}  {b['t']:.1f}s  {b['text'] or '(wipe)'}"
            while d.textlength(txt, font=font) > w - 8 and len(txt) > 4:
                txt = txt[:-2].rstrip() + "…"
            d.text((x + 4, y + h + 4), txt, fill="#c8ccd6", font=font)
        path = out if k == 0 else out.with_name(f"{out.stem}.{k // PER_SHEET + 1}.png")
        sheet.save(path)
        paths.append(path)
    sha.write_text(digest)
    return paths, changed


def check(a):
    pairs = find(a.files, a.scene)
    prefetch(pairs)
    Path("media/board").mkdir(parents=True, exist_ok=True)

    def one(fs):
        f, s = fs
        snaps = Path("media/snaps") / f"{Path(f).stem}.{s}.{os.getpid()}"
        ok, ls = manim(f, s, ["-ql", "--dry_run", "--disable_caching", "--frame_rate", "10"],
                       {"MTK_SNAP": str(snaps.resolve())})
        res = board(snaps, Path("media/board") / f"{Path(f).stem}.{s}.png") if ok else ([], False)
        shutil.rmtree(snaps, ignore_errors=True)
        return ok, ls, res

    with cf.ThreadPoolExecutor(a.jobs or slots()) as ex:
        results = list(ex.map(one, pairs))
    total = words = nlint = 0
    fresh = []
    for (f, s), (ok, ls, (paths, changed)) in zip(pairs, results):
        if not ok:
            failure(f, s, ls)
            continue
        ms = marks(ls)
        rep = next((m for m in ms if m.startswith("REPORT")), "REPORT ? 0s 0w")
        sec = float(re.search(r" ([\d.]+)s", rep).group(1))
        total += sec
        words += int(re.search(r" (\d+)w", rep).group(1))
        lint = [m for m in ms if m.startswith("LINT")]
        nlint += len(lint)
        tag = "NEW " if changed else "same"
        if changed:
            fresh += paths
        info = rep.split(" ", 2)[2]
        print(f"{Path(f).stem} {s}  {info}  [{tag}] {' '.join(str(p) for p in paths) or '(no stills)'}")
        for m in lint:
            print("   ", m)
    print(f"TOTAL {int(total // 60)}:{int(total % 60):02d}  {words} words  {nlint} lint  "
          f"{len(fresh)} new/changed storyboard(s) to look at; unchanged ones are marked [same]")


def render(a):
    pairs = find(a.files, a.scene)
    prefetch(pairs)
    flags, res = QUAL[a.q]
    with cf.ThreadPoolExecutor(a.jobs or slots()) as ex:
        results = list(ex.map(lambda fs: manim(*fs, flags), pairs))
    bad = False
    for (f, s), (ok, ls) in zip(pairs, results):
        if not ok:
            bad = True
            failure(f, s, ls)
        else:
            for m in marks(ls):
                if m.startswith("LINT"):
                    print("   ", m)
    if bad:
        sys.exit(1)
    vids = [Path("media/videos") / Path(f).stem / res / f"{s}.mp4" for f, s in pairs]
    name = a.o or (Path(pairs[0][0]).stem if len({f for f, _ in pairs}) == 1 else Path.cwd().name)
    Path("out").mkdir(exist_ok=True)
    out = Path("out") / f"{name}.mp4"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as lst:
        lst.writelines(f"file '{v.resolve()}'\n" for v in vids)
    # each scene's audio ends before its video does, so a plain concat leaves timestamp gaps that drift in
    # editors and some players; aresample fills them with silence and apad pads the tail to the video's end
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst.name,
                    "-c:v", "copy", "-af", "aresample=async=1:first_pts=0,apad", "-shortest", "-c:a", "aac",
                    "-b:a", "192k", str(out)], check=True)
    os.unlink(lst.name)
    print(f"{out.resolve()}  {dur(out):.1f}s\nchapters:")
    t = 0.0
    for (f, s), v in zip(pairs, vids):
        print(f"  {int(t // 60)}:{int(t % 60):02d}  {Path(f).stem} {s}")
        t += dur(v)
    sil = subprocess.run(["ffmpeg", "-nostdin", "-i", str(out), "-vn", "-af", "silencedetect=noise=-45dB:d=3", "-f",
                          "null", "-"], capture_output=True, text=True).stderr
    for m in re.finditer(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", sil):
        print(f"  silence {float(m.group(2)):.1f}s ending at {float(m.group(1)):.1f}s")


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(p)], capture_output=True, text=True).stdout)


def frames(a):
    from PIL import Image, ImageDraw, ImageFont
    w = 960
    font = ImageFont.load_default(size=20)
    tiles = []
    with tempfile.TemporaryDirectory() as tmp:
        for t in a.sec:
            p = Path(tmp) / f"{t}.png"
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", str(t), "-i", a.video,
                            "-frames:v", "1", "-vf", f"scale={w}:-2", str(p)], check=True)
            tiles.append((t, Image.open(p).convert("RGB")))
    h = tiles[0][1].height
    cols = 1 if len(tiles) == 1 else 2
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols - 1) * 6, rows * (h + 30 + 6)), "#05060a")
    d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(tiles):
        x, y = (i % cols) * (w + 6), (i // cols) * (h + 36)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + h + 5), f"{int(float(t) // 60)}:{float(t) % 60:04.1f}", fill="#c8ccd6", font=font)
    out = Path("media/frames") / f"{Path(a.video).stem}.{'_'.join(a.sec)}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(out)


def recipe(a):
    path = Path(importlib.util.find_spec("mtk").origin).parent / "recipes.py"  # find_spec doesn't import manim
    src = path.read_text()
    blocks = re.split(r"(?m)^(?=class )", src)[1:]
    if not a.name:
        print(path)
        for b in blocks:
            name = ANY.match(b).group(1)
            doc = re.search(r'"""(.*?)(?:\n|""")', b)
            print(f"  {name:22s} {doc.group(1).strip() if doc else ''}")
        return
    hit = [b for b in blocks if ANY.match(b).group(1).startswith(a.name)]
    print("\n".join(hit).rstrip() if hit else f"no recipe {a.name}; run `mtk recipe` for the list")


def main():
    p = argparse.ArgumentParser(prog="mtk", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", check), ("render", render)):
        c = sub.add_parser(name)
        c.add_argument("files", nargs="*")
        c.add_argument("-s", "--scene", action="append", help="scene name prefix(es), comma-separated or repeated")
        c.add_argument("-j", "--jobs", type=int)
        if name == "render":
            c.add_argument("-q", default="h", choices=QUAL)
            c.add_argument("-o", help="output name (default: the file, or this folder for several)")
        c.set_defaults(fn=fn)
    c = sub.add_parser("frames")
    c.add_argument("video")
    c.add_argument("sec", nargs="+")
    c.set_defaults(fn=frames)
    c = sub.add_parser("recipe")
    c.add_argument("name", nargs="?")
    c.set_defaults(fn=recipe)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
