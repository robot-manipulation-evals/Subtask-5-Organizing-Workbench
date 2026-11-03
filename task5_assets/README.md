# Task 5 – Organizing the workbench: asset pack

Scene from *Competition Designs*, Task 5: 8–12 reagent bottles on the bench. The robot reads each GHS label, then stores the bottle in the matching cabinet or shelf zone.

## What's in this folder (ready to use)

| Path | What it is |
|---|---|
| `labels/<chemical>.png` | 12 GHS bottle labels, 1600×800 px (2:1). Map onto the front of a 500 mL bottle, or print at 100 × 50 mm (~400 dpi) for real bottles. |
| `zone_signs/<zone>.png` | 7 storage-zone signs, 1200×400 px, for the cabinet doors, trays and shelves. |
| `pictograms/GHS01–09.{svg,png}` | The nine official GHS pictograms, from the MIT-licensed npm package `@ghs-hazard-pictograms/assets` (artwork originates from UNECE). |
| `chemicals.json` | Ground truth: name, CAS, signal word, pictograms, H-statements, barcode (catalog no.), storage group, correct zone, incompatible pairs. |
| `tools/make_labels.js` | Generator. Add a chemical to `chemicals.json`, then run `node tools/make_labels.js`. |
| `previews/` | Contact sheets. |

Each label has a real Code 128 barcode (`BR-1001` and up) and an empty "Received:" box, so the same bottles also work for Task 8 (inventory, date stickers, scanning). The brand "Benchmark Reagents" is made up on purpose.

### Chemical set and correct zones

| Bottle | Pictograms | Zone |
|---|---|---|
| Sulfuric acid 98 % | GHS05 | Corrosives – acids |
| Hydrochloric acid 37 % | GHS05, 07 | Corrosives – acids |
| Nitric acid 70 % | GHS03, 05, 06 | Corrosives – **oxidizing-acid tray** |
| Sodium hydroxide | GHS05 | Corrosives – bases |
| Ammonium hydroxide 28 % | GHS05, 07, 09 | Corrosives – bases |
| Acetic acid, glacial | GHS02, 05 | **Flammables** (trick: organic acid) |
| Ethanol, Acetone | GHS02, 07 | Flammables |
| Methanol | GHS02, 06, 08 | Flammables (toxic, but flammability decides storage) |
| Hydrogen peroxide 30 % | GHS05, 07 | **Oxidizers** (trick: no GHS03 on a 30 % label) |
| Sodium azide | GHS06, 08, 09 | Toxics |
| Sodium chloride | none | General shelf |

GHS data follows typical supplier SDS classifications. Check the SDS for the exact products you use.

## Isaac Sim scene (`isaac/`)

```
isaac/
  build_task5_scene.py     builds the scene → scene/task5_scene.usda + scene/task5_scene_manifest.json
  reference_solution.py    every bottle in its correct tray → scene/task5_scene_solved.usda (+ _solution.json target poses)
  score_task5.py           scores any stage (saved file or live Isaac stage) against the manifest
  run_in_isaac.py          opens a stage in Isaac Sim, runs physics, prints the score; --snapshot / --json-out (hook your policy in here)
  asset_list.py            the NVIDIA assets the scene uses (shared by the build and fetch scripts)
  fetch_assets.py          downloads those assets for offline use:  python3 fetch_assets.py <dir>  then  --assets-root <dir>
  gilbreth/                Slurm + Apptainer scripts for Purdue's Gilbreth cluster (see below)
  scene/                   pre-built with seed 0 (assets stream from NVIDIA's server)
```

**Layout:** a two-wall lab. The robot works in a 1.3 m aisle between the walls.
- **Wall A:** a procedural chemistry bench (black epoxy top at 0.90 m, steel frame, lower shelf, backsplash) holding the 12 labelled bottles in 2 rows, plus a chrome wire shelf with three labelled trays: OXIDIZERS, TOXIC, GENERAL.
- **Wall B:** three articulated Sektion cabinets: FLAMMABLE (yellow), CORROSIVE – ACIDS (blue, with a separate OXIDIZING ACIDS tray inside) and CORROSIVE – BASES (blue). Zone signs are on the doors and swing with them, and every tray has its own label.

**Details:**
- Bottles are rigid bodies with filled masses (for example, H₂SO₄ is 1.02 kg and the sodium azide jar is 0.15 kg).
- Nitric acid and sodium azide are in amber bottles.
- Labels are textured meshes wrapped on each bottle, so they move with it.
- Bottle names are neutral (`Bottle_01…12`), so the scene graph doesn't give away the answer. The mapping is in the manifest.

