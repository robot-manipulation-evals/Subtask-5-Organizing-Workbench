#!/usr/bin/env python3
"""
Build the Task 5 (Organizing the workbench / chemical storage segregation) scene as a USD stage for Isaac Sim.

Layout (Z-up, metres). The robot works in the aisle between two walls:

    Wall A (x = -0.45, fronts face +X):  [ wire shelf: OXIDIZERS | TOXIC | GENERAL ]  [ lab bench with 12 labelled bottles ]
    Wall B (x = +2.25, fronts face -X):  [ FLAMMABLES cabinet ] [ ACIDS cabinet (+ oxidizing-acid tray) ] [ BASES cabinet ]

* Bottles: NVIDIA SimReady Boston-round bottles (liquids) and wide-mouth packer jars (solids). They are rigid bodies with
  realistic filled masses. GHS labels are separate textured meshes wrapped on each bottle (from ../labels/*.png).
* Cabinets: Isaac Lab's articulated Sektion cabinet (2 hinged doors + 2 drawers), recoloured, with zone signs on the
  doors and secondary-containment trays inside.
* Bench: built here from simple boxes (black epoxy top at 0.90 m, steel frame, lower shelf), all with colliders.
* A scene_manifest.json is written next to the stage. It holds the ground truth (bottle -> chemical -> correct zone) and
  each zone's volume for scoring (see score_task5.py).

Only the pxr USD API is used, so this runs with Isaac Sim's python (./python.sh build_task5_scene.py) or any Python with
`pip install usd-core`. Then open the .usda in Isaac Sim (File > Open) and press Play. By default the assets stream from
NVIDIA's public asset server (internet required). Use --assets-root to point at a local copy instead.
"""
import argparse
import json
import math
import os
import random

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdShade, Vt

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)  # task5_assets/

import sys  # noqa: E402

sys.path.insert(0, HERE)
from asset_list import ASSETS, DEFAULT_ASSETS_ROOT  # noqa: E402  (shared with fetch_assets.py)

# ---------------------------------------------------------------- layout (edit freely)
WALL_A_X = -0.45          # back wall behind bench + shelf
AISLE = 1.30              # clear floor between bench front and cabinet fronts
BENCH = dict(length=1.80, depth=0.75, top_z=0.90, top_thk=0.03, y=0.0)
SHELF_Y = -1.60           # centre of the wire shelf along wall A
CABINET_GAP = 0.06
BOTTLE_ROWS_X = (0.20, 0.06)              # bottle rows, measured from the bench centre-line towards the front (+X)
BOTTLE_COL_PITCH = 0.15

# ---------------------------------------------------------------- measured asset geometry (Isaac 5.1 / SimReady)
# Sektion cabinet, in its own frame: front (doors) faces +X, origin at the centre of the box.
CAB = dict(min_z=-0.384, back_x=-0.308, door_x=0.326, half_w=0.384,
           floor_z=-0.351, inner_x=(-0.270, 0.296), inner_y=(-0.355, 0.355), ceil_z=0.120)
DOOR_LINKS = {"door_left_link": Gf.Vec3d(0.3162, -0.3757, -0.12973), "door_right_link": Gf.Vec3d(0.3162, 0.3757, -0.12973)}
DOOR_SPAN_Y = {"door_left_link": (-0.382, -0.001), "door_right_link": (0.001, 0.382)}
DOOR_SPAN_Z = (-0.384, 0.124)
CAB_RECOLOR = ["sektion/visuals", "door_left_link/visuals", "door_right_link/visuals",
               "drawer_top/visuals", "drawer_bottom/visuals"]
SHELF_TOP_Z = 0.87
SHELF_HALF = (0.308, 0.612)
# Label bands: (centre x offset, radius, z0, z1); body straight-wall sections measured from the meshes.
LABEL_FIT = {"liquid_bottle": (0.0, 0.0458, 0.030, 0.100), "solid_jar": (-0.002, 0.0398, 0.028, 0.086)}

