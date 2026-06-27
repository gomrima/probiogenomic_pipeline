#!/usr/bin/env bash
set -euo pipefail

# ===========================================================================
# Module 06 ISEScan mobilome - resume-aware, progress-visible launcher.
#
# Aligned with the corrected reference launcher (2026-05-30):
#   * No "conda run" wrapper: it buffered the child output and made an active
#     run look frozen. We call the environment python directly, unbuffered,
#     with the environment bin on PATH so isescan.py and its dependencies
#     (FragGeneScan, hmmer, blast) resolve. Output is line-buffered via stdbuf.
#   * Default threads = 2 (recommended on 8 GB RAM); the python caps at 4.
#   * The module checkpoint is created only when every genome produced a valid
#     result (python exit 0). On exit 3 (full pass, some genomes failed/timed
#     out) no checkpoint is created by default, so a relaunch reuses the valid
#     genomes and retries only the failed ones. Set ALLOW_PARTIAL=1 to accept a
#     partial result and create the checkpoint anyway.
#   * The Excel workbook is built last from the finalized TSVs and never blocks
#     the pipeline-critical TSV outputs. Set MAKE_XLSX=0 to skip it.
#
# Optional environment overrides (all have safe defaults):
#   ISESCAN_THREADS    threads for ISEScan (default = THREADS or 2; capped at 4)
#   PER_GENOME_TIMEOUT seconds per genome before ISEScan is killed (default 7200; 0 disables)
#   HEARTBEAT_SECONDS  liveness message interval while ISEScan runs (default 120; 0 disables)
#   MIN_CSV_SIZE       minimum bytes for a CSV to be considered reusable (default 1)
#   KEEP_STALE_BACKUP  1 = rename stale per-genome dirs instead of deleting them
#   FORCE_RERUN        1 = ignore existing CSVs and rerun every genome
#   PLAN_ONLY          1 = only classify genomes (reuse vs rerun), no ISEScan
#   MAKE_XLSX          0 = skip the optional Excel workbook
#   ALLOW_PARTIAL      1 = create the checkpoint even if some genomes failed
# ===========================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"

STEP_ID="06_run_isescan_mobilome"
SCRIPT="$SCRIPT_DIR/06_isescan_mobilome.py"
MANIFEST="$PIPE_ROOT/work/manifest/input_manifest.tsv"
RAW_ROOT="$PIPE_ROOT/work/intermediate/mobilome/isescan_raw"
TSV_DIR="$PIPE_ROOT/results/tsv/mobilome"
XLSX_DIR="$PIPE_ROOT/results/xlsx/mobilome"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/06_run_isescan_mobilome.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/06_run_isescan_mobilome.done"

# Optional overrides. ISESCAN_THREADS falls back to the pipeline-wide THREADS
# (default 2). The python script caps the effective thread count at 4.
ISESCAN_THREADS="${ISESCAN_THREADS:-${THREADS:-2}}"
PER_GENOME_TIMEOUT="${PER_GENOME_TIMEOUT:-7200}"
HEARTBEAT_SECONDS="${HEARTBEAT_SECONDS:-120}"
MIN_CSV_SIZE="${MIN_CSV_SIZE:-1}"
KEEP_STALE_BACKUP="${KEEP_STALE_BACKUP:-0}"
FORCE_RERUN="${FORCE_RERUN:-0}"
PLAN_ONLY="${PLAN_ONLY:-0}"
MAKE_XLSX="${MAKE_XLSX:-1}"
ALLOW_PARTIAL="${ALLOW_PARTIAL:-0}"

mkdir -p "$RAW_ROOT" "$TSV_DIR" "$XLSX_DIR" "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"

