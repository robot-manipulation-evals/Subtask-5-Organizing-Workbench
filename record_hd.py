"""Run inspect-robots with the YAM cameras rendered at a higher resolution, for sharper review videos.

yam_arena renders every camera at 640x360 and then resizes to -E cam_width x cam_height, so asking for more
only upscales. This wrapper raises the render size itself (BimanualYamEmbodiment's default cam_height /
cam_width) to RENDER_W x RENDER_H, then hands the command line to the normal inspect-robots CLI in the same
process. Each camera's calibrated lens scales with the render size, so the views are the same, only sharper.
Pass the same size as -E cam_width / cam_height so the final resize is a no-op.

    RENDER_W=1280 RENDER_H=720 python record_hd.py run --embodiment yam_arena --policy yam_scripted \\
        -E task=ghs_sort.py -E cam_width=1280 -E cam_height=720 ...

Use it for the scripted demo only. Dream-1 always receives 320x176 frames whatever the render size, so the
Dream run is recorded with the plain CLI.
"""

import importlib.abc
import importlib.util
import inspect
import os
import sys

W = int(os.environ.get("RENDER_W", "1280"))
H = int(os.environ.get("RENDER_H", "720"))


def _patch_class(module):
    cls = module.BimanualYamEmbodiment
    init = cls.__init__
    params = inspect.signature(init).parameters
    if "cam_height" not in params or "cam_width" not in params:
        sys.exit("BimanualYamEmbodiment no longer takes cam_height/cam_width; update record_hd.py")

    def patched(self, *args, **kwargs):
        kwargs.setdefault("cam_height", H)
        kwargs.setdefault("cam_width", W)
        init(self, *args, **kwargs)

    cls.__init__ = patched
    print(f"[record_hd] YAM cameras render at {W}x{H}", file=sys.stderr)


class _Hook(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """yam_arena.embodiment imports Isaac Lab, so it can only load after Isaac Sim starts: patch it when the
    embodiment imports it, not before."""

    NAME = "yam_arena.embodiment"

    def find_spec(self, name, path, target=None):
        if name != self.NAME:
            return None
        sys.meta_path.remove(self)
        spec = importlib.util.find_spec(name)
        self._inner = spec.loader
        spec.loader = self
        return spec

    def create_module(self, spec):
        return self._inner.create_module(spec)

    def exec_module(self, module):
        self._inner.exec_module(module)
        _patch_class(module)


if __name__ == "__main__":
    sys.meta_path.insert(0, _Hook())
    from inspect_robots.cli import main

    sys.argv[0] = "inspect-robots"
    sys.exit(main())
