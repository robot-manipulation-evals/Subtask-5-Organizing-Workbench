"""On the station table, four 100 mL reagent bottles (50 mm wide, 103 mm tall) stand in a row 22 cm in front
of the arms, two on each side, each with a hazard label wrapped all the way around it. Behind them, 38 cm out, is a
row of six fixed storage trays (115 mm square, 30 mm walls), three on each side, each with a coloured storage-class
sign on its back edge. Every bottle has exactly one correct tray, on its own side. The bottles are loose; the trays
are fixed.
"""

import os
import sys
from pathlib import Path

import numpy as np

from yam_arena.constants import FINGER_OPEN
from yam_arena.demo import Waypoint, pick_place_waypoints
from yam_arena.task_file import TABLE_TOP, Asset

SCENE = "station"
TOP = TABLE_TOP[SCENE]

# ---- custom USDs (assets/, next to this file) registered as Arena library assets ----------------------------
# yam_arena resolves an Asset by AssetRegistry().get_asset_by_name(name).usd_path, so registering an object with
# a usd_path is all it takes; the framework itself is unchanged. Each bottle file references NVIDIA's SimReady
# Boston round bottle (streamed from NVIDIA's public asset server) and adds the wrapped label.
ASSET_DIR = Path(__file__).resolve().parent / "assets"


class _UsdAsset:
    def __init__(self, name: str, usd_path: Path):
        if not usd_path.is_file():
            raise FileNotFoundError(f"{usd_path} is missing")
        self.name = name
        self.usd_path = str(usd_path)


def _register(key: str, file_name: str) -> str:
    from isaaclab_arena.assets.registries import AssetRegistry  # imports no Isaac Sim modules

    reg = AssetRegistry()
    if not reg.is_registered(key, ensure_loaded=False):
        reg.register(_UsdAsset(key, ASSET_DIR / file_name), key)
    return key


# ---- layout -------------------------------------------------------------------------------------------------
# Arm bases at y = +-0.305; each arm reaches only its own side, where it has two bottles and three trays. The
# layout was searched so the tray has to come from the label: the nearest tray is wrong for every bottle, and no
# other fixed rule (second-nearest, farthest, outer, middle or inner tray, swapping a side's two bottles) puts more
# than two of the four in the right tray. With 4 bottles and 3 trays a side, some rule always gets 2; a guess gets
# a bottle right one time in three. The outer trays sit 0.5 cm inside the arm bases so the grippers' starting pose
# doesn't hide their signs from the top camera.
BOTTLE_X, TRAY_X = 0.22, 0.38
BOTTLE_EXTENT = 0.05  # widest horizontal size, label included (m)
GRIP_Z = 0.060  # TCP height above the table for a grasp on the bottle's straight wall (wall ends at 0.081)
TRAY_FLOOR = 0.004  # tray floor thickness (m)
TRAY_INNER_HALF = 0.0525  # half the tray's inside width (m)

# zone -> y of its tray (m, + is the robot's left)
TRAYS = {
    "corrosives_acids": 0.31,
    "flammables_cabinet": 0.19,
    "toxics": 0.07,
    "oxidizers": -0.07,
    "corrosives_bases": -0.19,
    "general_shelf": -0.31,
}
# chemical -> (y it starts at, correct zone, mass). Masses: 100 mL of liquid + 60 g glass bottle.
BOTTLES = {
    "acetic_acid": (0.27, "flammables_cabinet", 0.06 + 0.1 * 1.05),
    "hydrochloric_acid": (0.10, "corrosives_acids", 0.06 + 0.1 * 1.18),
    "ammonium_hydroxide": (-0.10, "corrosives_bases", 0.06 + 0.1 * 0.90),
    "hydrogen_peroxide": (-0.27, "oxidizers", 0.06 + 0.1 * 1.11),
}

# Object names are neutral (the answer is not in the scene graph): bottle_1..4 and tray_1..6, left to right.
BOTTLE_NAME = {c: f"bottle_{i + 1}" for i, c in enumerate(sorted(BOTTLES, key=lambda c: -BOTTLES[c][0]))}
TRAY_NAME = {z: f"tray_{i + 1}" for i, z in enumerate(sorted(TRAYS, key=lambda z: -TRAYS[z]))}

OBJECTS = [
    *(
        Asset(BOTTLE_NAME[chem], _register(f"ghs_sort_{BOTTLE_NAME[chem]}", f"{chem}.usda"),
              xy=(BOTTLE_X, y), extent=BOTTLE_EXTENT, mass=round(mass, 3))
        for chem, (y, _, mass) in BOTTLES.items()
    ),
    *(
        Asset(TRAY_NAME[zone], _register(f"ghs_sort_{TRAY_NAME[zone]}", f"tray_{zone}.usda"),
              xy=(TRAY_X, y), extent=0.115)
        for zone, y in TRAYS.items()
    ),
]


