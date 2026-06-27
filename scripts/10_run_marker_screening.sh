#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="10_run_marker_screening"
SCRIPT="$SCRIPT_DIR/10_marker_screening.py"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/10_run_marker_screening.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/10_run_marker_screening.done"
MARKERS_XLSX="$PIPE_ROOT/db/compiled/markers_DB.xlsx"
MARKER_METADATA="$PIPE_ROOT/db/compiled/metadata/marker_metadata.tsv"
DIAMOND_DB="$PIPE_ROOT/db/compiled/diamond/all_markers_for_diamond.dmnd"
HMM_DB="$PIPE_ROOT/db/compiled/hmm/all_markers.hmm"
mkdir -p "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then
    log_info "Checkpoint exists: $CHECKPOINT_FILE"
    log_info "Step $STEP_ID already completed. Skipping."
    exit 0
fi
require_file "$SCRIPT"
if [[ ! -f "$DIAMOND_DB" || ! -f "$HMM_DB" || ! -f "$MARKER_METADATA" || ! -f "$MARKERS_XLSX" ]]; then
    log_error "Compiled marker resources are incomplete."
    log_error "Expected files:"
    log_error "  $DIAMOND_DB"
    log_error "  $HMM_DB"
    log_error "  $MARKER_METADATA"
    log_error "  $MARKERS_XLSX"
    log_error "Run this setup first after placing db/markers_DB.xlsx, db/marker_fastas and db/hmm_profiles:"
    log_error "  bash scripts/01_run_prepare_marker_resources.sh"
    exit 1
fi
{
    log_info "Starting $STEP_ID"
    log_info "PIPE_ROOT=$PIPE_ROOT"
    log_info "SCRIPT=$SCRIPT"
    log_info "TMPDIR=$TMPDIR"
    run_python_in_env "$CORE_ENV" "$SCRIPT"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

