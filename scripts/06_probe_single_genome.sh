#!/usr/bin/env bash
set -euo pipefail

# ===========================================================================
# Module 06 helper - isolate and probe a single genome with ISEScan.
#
# Runs ISEScan on ONE genome from the manifest, in a fresh clean output
# directory, directly (no resume logic, no conda run), with unbuffered
# line-by-line output. This isolates whether a hang is genome-specific or
# ISEScan-specific, separately from the pipeline. It does not touch the
# pipeline raw directories, the consolidated TSVs, or the checkpoint.
#
# Usage
#   bash 06_probe_single_genome.sh GENOME_ID [THREADS]
#
# Examples
#   # Probe a suspected slow genome at 1 thread, no timeout, observe freely
#   bash 06_probe_single_genome.sh Path11_Bordetella_pertussis_H640 1
#   # Probe with a 1 hour safety timeout
#   PROBE_TIMEOUT=3600 bash 06_probe_single_genome.sh Path11_Bordetella_pertussis_H640 2
#
# Environment overrides
#   PROBE_TIMEOUT=0   seconds before ISEScan is killed (0 = no timeout)
# ===========================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/lib/common.sh"

MANIFEST="$PIPE_ROOT/work/manifest/input_manifest.tsv"
TMP_DIR="${TMPDIR:-$PIPE_ROOT/work/tmp}"

GENOME_ID="${1:-}"
THREADS="${2:-1}"
PROBE_TIMEOUT="${PROBE_TIMEOUT:-0}"

if [[ -z "$GENOME_ID" ]]; then
    echo "Usage: $0 GENOME_ID [THREADS]" >&2
    exit 2
fi
require_file "$MANIFEST"

export PATH="$CORE_ENV/bin:$PATH"
export TMPDIR="$TMP_DIR"
export PYTHONUNBUFFERED=1
mkdir -p "$TMP_DIR"

if ! command -v isescan.py >/dev/null 2>&1; then
    echo "[FATAL] isescan.py not on PATH (looked in $CORE_ENV/bin)." >&2
    exit 1
fi

# Resolve the normalized FNA for this genome from the manifest (status OK only).
FNA="$(awk -F '\t' -v g="$GENOME_ID" '
NR==1 { for (i=1; i<=NF; i++) col[$i]=i; next }
{ if ($col["genome_id"]==g && $col["status"]=="OK") { print $col["normalized_fna"]; exit } }
' "$MANIFEST")"

if [[ -z "$FNA" || ! -f "$FNA" ]]; then
    echo "[FATAL] Could not resolve an existing FNA for genome '$GENOME_ID' in $MANIFEST" >&2
    exit 1
fi

OUT="$TMP_DIR/isescan_probe_${GENOME_ID}_$(date +%Y%m%d_%H%M%S)"
rm -rf "$OUT"
mkdir -p "$OUT"

echo "============================================================"
echo "[PROBE] genome  = $GENOME_ID"
echo "[PROBE] threads = $THREADS"
echo "[PROBE] timeout = $PROBE_TIMEOUT s (0 = none)"
echo "[PROBE] FNA     = $FNA"
echo "[PROBE] OUT     = $OUT"
echo "[PROBE] starting ISEScan directly, unbuffered..."
echo "============================================================"

start=$(date +%s)
set +e
if [[ "$PROBE_TIMEOUT" -gt 0 ]]; then
    stdbuf -oL -eL timeout -s TERM "$PROBE_TIMEOUT" \
        isescan.py --seqfile "$FNA" --output "$OUT" --nthread "$THREADS"
else
    stdbuf -oL -eL \
        isescan.py --seqfile "$FNA" --output "$OUT" --nthread "$THREADS"
fi
rc=$?
set -e
end=$(date +%s)

echo "============================================================"
echo "[PROBE] ISEScan exit code : $rc  (124 = timed out)"
echo "[PROBE] elapsed           : $(( end - start )) s"
echo "[PROBE] CSV files produced:"
find "$OUT" -type f -name '*.csv' -printf '  %p (%s bytes)\n' 2>/dev/null || true
echo "[PROBE] all output files:"
find "$OUT" -type f -printf '  %p (%s bytes)\n' 2>/dev/null | head -40 || true
echo "============================================================"
exit "$rc"
