#!/usr/bin/env python3

import argparse
from pathlib import Path


REQUIRED_FILES = [
    "scripts/01_run_prepare_marker_resources.sh",
    "dev/bagel5_full_integration/parser_design/parse_bagel5_bacteriocins_matrix.py",
    "dev/epssmash_full_integration/parser_design/parse_epssmash_products_to_binary_matrix.py",
    "AUTHORS.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/tool_references.md",
    "docs/database_references.md",
    "docs/marker_database_attribution.md",
    "metadata/tool_and_database_citations.tsv",
    "metadata/marker_database_provenance.tsv",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit release packaging hygiene and required support files.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    rows = ["check_id\tstatus\tnotes"]
    failures = 0

    for rel in REQUIRED_FILES:
        status = "PASS" if (root / rel).is_file() else "FAIL"
        if status == "FAIL":
            failures += 1
        rows.append(f"required_file:{rel}\t{status}\t{rel}")

    pyc_files = sorted(root.rglob("*.pyc"))
    status = "PASS" if not pyc_files else "FAIL"
    if pyc_files:
        failures += 1
    rows.append(f"no_pyc_files\t{status}\t{len(pyc_files)} pyc files")

    pycache_dirs = sorted(p for p in root.rglob("__pycache__") if p.is_dir())
    status = "PASS" if not pycache_dirs else "FAIL"
    if pycache_dirs:
        failures += 1
    rows.append(f"no_pycache_dirs\t{status}\t{len(pycache_dirs)} pycache directories")

    dockerignore = root / ".dockerignore"
    dockerfile = root / "Dockerfile"
    status = "PASS" if (not dockerignore.exists() or dockerfile.is_file()) else "FAIL"
    if status == "FAIL":
        failures += 1
    rows.append("dockerignore_has_dockerfile\t" + status + "\t.dockerignore only allowed when Dockerfile exists")

    readme_no_ext = root / "Documentation" / "README_V4"
    status = "PASS" if not readme_no_ext.exists() else "FAIL"
    if status == "FAIL":
        failures += 1
    rows.append("no_extensionless_readme_duplicate\t" + status + "\tDocumentation/README_V4")

    launcher = root / "scripts" / "run_pipeline_final.sh"
    text = launcher.read_text(encoding="utf-8", errors="replace")
    expected_fragments = [
        "preflight_marker_resources",
        "01_run_prepare_marker_resources.sh",
        "dev/bagel5_full_integration/parser_design/parse_bagel5_bacteriocins_matrix.py",
        "ANTISMASH_DEPENDENCIES_ENV/bin/epsSMASH",
        "dev/epssmash_full_integration/parser_design/parse_epssmash_products_to_binary_matrix.py",
    ]
    for fragment in expected_fragments:
        status = "PASS" if fragment in text else "FAIL"
        if status == "FAIL":
            failures += 1
        rows.append(f"launcher_contract:{fragment}\t{status}\t{fragment}")

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