# ---- scoring ------------------------------------------------------------------------------------------------
def _tilt_deg(quat_xyzw) -> float:
    x, y, z, w = quat_xyzw
    up_z = 1.0 - 2.0 * (x * x + y * y)  # world z of the bottle's own z axis
    return float(np.degrees(np.arccos(np.clip(up_z, -1.0, 1.0))))


def _upright(state) -> bool:
    return _tilt_deg(state.quat_xyzw) < 20.0


def _in_tray(bottle, tray) -> bool:
    """Standing inside the tray: centre over the tray's inside, bottom on its floor (not on a rim), upright."""
    d = np.abs(bottle.pos[:2] - tray.pos[:2])
    return bool(
        np.all(d < TRAY_INNER_HALF - 0.015)
        and bottle.low[2] < tray.low[2] + TRAY_FLOOR + 0.015
        and _upright(bottle)
    )


def _correct(objects) -> list[bool]:
    return [_in_tray(objects[BOTTLE_NAME[c]], objects[TRAY_NAME[z]]) for c, (_, z, _) in BOTTLES.items()]


def _any_tipped(objects) -> bool:
    return any(not _upright(objects[BOTTLE_NAME[c]]) for c in BOTTLES)


def success(objects):
    """All four bottles upright and still in their correct trays."""
    return all(_correct(objects)) and all(objects[BOTTLE_NAME[c]].resting() for c in BOTTLES)


def distance(objects):
    """Summed metres from each bottle to the centre of its correct tray (xy)."""
    return float(sum(
        np.linalg.norm(objects[BOTTLE_NAME[c]].pos[:2] - objects[TRAY_NAME[z]].pos[:2])
        for c, (_, z, _) in BOTTLES.items()
    ))


def score(objects):
    """0.25 per bottle standing upright in its correct tray. A bottle tipped over anywhere (more than 20 degrees
    from vertical, a spill) scores the whole trial 0."""
    if os.environ.get("GHS_SORT_DEBUG"):
        _debug(objects)
    if _any_tipped(objects):
        return 0.0
    return 0.25 * sum(_correct(objects))


def _debug(objects):
    """GHS_SORT_DEBUG=1: print each bottle's offset from its tray, bottom height and tilt (stderr)."""
    for c, (_, z, _) in BOTTLES.items():
        b, t = objects[BOTTLE_NAME[c]], objects[TRAY_NAME[z]]
        d = b.pos[:2] - t.pos[:2]
        print(f"[ghs_sort] {c:19s} dxy=({d[0]:+.3f},{d[1]:+.3f}) bottom={b.low[2] - t.low[2]:+.3f} "
              f"tilt={_tilt_deg(b.quat_xyzw):5.1f} resting={b.resting()} in_tray={_in_tray(b, t)}", file=sys.stderr)


# ---- scripted demo ------------------------------------------------------------------------------------------
TRAVEL_Z = TOP + 0.12  # carried bottle's bottom 6 cm up: clears the 3 cm tray walls
# "Read the label" pose before each pick. The wrist camera rides 13.4 cm above the TCP and 8 cm beyond it, looking
# down (tilted 8 deg back toward the fingers). With the TCP 4.5 cm past the bottle's centre and 13.1 cm above the
# table, the camera looks at the bottle's far side about 25 deg from vertical: the whole label is in view (at 30 deg
# the bottle leaves the bottom of the frame, at 20 deg the label is seen mostly from above); the fingertips stay
# 1.5 cm above the cap.
LOOK_DX, LOOK_Z = 0.045, TOP + 0.131
LOOK_HOLD_S = 1.0


def _move(chem):
    y, zone, _ = BOTTLES[chem]
    look = (BOTTLE_X + LOOK_DX, y, LOOK_Z)
    read = [
        Waypoint(1.5, look, FINGER_OPEN, "to the label"),
        Waypoint(LOOK_HOLD_S, look, FINGER_OPEN, "read the label"),
    ]
    pick = (BOTTLE_X, y, TOP + GRIP_Z)
    place = (TRAY_X, TRAYS[zone], TOP + TRAY_FLOOR + GRIP_Z + 0.005)
    return read + pick_place_waypoints(pick, place, travel_z=TRAVEL_Z)


def demo():
    """Each arm holds its wrist camera over a bottle's label for a second, then stores the bottle; outer bottle
    first. Left: acetic acid to FLAMMABLE, then hydrochloric acid out to INORGANIC ACIDS; right: hydrogen peroxide in
    to OXIDIZERS, then ammonium hydroxide to BASES."""
    return {
        "left": _move("acetic_acid") + _move("hydrochloric_acid"),
        "right": _move("hydrogen_peroxide") + _move("ammonium_hydroxide"),
    }
