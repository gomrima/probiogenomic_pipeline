#!/usr/bin/env python3

import argparse
from pathlib import Path


EXPECTED = {
    "LIGHT": [
        "00_prepare_inputs",
        "02_run_safety_abricate",
        "03_run_tasmania_screen",
        "04_run_crispr_minced",
        "05_run_bacterial_toxins_screen",
        "10_run_marker_screening",
        "12_run_cazymes_dbcan",
        "17_run_pipeline_consolidation",
    ],
    "STANDARD": [
        "00_prepare_inputs",
        "02_run_safety_abricate",
        "03_run_tasmania_screen",
        "04_run_crispr_minced",
        "05_run_bacterial_toxins_screen",
        "06_run_isescan_mobilome",
        "07_run_mobsuite_plasmids",
        "10_run_marker_screening",
        "12_run_cazymes_dbcan",
        "17_run_pipeline_consolidation",
    ],
    "FULL": [
        "00_prepare_inputs",
        "02_run_safety_abricate",
        "03_run_tasmania_screen",
        "04_run_crispr_minced",
        "05_run_bacterial_toxins_screen",
        "06_run_isescan_mobilome",
        "07_run_mobsuite_plasmids",
        "08_run_genomad_prophages",
        "09_run_mobile_safety_cooccurrence",
        "10_run_marker_screening",
        "11_run_probiosml_screen",
        "12_run_cazymes_dbcan",
        "13_run_antismash_minimal",
        "14_run_bagel5_full",
        "15_run_epssmash_full",
        "16_run_probml_screen",
        "17_run_pipeline_consolidation",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final mode sequence declarations.")
    parser.add_argument("--launcher", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    launcher = Path(args.launcher).resolve()
    text = launcher.read_text(encoding="utf-8")
    rows = ["mode\texpected_sequence\tstatus"]
    failures = 0
    for mode, steps in EXPECTED.items():
        status = "PASS"
        for step in steps:
            if step not in text:
                status = "FAIL"
                failures += 1
        rows.append(f"{mode}\t{' -> '.join(steps)}\t{status}")
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

