#!/usr/bin/env bash

set -euo pipefail

# ---------------------------------------------------------------------------
# CRLF auto-fix (Level 2 protection)
# Silently remove Windows \r line endings from all pipeline scripts before
# any wrapper is sourced or executed. This is a no-op on files that are
# already LF-only. It makes the package robust to zip transfers from Windows
# without requiring any manual action from the user.
# ---------------------------------------------------------------------------
_crlf_fix() {
    local f="$1"
    [[ -f "$f" ]] || return 0
    if grep -qP '\r' "$f" 2>/dev/null; then
        sed -i 's/\r//' "$f"
    fi
}
_CRLF_SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
for _f in "$_CRLF_SCRIPT_DIR"/*.sh \
           "$_CRLF_SCRIPT_DIR"/lib/*.sh \
           "$_CRLF_SCRIPT_DIR"/*.py \
           "$_CRLF_SCRIPT_DIR"/lib/*.py; do
    _crlf_fix "$_f"
done
unset -f _crlf_fix
unset _f _CRLF_SCRIPT_DIR
# ---------------------------------------------------------------------------

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<USAGE
Usage:
  bash run_pipeline_final.sh --input_dir PATH [--mode LIGHT|STANDARD|FULL] [--run_name NAME] [--resume]

Options:
  --input_dir PATH       Input genome directory.
  --mode MODE           LIGHT, STANDARD, or FULL. Default: STANDARD.
  --run_name NAME       Run name. Default: timestamp plus mode.
  --resume              Resume a previous interrupted run without resetting work or results.
  --from_step STEP_ID   Start at a final step id, for example 08_run_genomad_prophages.
  --force_step STEP_ID  Remove the checkpoint for one step before running it.
  --threads N           Thread count exported to module wrappers. Default: 2.
  --unicode-progress    Enable optional Unicode progress in Python helpers.
  -h, --help            Show this help.
USAGE
}

safe_name() {
    local value="$1"
    value="${value// /_}"
    value="${value//\//_}"
    value="${value//:/_}"
    value="$(printf '%s' "$value" | sed 's/[^A-Za-z0-9._-]/_/g')"
    printf '%s\n' "$value"
}

MODE="STANDARD"
INPUT_DIR=""
RUN_NAME=""
RESUME=0
FROM_STEP=""
FORCE_STEP=""
THREADS="${THREADS:-2}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --input_dir) [[ $# -ge 2 ]] || fail "--input_dir requires a value"; INPUT_DIR="$2"; shift 2 ;;
        --mode) [[ $# -ge 2 ]] || fail "--mode requires a value"; MODE="$2"; shift 2 ;;
        --run_name) [[ $# -ge 2 ]] || fail "--run_name requires a value"; RUN_NAME="$2"; shift 2 ;;
        --resume) RESUME=1; shift ;;
        --from_step) [[ $# -ge 2 ]] || fail "--from_step requires a value"; FROM_STEP="$2"; shift 2 ;;
        --force_step) [[ $# -ge 2 ]] || fail "--force_step requires a value"; FORCE_STEP="$2"; shift 2 ;;
        --threads) [[ $# -ge 2 ]] || fail "--threads requires a value"; THREADS="$2"; shift 2 ;;
        --unicode-progress) export PIPE_PROGRESS_UNICODE=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Unknown argument: $1" ;;
    esac
done

case "$MODE" in
    LIGHT|STANDARD|FULL) ;;
    *) fail "Invalid mode: $MODE" ;;
esac

if [[ -z "$INPUT_DIR" && "$RESUME" -eq 0 ]]; then
    INPUT_DIR="$PIPE_ROOT/input"
fi
if [[ "$RESUME" -eq 0 ]]; then
    require_dir "$INPUT_DIR"
fi

# Resuming without a run name makes the run logs and exports belong to a new
# timestamped run while the work/results state comes from the interrupted run,
# which breaks traceability. Require an explicit run name when resuming.
if [[ "$RESUME" -eq 1 && -z "$RUN_NAME" ]]; then
    fail "--resume requires --run_name so the resumed run stays traceable. Pass the run_name of the interrupted run."
fi

RUN_STAMP="$(date '+%Y%m%d_%H%M%S')"
if [[ -z "$RUN_NAME" ]]; then
    RUN_NAME="$(safe_name "${RUN_STAMP}_${MODE}")"
else
    RUN_NAME="$(safe_name "$RUN_NAME")"
fi

RUN_DIR="$PIPE_ROOT/runs/$RUN_NAME"
RUN_LOG_DIR="$RUN_DIR/logs"
RUN_META_DIR="$RUN_DIR/meta"
RUN_ARCHIVE_DIR="$RUN_DIR/archive_pre_run_state"
RUN_EXPORT_DIR="$RUN_DIR/export"
RUN_TMPDIR="$RUN_DIR/tmp"

mkdir -p "$RUN_LOG_DIR" "$RUN_META_DIR" "$RUN_ARCHIVE_DIR" "$RUN_EXPORT_DIR" "$RUN_TMPDIR"
RUN_LOG="$RUN_LOG_DIR/run_pipeline_final.log"
exec > >(tee -a "$RUN_LOG") 2>&1

export THREADS
export MODE
export TMPDIR="$RUN_TMPDIR"
export PIPE_ROOT

write_run_info() {
    {
        printf 'run_name\t%s\n' "$RUN_NAME"
        printf 'mode\t%s\n' "$MODE"
        printf 'resume\t%s\n' "$RESUME"
        printf 'input_dir\t%s\n' "${INPUT_DIR:-NA}"
        printf 'pipe_root\t%s\n' "$PIPE_ROOT"
        printf 'run_dir\t%s\n' "$RUN_DIR"
        printf 'threads\t%s\n' "$THREADS"
        printf 'start_time_utc\t%s\n' "$(timestamp_utc)"
    } > "$RUN_META_DIR/run_info.tsv"
}

preflight_marker_resources() {
    local missing=0
    local required_files=(
        "$PIPE_ROOT/db/compiled/markers_DB.xlsx"
        "$PIPE_ROOT/db/compiled/metadata/marker_metadata.tsv"
        "$PIPE_ROOT/db/compiled/diamond/all_markers_for_diamond.dmnd"
        "$PIPE_ROOT/db/compiled/hmm/all_markers.hmm"
    )
    local path
    for path in "${required_files[@]}"; do
        if [[ ! -f "$path" ]]; then
            log_error "Missing compiled marker resource: $path"
            missing=1
        fi
    done
    if [[ "$missing" -eq 1 ]]; then
        fail "Module 10 requires compiled marker resources. Run: bash scripts/01_run_prepare_marker_resources.sh"
    fi
}

preflight_full_resources() {
    [[ "$MODE" == "FULL" ]] || return 0

    local missing=0
    local bagel5_script="${BAGEL5_SCRIPT:-$PIPE_ROOT/external_tools/BAGEL5/src/data/bagel5/scripts/bagel5.py}"
    local bagel5_parser="${BAGEL5_PARSER_SCRIPT:-$PIPE_ROOT/dev/bagel5_full_integration/parser_design/parse_bagel5_bacteriocins_matrix.py}"
    local epssmash_exec="${EPSSMASH_EXEC:-$ANTISMASH_DEPENDENCIES_ENV/bin/epsSMASH}"
    local epssmash_db="${EPSSMASH_DB:-$PIPE_ROOT/db/epssmash}"
    local epssmash_parser="${EPSSMASH_PARSER_SCRIPT:-$PIPE_ROOT/dev/epssmash_full_integration/parser_design/parse_epssmash_products_to_binary_matrix.py}"

    if [[ ! -f "$bagel5_script" ]]; then
        log_error "Missing BAGEL5 script: $bagel5_script"
        missing=1
    fi
    if [[ ! -f "$bagel5_parser" ]]; then
        log_error "Missing BAGEL5 parser: $bagel5_parser"
        missing=1
    fi
    if [[ ! -x "$epssmash_exec" ]]; then
        log_error "Missing epsSMASH executable: $epssmash_exec"
        missing=1
    fi
    if [[ ! -d "$epssmash_db" ]]; then
        log_error "Missing epsSMASH database directory: $epssmash_db"
        missing=1
    fi
    if [[ ! -f "$epssmash_parser" ]]; then
        log_error "Missing epsSMASH parser: $epssmash_parser"
        missing=1
    fi
    if [[ "$missing" -eq 1 ]]; then
        fail "FULL mode requires BAGEL5 and epsSMASH resources. Install them or override BAGEL5_SCRIPT, BAGEL5_PARSER_SCRIPT, EPSSMASH_EXEC, EPSSMASH_DB and EPSSMASH_PARSER_SCRIPT."
    fi
}

archive_runtime_if_needed() {
    [[ "$RESUME" -eq 0 ]] || return 0
    for subdir in work results; do
        local src="$PIPE_ROOT/$subdir"
        if [[ -e "$src" ]]; then
            mkdir -p "$RUN_ARCHIVE_DIR"
            mv "$src" "$RUN_ARCHIVE_DIR/$subdir"
            log_info "Archived previous $subdir to $RUN_ARCHIVE_DIR/$subdir"
        fi
    done
    mkdir -p "$PIPE_ROOT/work/checkpoints" "$PIPE_ROOT/work/manifest" "$PIPE_ROOT/results/logs"
}

snapshot_outputs() {
    mkdir -p "$RUN_EXPORT_DIR"
    for subdir in work results; do
        if [[ -e "$PIPE_ROOT/$subdir" ]]; then
            cp -a "$PIPE_ROOT/$subdir" "$RUN_EXPORT_DIR/" 2>/dev/null || true
        fi
    done
}

step_checkpoint() {
    printf '%s/work/checkpoints/%s.done\n' "$PIPE_ROOT" "$1"
}

run_step() {
    local step_id="$1"
    local script_name="$2"
    local label="$3"
    local arg="${4:-}"
    local index="$5"
    local total="$6"
    local checkpoint
    checkpoint="$(step_checkpoint "$step_id")"

    if [[ -n "$FROM_STEP" && "$FROM_STEP" != "$step_id" && "${FROM_STEP_REACHED:-0}" -eq 0 ]]; then
        log_info "[SKIP] Before requested from_step: $step_id"
        return 0
    fi
    if [[ -n "$FROM_STEP" && "$FROM_STEP" == "$step_id" ]]; then
        FROM_STEP_REACHED=1
    fi

    if [[ "$FORCE_STEP" == "$step_id" ]]; then
        rm -f "$checkpoint"
        log_info "Removed checkpoint for forced step: $checkpoint"
    fi

    if [[ "$RESUME" -eq 1 && -f "$checkpoint" && -s "$checkpoint" ]]; then
        log_info "[RESUME] Skipping completed step $step_id"
        append_pipeline_state "resume_skip" "$step_id"
        return 0
    fi

    printf '\n'
    printf '================================================================================\n'
    printf '[STEP %s/%s] %s\n' "$index" "$total" "$label"
    printf '================================================================================\n'
    append_pipeline_state "step_start" "$step_id"

    if [[ -n "$arg" ]]; then
        bash "$SCRIPT_DIR/$script_name" "$arg"
    else
        bash "$SCRIPT_DIR/$script_name"
    fi

    append_pipeline_state "step_done" "$step_id"
}

case "$MODE" in
    LIGHT)
        STEPS=(
            "00_prepare_inputs|00_prepare_inputs.sh|Input preparation|$INPUT_DIR"
            "02_run_safety_abricate|02_run_safety_abricate.sh|ABRicate safety screening|"
            "03_run_tasmania_screen|03_run_tasmania_screen.sh|TASmania toxin antitoxin screening|"
            "04_run_crispr_minced|04_run_crispr_minced.sh|CRISPR screening with MinCED|"
            "05_run_bacterial_toxins_screen|05_run_bacterial_toxins_screen.sh|DBETH and PAT toxin screening|"
            "10_run_marker_screening|10_run_marker_screening.sh|Core probiotic marker screening|"
            "12_run_cazymes_dbcan|12_run_cazymes_dbcan.sh|dbCAN CAZyme screening|"
            "17_run_pipeline_consolidation|17_run_pipeline_consolidation.sh|Final consolidation|"
        )
        ;;
    STANDARD)
        STEPS=(
            "00_prepare_inputs|00_prepare_inputs.sh|Input preparation|$INPUT_DIR"
            "02_run_safety_abricate|02_run_safety_abricate.sh|ABRicate safety screening|"
            "03_run_tasmania_screen|03_run_tasmania_screen.sh|TASmania toxin antitoxin screening|"
            "04_run_crispr_minced|04_run_crispr_minced.sh|CRISPR screening with MinCED|"
            "05_run_bacterial_toxins_screen|05_run_bacterial_toxins_screen.sh|DBETH and PAT toxin screening|"
            "06_run_isescan_mobilome|06_run_isescan_mobilome.sh|ISEScan insertion sequence screening|"
            "07_run_mobsuite_plasmids|07_run_mobsuite_plasmids.sh|MOB-suite plasmid screening|"
            "10_run_marker_screening|10_run_marker_screening.sh|Core probiotic marker screening|"
            "12_run_cazymes_dbcan|12_run_cazymes_dbcan.sh|dbCAN CAZyme screening|"
            "17_run_pipeline_consolidation|17_run_pipeline_consolidation.sh|Final consolidation|"
        )
        ;;
    FULL)
        STEPS=(
            "00_prepare_inputs|00_prepare_inputs.sh|Input preparation|$INPUT_DIR"
            "02_run_safety_abricate|02_run_safety_abricate.sh|ABRicate safety screening|"
            "03_run_tasmania_screen|03_run_tasmania_screen.sh|TASmania toxin antitoxin screening|"
            "04_run_crispr_minced|04_run_crispr_minced.sh|CRISPR screening with MinCED|"
            "05_run_bacterial_toxins_screen|05_run_bacterial_toxins_screen.sh|DBETH and PAT toxin screening|"
            "06_run_isescan_mobilome|06_run_isescan_mobilome.sh|ISEScan insertion sequence screening|"
            "07_run_mobsuite_plasmids|07_run_mobsuite_plasmids.sh|MOB-suite plasmid screening|"
            "08_run_genomad_prophages|08_run_genomad_prophages.sh|geNomad prophage screening|"
            "09_run_mobile_safety_cooccurrence|09_run_mobile_safety_cooccurrence.sh|Mobile safety co-occurrence|"
            "10_run_marker_screening|10_run_marker_screening.sh|Core probiotic marker screening|"
            "11_run_probiosml_screen|11_run_probiosml_screen.sh|ProbioSML marker screening|"
            "12_run_cazymes_dbcan|12_run_cazymes_dbcan.sh|dbCAN CAZyme screening|"
            "13_run_antismash_minimal|13_run_antismash_minimal.sh|antiSMASH BGC screening|"
            "14_run_bagel5_full|14_run_bagel5_full.sh|BAGEL5 bacteriocin screening|"
            "15_run_epssmash_full|15_run_epssmash_full.sh|epsSMASH EPS screening|"
            "16_run_probml_screen|16_run_probml_screen.sh|ProbML external classifier|"
            "17_run_pipeline_consolidation|17_run_pipeline_consolidation.sh|Final consolidation|"
        )
        ;;
esac

# Validate --from_step / --force_step against the steps of the selected mode.
# An unknown --from_step would otherwise skip every step and end the run as if
# it had completed, which is a silent reproducibility failure.
STEP_IDS=()
for entry in "${STEPS[@]}"; do
    IFS='|' read -r sid _ _ _ <<< "$entry"
    STEP_IDS+=("$sid")
done
step_in_list() {
    local needle="$1"; shift
    local s
    for s in "$@"; do [[ "$s" == "$needle" ]] && return 0; done
    return 1
}
if [[ -n "$FROM_STEP" ]] && ! step_in_list "$FROM_STEP" "${STEP_IDS[@]}"; then
    fail "--from_step '$FROM_STEP' is not a step of mode $MODE. Valid steps: ${STEP_IDS[*]}"
fi
if [[ -n "$FORCE_STEP" ]] && ! step_in_list "$FORCE_STEP" "${STEP_IDS[@]}"; then
    fail "--force_step '$FORCE_STEP' is not a step of mode $MODE. Valid steps: ${STEP_IDS[*]}"
fi

preflight_marker_resources
preflight_full_resources
write_run_info
archive_runtime_if_needed
append_pipeline_state "run_start" "pipeline"

TOTAL="${#STEPS[@]}"
FROM_STEP_REACHED=0
if [[ -z "$FROM_STEP" ]]; then
    FROM_STEP_REACHED=1
fi

index=0
for entry in "${STEPS[@]}"; do
    index=$((index + 1))
    IFS='|' read -r step_id script_name label arg <<< "$entry"
    run_step "$step_id" "$script_name" "$label" "$arg" "$index" "$TOTAL"
done

snapshot_outputs
append_pipeline_state "run_done" "pipeline"
printf 'end_time_utc\t%s\n' "$(timestamp_utc)" >> "$RUN_META_DIR/run_info.tsv"

log_done "Pipeline completed."
log_info "Run directory: $RUN_DIR"
