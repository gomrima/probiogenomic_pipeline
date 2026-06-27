#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="00_prepare_inputs"
INPUT_DIR="${1:-${INPUT_DIR:-$PIPE_ROOT/input}}"
SCRIPT="$SCRIPT_DIR/00_prepare_inputs.py"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/00_prepare_inputs.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/00_prepare_inputs.done"
mkdir -p "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then
    log_info "Checkpoint exists: $CHECKPOINT_FILE"
    log_info "Step $STEP_ID already completed. Skipping."
    exit 0
fi
require_file "$SCRIPT"
require_dir "$INPUT_DIR"
{
    log_info "Starting $STEP_ID"
    log_info "PIPE_ROOT=$PIPE_ROOT"
    log_info "INPUT_DIR=$INPUT_DIR"
    run_python_in_env "$CORE_ENV" "$SCRIPT" "$INPUT_DIR"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

