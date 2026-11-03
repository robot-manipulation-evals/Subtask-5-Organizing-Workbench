#!/usr/bin/env python3
"""
Score Task 5 from bottle poses. Works on a saved stage, or on the live stage inside Isaac Sim (PhysX writes poses back to USD).

  python score_task5.py scene/task5_scene_after_run.usda                    # manifest found next to the original stage
  python score_task5.py my_run.usda --manifest scene/task5_scene_manifest.json

Inside Isaac Sim (Script Editor):
  import omni.usd, json, sys; sys.path.append("<path>/task5_assets/isaac"); import score_task5
  print(score_task5.report(score_task5.score(omni.usd.get_context().get_stage(), json.load(open(".../task5_scene_manifest.json")))))

Per bottle, the check reports:
  correct    - the bottle's base is inside its correct zone volume (tray interior, 30 cm high) and the bottle is upright
  wrong_zone - stored, but in the wrong zone
  not_stored - in no zone (still on the bench, on the floor, ...)
It also reports incompatible storage groups sharing one tray, and tipped-over bottles.
Door state is not checked here: read the cabinet door joint positions from your controller.
"""
import argparse
import glob
import json
import math
import os

from pxr import Gf, Usd, UsdGeom

UPRIGHT_MAX_TILT_DEG = 20.0
Z_TOLERANCE = 0.02  # a bottle base may sit up to 2 cm below the zone floor


def bottle_pose(stage, prim_path):
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return None, None
    m = UsdGeom.XformCache().GetLocalToWorldTransform(prim)
    pos = m.ExtractTranslation()
    up = m.TransformDir(Gf.Vec3d(0, 0, 1)).GetNormalized()
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, up[2]))))
    return pos, tilt


def zone_of(pos, zones):
    for zone_id, vols in zones.items():
        for v in vols:
            lo, hi = v["aabb_min"], v["aabb_max"]
            if lo[0] <= pos[0] <= hi[0] and lo[1] <= pos[1] <= hi[1] and lo[2] - Z_TOLERANCE <= pos[2] <= hi[2]:
                return zone_id, v["prim"]
    return None, None


def score(stage, manifest):
    rows, by_tray = [], {}
    for b in manifest["bottles"]:
        pos, tilt = bottle_pose(stage, b["prim"])
        if pos is None:
            rows.append(dict(b, status="missing", zone=None, tilt=None, pos=None))
            continue
        zone, tray = zone_of(pos, manifest["zones"])
        upright = tilt <= UPRIGHT_MAX_TILT_DEG
        if zone is None:
            status = "not_stored"
        elif zone == b["correct_zone"]:
            status = "correct" if upright else "correct_but_tipped"
        else:
            status = "wrong_zone"
        if tray:
            by_tray.setdefault(tray, []).append(b)
        rows.append(dict(b, status=status, zone=zone, tilt=round(tilt, 1), pos=[round(v, 3) for v in pos]))
    clashes = []
    pairs = {frozenset(p) for p in manifest["incompatible_groups"]}
    for tray, items in by_tray.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                g = frozenset((items[i]["storage_group"], items[j]["storage_group"]))
                if g in pairs:
                    clashes.append((tray, items[i]["chemical_id"], items[j]["chemical_id"]))
    n_ok = sum(r["status"] == "correct" for r in rows)
    return {"bottles": rows, "correct": n_ok, "total": len(rows), "score": round(n_ok / max(1, len(rows)), 3),
            "incompatible_pairs": clashes, "tipped": [r["chemical_id"] for r in rows if r["tilt"] and r["tilt"] > UPRIGHT_MAX_TILT_DEG]}


def report(res):
    lines = [f"{'bottle':10} {'chemical':22} {'status':20} {'in zone':34} correct zone"]
    for r in res["bottles"]:
        lines.append(f"{r['prim'].split('/')[-1]:10} {r['chemical_id']:22} {r['status']:20} {str(r['zone']):34} {r['correct_zone']}")
    lines.append(f"\nScore: {res['correct']}/{res['total']} correctly stored ({res['score']:.0%})")
    lines.append(f"Incompatible pairs sharing a tray: {res['incompatible_pairs'] or 'none'}")
    lines.append(f"Tipped over: {res['tipped'] or 'none'}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage")
    ap.add_argument("--manifest")
    ap.add_argument("--json", action="store_true", help="print machine-readable results")
    a = ap.parse_args()
    man_path = a.manifest or (glob.glob(os.path.join(os.path.dirname(os.path.abspath(a.stage)), "*_manifest.json")) or [None])[0]
    if not man_path:
        raise SystemExit("no manifest found: pass --manifest")
    res = score(Usd.Stage.Open(a.stage), json.load(open(man_path)))
    print(json.dumps(res, indent=2) if a.json else report(res))
