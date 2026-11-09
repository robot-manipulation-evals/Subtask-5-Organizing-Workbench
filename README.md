# Store reagent bottles by hazard class

Four labelled reagent bottles stand on the bench in front of a row of six storage trays: INORGANIC ACIDS, FLAMMABLE,
TOXIC, OXIDIZERS, BASES and GENERAL. The robot has to read each bottle's label and put it in the tray where it
belongs. Two bottles are the classic storage mistakes: glacial acetic acid is an acid but is stored with the
flammables, and 30 % hydrogen peroxide is corrosive but is stored with the oxidizers. Each arm has two bottles and
three trays on its own side, and the layout is chosen so that the tray can only come from the label (see below).

## Run a trial
On a machine with the official simulator (the Robocurve Brev launchable, or `yam-isaac-lab-arena`'s `setup.sh`), with
a Dream API key in `~/.dreamlabs/credentials`, from this folder:

```bash
INSTRUCTION="Read the label on each bottle before you grasp it, then put each bottle in the storage tray where it belongs."

# Dream-1
inspect-robots run --embodiment yam_arena --policy dream \
  -E task=ghs_sort.py -E object_jitter=0 -E control_hz=20 -E cam_width=640 -E cam_height=360 \
  --instruction "$INSTRUCTION" --scorer task_score --max-steps 2400 --store-frames --log-dir ~/yam-eval/ghs-dream

# The scripted demo, which reaches full score
inspect-robots run --embodiment yam_arena --policy yam_scripted \
  -E task=ghs_sort.py -E object_jitter=0 -E control_hz=20 -E cam_width=640 -E cam_height=360 \
  --instruction "$INSTRUCTION" --scorer task_score --max-steps 600 --store-frames --log-dir ~/yam-eval/ghs-demo

# One MP4 per camera, next to each run's frames
for log in ~/yam-eval/ghs-*/*.json; do inspect-robots video "$log"; done
```

The run prints `task_score` at the end. `GHS_SORT_DEBUG=1` also prints, for each bottle, its offset from its correct
tray, its height above the tray floor and its tilt.

Camera size: Dream-1's adapter always sends it 320x176 frames, whatever `cam_width`/`cam_height` say; 640x360 is the
simulator's native render, so it only makes the recorded video sharper. The submitted demo video was recorded at
1280x720 with `record_hd.py`, which renders the same calibrated cameras at a higher resolution (same views):

```bash
RENDER_W=1280 RENDER_H=720 python record_hd.py run --embodiment yam_arena --policy yam_scripted \
  -E task=ghs_sort.py -E object_jitter=0 -E control_hz=20 -E cam_width=1280 -E cam_height=720 \
  --instruction "$INSTRUCTION" --scorer task_score --max-steps 600 --store-frames --log-dir ~/yam-eval/ghs-demo-hd
```

## Layout and where each bottle belongs
Trays 38 cm in front of the arm bases, bottles 22 cm; y is across the table, + to the robot's left.

| Tray (sign) | y | Reached by |
|---|---|---|
| INORGANIC ACIDS (blue, GHS05) | +31 cm | left arm |
| FLAMMABLE (yellow, GHS02) | +19 cm | left arm |
| TOXIC (white, GHS06) | +7 cm | left arm |
| OXIDIZERS (white, GHS03) | -7 cm | right arm |
| BASES (blue, GHS05) | -19 cm | right arm |
| GENERAL (grey, no pictogram) | -31 cm | right arm |

| Bottle | Starts at y | Correct tray | Why |
|---|---|---|---|
| Acetic acid, glacial | +27 cm | FLAMMABLE | flammable organic acid (GHS02, GHS05); kept away from inorganic and oxidizing acids |
| Hydrochloric acid 37 % | +10 cm | INORGANIC ACIDS | inorganic acid (GHS05, GHS07) |
| Ammonium hydroxide 28 % | -10 cm | BASES | base (GHS05, GHS07, GHS09) |
| Hydrogen peroxide 30 % | -27 cm | OXIDIZERS | oxidizer, kept away from flammables and organics (label shows GHS05, GHS07) |

These follow standard chemical-storage segregation (flammables, inorganic acids, bases, oxidizers, toxics kept
apart). TOXIC and GENERAL are distractors: no bottle belongs there.

Each arm reaches only its own side, so each bottle has three possible trays. The layout was chosen by search so the
labels matter: the nearest tray is wrong for every bottle, and no rule that ignores the labels (every bottle in its
nearest, second-nearest or farthest tray; in its side's outer, middle or inner tray; or each side's two bottles
swapped) gets more than two of the four right. With four bottles and three trays a side some such rule always gets
two; a random choice gets each bottle right one time in three.

## Scoring
A bottle counts when, at the end, it stands upright (tilted at most 20 degrees) inside its correct tray: its centre
within 3.75 cm of the tray's centre along both table axes, and its bottom within 1.5 cm of the tray floor (not on a
rim). 0.25 per bottle that counts. Any bottle tilted more than 20 degrees anywhere, in a tray or not, is a spill and
scores the trial 0. The trial ends at 1.0 once all four count and are still (under 1 cm/s) for 1 s.

On a real bench: a photo from above shows which tray each bottle is in, and a ruler from the tray wall checks the
centre; a bottle lying down is visible in the same photo.

`test_ghs_sort.py` checks the scoring (start 0, all sorted 1.0, a quarter per bottle, the label-blind rules above
at most 0.5 and the nearest tray 0, a tipped bottle 0, a bottle on a rim 0) and that the demo stays within the joint
limits, without the simulator:
`python -m pytest -q test_ghs_sort.py`.

## Runtime and seeds
- The scripted demo sorts all four bottles in 24 s of simulated time (two bottles per arm, both arms at once); the
  trial then ends with success. Before each grasp it holds the wrist camera over the bottle for 1 s, looking at the
  label from about 25 degrees off vertical, the way a policy following the instruction would check it. On an L40S
  the demo run takes about 3 minutes including Isaac Sim's start, and a 2,400-step Dream-1 run about 7 minutes.
- One fixed layout: `-E object_jitter=0`, so the seed doesn't change the start.

## Files
- `ghs_sort.py`: the task file (objects, scoring, demo).
- `assets/`: the four bottles and six trays as USD, with their textures. Each bottle references NVIDIA's SimReady
  Boston round bottle (`naturalbostonroundbottle_a03`, streamed from NVIDIA's public asset server) scaled to
  100 mL, with a label mesh wrapped around its straight wall. The task file registers these files as Arena library
  assets, so the official stack runs it unchanged.
- `record_hd.py`: renders the cameras at a higher resolution for review videos (scripted demo only).
- `test_ghs_sort.py`: offline checks.

The GHS pictograms on the labels and signs are the official UNECE artwork, from the MIT-licensed npm package
`@ghs-hazard-pictograms/assets`.