**Use it:**
```bash
python isaac/build_task5_scene.py --seed 3 --label-yaw-jitter 60   # new shuffle, labels partly turned away
python isaac/reference_solution.py isaac/scene/task5_scene.usda
python isaac/score_task5.py isaac/scene/task5_scene_solved.usda     # → 12/12
./python.sh isaac/run_in_isaac.py --stage isaac/scene/task5_scene.usda   # from the Isaac Sim install folder
```
- The scripts need only `pxr`: either Isaac Sim's `./python.sh`, or any Python with `pip install usd-core`.
- Outside Isaac Sim, plain `usd-core` prints "Could not open asset @https:…" warnings because it can't download from https. This is expected: Isaac Sim streams those assets.
- To work offline, download the Isaac Sim asset pack and pass `--assets-root /path/to/pack`.
- All layout numbers (aisle width, bench size, shelf position, bottle spacing) are constants at the top of `build_task5_scene.py`.

**What's been checked (outside Isaac Sim, using a local copy of the assets):**
- The composed geometry: bottles on the bench with no overlaps, trays inside the cabinet compartments, signs on the doors, the cabinet recoloring, the fixed-base pose, and amber glass.
- The scorer: 0/12 on the start scene, 12/12 on the solved scene, and it catches wrong zones, incompatible pairs and tipped bottles.
- Rough WebGL previews are in `previews/isaac_*.png`. They are not Isaac renders.

**Not yet run in Isaac Sim:** PhysX behavior (bottles settling, door joints with the cabinet rotated 180°), RTX lighting and how the MDL materials look, and `run_in_isaac.py`. Your first test: open `scene/task5_scene_solved.usda`, press Play, and check that the bottles stay upright and the doors open.

## Running on Purdue Gilbreth (Slurm + Apptainer): `isaac/gilbreth/`

Isaac Sim needs a GPU with RT cores. On Gilbreth that is the **A10 partition**. The V100, A100 and H100 partitions are not supported by Isaac Sim's renderer. The scripts run the official `nvcr.io/nvidia/isaac-sim:5.1.0` container through Apptainer and keep everything big in scratch (`$RCAC_SCRATCH/task5`, override with `WORK=...`).

| File | What it does |
|---|---|
| `config.sh` | shared paths, plus the `isaac_exec` wrapper (GPU, writable Kit caches, folder mounts, EULA env vars) |
| `setup_gilbreth.sh` | **run once**: pulls the container (~15 GB) and downloads the scene's assets (82 MB, so compute nodes need no internet). On a GPU node it also runs a smoke test that must print 12/12, which warms the shader cache. |
| `task5_isaac.slurm` | the job: builds the scene for a seed → runs it headless → saves overview-camera snapshots, `score.json` and `result.usda` to `$WORK/runs/<job>_seed<N>/` |

```bash
# find your account name first
slist
cd task5_assets/isaac/gilbreth
sbatch -A <account> setup_gilbreth.sh                  # once; check setup-<jobid>.out for "Score: 12/12"
sbatch -A <account> task5_isaac.slurm                  # seed 0
sbatch -A <account> --array=0-9 task5_isaac.slurm      # 10 shuffled scenes
sbatch -A <account> --export=ALL,MODE=solved task5_isaac.slurm          # oracle check
sbatch -A <account> --export=ALL,SEED=3,JITTER=60,STEPS=600 task5_isaac.slurm
```

- **Defaults:** `--partition=a10 --qos=standby --gpus-per-node=1 --cpus-per-task=8 --mem=64G --time=01:00:00`. Gilbreth rejects jobs without an account, partition and `--mem`. Use `-q normal` if your group owns A10 nodes. `showpartitions` lists what you can use.
- **Your robot policy** goes in the marked loop in `run_in_isaac.py`. The Slurm job already passes `--headless`.
- **Snapshots** come from Replicator. If that fails, the run prints `snapshot failed:` and still scores.

**Checked here:**
- Shellcheck is clean.
- `fetch_assets.py` downloads everything the scene needs. I checked with USD dependency analysis that nothing outside the folder is required.
- A dry run of the whole Slurm flow with a fake `apptainer` gave the right seeds, array naming, mounts and env, and scored 0/12 (start) and 12/12 (solved).

**Not checked (no Gilbreth access):**
- The real Apptainer and Isaac Sim run: driver version, Vulkan inside the container, Replicator snapshots.
- The A10 partition's current limits. Older RCAC pages say standby is limited to 4 h.

