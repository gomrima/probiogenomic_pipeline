#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="12_run_cazymes_dbcan"
SCRIPT="$SCRIPT_DIR/12_cazymes_dbcan.py"
MANIFEST="$PIPE_ROOT/work/manifest/input_manifest.tsv"
DBCAN_DB="${DBCAN_DB:-$PIPE_ROOT/db/dbcan/compiled/dbCAN.txt}"
RAW_DIR="$PIPE_ROOT/work/intermediate/cazy/hmmscan_raw"
TSV_DIR="$PIPE_ROOT/results/tsv/cazy"
XLSX_DIR="$PIPE_ROOT/results/xlsx/cazy"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/12_run_cazymes_dbcan.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/12_run_cazymes_dbcan.done"
THREADS="${THREADS:-2}"
mkdir -p "$RAW_DIR" "$TSV_DIR" "$XLSX_DIR" "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then log_info "Checkpoint exists: $CHECKPOINT_FILE"; exit 0; fi
require_file "$SCRIPT"
require_file "$MANIFEST"
{
    log_info "Starting $STEP_ID"
    run_python_in_env "$CORE_ENV" "$SCRIPT" --manifest "$MANIFEST" --dbcan-db "$DBCAN_DB" --raw-dir "$RAW_DIR" --output-tsv-dir "$TSV_DIR" --output-xlsx-dir "$XLSX_DIR" --threads "$THREADS" --hmmscan-bin hmmscan
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

