#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="14_run_bagel5_full"
SCRIPT="$SCRIPT_DIR/14_bagel5_full.py"
MANIFEST="$PIPE_ROOT/work/manifest/input_manifest.tsv"
BAGEL5_SCRIPT="${BAGEL5_SCRIPT:-$PIPE_ROOT/external_tools/BAGEL5/src/data/bagel5/scripts/bagel5.py}"
PARSER_SCRIPT="${BAGEL5_PARSER_SCRIPT:-$PIPE_ROOT/dev/bagel5_full_integration/parser_design/parse_bagel5_bacteriocins_matrix.py}"
RAW_ROOT="$PIPE_ROOT/work/intermediate/bgc/bagel5/raw_bagel5_output"
STAGED_INPUT_DIR="$PIPE_ROOT/work/intermediate/bgc/bagel5/staged_input"
TSV_DIR="$PIPE_ROOT/results/tsv/bgc"
XLSX_DIR="$PIPE_ROOT/results/xlsx/bgc"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/14_run_bagel5_full.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/14_run_bagel5_full.done"
THREADS="${THREADS:-2}"
mkdir -p "$RAW_ROOT" "$STAGED_INPUT_DIR" "$TSV_DIR" "$XLSX_DIR" "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then log_info "Checkpoint exists: $CHECKPOINT_FILE"; exit 0; fi
require_file "$SCRIPT"
require_file "$MANIFEST"
{
    log_info "Starting $STEP_ID"
    run_python_in_env "$CORE_ENV" "$SCRIPT" --manifest "$MANIFEST" --raw-root "$RAW_ROOT" --staged-input-dir "$STAGED_INPUT_DIR" --output-tsv-dir "$TSV_DIR" --output-xlsx-dir "$XLSX_DIR" --bagel5-env "$BAGEL5_ENV" --bagel5-script "$BAGEL5_SCRIPT" --parser-script "$PARSER_SCRIPT" --threads "$THREADS"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

