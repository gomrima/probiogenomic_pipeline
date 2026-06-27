#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="16_run_probml_screen"
SCRIPT="$SCRIPT_DIR/16_probml_screen.py"
MANIFEST="${PROBML_MANIFEST:-$PIPE_ROOT/work/manifest/input_manifest.tsv}"
PROBML_MODELS_DIR="${PROBML_MODELS_DIR:-$PIPE_ROOT/db/ProbML/MLG_Dashboard-main/models}"
TSV_DIR="$PIPE_ROOT/results/tsv/probml"
XLSX_DIR="$PIPE_ROOT/results/xlsx/probml"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/16_run_probml_screen.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/16_run_probml_screen.done"
THREADS="${THREADS:-2}"
THRESHOLD="${PROBML_THRESHOLD:-0.5}"
MODELS="${PROBML_MODELS:-all}"
mkdir -p "$TSV_DIR" "$XLSX_DIR" "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then log_info "Checkpoint exists: $CHECKPOINT_FILE"; exit 0; fi
require_file "$SCRIPT"
require_file "$MANIFEST"
{
    log_info "Starting $STEP_ID"
    run_python_in_env "$PROBML_ENV" "$SCRIPT" --pipeline-root "$PIPE_ROOT" --manifest "$MANIFEST" --models-dir "$PROBML_MODELS_DIR" --output-tsv-dir "$TSV_DIR" --output-xlsx-dir "$XLSX_DIR" --models "$MODELS" --threshold "$THRESHOLD" --threads "$THREADS"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

