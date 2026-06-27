#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="05_run_bacterial_toxins_screen"
SCRIPT="$SCRIPT_DIR/05_bacterial_toxins_screen.py"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/05_run_bacterial_toxins_screen.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/05_run_bacterial_toxins_screen.done"
mkdir -p "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then
    log_info "Checkpoint exists: $CHECKPOINT_FILE"
    log_info "Step $STEP_ID already completed. Skipping."
    exit 0
fi
require_file "$SCRIPT"
{
    log_info "Starting $STEP_ID"
    log_info "PIPE_ROOT=$PIPE_ROOT"
    log_info "SCRIPT=$SCRIPT"
    log_info "TMPDIR=$TMPDIR"
    run_python_in_env "$CORE_ENV" "$SCRIPT"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

