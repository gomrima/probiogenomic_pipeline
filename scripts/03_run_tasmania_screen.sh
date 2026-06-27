#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"
STEP_ID="03_run_tasmania_screen"
SCRIPT="$SCRIPT_DIR/03_tasmania_screen.py"
LOG_DIR="$PIPE_ROOT/results/logs"
LOG_FILE="$LOG_DIR/03_run_tasmania_screen.log"
TMPDIR_PATH="${TMPDIR:-$PIPE_ROOT/work/tmp}"
FAA_DIR="$PIPE_ROOT/work/normalized_faa"
TAS_DB="${TASMANIA_DB:-$PIPE_ROOT/db/tasmania/compiled/tasmania_all.hmm}"
RAW_DIR="$PIPE_ROOT/work/intermediate/ta_systems/hmmer_raw"
RESULTS_TSV_DIR="$PIPE_ROOT/results/tsv/ta_systems"
RESULTS_XLSX_DIR="$PIPE_ROOT/results/xlsx/ta_systems"
CHECKPOINT_DIR="$PIPE_ROOT/work/checkpoints"
CHECKPOINT_FILE="$CHECKPOINT_DIR/03_run_tasmania_screen.done"
THREADS="${THREADS:-2}"
mkdir -p "$LOG_DIR" "$TMPDIR_PATH" "$RAW_DIR" "$RESULTS_TSV_DIR" "$RESULTS_XLSX_DIR" "$CHECKPOINT_DIR"
export TMPDIR="$TMPDIR_PATH" PIPE_ROOT
if step_checkpoint_valid "$CHECKPOINT_FILE"; then
    log_info "Checkpoint exists: $CHECKPOINT_FILE"
    log_info "Step $STEP_ID already completed. Skipping."
    exit 0
fi
require_file "$SCRIPT"
require_file "$TAS_DB"
shopt -s nullglob
faa_files=("$FAA_DIR"/*.faa)
shopt -u nullglob
[[ ${#faa_files[@]} -gt 0 ]] || fail "No FAA files found in $FAA_DIR"
{
    log_info "Starting $STEP_ID"
    log_info "Genomes with available FAA: ${#faa_files[@]}"
    idx=0
    for faa in "${faa_files[@]}"; do
        idx=$((idx + 1))
        genome_id="$(basename "$faa" .faa)"
        domtbl="$RAW_DIR/${genome_id}.tasmania.domtblout"
        stdout_file="$RAW_DIR/${genome_id}.tasmania.stdout.txt"
        if [[ -s "$domtbl" && -s "$stdout_file" ]]; then
            log_info "[RESUME] Skipping $genome_id. Existing TASmania raw outputs are present."
            continue
        fi
        log_info "Step 03 | TASmania | $idx/${#faa_files[@]} | active $genome_id"
        conda run -p "$CORE_ENV" hmmscan --cpu "$THREADS" --domtblout "$domtbl.tmp" --noali "$TAS_DB" "$faa" > "$stdout_file.tmp" 2>&1
        mv "$domtbl.tmp" "$domtbl"
        mv "$stdout_file.tmp" "$stdout_file"
    done
    run_python_in_env "$CORE_ENV" "$SCRIPT"
    write_checkpoint "$CHECKPOINT_FILE"
    log_done "Step $STEP_ID completed."
} 2>&1 | tee -a "$LOG_FILE"