# Filled masses (kg): bottle/jar tare + contents (500 mL x density, or the solid mass on the label).
DENSITY = {"sulfuric_acid": 1.84, "nitric_acid": 1.41, "hydrochloric_acid": 1.18, "acetic_acid": 1.05,
           "ammonium_hydroxide": 0.90, "ethanol": 0.789, "acetone": 0.784, "methanol": 0.792,
           "hydrogen_peroxide": 1.11}

COLORS = {
    "epoxy": (0.03, 0.03, 0.035), "steel": (0.55, 0.57, 0.60), "flammable_yellow": (0.96, 0.75, 0.0),
    "corrosive_blue": (0.10, 0.33, 0.66), "tray": (0.08, 0.08, 0.09), "wall": (0.82, 0.83, 0.82),
    "floor": (0.45, 0.47, 0.48), "amber_glass": (0.55, 0.27, 0.05),
}


# ---------------------------------------------------------------- helpers
def preview_material(stage, path, color, roughness=0.5, metallic=0.0, texture=None, opacity=1.0):
    mat = UsdShade.Material.Define(stage, path)
    sh = UsdShade.Shader.Define(stage, path + "/Shader")
    sh.CreateIdAttr("UsdPreviewSurface")
    sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    sh.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
    if opacity < 1.0:
        sh.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(opacity)
    if texture:
        st = UsdShade.Shader.Define(stage, path + "/st")
        st.CreateIdAttr("UsdPrimvarReader_float2")
        st.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
        tex = UsdShade.Shader.Define(stage, path + "/Texture")
        tex.CreateIdAttr("UsdUVTexture")
        tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture)
        tex.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
        tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("clamp")
        tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("clamp")
        tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st.ConnectableAPI(), "result")
        tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex.ConnectableAPI(), "rgb")
    else:
        sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    return mat


def bind(prim, mat, stronger=False):
    api = UsdShade.MaterialBindingAPI.Apply(prim)
    strength = UsdShade.Tokens.strongerThanDescendants if stronger else UsdShade.Tokens.weakerThanDescendants
    api.Bind(mat, bindingStrength=strength)


def box(stage, path, center, size, mat, collide=True):
    """Axis-aligned box (static collider) from a unit cube."""
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    xf = UsdGeom.Xformable(cube)
    xf.AddTranslateOp().Set(Gf.Vec3d(*center))
    xf.AddScaleOp().Set(Gf.Vec3f(*size))
    cube.CreateExtentAttr([(-0.5, -0.5, -0.5), (0.5, 0.5, 0.5)])
    bind(cube.GetPrim(), mat)
    if collide:
        UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
    return cube


def textured_quad(stage, path, center, width, height, normal_axis, mat):
    """Flat rectangle facing +X or -X (normal_axis = +1 / -1), textured left-to-right as seen from the front."""
    cx, cy, cz = center
    w, h = width / 2, height / 2
    s = normal_axis
    pts = [(cx, cy - s * w, cz - h), (cx, cy + s * w, cz - h), (cx, cy + s * w, cz + h), (cx, cy - s * w, cz + h)]
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr([Gf.Vec3f(*p) for p in pts])
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    mesh.CreateSubdivisionSchemeAttr("none")
    mesh.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pts])))
    st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
    st.Set([(0, 0), (1, 0), (1, 1), (0, 1)])
    bind(mesh.GetPrim(), mat)
    return mesh


