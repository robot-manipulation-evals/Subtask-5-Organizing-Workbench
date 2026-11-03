"""
Open the Task 5 scene in Isaac Sim, let physics settle, and print the score.
Run it with Isaac Sim's python (5.x), on a workstation or in the container on a cluster:

  ./python.sh <path>/task5_assets/isaac/run_in_isaac.py --stage <path>/task5_assets/isaac/scene/task5_scene.usda
  ./python.sh .../run_in_isaac.py --stage .../scene/task5_scene_solved.usda --headless   # should print 12/12
  ./python.sh .../run_in_isaac.py --stage ... --headless --snapshot out/ --json-out out/score.json

Hook your robot policy into the marked loop. Use --save to write the settled stage, then score it offline.
"""
import argparse
import json
import os
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--stage", required=True)
ap.add_argument("--manifest")
ap.add_argument("--steps", type=int, default=240, help="simulation frames to run (~4 s at 60 Hz)")
ap.add_argument("--headless", action="store_true")
ap.add_argument("--save", help="export the stage after the run, e.g. run_result.usda")
ap.add_argument("--snapshot", help="folder for RGB images from /World/Cameras/Overview (before and after the run)")
ap.add_argument("--json-out", help="write the score as JSON here")
args = ap.parse_args()

from isaacsim import SimulationApp  # noqa: E402  (must come before any omni import)

app = SimulationApp({"headless": args.headless, "width": 1280, "height": 720})

import omni.timeline  # noqa: E402
import omni.usd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_task5  # noqa: E402

stage_path = os.path.abspath(args.stage)
ctx = omni.usd.get_context()
ctx.open_stage(stage_path)
while ctx.get_stage_loading_status()[2] > 0:  # wait for assets to load
    app.update()
for _ in range(10):
    app.update()


def snapshot(tag):
    """Best-effort RGB capture with Replicator; never aborts the run."""
    if not args.snapshot:
        return
    try:
        import omni.replicator.core as rep
        out = os.path.join(os.path.abspath(args.snapshot), tag)
        rp = rep.create.render_product("/World/Cameras/Overview", (1280, 720))
        writer = rep.WriterRegistry.get("BasicWriter")
        writer.initialize(output_dir=out, rgb=True)
        writer.attach([rp])
        for _ in range(3):  # let the RTX renderer converge a little
            rep.orchestrator.step()
        writer.detach()
        rp.destroy()
        print("snapshot ->", out)
    except Exception as e:  # noqa: BLE001
        print("snapshot failed:", repr(e))


snapshot("before")
timeline = omni.timeline.get_timeline_interface()
timeline.play()
for _ in range(args.steps):
    # ---- your robot / policy step goes here ----
    app.update()
timeline.pause()
snapshot("after")

man_path = args.manifest or os.path.splitext(stage_path.replace("_solved", ""))[0] + "_manifest.json"
result = score_task5.score(ctx.get_stage(), json.load(open(man_path)))
print(score_task5.report(result))
if args.json_out:
    os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
    with open(args.json_out, "w") as f:
        json.dump(result, f, indent=2)
if args.save:
    ctx.get_stage().Export(os.path.abspath(args.save))
    print("saved", args.save)
timeline.stop()
app.close()
