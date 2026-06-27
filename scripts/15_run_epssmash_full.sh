#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="15_run_epssmash_full"
SCRIPT="$SCRIPT_DIR/15_epssmash_full.py"
MANIFEST="$PIPE_ROOT/work/manifest/input_manifest.tsv"
EPSSMASH_EXEC="${EPSSMASH_EXEC:-$ANTISMASH_DEPENDENCIES_ENV/bin/epsSMASH}"
DB_DIR="${EPSSMASH_DB:-$PIPE_ROOT/db/epssmash}"
PARSER_SCRIPT="${EPSSMASH_PARSER_SCRIPT:-$PIPE_ROOT/dev/epssmash_full_integration/parser_design/parse_epssmash_products_to_binary_matrix.py}"
RAW_ROOT="$PIPE_ROOT/work/intermediate/bgc/epssmash/raw_epssmash_output"
JSON_DIR="$PIPE_ROOT/work/intermediate/bgc/epssmash/collected_json"
TSV_DIR="$PIPE_ROOT/results/tsv/bgc"
XLSX_DIR="$PIPE_ROOT/results/xlsx/bgc"
LOG_DIR="$PIPE_ROOT/results/logs"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
LOG_FILE="$LOG_DIR/15_run_epssmash_full.log"
CHECKPOINT_FILE="$CHECKPOINT_DIR/15_run_epssmash_full.done"
THREADS="${THREADS:-2}"
mkdir -p "$RAW_ROOT" "$JSON_DIR" "$TSV_DIR" "$XLSX_DIR" "$LOG_DIR" "$CHECKPOINT_DIR" "$TMPDIR_PATH"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then log_info "Checkpoint exists: $CHECKPOINT_FILE"; exit 0; fi
require_file "$SCRIPT"
require_file "$MANIFEST"
{
    log_info "Starting $STEP_ID"
    run_python_in_env "$CORE_ENV" "$SCRIPT" --manifest "$MANIFEST" --raw-root "$RAW_ROOT" --json-dir "$JSON_DIR" --output-tsv-dir "$TSV_DIR" --output-xlsx-dir "$XLSX_DIR" --epssmash-exec "$EPSSMASH_EXEC" --db-dir "$DB_DIR" --parser-script "$PARSER_SCRIPT" --threads "$THREADS"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