def wrap_label(stage, path, cx, radius, z0, z1, aspect, mat, segments=48):
    """Partial cylinder centred on the +X side of the bottle, sized so the texture keeps its aspect ratio."""
    arc = (z1 - z0) * aspect
    span = arc / radius
    pts, uvs, idx = [], [], []
    for i in range(segments + 1):
        a = -span / 2 + span * i / segments
        for z in (z0, z1):
            pts.append(Gf.Vec3f(cx + radius * math.cos(a), radius * math.sin(a), z))
    for i in range(segments):
        b, t, b2, t2 = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
        idx += [b, b2, t2, t]
        u0, u1 = i / segments, (i + 1) / segments
        uvs += [(u0, 0), (u1, 0), (u1, 1), (u0, 1)]
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(pts)
    mesh.CreateFaceVertexCountsAttr([4] * segments)
    mesh.CreateFaceVertexIndicesAttr(idx)
    mesh.CreateSubdivisionSchemeAttr("none")
    mesh.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(Vt.Vec3fArray(pts)))
    st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
    st.Set(uvs)
    bind(mesh.GetPrim(), mat)
    return mesh


def yaw_quat(deg):
    r = math.radians(deg) / 2
    return Gf.Quatf(math.cos(r), 0, 0, math.sin(r))


def rotate_z(v, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])


def add_ref(stage, path, asset_url):
    prim = stage.DefinePrim(path, "Xform")
    prim.GetReferences().AddReference(asset_url)
    return prim


def set_xform(prim, translate, yaw_deg=0.0):
    """Reuse the asset's own op order (translate, rotateXYZ, scale) when present, otherwise author a fresh stack."""
    xf = UsdGeom.Xformable(prim)
    ops = {op.GetOpName(): op for op in xf.GetOrderedXformOps()}
    if "xformOp:translate" in ops and "xformOp:rotateXYZ" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(*translate))
        ops["xformOp:rotateXYZ"].Set(Gf.Vec3f(0, 0, yaw_deg))
    elif "xformOp:translate" in ops and "xformOp:orient" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(*translate))
        q = yaw_quat(yaw_deg)
        ops["xformOp:orient"].Set(Gf.Quatd(q.GetReal(), Gf.Vec3d(q.GetImaginary())) if
                                  ops["xformOp:orient"].GetPrecision() == UsdGeom.XformOp.PrecisionDouble else q)
    else:
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
        xf.AddRotateXYZOp().Set(Gf.Vec3f(0, 0, yaw_deg))


def tray(stage, path, center, size_xy, mat, wall=0.006, height=0.06):
    """Open-top containment tray made of 5 boxes. center = (x, y, z_bottom)."""
    x, y, z = center
    sx, sy = size_xy
    UsdGeom.Xform.Define(stage, path)
    box(stage, f"{path}/Floor", (x, y, z + wall / 2), (sx, sy, wall), mat)
    zc = z + height / 2
    box(stage, f"{path}/WallFront", (x + sx / 2 - wall / 2, y, zc), (wall, sy, height), mat)
    box(stage, f"{path}/WallBack", (x - sx / 2 + wall / 2, y, zc), (wall, sy, height), mat)
    box(stage, f"{path}/WallLeft", (x, y - sy / 2 + wall / 2, zc), (sx, wall, height), mat)
    box(stage, f"{path}/WallRight", (x, y + sy / 2 - wall / 2, zc), (sx, wall, height), mat)


