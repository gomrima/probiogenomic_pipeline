#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="07_run_mobsuite_plasmids"
SCRIPT="$SCRIPT_DIR/07_mobsuite_plasmids.py"
MANIFEST="$PIPE_ROOT/work/manifest/input_manifest.tsv"
DB_DIR="${MOBSUITE_DB:-$PIPE_ROOT/db/mob_suite}"
RAW_ROOT="$PIPE_ROOT/work/intermediate/mobilome/mobsuite_raw"
TSV_DIR="$PIPE_ROOT/results/tsv/mobilome"
XLSX_DIR="$PIPE_ROOT/results/xlsx/mobilome"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/07_run_mobsuite_plasmids.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/07_run_mobsuite_plasmids.done"
THREADS="${THREADS:-2}"
mkdir -p "$RAW_ROOT" "$TSV_DIR" "$XLSX_DIR" "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then log_info "Checkpoint exists: $CHECKPOINT_FILE"; exit 0; fi
require_file "$SCRIPT"
require_file "$MANIFEST"
{
    log_info "Starting $STEP_ID"
    run_python_in_env "$MOBSUITE_ENV" "$SCRIPT" --manifest "$MANIFEST" --raw-root "$RAW_ROOT" --db-dir "$DB_DIR" --output-tsv-dir "$TSV_DIR" --output-xlsx-dir "$XLSX_DIR" --threads "$THREADS"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

