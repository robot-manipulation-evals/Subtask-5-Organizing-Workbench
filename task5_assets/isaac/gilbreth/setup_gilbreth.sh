#!/bin/bash
# One-time setup for running the Task 5 Isaac Sim scene on Purdue's Gilbreth cluster.
#   1. pulls the Isaac Sim container into scratch (~15 GB, takes a while)
#   2. downloads the scene's NVIDIA assets into scratch, so compute jobs need no internet
#   3. if a GPU is visible: smoke test (solved scene must score 12/12) and warms the shader cache
#
# Submit it as a job (recommended, login nodes limit long/large processes):
#   cd task5_assets/isaac/gilbreth && sbatch -A <your_account> setup_gilbreth.sh
# or run steps 1-2 directly on a login node:   bash setup_gilbreth.sh
#
#SBATCH --job-name=task5-setup
#SBATCH --account=CHANGE_ME
#SBATCH --partition=a10
#SBATCH --qos=standby
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gpus-per-node=1
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=%x-%j.out

set -euo pipefail
HERE="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
[[ -f "$HERE/config.sh" ]] || { echo "Run/submit this from task5_assets/isaac/gilbreth/ (config.sh not found in $HERE)" >&2; exit 1; }
source "$HERE/config.sh"
find_runtime

mkdir -p "$(dirname "$IMAGE")" "$ASSETS_DIR" "$CACHE" "$RUNS"
echo "WORK=$WORK"; echo "TASK5_DIR=$TASK5_DIR"

# ---- 1. container image
if [[ -s "$IMAGE" ]]; then
    echo "image exists: $IMAGE"
else
    export APPTAINER_CACHEDIR="$WORK/apptainer_cache" APPTAINER_TMPDIR="$WORK/apptainer_tmp"
    export SINGULARITY_CACHEDIR="$APPTAINER_CACHEDIR" SINGULARITY_TMPDIR="$APPTAINER_TMPDIR"
    mkdir -p "$APPTAINER_CACHEDIR" "$APPTAINER_TMPDIR"
    echo "pulling nvcr.io/nvidia/isaac-sim:$ISAAC_SIM_VERSION -> $IMAGE"
    "$RT" pull "$IMAGE" "docker://nvcr.io/nvidia/isaac-sim:$ISAAC_SIM_VERSION"
    rm -rf "$APPTAINER_TMPDIR"
fi

# ---- 2. scene assets (stdlib python; works with the system python3)
python3 "$TASK5_DIR/isaac/fetch_assets.py" "$ASSETS_DIR"

# ---- 3. smoke test on a GPU node
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
    T="$RUNS/setup_smoke_test"
    mkdir -p "$T"
    isaac_exec /isaac-sim/python.sh "$TASK5_DIR/isaac/build_task5_scene.py" \
        --assets-root "$ASSETS_DIR" --out "$T/task5_scene.usda" --seed 0
    isaac_exec /isaac-sim/python.sh "$TASK5_DIR/isaac/reference_solution.py" "$T/task5_scene.usda"
    isaac_exec /isaac-sim/python.sh "$TASK5_DIR/isaac/run_in_isaac.py" --headless --steps 120 \
        --stage "$T/task5_scene_solved.usda" --manifest "$T/task5_scene_manifest.json" \
        --snapshot "$T/snapshots" --json-out "$T/score.json"
    echo "smoke test done; expect 'Score: 12/12' above and images in $T/snapshots"
else
    echo "no GPU here: skipped the smoke test (submit with sbatch to run it)"
fi
