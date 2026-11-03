#!/usr/bin/env python3
"""
Write the "solved" version of the scene: every bottle standing upright in its correct tray.
It is a small USD layer that sublayers the original scene and only moves the bottles. Use it to:
  * check that the bottles physically fit in the trays (open it in Isaac Sim and press Play),
  * get target poses for a scripted/oracle policy (printed, and saved as *_solution.json),
  * sanity-check the scorer (should give 12/12).

  python reference_solution.py scene/task5_scene.usda
"""
import argparse
import json
import math
import os

from pxr import Gf, Sdf, Usd, UsdGeom

PITCH = 0.105          # centre-to-centre spacing inside a tray
INSET = 0.055          # keep bottle centres this far from the tray walls
TRAY_FLOOR = 0.006     # tray floor thickness (see tray() in build_task5_scene.py)


def plan(manifest):
    by_zone = {}
    for b in manifest["bottles"]:
        by_zone.setdefault(b["correct_zone"], []).append(b)
    targets = {}
    for zone_id, bottles in by_zone.items():
        vols = manifest["zones"][zone_id]
        lo, hi = vols[0]["aabb_min"], vols[0]["aabb_max"]
        nx = max(1, int((hi[0] - lo[0] - 2 * INSET) // PITCH) + 1)
        ny = max(1, int((hi[1] - lo[1] - 2 * INSET) // PITCH) + 1)
        if len(bottles) > nx * ny:
            raise SystemExit(f"zone {zone_id}: {len(bottles)} bottles do not fit ({nx}x{ny} slots)")
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        cols = min(len(bottles), ny)
        rows = math.ceil(len(bottles) / cols)
        for i, b in enumerate(bottles):
            r, c = divmod(i, cols)
            x = cx + (r - (rows - 1) / 2) * PITCH
            y = cy + (c - (cols - 1) / 2) * PITCH
            targets[b["prim"]] = (round(x, 4), round(y, 4), round(lo[2] + TRAY_FLOOR + 0.001, 4))
    return targets


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage")
    ap.add_argument("--manifest")
    a = ap.parse_args()
    stage_path = os.path.abspath(a.stage)
    man_path = a.manifest or os.path.splitext(stage_path)[0] + "_manifest.json"
    manifest = json.load(open(man_path))
    targets = plan(manifest)

    out = os.path.splitext(stage_path)[0] + "_solved.usda"
    layer = Sdf.Layer.CreateNew(out)
    layer.subLayerPaths.append(os.path.basename(stage_path))
    stage = Usd.Stage.Open(layer)
    stage.SetEditTarget(layer)
    aisle_far_x = manifest["robot_aisle"]["x"][1]
    for prim_path, (x, y, z) in targets.items():
        prim = stage.GetPrimAtPath(prim_path)
        ops = {op.GetOpName(): op for op in UsdGeom.Xformable(prim).GetOrderedXformOps()}
        ops["xformOp:translate"].Set(Gf.Vec3d(x, y, z))
        if x > aisle_far_x and "xformOp:rotateXYZ" in ops:  # inside a cabinet on wall B: turn label towards the doors
            ops["xformOp:rotateXYZ"].Set(Gf.Vec3f(0, 0, 180))
    layer.Save()
    with open(os.path.splitext(stage_path)[0] + "_solution.json", "w") as f:
        json.dump({p: {"position": t} for p, t in targets.items()}, f, indent=2)
    for b in manifest["bottles"]:
        print(f"{b['prim'].split('/')[-1]}  {b['chemical_id']:20} -> {b['correct_zone']:32} {targets[b['prim']]}")
    print("wrote", out)