# ---------------------------------------------------------------- scene
def build(args):
    chem = json.load(open(os.path.join(PACK, "chemicals.json")))
    out = os.path.abspath(args.out)
    out_dir = os.path.dirname(out)
    os.makedirs(out_dir, exist_ok=True)
    rel = lambda p: os.path.relpath(p, out_dir).replace(os.sep, "/")
    root = args.assets_root.rstrip("/")
    url = lambda key: f"{root}/{ASSETS[key]}"

    stage = Usd.Stage.CreateNew(out)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1.0)
    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    scene = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
    scene.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
    scene.CreateGravityMagnitudeAttr(9.81)

    L = "/World/Looks"
    M = {k: preview_material(stage, f"{L}/{k}", c, roughness=0.35 if k == "epoxy" else 0.5,
                             metallic=0.6 if k == "steel" else 0.0) for k, c in COLORS.items()}
    sign_mat = {}
    for z in chem["zones"]:
        sign_mat[z] = preview_material(stage, f"{L}/Sign_{z}", (1, 1, 1), texture=rel(os.path.join(PACK, "zone_signs", z + ".png")))

    # --- room
    bench_front_x = WALL_A_X + BENCH["depth"]
    wall_b_x = bench_front_x + AISLE + (CAB["door_x"] - CAB["back_x"]) + 0.02
    box(stage, "/World/Room/Floor", (0.5, -0.5, -0.01), (12, 12, 0.02), M["floor"])
    box(stage, "/World/Room/WallA", (WALL_A_X - 0.06, -0.5, 1.2), (0.1, 6.0, 2.4), M["wall"])
    box(stage, "/World/Room/WallB", (wall_b_x + 0.06, -0.5, 1.2), (0.1, 6.0, 2.4), M["wall"])
    dome = UsdLux.DomeLight.Define(stage, "/World/Lights/Dome")
    dome.CreateIntensityAttr(800)
    sun = UsdLux.DistantLight.Define(stage, "/World/Lights/Key")
    sun.CreateIntensityAttr(2500)
    UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(-35, 25, 0))

    # --- lab bench (procedural)
    b = BENCH
    bx = WALL_A_X + b["depth"] / 2
    top_c = b["top_z"] - b["top_thk"] / 2
    B = "/World/LabBench"
    UsdGeom.Xform.Define(stage, B)
    box(stage, f"{B}/Top", (bx, b["y"], top_c), (b["depth"], b["length"], b["top_thk"]), M["epoxy"])
    leg_h = b["top_z"] - b["top_thk"]
    for i, (dx, dy) in enumerate([(-1, -1), (-1, 1), (1, -1), (1, 1)]):
        box(stage, f"{B}/Leg{i}", (bx + dx * (b["depth"] / 2 - 0.04), b["y"] + dy * (b["length"] / 2 - 0.04), leg_h / 2),
            (0.05, 0.05, leg_h), M["steel"])
    box(stage, f"{B}/ApronFront", (bx + b["depth"] / 2 - 0.04, b["y"], leg_h - 0.05), (0.03, b["length"] - 0.1, 0.08), M["steel"])
    box(stage, f"{B}/ApronBack", (bx - b["depth"] / 2 + 0.04, b["y"], leg_h - 0.05), (0.03, b["length"] - 0.1, 0.08), M["steel"])
    box(stage, f"{B}/LowerShelf", (bx, b["y"], 0.16), (b["depth"] - 0.06, b["length"] - 0.06, 0.02), M["steel"])
    box(stage, f"{B}/Backsplash", (WALL_A_X + 0.01, b["y"], b["top_z"] + 0.075), (0.02, b["length"], 0.15), M["epoxy"])

    zones = {}

    def add_zone(zone_id, prim_path, lo, hi):
        zones.setdefault(zone_id, []).append({"prim": prim_path, "aabb_min": [round(v, 4) for v in lo],
                                              "aabb_max": [round(v, 4) for v in hi]})

    def tray_with_zone(path, zone_id, c_xy, z_bottom, size_xy, label_side):
        tray(stage, path, (c_xy[0], c_xy[1], z_bottom), size_xy, M["tray"])
        sx, sy = size_xy
        front_x = c_xy[0] + label_side * (sx / 2 + 0.0015)
        w = min(0.20, sy * 0.6)
        textured_quad(stage, f"{path}/Label", (front_x, c_xy[1], z_bottom + 0.032), w, w / 3, label_side, sign_mat[zone_id])
        add_zone(zone_id, path, (c_xy[0] - sx / 2, c_xy[1] - sy / 2, z_bottom), (c_xy[0] + sx / 2, c_xy[1] + sy / 2, z_bottom + 0.30))

    # --- wire shelf with three zone trays on the top tier (wall A)
    sh_x = WALL_A_X + SHELF_HALF[0] + 0.01
    shelf = add_ref(stage, "/World/Storage/GeneralShelf", url("shelf"))
    set_xform(shelf, (sh_x, SHELF_Y, 0.0))
    shelf.GetVariantSets().GetVariantSet("PhysicsVariant").SetVariantSelection("RigidBody")
    UsdPhysics.RigidBodyAPI.Apply(shelf).CreateRigidBodyEnabledAttr(False)  # static collider
    for i, z in enumerate(["oxidizers", "toxics", "general_shelf"]):
        ty = SHELF_Y + (i - 1) * 0.40
        tray_with_zone(f"/World/Storage/ShelfTray_{z}", z, (sh_x, ty), SHELF_TOP_Z + 0.002, (0.46, 0.37), +1)

    # --- three articulated cabinets (wall B, rotated 180 deg so doors face the aisle)
    cab_x = wall_b_x + CAB["back_x"] - 0.01  # yaw 180: local back (-x) maps to +x
    cab_specs = [
        ("FlammablesCabinet", "flammable_yellow", "flammables_cabinet", -(2 * CAB["half_w"] + CABINET_GAP),
         [("flammables_cabinet", (-0.0, 0.0), (0.52, 0.68))]),
        ("AcidsCabinet", "corrosive_blue", "corrosives_acids", 0.0,
         [("corrosives_acids", (0.0, -0.175), (0.52, 0.33)),
          ("corrosives_acids_oxidizing_tray", (0.0, 0.175), (0.52, 0.33))]),
        ("BasesCabinet", "corrosive_blue", "corrosives_bases", 2 * CAB["half_w"] + CABINET_GAP,
         [("corrosives_bases", (0.0, 0.0), (0.52, 0.68))]),
    ]
    for name, color, door_zone, cy, trays in cab_specs:
        path = f"/World/Storage/{name}"
        cab = add_ref(stage, path, url("cabinet"))
        pos = (cab_x, cy, -CAB["min_z"] + 0.001)
        set_xform(cab, pos, 180.0)
        # the articulation is fixed to the world by /cabinet/rootJoint (body0 = world): give it this pose
        rj = UsdPhysics.FixedJoint(stage.OverridePrim(f"{path}/rootJoint"))
        rj.CreateLocalPos0Attr().Set(Gf.Vec3f(*pos))
        rj.CreateLocalRot0Attr().Set(yaw_quat(180.0))
        for sub in CAB_RECOLOR:  # de-instance the panels so they can take a new colour
            p = stage.OverridePrim(f"{path}/{sub}")
            p.SetInstanceable(False)
            bind(p, M[color], stronger=True)
        for link, origin in DOOR_LINKS.items():  # zone sign on each door, parented to the door so it swings with it
            y0, y1 = DOOR_SPAN_Y[link]
            yc = (y0 + y1) / 2 - origin[1]
            zc = (DOOR_SPAN_Z[0] + DOOR_SPAN_Z[1]) / 2 - origin[2]
            textured_quad(stage, f"{path}/{link}/ZoneSign", (CAB["door_x"] - origin[0] + 0.007, yc, zc), 0.33, 0.11, +1,
                          sign_mat[door_zone])
        for zone_id, (lx, ly), size in trays:
            centre_local = ((CAB["inner_x"][0] + CAB["inner_x"][1]) / 2 + lx, ly, 0)
            wx, wy, _ = rotate_z(centre_local, 180.0)
            tray_with_zone(f"/World/Storage/{name}_Tray_{zone_id}", zone_id, (wx + pos[0], wy + pos[1]),
                           pos[2] + CAB["floor_z"] + 0.002, size, -1)

    # --- bottles on the bench
    rng = random.Random(args.seed)
    chems = list(chem["chemicals"])
    if not args.no_shuffle:
        rng.shuffle(chems)
    n_cols = math.ceil(len(chems) / len(BOTTLE_ROWS_X))
    slots = [(bx + rx, b["y"] + (c - (n_cols - 1) / 2) * BOTTLE_COL_PITCH)
             for rx in BOTTLE_ROWS_X for c in range(n_cols)]
    bottles = []
    for i, (c, (x, y)) in enumerate(zip(chems, slots)):
        kind = "solid_jar" if c["size"].strip().endswith("g") else "liquid_bottle"
        path = f"/World/BenchItems/Bottle_{i + 1:02d}"
        prim = add_ref(stage, path, url(kind))
        yaw = rng.uniform(-args.label_yaw_jitter, args.label_yaw_jitter)
        set_xform(prim, (x, y, b["top_z"] + 0.001), yaw)
        prim.GetVariantSets().GetVariantSet("PhysicsVariant").SetVariantSelection("RigidBody")
        size_val = float("".join(ch for ch in c["size"] if ch.isdigit() or ch == "."))
        mass = (0.05 + size_val / 1000.0) if kind == "solid_jar" else (0.10 + 0.5 * DENSITY.get(c["id"], 1.0))
        UsdPhysics.MassAPI.Apply(prim).CreateMassAttr(round(mass, 3))
        cx, r, z0, z1 = LABEL_FIT[kind]
        lm = preview_material(stage, f"{L}/Label_{c['id']}", (1, 1, 1), roughness=0.6,
                             texture=rel(os.path.join(PACK, "labels", c["id"] + ".png")))
        wrap_label(stage, f"{path}/GHSLabel", cx, r, z0, z1, 2.0, lm)
        if kind == "liquid_bottle" and "amber" in c.get("container", ""):
            body = stage.OverridePrim(f"{path}/naturalbostonroundbottle_a03_inst/SM_NaturalBostonRoundBottle_A03_01/"
                                      "M_NaturalBostonRoundBottle_A01_Body")
            bind(body, M["amber_glass"])
        bottles.append({"prim": path, "chemical_id": c["id"], "name": c["name"], "container": kind,
                        "mass_kg": round(mass, 3), "correct_zone": c["zone"], "storage_group": c["storage_group"],
                        "start_xy": [round(x, 3), round(y, 3)]})

    # --- overview camera
    cam = UsdGeom.Camera.Define(stage, "/World/Cameras/Overview")
    cam.CreateFocalLengthAttr(18.0)
    cam.CreateClippingRangeAttr(Gf.Vec2f(0.05, 100))
    eye, target = Gf.Vec3d(bench_front_x + AISLE * 0.7, 2.35, 2.25), Gf.Vec3d(bench_front_x + AISLE * 0.42, -0.7, 0.35)
    m = Gf.Matrix4d().SetLookAt(eye, target, Gf.Vec3d(0, 0, 1)).GetInverse()
    UsdGeom.Xformable(cam).AddTransformOp().Set(m)

    stage.GetRootLayer().customLayerData = {"task": "Task 5 - Organizing the workbench", "seed": args.seed}
    stage.Save()

    manifest = {"stage": os.path.basename(out), "assets_root": root, "seed": args.seed,
                "bottles": bottles, "zones": zones, "zone_descriptions": chem["zones"],
                "incompatible_groups": chem["incompatible_groups"],
                "robot_aisle": {"x": [round(bench_front_x, 3), round(bench_front_x + AISLE, 3)], "y": [-2.4, 1.4]}}
    with open(os.path.splitext(out)[0] + "_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {out}\nwrote {os.path.splitext(out)[0]}_manifest.json  ({len(bottles)} bottles, {sum(len(v) for v in zones.values())} zone volumes)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "scene", "task5_scene.usda"))
    ap.add_argument("--assets-root", default=DEFAULT_ASSETS_ROOT,
                    help="where Assets/... lives: NVIDIA's S3 (default), an omniverse:// server, or a local folder")
    ap.add_argument("--seed", type=int, default=0, help="shuffles which bottle sits where")
    ap.add_argument("--no-shuffle", action="store_true", help="bottles in chemicals.json order")
    ap.add_argument("--label-yaw-jitter", type=float, default=0.0,
                    help="random +/- degrees each bottle is turned (0 = every label faces the robot)")
    build(ap.parse_args())
