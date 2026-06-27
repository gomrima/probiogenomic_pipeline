#!/usr/bin/env python3

import argparse
from pathlib import Path


EXPECTED = [
    "00_prepare_inputs.sh",
    "00_prepare_inputs.py",
    "01_run_prepare_marker_resources.sh",
    "01_prepare_marker_resources.py",
    "02_run_safety_abricate.sh",
    "02_safety_abricate.py",
    "03_run_tasmania_screen.sh",
    "03_tasmania_screen.py",
    "04_run_crispr_minced.sh",
    "04_crispr_minced.py",
    "05_run_bacterial_toxins_screen.sh",
    "05_bacterial_toxins_screen.py",
    "06_run_isescan_mobilome.sh",
    "06_isescan_mobilome.py",
    "07_run_mobsuite_plasmids.sh",
    "07_mobsuite_plasmids.py",
    "08_run_genomad_prophages.sh",
    "08_genomad_prophages.py",
    "09_run_mobile_safety_cooccurrence.sh",
    "09_mobile_safety_cooccurrence.py",
    "10_run_marker_screening.sh",
    "10_marker_screening.py",
    "11_run_probiosml_screen.sh",
    "11_probiosml_screen.py",
    "12_run_cazymes_dbcan.sh",
    "12_cazymes_dbcan.py",
    "13_run_antismash_minimal.sh",
    "13_antismash_minimal.py",
    "14_run_bagel5_full.sh",
    "14_bagel5_full.py",
    "15_run_epssmash_full.sh",
    "15_epssmash_full.py",
    "16_run_probml_screen.sh",
    "16_probml_screen.py",
    "17_run_pipeline_consolidation.sh",
    "17_pipeline_consolidation.py",
    "run_pipeline_final.sh",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final module numbering.")
    parser.add_argument("--scripts-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    scripts_dir = Path(args.scripts_dir).resolve()
    output = Path(args.output).resolve()
    rows = ["file\tstatus"]
    missing = []
    for name in EXPECTED:
        status = "PASS" if (scripts_dir / name).is_file() else "FAIL"
        rows.append(f"{name}\t{status}")
        if status == "FAIL":
            missing.append(name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
