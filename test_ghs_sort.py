"""Checks of ghs_sort.py's scoring and demo, without the simulator. Needs yam_arena (the official stack):

    python -m pytest -q test_ghs_sort.py
"""

import math
from pathlib import Path

import numpy as np
import pytest

from yam_arena import ik, station
from yam_arena.constants import CONTROL_HZ
from yam_arena.demo import ArmPlan
from yam_arena.task_file import TABLE_TOP, ObjectState, load

TASK = load(Path(__file__).with_name("ghs_sort.py"))
M = TASK.module
TOP = TABLE_TOP["station"]
BOTTLE_H, BOTTLE_R = 0.103, 0.025
TRAY_H = 0.0875  # tray with its sign card


def state(x, y, bottom, h, r, tilt_deg=0.0, moving=False):
    """An object at x, y with its lowest point at ``bottom``, tilted ``tilt_deg`` about world x."""
    t = math.radians(tilt_deg)
    centre = np.array([x, y, bottom + h / 2 * math.cos(t) + r * math.sin(t)])
    half = np.array([r, r * math.cos(t) + h / 2 * math.sin(t), h / 2 * math.cos(t) + r * math.sin(t)])
    return ObjectState(
        pos=centre,
        quat_xyzw=np.array([math.sin(t / 2), 0.0, 0.0, math.cos(t / 2)]),
        lin_vel=np.array([0.05, 0.0, 0.0]) if moving else np.zeros(3),
        ang_vel=np.zeros(3),
        low=centre - half,
        high=centre + half,
    )


def trays():
    return {M.TRAY_NAME[z]: state(M.TRAY_X, y, TOP, TRAY_H, 0.0575) for z, y in M.TRAYS.items()}


def in_tray(zone, **kw):
    return state(M.TRAY_X, M.TRAYS[zone], TOP + M.TRAY_FLOOR, BOTTLE_H, BOTTLE_R, **kw)


def at_start(chem, **kw):
    return state(M.BOTTLE_X, M.BOTTLES[chem][0], TOP, BOTTLE_H, BOTTLE_R, **kw)


def scene(where):
    """``where``: chemical -> bottle state; chemicals not named stay where they start."""
    out = trays()
    for chem in M.BOTTLES:
        out[M.BOTTLE_NAME[chem]] = where.get(chem, at_start(chem))
    return out


def correct(chem, **kw):
    return in_tray(M.BOTTLES[chem][1], **kw)


def side_trays(chem):
    """The trays this bottle's arm can reach: the ones on its side."""
    sign = np.sign(M.BOTTLES[chem][0])
    return [z for z, y in M.TRAYS.items() if np.sign(y) == sign]


def test_loads_with_ten_objects_and_neutral_names():
    names = [o.name for o in TASK.objects]
    assert sorted(names) == [f"bottle_{i}" for i in range(1, 5)] + [f"tray_{i}" for i in range(1, 7)]
    assert sorted(TASK.free_objects) == [f"bottle_{i}" for i in range(1, 5)]
    for name in ("acid", "base", "peroxide", "flamm", "oxid", "toxic", "general"):
        assert not any(name in o.name or name in o.asset for o in TASK.objects)


def test_each_arm_has_three_trays_and_its_bottles_belong_on_its_side():
    for chem, (y, zone, _) in M.BOTTLES.items():
        assert len(side_trays(chem)) == 3 and zone in side_trays(chem)


def test_no_fixed_rule_does_better_than_half():
    """Rules that ignore the labels: every bottle in its nearest, second-nearest or farthest tray; in the outer,
    middle or inner tray of its side; or each side's two bottles swapped into each other's nearest tray. The nearest
    tray is wrong for every bottle, and no rule gets more than two of the four."""
    def by_distance(chem, k):
        y = M.BOTTLES[chem][0]
        return sorted(side_trays(chem), key=lambda z: abs(M.TRAYS[z] - y))[k]

    def by_position(chem, k):
        return sorted(side_trays(chem), key=lambda z: -abs(M.TRAYS[z]))[k]

    assert M.score(scene({c: in_tray(by_distance(c, 0)) for c in M.BOTTLES})) == 0.0
    for rule in (by_distance, by_position):
        for k in range(3):
            assert M.score(scene({c: in_tray(rule(c, k)) for c in M.BOTTLES})) <= 0.5
    left = [c for c in M.BOTTLES if M.BOTTLES[c][0] > 0]
    right = [c for c in M.BOTTLES if M.BOTTLES[c][0] < 0]
    swapped = {}
    for a, b in (left, right):
        swapped.update({a: in_tray(by_distance(b, 0)), b: in_tray(by_distance(a, 0))})
    assert M.score(scene(swapped)) <= 0.5


def test_no_bottle_is_in_line_with_a_tray_or_equally_near_two():
    for chem, (y, _, _) in M.BOTTLES.items():
        d = sorted(abs(M.TRAYS[z] - y) for z in side_trays(chem))
        assert d[0] >= 0.03 and d[1] - d[0] >= 0.02 and d[2] - d[1] >= 0.02


def test_start_scores_zero():
    assert M.score(scene({})) == 0.0 and not M.success(scene({}))


def test_all_sorted_is_success():
    objs = scene({c: correct(c) for c in M.BOTTLES})
    assert M.score(objs) == 1.0 and M.success(objs)


def test_partial_credit_is_a_quarter_per_bottle():
    for n in range(5):
        chems = list(M.BOTTLES)[:n]
        assert M.score(scene({c: correct(c) for c in chems})) == pytest.approx(0.25 * n)


def test_a_tipped_bottle_anywhere_zeroes_the_trial():
    where = {c: correct(c) for c in M.BOTTLES}
    where["hydrochloric_acid"] = at_start("hydrochloric_acid", tilt_deg=90)
    assert M.score(scene(where)) == 0.0


def test_a_slight_lean_still_counts_but_a_large_one_does_not():
    assert M.score(scene({c: correct(c, tilt_deg=10) for c in M.BOTTLES})) == 1.0
    assert M.score(scene({"acetic_acid": correct("acetic_acid", tilt_deg=25)})) == 0.0


def test_a_bottle_on_the_tray_rim_does_not_count():
    on_rim = state(M.TRAY_X - 0.05, M.TRAYS["flammables_cabinet"], TOP + 0.03, BOTTLE_H, BOTTLE_R)
    assert M.score(scene({"acetic_acid": on_rim})) == 0.0


def test_success_needs_the_bottles_still():
    assert M.success(scene({c: correct(c) for c in M.BOTTLES}))
    objs = scene({c: correct(c, moving=(c == "acetic_acid")) for c in M.BOTTLES})
    assert not M.success(objs) and M.score(objs) == 1.0


@pytest.mark.parametrize("side", ["left", "right"])
def test_the_demo_is_reachable_within_the_joint_limits(side):
    arm = ArmPlan(TASK.demo()[side], station.BASES[side])
    actions = np.array([arm.action7((k + 1) / CONTROL_HZ)[0] for k in range(round(arm.duration * CONTROL_HZ) + 5)])
    assert arm.worst_ik_mm < 0.5 and arm.worst_ik_deg < 0.1
    assert np.all(actions[:, :6] >= ik.LOWER) and np.all(actions[:, :6] <= ik.UPPER)
