#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="13_run_antismash_minimal"
SCRIPT="$SCRIPT_DIR/13_antismash_minimal.py"
MANIFEST="$PIPE_ROOT/work/manifest/input_manifest.tsv"
DB_DIR="${ANTISMASH_DB:-$PIPE_ROOT/db/antismash}"
ANTISMASH_EXEC="${ANTISMASH_EXEC:-$ANTISMASH_ENV/bin/antismash}"
RAW_ROOT="$PIPE_ROOT/work/intermediate/bgc/antismash_raw"
TSV_DIR="$PIPE_ROOT/results/tsv/bgc"
XLSX_DIR="$PIPE_ROOT/results/xlsx/bgc"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/13_run_antismash_minimal.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/13_run_antismash_minimal.done"
THREADS="${THREADS:-2}"
mkdir -p "$RAW_ROOT" "$TSV_DIR" "$XLSX_DIR" "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then log_info "Checkpoint exists: $CHECKPOINT_FILE"; exit 0; fi
require_file "$SCRIPT"
require_file "$MANIFEST"
{
    log_info "Starting $STEP_ID"
    run_python_in_env "$CORE_ENV" "$SCRIPT" --manifest "$MANIFEST" --raw-root "$RAW_ROOT" --db-dir "$DB_DIR" --output-tsv-dir "$TSV_DIR" --output-xlsx-dir "$XLSX_DIR" --threads "$THREADS" --antismash-exec "$ANTISMASH_EXEC" --antismash-env-bin "$ANTISMASH_ENV/bin"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

