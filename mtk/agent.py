"""The agent renderer (`mtk render --agent`): same scene code, same Cairo pixels, drawn only where something changed.

One process steps the scene through every frame without drawing and fingerprints what the camera would draw. A worker
forked at the start of each play is the same scene at the same instant: told the fingerprint when the play ends, it
exits if a segment with that fingerprint exists, and otherwise draws and encodes the play with manim's own code.
So plays draw in parallel inside a scene, and an edit redraws only the plays whose pictures it changed.
"""
import hashlib
import os
import sys
import time
import traceback
from enum import Enum

import numpy as np
from manim import ThreeDScene, __version__, config
from manim.renderer.cairo_renderer import CairoRenderer
from manim.utils.iterables import list_update

from mtk_cli import try_slot

SCALARS = (int, float, str, type(None), np.number, Enum)


def feed(h, mobs):
    """Everything drawing could read: every number and array on each mobject, in draw order. Attributes drawing
    ignores can only cost a cache miss; hashing all of them is what makes a stale segment impossible to miss."""
    for m in mobs:
        h.update(type(m).__name__.encode())
        for k, v in m.__dict__.items():
            if isinstance(v, np.ndarray):
                if v.dtype != object:
                    h.update(f"{k}{v.shape}".encode())
                    h.update(v.tobytes())
            elif isinstance(v, SCALARS) and k != "original_id":  # svgelements' id(): differs on every run
                h.update(f"{k}={v}".encode())


def install(scene):
    r, w, cam = scene.renderer, scene.renderer.file_writer, scene.renderer.camera
    config.max_files_cached = 2000  # manim's default of 100 would evict segments of a long scene
    live, failed = {}, []
    st = dict(plays=0, reused=0, frames=0, drawn=0)
    cur = {}

    def frame(mobs):
        frame_m = getattr(cam, "frame", None)
        if frame_m is not None:
            cur["h"].update(frame_m.points.tobytes())
        feed(cur["h"], cam.get_mobjects_to_display(mobs))
        cur["n"] += 1

    def render(sc, t, moving=None):  # one frame: no drawing, the clock moves as in CairoRenderer.add_frame
        frame(moving or list_update(sc.mobjects, sc.foreground_mobjects))
        r.add_frame(None)

    def update_frame(sc, mobjects=None, **kw):  # only the frozen-frame path still calls this
        frame(mobjects or list_update(sc.mobjects, sc.foreground_mobjects))

    def static(sc, mobs):
        feed(cur["h"], cam.get_mobjects_to_display(mobs or []))

    def write_frame(_, num_frames=1):
        cur["h"].update(f"x{num_frames}".encode())
        cur["n"] += num_frames - 1

    stubs = (
        (r, dict(render=render, update_frame=update_frame, save_static_frame_data=static, get_frame=lambda: None)),
        (w, dict(write_frame=write_frame, begin_animation=lambda *a: None, end_animation=lambda *a: None,
                 add_partial_movie_file=lambda *a: None)),
    )
    for obj, fns in stubs:
        vars(obj).update(fns)

    def reap(block=False):
        """Collect finished workers, freeing their slots; block: wait until none are left."""
        while live:
            pid, status = os.waitpid(-1, 0 if block else os.WNOHANG)
            if not pid:
                return
            fd = live.pop(pid, None)
            if fd is not None:
                os.close(fd)
            if status:
                failed.append(pid)

    def slot():
        """The scene's process holds a free render slot for each drawing worker, so workers never pile up waiting:
        a worker's memory stops being shared as soon as Python touches it, and on 8 GB a pile-up swaps."""
        while True:
            fd = try_slot()
            if fd is not None:
                return fd
            reap()
            time.sleep(0.02)

    def worker(rd, a, kw):
        """Forked at the start of a play: wait for the fingerprint, then play it for real, or just exit."""
        try:
            for fd in live.values():  # others' slots: an inherited copy would keep them locked until this worker exits
                if fd is not None:
                    os.close(fd)
            name = os.read(rd, 256).decode()
            if not name:
                os._exit(0)
            for obj, fns in stubs:
                for k in fns:
                    del vars(obj)[k]
            path = w.partial_movie_directory / f"{name}{config.movie_file_extension}"
            tmp = path.with_name(f"{name}.{os.getpid()}.tmp{config.movie_file_extension}")
            w.add_partial_movie_file = lambda *x: None
            begin = w.begin_animation
            w.begin_animation = lambda allow: begin(True, tmp)
            CairoRenderer.play(r, scene, *a, **kw)
            w.join_all_encode_jobs()
            os.replace(tmp, path)  # atomic: a segment under its real name is always complete
            os._exit(0)
        except BaseException:
            traceback.print_exc()
            sys.stderr.flush()
            os._exit(1)

    def play(sc, *a, **kw):
        sys.stdout.flush()
        rd, wr = os.pipe()
        pid = os.fork()
        if not pid:
            os.close(wr)
            worker(rd, a, kw)
        os.close(rd)
        # ponytail: 3D frames also depend on the camera's angles and fixed-in-frame sets, so 3D never reuses a segment
        salt = os.urandom(8) if isinstance(sc, ThreeDScene) else f"{__version__} {config.frame_rate}".encode()
        cur.update(h=hashlib.blake2b(salt, digest_size=16), n=0)
        CairoRenderer.play(r, sc, *a, **kw)
        name = cur["h"].hexdigest()
        type(w).add_partial_movie_file(w, name)
        st["plays"] += 1
        st["frames"] += cur["n"]
        if os.path.exists(w.partial_movie_files[-1]):
            st["reused"] += 1
            live[pid] = None
        else:
            st["drawn"] += cur["n"]
            live[pid] = slot()
            os.write(wr, name.encode())
        os.close(wr)
        reap()

    def scene_finished(sc):
        reap(block=True)
        if failed:
            raise RuntimeError(f"{len(failed)} render worker(s) failed")
        print(f"AGENT {type(sc).__name__} {st['plays']} plays {st['reused']} reused "
              f"{st['drawn']}/{st['frames']} frames drawn", flush=True)
        CairoRenderer.scene_finished(r, sc)

    r.play, r.scene_finished = play, scene_finished