**If it fails:**
- **Vulkan or GPU errors:** compare `nvidia-smi`'s driver with the Isaac Sim 5.1 requirements. Then try replacing `--nv` with `--nvccli` in `config.sh`.
- **Pull asks for credentials:** run `apptainer remote login --username '$oauthtoken' docker://nvcr.io` with your NGC API key.
- **First run is slow:** Kit compiles its shaders once into `$WORK/isaac_cache`, and later jobs reuse them.

## Isaac Sim: recommended assets (native USD, physics already set up)

All of these load directly from NVIDIA's public asset server. In Isaac Sim, open the Content browser at the path below, or reference the URL in your stage. Prefix: `https://omniverse-content-production.s3-us-west-2.amazonaws.com/`

| Scene item | Asset | Size (m) | Notes |
|---|---|---|---|
| Liquid reagent bottles (500 mL) | `Assets/simready_content/common_assets/props/naturalbostonroundbottle_a03/naturalbostonroundbottle_a03.usd` | 0.09 × 0.09 × 0.19 | Boston round, the classic reagent bottle. Rigid body, semantic class "bottle". a01/a02 are smaller sizes. |
| Solid reagent jars (NaOH, NaCl, NaN₃) | `.../props/whitepackerbottle_a04/whitepackerbottle_a04.usd` | 0.08 × 0.08 × 0.14 | Wide-mouth HDPE packer bottle. a01–a03 are smaller. |
| Solvent jugs (optional, larger) | `.../props/fstylejug_a01/fstylejug_a01.usd` | 0.06 × 0.14 × 0.19 | F-style jug |
| **Flammable and corrosives cabinets** | `Assets/Isaac/5.1/Isaac/Props/Sektion_Cabinet/sektion_cabinet_instanceable.usd` | 0.67 × 0.76 × 0.79 | **Articulated**: 2 hinged doors (0 to −90°) and 2 drawers (0–0.40 m). This is Isaac Lab's standard cabinet. Use two copies: recolor one yellow (flammables) and one blue (corrosives), then put `zone_signs/*.png` on the doors. |
| Cabinet look-alike (doors do not open) | `.../props/contemporary_lockedstorage/contemporary_lockedstorage.usd` | 0.60 × 0.87 × 0.66 | Two-door metal undercounter cabinet. Single rigid body only. |
| General chemical shelf | `.../props/wireshelving_a01/wireshelving_a01.usd` (or `_a05`, 1.22 m wide) | 0.46 × 0.77 × 0.87 | Chrome wire shelving, the standard in labs. Steel options: `openindustrialsteelshelving_a01`, `heavydutysteelshelving_a01`. |
| Secondary containment trays | `.../props/container_h01/container_h01.usd`, `container_a01` | 0.61 × 0.41 × 0.25 | Use inside the cabinets to separate acids, oxidizing acids and bases. |

Label sizing: on the Boston round a03 (90 mm diameter), a 140 × 70 mm label covers half the circumference. On the packer a04 (80 mm), use 120 × 60 mm. Both keep the 2:1 ratio of `labels/*.png`.

The license is NVIDIA's Omniverse/Isaac Sim asset terms (free to use with Isaac Sim). SimReady thumbnails and metadata: `Assets/simready_content/asset_info.json`.

