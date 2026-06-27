#!/usr/bin/env python3

"""Parse BAGEL5 session output into a per-genome bacteriocin presence matrix.

Reproduces the V3/V4 semantics, established against the V3 reference summary:

A bacteriocin is counted only when BAGEL5 fills the final `Name` column of its
annotation table (e.g. Plantaricin_EF_plnE, Helveticin_J_hlv, Microcin_H47_mchB).
That column is populated only when the identification reaches a named core /
structural gene match. A context-only HMM hit fills `CoreName` but leaves `Name`
empty and must NOT be counted. Verified case: POT06 has CoreName=Helveticin_J
but Name empty, and the V3 reference scores it 0.

We therefore read ONLY the `Name` column. We deliberately ignore CoreName,
CoreHMM, CoreBlast, Class, SubClass, product, gene, and the __AOI.table
subject_ids (internal HMM/BlastP model codes), all of which caused over-counting.

Annotation-table schema (tab separated):
  locus_tag chrom type start end strand gene product CoreName CoreHMM
  ContextName ContextHMM CoreBlast Name StructuralGene Class SubClass
  Peptide CysSerThr PEPMatch color Type
"""

import csv
import re
import sys
from pathlib import Path


NAME_COL = "name"
STOP_VALUES = {"", "-", "na", "n/a", "none", "false", "true", "lightgrey"}


def slugify(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80]


def staged_name_from_dir(staged_dir: Path) -> str:
    fasta_files = sorted(
        p for p in staged_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".fna", ".fa", ".fasta", ".fas"}
    )
    if fasta_files:
        return fasta_files[0].name
    return staged_dir.name


def clean_cell(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in STOP_VALUES:
        return ""
    return text


def annotation_tables(session_dir: Path) -> list:
    clean = sorted(session_dir.rglob("*__AOI.Annotation.Clean.table"))
    if clean:
        return clean
    return sorted(session_dir.rglob("*.annotation.table"))


def read_rows(path: Path) -> list:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    try:
        return list(csv.DictReader(text.splitlines(), delimiter="\t"))
    except Exception:
        return []


def name_column(fieldnames: list):
    for name in fieldnames or []:
        if str(name).strip().lower() == NAME_COL:
            return name
    return None


def collect_names(session_dir: Path) -> list:
    """Distinct, non-empty values of the BAGEL5 `Name` column for this genome."""
    names = set()
    for table in annotation_tables(session_dir):
        rows = read_rows(table)
        if not rows:
            continue
        col = name_column(list(rows[0].keys()))
        if col is None:
            continue
        for row in rows:
            value = clean_cell(row.get(col, ""))
            if value:
                names.add(value)
    return sorted(names)


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: parse_bagel5_bacteriocins_matrix.py SESSION_DIR STAGED_DIR OUTPUT_DIR", file=sys.stderr)
        return 2

    session_dir = Path(sys.argv[1]).resolve()
    staged_dir = Path(sys.argv[2]).resolve()
    output_dir = Path(sys.argv[3]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not session_dir.is_dir():
        print("Session directory not found: " + str(session_dir), file=sys.stderr)
        return 1
    if not staged_dir.is_dir():
        print("Staged directory not found: " + str(staged_dir), file=sys.stderr)
        return 1

    staged_name = staged_name_from_dir(staged_dir)
    names = collect_names(session_dir)
    features = ["bagel5__" + slugify(n) for n in names]

    out_path = output_dir / "bagel5_bacteriocin_matrix.tsv"
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["staged_name", *features])
        writer.writerow([staged_name, *([1] * len(features))])

    summary_path = output_dir / "bagel5_parser_summary.tsv"
    with summary_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["staged_name", "n_bacteriocins", "detected_names", "parser_note"])
        writer.writerow([staged_name, len(names), ";".join(names),
                         "reads only the BAGEL5 Name column from annotation tables (V3-aligned)"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
