#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [[ "$(basename "$SCRIPT_DIR")" == "lib" ]]; then
    SCRIPT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
fi
export PIPE_ROOT="${PIPE_ROOT:-$( cd "$SCRIPT_DIR/.." && pwd )}"
export PIPELINE_ROOT="${PIPELINE_ROOT:-$PIPE_ROOT}"

CORE_ENV="${CORE_ENV:-$PIPE_ROOT/conda/envs/probio_core}"
PROBML_ENV="${PROBML_ENV:-$PIPE_ROOT/conda/envs/probml_env}"
GENOMAD_ENV="${GENOMAD_ENV:-$PIPE_ROOT/conda/envs/genomad_env}"
ANTISMASH_ENV="${ANTISMASH_ENV:-$PIPE_ROOT/conda/envs/antismash_env}"
ANTISMASH_DEPENDENCIES_ENV="${ANTISMASH_DEPENDENCIES_ENV:-$PIPE_ROOT/conda/envs/antismash_dependencies}"
BAGEL5_ENV="${BAGEL5_ENV:-$PIPE_ROOT/conda/envs/bagel5_env}"
EPSSMASH_ENV="${EPSSMASH_ENV:-$PIPE_ROOT/conda/envs/epssmash_env}"
MOBSUITE_ENV="${MOBSUITE_ENV:-$PIPE_ROOT/conda/envs/mob_suite_env}"

log_info() { printf '[INFO] %s\n' "$*"; }
log_warn() { printf '[WARN] %s\n' "$*" >&2; }
log_error() { printf '[ERROR] %s\n' "$*" >&2; }
log_done() { printf '[DONE] %s\n' "$*"; }
fail() { log_error "$*"; exit 1; }

timestamp_utc() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
}

ensure_dir() {
    mkdir -p "$1"
}

require_file() {
    [[ -f "$1" ]] || fail "Missing required file: $1"
}

require_dir() {
    [[ -d "$1" ]] || fail "Missing required directory: $1"
}

require_executable() {
    [[ -x "$1" ]] || fail "Missing executable file: $1"
}

step_checkpoint_valid() {
    local checkpoint="$1"
    [[ -f "$checkpoint" && -s "$checkpoint" ]]
}

write_checkpoint() {
    local checkpoint="$1"
    local status="${2:-DONE}"
    ensure_dir "$(dirname "$checkpoint")"
    {
        printf 'status\t%s\n' "$status"
        printf 'timestamp_utc\t%s\n' "$(timestamp_utc)"
        printf 'pipe_root\t%s\n' "$PIPE_ROOT"
    } > "$checkpoint"
}

append_pipeline_state() {
    local event="$1"
    local step_id="${2:-NA}"
    local state_file="$PIPE_ROOT/work/checkpoints/pipeline_state.tsv"
    ensure_dir "$(dirname "$state_file")"
    if [[ ! -f "$state_file" ]]; then
        printf 'timestamp_utc\tevent\tstep_id\tpipe_root\n' > "$state_file"
    fi
    printf '%s\t%s\t%s\t%s\n' "$(timestamp_utc)" "$event" "$step_id" "$PIPE_ROOT" >> "$state_file"
}

run_python_in_env() {
    local env_path="$1"
    shift
    # --no-capture-output streams the child's stdout/stderr live; plain "conda run"
    # buffers it, which makes long-running modules look frozen in the terminal.
    # "python -u" disables Python's own output buffering for the same reason.
    if command -v conda >/dev/null 2>&1; then
        conda run --no-capture-output -p "$env_path" python -u "$@"
    else
        "$env_path/bin/python" -u "$@"
    fi
}
