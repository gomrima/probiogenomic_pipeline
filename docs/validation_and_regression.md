# Validation and regression

The final repository includes static and output-level validation tools.

Static validation:

```bash
python -m py_compile $(find scripts -name '*.py' | sort)
bash -n scripts/run_pipeline_final.sh
python tests/audit_portability.py --root scripts --output metadata/PORTABILITY_AUDIT.tsv
python tests/audit_numbering.py --scripts-dir scripts --output metadata/NUMBERING_AUDIT.tsv
python tests/audit_mode_sequences.py --launcher scripts/run_pipeline_final.sh --output metadata/MODE_SEQUENCE_AUDIT.tsv
```

Output regression validation:

```bash
python tests/validate_outputs.py --legacy_results /path/to/legacy/results --final_results /path/to/final/results --output_report metadata/REGRESSION_VALIDATION_REPORT.md --strict
```

The pipeline was validated end to end on Linux Mint 22.3 (kernel 6.17.0-14-generic, host gma-Inspiron-15-3567) with a 10-genome test set on 2026-06-13. All 17 FULL-mode modules completed without error. No legacy output set exists for numeric regression (see `metadata/REGRESSION_VALIDATION_REPORT.md`).