### LabUtopia instruments (for the other tasks)
The LabUtopia dataset (https://huggingface.co/datasets/Ruinwalker/LabUtopia-Dataset, **CC-BY-NC-4.0**, not gated) has 95 USD instruments made for Isaac Sim. It has no reagent bottles or safety cabinets, but it covers your other tasks: `Centrifuge_01–03`, `ElectronicScale_01–05`, `pHMeter`, `Incubator_01–02`, `BiologicalSafetyCabinets`, `FumeHood_01–02`, `VortexOscillator`, `Microscope`, `TubeRack`, `Pipette`, `HeatingPlate`, plus beakers and flasks, and 92 complete lab room scenes. The non-commercial license is fine for a research benchmark.

## 3D models found online (Sketchfab, CC-BY, glTF/FBX)

Use these if you want real glass bottles instead of the HDPE SimReady ones. Sketchfab downloads need a free Sketchfab account. Convert GLB to USD in Isaac Sim (File → Import, or the Asset Converter extension). All of the models below are confirmed CC Attribution through the Sketchfab API:
- **Cabinet for storing flammable liquids** by GokouFG (4.2k faces, game-ready). https://sketchfab.com/3d-models/17be9697ac7d449ba8dd3c4b13a5e05c
- **Laboratory Cabinet Storage** by nakedsingularity (576 faces, real-world scale, separate parts for door animation). https://sketchfab.com/3d-models/6c5d3bde09dd4f55ad973d8429441190
- **Laboratory Chemical Storage Free** by AMMediaGames (29k faces). https://sketchfab.com/3d-models/64133eefb77f4af7994e207badd7b1ff
- **Lab Shelf & Utility Cart** by nakedsingularity (real-world scale). https://sketchfab.com/3d-models/f0a63ba527db45be91b5520ae4470dbd
- **Chemical Bottles** by AppleCrumbleTea (8.9k faces). https://sketchfab.com/3d-models/4224d59cf12c4cbca303cce699a7aab0
- **Copper Oxide Powder Bottle** by AmirulIqwan (2k faces, powder jar). https://sketchfab.com/3d-models/f1cf4cafa05f4e268acde5645e8296f1
- **Container for chemicals** by bytephunk (4k faces, threaded spout). https://sketchfab.com/3d-models/090cdf8f3d414ecc87725122997fc80a
- **Emergency Shower with Eye Wash** by cesar.seidel (set dressing). https://sketchfab.com/3d-models/61a536cf4e1f4995a8128863f8994e3e

## Earlier web-search results

These were found through web search before Sketchfab and Hugging Face were reachable. **Check each license on its page before you download.**

### Reagent bottles (none come with GHS labels; apply `labels/*.png`)
- **Chemistry bottle** by akenoq: free, CC-BY, ~320 tris, a good physics/sim proxy. https://sketchfab.com/3d-models/chemistry-bottle-617aa06ab1274fd78275a573c963e893
- **Assorted Bottle – Chemical Lab** by kane_sk06: free, CC-BY, ~286k tris (decimate for sim). https://sketchfab.com/3d-models/assorted-bottle-chemical-lab-286cf37a56ac46e499f2e743fc1875f5
- **Lab/medicine bottle** by Sousinho: free. https://sketchfab.com/3d-models/labmedicine-bottle-90d4bead93af4c69897d39688164d567
- **Chemistry Glassware** by maxdragonn: free, CC-BY (beakers/flasks for bench clutter). https://sketchfab.com/3d-models/chemistry-glassware-b8594f7dc7e8442dbaaae7a11da4a962
- Paid, higher quality: **Chemical Reagent Substance Bottles** (5 plastic PBR bottles, real-world scale) https://sketchfab.com/3d-models/chemical-reagent-substance-bottles-plastic-pbr-4e83fe64813142ebb31287463743bc25 ; **Laboratory square glass bottle** (blank-label texture variants) https://www.cgtrader.com/3d-models/science/laboratory/laboratory-square-glass-bottle

### Flammable and corrosives cabinets
No good free, sim-ready yellow flammable cabinet or blue corrosives cabinet turned up. Options:
- **Recommended for a robot sim: PartNet-Mobility (SAPIEN)**. 345 articulated cabinets, already as URDF with hinged doors and joint limits. Recolor one yellow and one blue, then put the zone signs on the doors. Gated access: https://huggingface.co/datasets/sapien-sim/PartNetMobility
- Low-poly placeholders: 3D Warehouse "Flammable Cabinet" https://3dwarehouse.sketchup.com/model/u5170d17b-52e8-43c7-b45a-e481fbeabc65/Flammable-Cabinet ; Coohom low-poly chemical storage cabinet https://www.coohom.com/in/3d-models/-/low-poly-chemical-storage-cabinet-3d-model-mdtl~3FO49RU6R6D0 ; Homestyler hazardous-goods cabinet (red, recolor) https://www.homestyler.com/en/3d-models/red-metal-industrial-hazardous-goods-storage-cabinet-3d-model-60545856
- Real-size reference for modelling: a 45-gal flammable cabinet is ~43 × 18 × 65 in (W × D × H), with 2 doors and 2 adjustable shelves.

### Shelving
- **CC0 – Shelf 5** (CGTrader, free, CC0) https://www.cgtrader.com/free-3d-models/furniture/cabinet/cc0-shelf-5
- Coohom industrial metal shelving (free) https://www.coohom.com/in/3d-models/Shelf/industrial-metal-shelving-unit-3d-model-mdtl~3FO4GSQUE2KS
- Sketchfab collection "Shelving and Cabinets" https://sketchfab.com/jimbogies/collections/shelving-and-cabinets-5e46f27590a14026aa8ae5088b08e7a7

### Whole lab scene
- **LabUtopia** (NeurIPS 2025, MIT code): Isaac Sim 5.1 chemistry-lab USD scenes (benches, beakers, flasks, instruments) with a Franka robot. It has no reagent bottles or safety cabinets, but works as the room and bench around them. https://github.com/Rui-li023/LabUtopia
