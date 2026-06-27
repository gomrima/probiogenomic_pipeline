#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="17_run_pipeline_consolidation"
SCRIPT="$SCRIPT_DIR/17_pipeline_consolidation.py"
TSV_DIR="$PIPE_ROOT/results/tsv/final"
XLSX_DIR="$PIPE_ROOT/results/xlsx/final"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/17_run_pipeline_consolidation.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/17_run_pipeline_consolidation.done"
mkdir -p "$TSV_DIR" "$XLSX_DIR" "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then log_info "Checkpoint exists: $CHECKPOINT_FILE"; exit 0; fi
require_file "$SCRIPT"
{
    log_info "Starting $STEP_ID"
    run_python_in_env "$CORE_ENV" "$SCRIPT" --pipeline-root "$PIPE_ROOT" --output-tsv-dir "$TSV_DIR" --output-xlsx-dir "$XLSX_DIR" --mode "${MODE:-}"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

