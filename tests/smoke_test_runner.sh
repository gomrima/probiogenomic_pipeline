#!/usr/bin/env bash

set -euo pipefail

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

python -m py_compile $(find "$ROOT/scripts" -name '*.py' | sort)
bash -n "$ROOT/scripts/run_pipeline_final.sh"
python "$ROOT/tests/audit_portability.py" --root "$ROOT/scripts" --output "$ROOT/metadata/PORTABILITY_AUDIT.tsv"
python "$ROOT/tests/audit_numbering.py" --scripts-dir "$ROOT/scripts" --output "$ROOT/metadata/NUMBERING_AUDIT.tsv"
python "$ROOT/tests/audit_mode_sequences.py" --launcher "$ROOT/scripts/run_pipeline_final.sh" --output "$ROOT/metadata/MODE_SEQUENCE_AUDIT.tsv"

