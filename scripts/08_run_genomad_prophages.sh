#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="08_run_genomad_prophages"
SCRIPT="$SCRIPT_DIR/08_genomad_prophages.py"
MANIFEST="$PIPE_ROOT/work/manifest/input_manifest.tsv"
GENOMAD_DB="${GENOMAD_DB:-$PIPE_ROOT/db/genomad/genomad_db}"
RAW_ROOT="$PIPE_ROOT/work/intermediate/prophages/genomad_raw"
FASTA_OUT_ROOT="$PIPE_ROOT/work/intermediate/prophages/prophage_sequences"
TSV_DIR="$PIPE_ROOT/results/tsv/prophages"
XLSX_DIR="$PIPE_ROOT/results/xlsx/prophages"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/08_run_genomad_prophages.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/08_run_genomad_prophages.done"
THREADS="${THREADS:-2}"
GENOMAD_MIN_SCORE="${GENOMAD_MIN_SCORE:-0.7}"
GENOMAD_MIN_LENGTH="${GENOMAD_MIN_LENGTH:-1000}"
GENOMAD_SPLITS="${GENOMAD_SPLITS:-8}"
mkdir -p "$RAW_ROOT" "$FASTA_OUT_ROOT" "$TSV_DIR" "$XLSX_DIR" "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then log_info "Checkpoint exists: $CHECKPOINT_FILE"; exit 0; fi
require_file "$SCRIPT"
require_file "$MANIFEST"
{
    log_info "Starting $STEP_ID"
    run_python_in_env "$CORE_ENV" "$SCRIPT" --manifest "$MANIFEST" --raw-root "$RAW_ROOT" --fasta-out-root "$FASTA_OUT_ROOT" --output-tsv-dir "$TSV_DIR" --output-xlsx-dir "$XLSX_DIR" --genomad-env "$GENOMAD_ENV" --genomad-db "$GENOMAD_DB" --threads "$THREADS" --min-score "$GENOMAD_MIN_SCORE" --min-length "$GENOMAD_MIN_LENGTH" --splits "$GENOMAD_SPLITS"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