# Make ISEScan and its dependencies resolvable when calling the environment
# python directly (no conda run), and keep thread libraries from oversubscribing.
export TMPDIR="$TMPDIR_PATH"
export PIPE_ROOT
export PATH="$CORE_ENV/bin:$PATH"
export CONDA_PREFIX="$CORE_ENV"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="$ISESCAN_THREADS"
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# Skip if already complete (plan-only never short-circuits and never checkpoints).
if [[ "$PLAN_ONLY" != "1" ]] && step_checkpoint_valid "$CHECKPOINT_FILE"; then
    log_info "Checkpoint exists: $CHECKPOINT_FILE"
    log_info "Module 06 already completed. Skipping (remove the checkpoint to rebuild)."
    exit 0
fi

require_file "$SCRIPT"
require_file "$MANIFEST"

PYBIN="$CORE_ENV/bin/python"

PY_ARGS=(
    --manifest "$MANIFEST"
    --raw-root "$RAW_ROOT"
    --output-tsv-dir "$TSV_DIR"
    --output-xlsx-dir "$XLSX_DIR"
    --threads "$ISESCAN_THREADS"
    --min-csv-size "$MIN_CSV_SIZE"
    --per-genome-timeout "$PER_GENOME_TIMEOUT"
    --heartbeat-seconds "$HEARTBEAT_SECONDS"
)
if [[ "$KEEP_STALE_BACKUP" == "1" ]]; then PY_ARGS+=( --keep-stale-backup ); fi
if [[ "$FORCE_RERUN" == "1" ]]; then PY_ARGS+=( --force-rerun ); fi
if [[ "$PLAN_ONLY" == "1" ]]; then PY_ARGS+=( --plan-only ); fi
if [[ "$MAKE_XLSX" != "1" ]]; then PY_ARGS+=( --no-xlsx ); fi

log_info "Starting $STEP_ID (threads=$ISESCAN_THREADS, timeout=${PER_GENOME_TIMEOUT}s, heartbeat=${HEARTBEAT_SECONDS}s)" | tee -a "$LOG_FILE"

# Run the python module directly (no conda run), unbuffered and line-buffered,
# capturing its exit code through PIPESTATUS even though tee succeeds.
set +e
if [[ -x "$PYBIN" ]]; then
    stdbuf -oL -eL "$PYBIN" -u "$SCRIPT" "${PY_ARGS[@]}" 2>&1 | tee -a "$LOG_FILE"
    rc=${PIPESTATUS[0]}
else
    log_warn "Env python not executable at $PYBIN; falling back to conda run --no-capture-output."
    conda run --no-capture-output -p "$CORE_ENV" python -u "$SCRIPT" "${PY_ARGS[@]}" 2>&1 | tee -a "$LOG_FILE"
    rc=${PIPESTATUS[0]}
fi
set -e

# Plan-only never creates a checkpoint and never runs ISEScan.
if [[ "$PLAN_ONLY" == "1" ]]; then
    log_info "Plan-only run finished (rc=$rc). No genome executed, no checkpoint created."
    exit "$rc"
fi

case "$rc" in
    0)
        write_checkpoint "$CHECKPOINT_FILE"
        log_done "Step $STEP_ID completed (all genomes valid)."
        ;;
    3)
        log_warn "Module 06 completed a full pass but some genomes failed or timed out."
        log_warn "See $TSV_DIR/isescan_failures.tsv and $TSV_DIR/isescan_resume_report.tsv"
        if [[ "$ALLOW_PARTIAL" == "1" ]]; then
            write_checkpoint "$CHECKPOINT_FILE"
            log_info "ALLOW_PARTIAL=1: checkpoint created despite failures: $CHECKPOINT_FILE"
        else
            log_info "Checkpoint NOT created. A relaunch reuses valid genomes and retries only the failed ones."
            log_info "To accept the partial result and proceed, relaunch with ALLOW_PARTIAL=1."
        fi
        # The full pass completed and failures are recorded; do not abort the
        # master pipeline. The missing checkpoint is what drives the retry.
        ;;
    *)
        log_error "Module 06 aborted (rc=$rc). Checkpoint NOT created. Existing consolidated outputs left unchanged."
        exit "$rc"
        ;;
esac
