"""Isaac Sim / SimReady assets used by the Task 5 scene (shared by build_task5_scene.py and fetch_assets.py)."""

DEFAULT_ASSETS_ROOT = "https://omniverse-content-production.s3-us-west-2.amazonaws.com"
SIMREADY = "Assets/simready_content/common_assets/props"
ASSETS = {
    "liquid_bottle": f"{SIMREADY}/naturalbostonroundbottle_a03/naturalbostonroundbottle_a03.usd",  # 90 mm x 191 mm, ~500 mL
    "solid_jar": f"{SIMREADY}/whitepackerbottle_a04/whitepackerbottle_a04.usd",                    # 80 mm x 143 mm
    "shelf": f"{SIMREADY}/wireshelving_a05/wireshelving_a05.usd",                                  # 0.62 x 1.22 x 0.87 m
    "cabinet": "Assets/Isaac/5.1/Isaac/Props/Sektion_Cabinet/sektion_cabinet_instanceable.usd",     # 0.67 x 0.76 x 0.79 m
}

# Shared files the assets above pull in from outside their own folders (found with UsdUtils.ComputeAllDependencies):
# the SimReady props' RigidBody variant references physics materials (friction/restitution) here.
EXTRA_FOLDERS = ["Assets/simready_content/materials/physics/"]
