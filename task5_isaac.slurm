#!/bin/bash
# Task 5 (chemical storage) in Isaac Sim on Gilbreth: build a scene, run it headless, snapshot + score.
#
# Isaac Sim needs an RT-core (RTX) GPU. On Gilbreth that is the A10 partition. The V100, A100 and H100
# partitions have no RT cores, so Isaac Sim's renderer is not supported there.
#
#   cd task5_assets/isaac/gilbreth
#   sbatch -A <your_account> task5_isaac.slurm                     # seed 0, starting scene
#   sbatch -A <your_account> --array=0-9 task5_isaac.slurm         # 10 seeds (seed = array index)
#   sbatch -A <your_account> --export=ALL,MODE=solved task5_isaac.slurm          # oracle check, expect 12/12
#   sbatch -A <your_account> --export=ALL,SEED=3,JITTER=60,STEPS=600 task5_isaac.slurm
#
# Options (environment variables): SEED, MODE=start|solved, STEPS (sim frames, 60 per second),
# JITTER (label yaw jitter in degrees), BUILD_ARGS (extra args for build_task5_scene.py).
# Outputs: $WORK/runs/<jobid>[_<arrayidx>]_seed<SEED>/ → scene, manifest, snapshots/, score.json, result.usda
#
#SBATCH --job-name=task5-isaac
#SBATCH --account=CHANGE_ME
#SBATCH --partition=a10
#SBATCH --qos=standby
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gpus-per-node=1
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=%x-%j.out

set -euo pipefail
HERE="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
[[ -f "$HERE/config.sh" ]] || { echo "Submit this from task5_assets/isaac/gilbreth/ (config.sh not found in $HERE)" >&2; exit 1; }
source "$HERE/config.sh"
find_runtime

SEED="${SEED:-${SLURM_ARRAY_TASK_ID:-0}}"
MODE="${MODE:-start}"
STEPS="${STEPS:-240}"
JITTER="${JITTER:-0}"
BUILD_ARGS="${BUILD_ARGS:-}"

[[ -s "$IMAGE" ]] || { echo "ERROR: $IMAGE missing. Run setup_gilbreth.sh first." >&2; exit 1; }
[[ -d "$ASSETS_DIR/Assets" ]] || { echo "ERROR: $ASSETS_DIR missing. Run setup_gilbreth.sh first." >&2; exit 1; }

JOB_TAG="${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-local}}${SLURM_ARRAY_TASK_ID:+_$SLURM_ARRAY_TASK_ID}"
RUN="$RUNS/${JOB_TAG}_seed${SEED}"
mkdir -p "$RUN"
echo "host=$(hostname) job=$JOB_TAG seed=$SEED mode=$MODE steps=$STEPS run=$RUN"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv || true

# 1. build the scene for this seed (pure USD, takes seconds)
# shellcheck disable=SC2086  # BUILD_ARGS is intentionally word-split
isaac_exec /isaac-sim/python.sh "$TASK5_DIR/isaac/build_task5_scene.py" \
    --assets-root "$ASSETS_DIR" --out "$RUN/task5_scene.usda" \
    --seed "$SEED" --label-yaw-jitter "$JITTER" $BUILD_ARGS

STAGE="$RUN/task5_scene.usda"
if [[ "$MODE" == "solved" ]]; then
    isaac_exec /isaac-sim/python.sh "$TASK5_DIR/isaac/reference_solution.py" "$STAGE"
    STAGE="$RUN/task5_scene_solved.usda"
fi

# 2. simulate headless (your policy goes in run_in_isaac.py), snapshot the overview camera, score
isaac_exec /isaac-sim/python.sh "$TASK5_DIR/isaac/run_in_isaac.py" --headless \
    --stage "$STAGE" --manifest "$RUN/task5_scene_manifest.json" --steps "$STEPS" \
    --snapshot "$RUN/snapshots" --json-out "$RUN/score.json" --save "$RUN/result.usda"

echo "done: $RUN"
