#!/usr/bin/env python3

import subprocess
import os
from pathlib import Path
from typing import List, Dict

import pandas as pd

PIPE_ROOT = Path(os.environ.get("PIPE_ROOT", Path(__file__).resolve().parent.parent))

NORMALIZED_FNA_DIR = PIPE_ROOT / "work" / "normalized_fna"

MINCED_RAW_DIR = PIPE_ROOT / "work" / "intermediate" / "crispr" / "minced_raw"
MERGED_DIR = PIPE_ROOT / "work" / "intermediate" / "crispr" / "merged_tables"

RESULTS_TSV_DIR = PIPE_ROOT / "results" / "tsv" / "crispr"
RESULTS_XLSX_DIR = PIPE_ROOT / "results" / "xlsx" / "crispr"

DETAIL_COLUMNS = [
    "genome_id",
    "contig_id",
    "feature_type",
    "start",
    "end",
    "strand",
    "array_length_nt",
    "attributes",
    "pass_presence",
]


def ensure_dirs() -> None:
    for d in [MINCED_RAW_DIR, MERGED_DIR, RESULTS_TSV_DIR, RESULTS_XLSX_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def get_genome_fna_files() -> List[Path]:
    return sorted(NORMALIZED_FNA_DIR.glob("*.fna"))


def run_minced(genome_id: str, fna_file: Path) -> Dict[str, Path]:
    txt_out = MINCED_RAW_DIR / f"{genome_id}.minced.txt"
    gff_out = MINCED_RAW_DIR / f"{genome_id}.minced.gff"

    cmd = [
        "minced",
        "-gff",
        str(fna_file),
        str(txt_out),
        str(gff_out),
    ]

    subprocess.run(cmd, check=True)

    return {
        "txt": txt_out,
        "gff": gff_out,
    }


def parse_gff(gff_file: Path, genome_id: str) -> List[Dict]:
    rows: List[Dict] = []

    if not gff_file.exists():
        return rows

    with open(gff_file, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            if line.startswith("#"):
                continue

            parts = line.rstrip("\n").split("\t")
            if len(parts) != 9:
                continue

            seqid, source, feature_type, start, end, score, strand, phase, attributes = parts

            try:
                start_i = int(start)
                end_i = int(end)
            except ValueError:
                continue

            array_length_nt = end_i - start_i + 1
            pass_presence = 1 if array_length_nt > 0 else 0

            rows.append({
                "genome_id": genome_id,
                "contig_id": seqid,
                "feature_type": feature_type,
                "start": start_i,
                "end": end_i,
                "strand": strand,
                "array_length_nt": array_length_nt,
                "attributes": attributes,
                "pass_presence": pass_presence,
            })

    return rows


def build_detail_dataframe(all_rows: List[Dict]) -> pd.DataFrame:
    if not all_rows:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    df = pd.DataFrame(all_rows)

    for col in DETAIL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[DETAIL_COLUMNS].copy()

    int_cols = ["start", "end", "array_length_nt", "pass_presence"]
    text_cols = ["genome_id", "contig_id", "feature_type", "strand", "attributes"]

    for col in int_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    for col in text_cols:
        df[col] = df[col].fillna("").astype(str)

    df = df.sort_values(
        by=["genome_id", "contig_id", "start", "end"],
        kind="stable"
    ).reset_index(drop=True)

    return df


def build_binary_dataframe(detail_df: pd.DataFrame, genomes: List[str]) -> pd.DataFrame:
    genomes = sorted(genomes)

    if detail_df.empty:
        return pd.DataFrame({
            "genome_id": genomes,
            "crispr_array_present": [0] * len(genomes),
        })

    kept = detail_df[detail_df["pass_presence"] == 1].copy()

    present_genomes = set(kept["genome_id"].tolist())

    binary_df = pd.DataFrame({
        "genome_id": genomes,
        "crispr_array_present": [1 if g in present_genomes else 0 for g in genomes],
    })

    binary_df["crispr_array_present"] = (
        pd.to_numeric(binary_df["crispr_array_present"], errors="coerce")
        .fillna(0)
        .clip(upper=1)
        .astype(int)
    )

    return binary_df


def build_summary_dataframe(detail_df: pd.DataFrame, genomes: List[str]) -> pd.DataFrame:
    genomes = sorted(genomes)

    if detail_df.empty:
        return pd.DataFrame({
            "genome_id": genomes,
            "crispr_array_count": [0] * len(genomes),
        })

    kept = detail_df[detail_df["pass_presence"] == 1].copy()

    counts = (
        kept.groupby("genome_id", as_index=False)
        .size()
        .rename(columns={"size": "crispr_array_count"})
    )

    summary_df = pd.DataFrame({"genome_id": genomes})
    summary_df = summary_df.merge(counts, on="genome_id", how="left")
    summary_df["crispr_array_count"] = (
        pd.to_numeric(summary_df["crispr_array_count"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    return summary_df


def write_outputs(detail_df: pd.DataFrame, binary_df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    detail_out = RESULTS_TSV_DIR / "crispr_detection_detail.tsv"
    binary_out = RESULTS_TSV_DIR / "crispr_presence_absence_binary.tsv"
    summary_out = RESULTS_TSV_DIR / "crispr_summary_by_genome.tsv"

    merged_copy = MERGED_DIR / "crispr_detection_detail_copy.tsv"
    xlsx_out = RESULTS_XLSX_DIR / "crispr_minced_results.xlsx"

    detail_df.to_csv(detail_out, sep="\t", index=False, na_rep="")
    detail_df.to_csv(merged_copy, sep="\t", index=False, na_rep="")
    binary_df.to_csv(binary_out, sep="\t", index=False, na_rep="")
    summary_df.to_csv(summary_out, sep="\t", index=False, na_rep="")

    with pd.ExcelWriter(xlsx_out, engine="openpyxl") as writer:
        detail_df.to_excel(writer, sheet_name="crispr_detail", index=False)
        binary_df.to_excel(writer, sheet_name="crispr_binary", index=False)
        summary_df.to_excel(writer, sheet_name="crispr_summary", index=False)

    print(f"[INFO] CRISPR detail written to: {detail_out}")
    print(f"[INFO] CRISPR binary written to: {binary_out}")
    print(f"[INFO] CRISPR summary written to: {summary_out}")
    print(f"[INFO] CRISPR Excel workbook written to: {xlsx_out}")


def main() -> None:
    ensure_dirs()

    fna_files = get_genome_fna_files()
    if not fna_files:
        raise FileNotFoundError(f"No FNA files found in: {NORMALIZED_FNA_DIR}")

    print(f"[INFO] Genomes with available FNA: {len(fna_files)}")

    all_rows: List[Dict] = []
    genome_ids: List[str] = []

    for fna_file in fna_files:
        genome_id = fna_file.stem
        genome_ids.append(genome_id)

        print(f"[INFO] Running MinCED for {genome_id}")
        outputs = run_minced(genome_id, fna_file)

        rows = parse_gff(outputs["gff"], genome_id)
        all_rows.extend(rows)

    detail_df = build_detail_dataframe(all_rows)
    binary_df = build_binary_dataframe(detail_df, genome_ids)
    summary_df = build_summary_dataframe(detail_df, genome_ids)

    write_outputs(detail_df, binary_df, summary_df)


if __name__ == "__main__":
    main()

