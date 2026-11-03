# Shared settings for the Gilbreth Slurm scripts. Sourced by setup_gilbreth.sh and task5_isaac.slurm.
# Any of these can be overridden from the environment, e.g.  WORK=/scratch/gilbreth/$USER/other sbatch task5_isaac.slurm

ISAAC_SIM_VERSION="${ISAAC_SIM_VERSION:-5.1.0}"

# Big, re-creatable files (container image ~15 GB, assets, caches, run outputs) live in scratch, not in $HOME.
WORK="${WORK:-${RCAC_SCRATCH:-/scratch/gilbreth/$USER}/task5}"
IMAGE="${IMAGE:-$WORK/images/isaac-sim_${ISAAC_SIM_VERSION}.sif}"
ASSETS_DIR="${ASSETS_DIR:-$WORK/isaac_assets}"   # local copy of the NVIDIA assets (see fetch_assets.py)
CACHE="${CACHE:-$WORK/isaac_cache}"              # Kit shader/compute caches + container $HOME; reused across jobs
RUNS="${RUNS:-$WORK/runs}"

# The task5_assets folder (this file is task5_assets/isaac/gilbreth/config.sh)
TASK5_DIR="${TASK5_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

find_runtime() {
    if command -v apptainer >/dev/null 2>&1; then RT=apptainer
    elif command -v singularity >/dev/null 2>&1; then RT=singularity
    else
        module load apptainer >/dev/null 2>&1 || module load singularity >/dev/null 2>&1 || true
        if command -v apptainer >/dev/null 2>&1; then RT=apptainer
        elif command -v singularity >/dev/null 2>&1; then RT=singularity
        else echo "ERROR: neither apptainer nor singularity found (try: module avail apptainer)" >&2; return 1
        fi
    fi
    echo "container runtime: $RT ($($RT --version))"
}

# Run a command inside the Isaac Sim container with the GPU, writable caches, and the needed folders mounted.
isaac_exec() {
    mkdir -p "$CACHE"/{home,kit-cache,kit-data,hub}
    # APPTAINERENV_/SINGULARITYENV_ variables pass through --cleanenv (and keep commas, e.g. CUDA_VISIBLE_DEVICES=0,1)
    local v
    for v in ACCEPT_EULA=Y PRIVACY_CONSENT=Y OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1 \
             "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}"; do
        export "APPTAINERENV_$v" "SINGULARITYENV_$v"
    done
    "$RT" exec --nv --cleanenv \
        --home "$CACHE/home" \
        --bind "$CACHE/kit-cache:/isaac-sim/kit/cache" \
        --bind "$CACHE/kit-data:/isaac-sim/kit/data" \
        --bind "$CACHE/hub:/var/cache/hub" \
        --bind "$WORK" \
        --bind "$TASK5_DIR" \
        "$IMAGE" "$@"
}
