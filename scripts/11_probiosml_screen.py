#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module 11 - ProbioSML Screening

Screens genome proteomes against the ProbioSML database (ProbioDB_1.0.faa)
using DIAMOND blastp with strict parameters to minimise false positives.

The module now also splits the global ProbioSML outputs by functional category
using the mapping file probiosml_subpillar_annotation.tsv located in
db/ProbioSML_DB.

Important behaviour:
  - If global TSV outputs already exist, the module can run in reuse mode and
    only produce the category split outputs.
  - No DIAMOND search is relaunched when --split-only is used.
  - TSV and XLSX category outputs are produced in dedicated subdirectories.
  - The original global outputs are preserved unchanged.

Global outputs:
  results/tsv/probiosml/probiosml_detail.tsv
  results/tsv/probiosml/probiosml_presence_absence_binary.tsv
  results/tsv/probiosml/probiosml_summary_by_genome.tsv
  results/xlsx/probiosml/probiosml_results.xlsx

Category split outputs:
  results/tsv/probiosml/by_category/
  results/xlsx/probiosml/by_category/
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import os
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PIPE_ROOT = Path(os.environ.get("PIPE_ROOT", Path(__file__).resolve().parent.parent))

MANIFEST_TSV = PIPE_ROOT / "work" / "manifest" / "input_manifest.tsv"

PROBIOSML_DB_DIR = PIPE_ROOT / "db" / "ProbioSML_DB"
PROBIOSML_FAA    = PROBIOSML_DB_DIR / "ProbioDB_1.0.faa"
PROBIOSML_DMND   = PROBIOSML_DB_DIR / "ProbioDB_1.0.dmnd"
PROBIOSML_MAPPING = PROBIOSML_DB_DIR / "probiosml_subpillar_annotation.tsv"

TMP_DIR = PIPE_ROOT / "work" / "tmp"

RAW_DIR      = PIPE_ROOT / "work" / "intermediate" / "probiosml" / "diamond_raw"
RESULTS_TSV  = PIPE_ROOT / "results" / "tsv"  / "probiosml"
RESULTS_XLSX = PIPE_ROOT / "results" / "xlsx" / "probiosml"

DETAIL_TSV  = RESULTS_TSV / "probiosml_detail.tsv"
BINARY_TSV  = RESULTS_TSV / "probiosml_presence_absence_binary.tsv"
SUMMARY_TSV = RESULTS_TSV / "probiosml_summary_by_genome.tsv"
WORKBOOK    = RESULTS_XLSX / "probiosml_results.xlsx"

CATEGORY_TSV_DIR  = RESULTS_TSV / "by_category"
CATEGORY_XLSX_DIR = RESULTS_XLSX / "by_category"

CATEGORY_INDEX_TSV = CATEGORY_TSV_DIR / "00_split_index.tsv"
CATEGORY_MAPPING_USED_TSV = CATEGORY_TSV_DIR / "00_mapping_used.tsv"
CATEGORY_UNMAPPED_TSV = CATEGORY_TSV_DIR / "00_unmapped_markers.tsv"
CATEGORY_INDEX_XLSX = CATEGORY_XLSX_DIR / "00_probiosml_category_split_index.xlsx"

# ---------------------------------------------------------------------------
# DIAMOND parameters
# ---------------------------------------------------------------------------

DIAMOND_THREADS     = 2
DIAMOND_EVALUE      = 1e-10
DIAMOND_IDENTITY    = 40
DIAMOND_QUERY_COV   = 60
DIAMOND_SUBJECT_COV = 60
DIAMOND_MAX_TARGETS = 5


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def safe_filename(name: str, max_len: int = 120) -> str:
    name = safe_text(name)
    name = re.sub(r"[<>:\"/\\|?*]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("._ ")
    if not name:
        name = "Unclassified"
    return name[:max_len]


def safe_sheet_name(name: str, max_len: int = 31) -> str:
    name = safe_filename(name, max_len=max_len)
    if not name:
        name = "sheet"
    return name[:max_len]


def read_tsv(path: Path, label: str) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Missing file for {label}: {path}")
    try:
        return pd.read_csv(path, sep="\t", dtype=str).fillna("")
    except Exception as exc:
        raise RuntimeError(f"Cannot read {label}: {path}\n{exc}") from exc


def run_command(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def global_tsv_outputs_exist() -> bool:
    return DETAIL_TSV.is_file() and BINARY_TSV.is_file() and SUMMARY_TSV.is_file()


def global_workbook_exists() -> bool:
    return WORKBOOK.is_file()


def category_split_outputs_exist() -> bool:
    return CATEGORY_INDEX_TSV.is_file() and CATEGORY_MAPPING_USED_TSV.is_file()


def ensure_dirs() -> None:
    for d in [RAW_DIR, RESULTS_TSV, RESULTS_XLSX, TMP_DIR, CATEGORY_TSV_DIR, CATEGORY_XLSX_DIR]:
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Step 1 - Build DIAMOND database
# ---------------------------------------------------------------------------

def build_diamond_db() -> None:
    if PROBIOSML_DMND.exists():
        print(f"[INFO] DIAMOND database already exists: {PROBIOSML_DMND}", flush=True)
        return

    if not PROBIOSML_FAA.is_file():
        raise FileNotFoundError(f"ProbioSML FAA not found: {PROBIOSML_FAA}")

    print(f"[INFO] Building DIAMOND database from: {PROBIOSML_FAA}", flush=True)
    cmd = [
        "diamond", "makedb",
        "--in", str(PROBIOSML_FAA),
        "--db", str(PROBIOSML_DMND),
        "--threads", str(DIAMOND_THREADS),
    ]
    run_command(cmd)
    print(f"[INFO] DIAMOND database written to: {PROBIOSML_DMND}", flush=True)


# ---------------------------------------------------------------------------
# Step 2 - Parse ProbioSML marker IDs from FAA headers
# ---------------------------------------------------------------------------

def load_marker_ids() -> list[str]:
    if not PROBIOSML_FAA.is_file():
        raise FileNotFoundError(f"ProbioSML FAA not found: {PROBIOSML_FAA}")

    seen: set[str] = set()
    ordered: list[str] = []

    with open(PROBIOSML_FAA, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith(">"):
                continue
            seq_id = line[1:].strip().split()[0]
            if seq_id and seq_id not in seen:
                seen.add(seq_id)
                ordered.append(seq_id)

    if not ordered:
        raise ValueError(f"No sequences found in: {PROBIOSML_FAA}")

    print(f"[INFO] ProbioSML marker sequences loaded: {len(ordered)}", flush=True)
    return ordered


# ---------------------------------------------------------------------------
# Step 3 - Load manifest
# ---------------------------------------------------------------------------

def load_manifest() -> pd.DataFrame:
    if not MANIFEST_TSV.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_TSV}")

    df = pd.read_csv(MANIFEST_TSV, sep="\t")

    required = ["genome_id", "normalized_faa", "status"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in manifest: {missing}")

    df["genome_id"]      = df["genome_id"].map(safe_text)
    df["normalized_faa"] = df["normalized_faa"].fillna("").astype(str)
    df["status"]         = df["status"].fillna("").astype(str)

    df = df[df["normalized_faa"] != ""].copy()
    df["faa_exists"] = df["normalized_faa"].apply(lambda x: Path(x).is_file())
    df = df[df["faa_exists"]].copy()

    if df.empty:
        raise ValueError("No valid genomes with normalized_faa found in manifest.")

    if df["genome_id"].duplicated().any():
        dupes = sorted(df.loc[df["genome_id"].duplicated(), "genome_id"].unique().tolist())
        raise ValueError(f"Duplicated genome_id values in manifest: {dupes}")

    return df[["genome_id", "normalized_faa"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step 4 - Run DIAMOND per genome
# ---------------------------------------------------------------------------

def run_diamond(genome_id: str, faa_path: Path) -> Path:
    out_path = RAW_DIR / f"{genome_id}.probiosml.diamond.tsv"

    cmd = [
        "diamond", "blastp",
        "--db", str(PROBIOSML_DMND),
        "--query", str(faa_path),
        "--out", str(out_path),
        "--outfmt", "6",
        "qseqid", "sseqid", "pident", "length",
        "qlen", "slen", "qcovhsp", "scovhsp",
        "evalue", "bitscore",
        "--evalue", str(DIAMOND_EVALUE),
        "--id", str(DIAMOND_IDENTITY),
        "--query-cover", str(DIAMOND_QUERY_COV),
        "--subject-cover", str(DIAMOND_SUBJECT_COV),
        "--max-target-seqs", str(DIAMOND_MAX_TARGETS),
        "--more-sensitive",
        "--threads", str(DIAMOND_THREADS),
        "--tmpdir", str(TMP_DIR),
    ]

    run_command(cmd)
    return out_path


# ---------------------------------------------------------------------------
# Step 5 - Parse DIAMOND hits
# ---------------------------------------------------------------------------

def parse_diamond_hits(tsv_path: Path) -> dict[str, dict]:
    best: dict[str, dict] = {}

    if not tsv_path.exists() or tsv_path.stat().st_size == 0:
        return best

    with open(tsv_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 10:
                continue

            (qseqid, sseqid, pident, length,
             qlen, slen, qcovhsp, scovhsp,
             evalue, bitscore) = parts[:10]

            marker_id = sseqid.strip()

            try:
                bs = float(bitscore)
            except ValueError:
                bs = 0.0

            if marker_id not in best or bs > best[marker_id]["bitscore"]:
                best[marker_id] = {
                    "query_id": marker_id if qseqid == "" else qseqid,
                    "marker_id": marker_id,
                    "pident": float(pident),
                    "alignment_length": int(float(length)),
                    "query_length": int(float(qlen)),
                    "subject_length": int(float(slen)),
                    "query_coverage": float(qcovhsp),
                    "subject_coverage": float(scovhsp),
                    "evalue": float(evalue),
                    "bitscore": bs,
                }

    return best


# ---------------------------------------------------------------------------
# Step 6 - Build global outputs
# ---------------------------------------------------------------------------

def build_outputs(
    manifest_df: pd.DataFrame,
    marker_ids: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    detail_rows = []
    binary_rows = []

    for _, row in manifest_df.iterrows():
        genome_id = row["genome_id"]
        faa_path  = Path(row["normalized_faa"])

        print(f"[INFO] Running DIAMOND (ProbioSML) for {genome_id}", flush=True)
        diamond_tsv = run_diamond(genome_id, faa_path)
        best_hits   = parse_diamond_hits(diamond_tsv)

        detected_count = len(best_hits)

        for marker_id, hit in best_hits.items():
            detail_rows.append({
                "genome_id": genome_id,
                "marker_id": marker_id,
                "query_id": hit["query_id"],
                "pident": hit["pident"],
                "alignment_length": hit["alignment_length"],
                "query_length": hit["query_length"],
                "subject_length": hit["subject_length"],
                "query_coverage": hit["query_coverage"],
                "subject_coverage": hit["subject_coverage"],
                "evalue": hit["evalue"],
                "bitscore": hit["bitscore"],
            })

        bin_row = {"genome_id": genome_id}
        for mid in marker_ids:
            bin_row[mid] = 1 if mid in best_hits else 0
        binary_rows.append(bin_row)

        n_total = len(marker_ids)
        print(
            f"[INFO]   {genome_id}: {detected_count}/{n_total} "
            f"ProbioSML markers detected",
            flush=True,
        )

    if detail_rows:
        detail_df = pd.DataFrame(detail_rows)
        detail_df = detail_df.sort_values(
            ["genome_id", "marker_id", "bitscore"],
            ascending=[True, True, False],
            kind="stable",
        ).reset_index(drop=True)
    else:
        detail_df = pd.DataFrame(columns=[
            "genome_id", "marker_id", "query_id",
            "pident", "alignment_length", "query_length", "subject_length",
            "query_coverage", "subject_coverage", "evalue", "bitscore",
        ])

    binary_df = pd.DataFrame(binary_rows)
    for col in binary_df.columns:
        if col != "genome_id":
            binary_df[col] = pd.to_numeric(binary_df[col], errors="raise").astype(int)

    marker_cols = [c for c in binary_df.columns if c != "genome_id"]
    summary_df = binary_df[["genome_id"]].copy()
    summary_df["n_probiosml_markers_detected"] = (
        binary_df[marker_cols].sum(axis=1).astype(int)
        if marker_cols else 0
    )
    summary_df["n_probiosml_markers_total"] = len(marker_ids)
    summary_df["probiosml_any_hit"] = (
        (summary_df["n_probiosml_markers_detected"] > 0).astype(int)
    )

    return detail_df, binary_df, summary_df


# ---------------------------------------------------------------------------
# Step 7 - Write global outputs
# ---------------------------------------------------------------------------

def write_global_outputs(
    detail_df: pd.DataFrame,
    binary_df: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> None:
    detail_df.to_csv(DETAIL_TSV, sep="\t", index=False)
    binary_df.to_csv(BINARY_TSV, sep="\t", index=False)
    summary_df.to_csv(SUMMARY_TSV, sep="\t", index=False)

    with pd.ExcelWriter(WORKBOOK, engine="openpyxl") as writer:
        binary_df.to_excel(writer, sheet_name="probiosml_binary", index=False)
        detail_df.to_excel(writer, sheet_name="probiosml_detail", index=False)
        summary_df.to_excel(writer, sheet_name="probiosml_summary", index=False)

    print(f"[INFO] Detail table   -> {DETAIL_TSV}", flush=True)
    print(f"[INFO] Binary matrix  -> {BINARY_TSV}", flush=True)
    print(f"[INFO] Summary table  -> {SUMMARY_TSV}", flush=True)
    print(f"[INFO] Excel workbook -> {WORKBOOK}", flush=True)


# ---------------------------------------------------------------------------
# Step 8 - Load existing global outputs
# ---------------------------------------------------------------------------

def load_global_outputs_from_tsv_or_workbook() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if global_tsv_outputs_exist():
        print("[INFO] Loading existing global ProbioSML TSV outputs.", flush=True)
        detail_df = read_tsv(DETAIL_TSV, "ProbioSML detail TSV")
        binary_df = read_tsv(BINARY_TSV, "ProbioSML binary TSV")
        summary_df = read_tsv(SUMMARY_TSV, "ProbioSML summary TSV")
        return detail_df, binary_df, summary_df

    if global_workbook_exists():
        print("[INFO] TSV outputs incomplete. Loading existing ProbioSML XLSX workbook.", flush=True)
        try:
            binary_df = pd.read_excel(WORKBOOK, sheet_name="probiosml_binary", dtype=str).fillna("")
            detail_df = pd.read_excel(WORKBOOK, sheet_name="probiosml_detail", dtype=str).fillna("")
            summary_df = pd.read_excel(WORKBOOK, sheet_name="probiosml_summary", dtype=str).fillna("")
        except Exception as exc:
            raise RuntimeError(
                f"Cannot load expected sheets from workbook: {WORKBOOK}\n{exc}"
            ) from exc
        return detail_df, binary_df, summary_df

    raise FileNotFoundError(
        "Global ProbioSML outputs are missing. Required either the three TSV files "
        f"({DETAIL_TSV}, {BINARY_TSV}, {SUMMARY_TSV}) or workbook {WORKBOOK}."
    )


# ---------------------------------------------------------------------------
# Step 9 - Category split logic
# ---------------------------------------------------------------------------

def validate_mapping(mapping_df: pd.DataFrame) -> pd.DataFrame:
    required = {"marker", "category"}
    missing = required - set(mapping_df.columns)
    if missing:
        raise ValueError(
            "Missing columns in ProbioSML mapping file: "
            f"{sorted(missing)}. Found columns: {list(mapping_df.columns)}"
        )

    mapping_df = mapping_df.copy()
    mapping_df["marker"] = mapping_df["marker"].map(safe_text)
    mapping_df["category"] = mapping_df["category"].map(safe_text)

    if "function_label" not in mapping_df.columns:
        mapping_df["function_label"] = mapping_df["marker"]
    else:
        mapping_df["function_label"] = mapping_df["function_label"].map(safe_text)

    mapping_df = mapping_df[mapping_df["marker"] != ""].copy()
    mapping_df.loc[mapping_df["category"] == "", "category"] = "Unclassified"

    mapping_df = mapping_df.drop_duplicates(
        subset=["marker", "category", "function_label"]
    ).copy()

    return mapping_df[["marker", "category", "function_label"]].reset_index(drop=True)


def force_binary_values(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col == "genome_id":
            continue
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)
        out[col] = out[col].clip(lower=0, upper=1)
    return out


def build_category_summary(binary_cat: pd.DataFrame, category: str) -> pd.DataFrame:
    marker_cols = [c for c in binary_cat.columns if c != "genome_id"]
    summary = binary_cat[["genome_id"]].copy()
    summary["category"] = category
    summary["n_probiosml_markers_detected_in_category"] = (
        binary_cat[marker_cols].sum(axis=1).astype(int) if marker_cols else 0
    )
    summary["n_probiosml_markers_total_in_category"] = len(marker_cols)
    summary["probiosml_any_hit_in_category"] = (
        summary["n_probiosml_markers_detected_in_category"] > 0
    ).astype(int)
    return summary


def write_category_index_workbook(
    split_index: pd.DataFrame,
    mapping_df: pd.DataFrame,
    unmapped_df: pd.DataFrame,
) -> None:
    try:
        with pd.ExcelWriter(CATEGORY_INDEX_XLSX, engine="openpyxl") as writer:
            split_index.to_excel(writer, sheet_name="split_index", index=False)
            mapping_df.to_excel(writer, sheet_name="mapping_used", index=False)
            unmapped_df.to_excel(writer, sheet_name="unmapped_markers", index=False)
        print(f"[INFO] Category split index workbook -> {CATEGORY_INDEX_XLSX}", flush=True)
    except Exception as exc:
        print(f"[WARN] Could not write category index workbook: {exc}", flush=True)


def split_probiosml_by_category(
    detail_df: pd.DataFrame,
    binary_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    mapping_path: Path,
    write_category_xlsx: bool = True,
    include_unmapped: bool = False,
) -> pd.DataFrame:

    if not mapping_path.is_file():
        raise FileNotFoundError(f"ProbioSML category mapping file not found: {mapping_path}")

    if "genome_id" not in binary_df.columns:
        raise ValueError("The binary matrix does not contain the column genome_id.")
    if "genome_id" not in detail_df.columns or "marker_id" not in detail_df.columns:
        raise ValueError("The detail table must contain genome_id and marker_id columns.")

    mapping_df = validate_mapping(read_tsv(mapping_path, "ProbioSML category mapping"))

    binary_df = binary_df.copy()
    detail_df = detail_df.copy()
    summary_df = summary_df.copy()

    binary_df["genome_id"] = binary_df["genome_id"].map(safe_text)
    detail_df["genome_id"] = detail_df["genome_id"].map(safe_text)
    detail_df["marker_id"] = detail_df["marker_id"].map(safe_text)

    if "genome_id" in summary_df.columns:
        summary_df["genome_id"] = summary_df["genome_id"].map(safe_text)

    marker_cols = [c for c in binary_df.columns if c != "genome_id"]
    binary_marker_set = set(marker_cols)
    detail_marker_set = set(detail_df["marker_id"].unique())
    mapped_marker_set = set(mapping_df["marker"].unique())

    unmapped_all = sorted((binary_marker_set | detail_marker_set) - mapped_marker_set)
    unmapped_df = pd.DataFrame({
        "marker": unmapped_all,
        "in_binary": [int(m in binary_marker_set) for m in unmapped_all],
        "in_detail": [int(m in detail_marker_set) for m in unmapped_all],
    })

    mapping_df.to_csv(CATEGORY_MAPPING_USED_TSV, sep="\t", index=False)
    unmapped_df.to_csv(CATEGORY_UNMAPPED_TSV, sep="\t", index=False)

    if include_unmapped and unmapped_all:
        extra = pd.DataFrame({
            "marker": unmapped_all,
            "category": "Unmapped",
            "function_label": unmapped_all,
        })
        mapping_df = pd.concat([mapping_df, extra], ignore_index=True)

    print(f"[INFO] Category mapping file : {mapping_path}", flush=True)
    print(f"[INFO] Binary genomes       : {len(binary_df)}", flush=True)
    print(f"[INFO] Binary markers       : {len(marker_cols)}", flush=True)
    print(f"[INFO] Detail hits          : {len(detail_df)}", flush=True)
    print(f"[INFO] Mapped markers       : {len(mapped_marker_set)}", flush=True)
    print(f"[INFO] Unmapped markers     : {len(unmapped_all)}", flush=True)

    split_index_rows = []
    categories = sorted(mapping_df["category"].dropna().unique().tolist())

    for category in categories:
        category_mapping = mapping_df[mapping_df["category"] == category].copy()
        category_markers_all = category_mapping["marker"].drop_duplicates().tolist()
        category_marker_set = set(category_markers_all)

        category_markers_binary = [
            m for m in category_markers_all
            if m in binary_marker_set
        ]

        detail_cat = detail_df[detail_df["marker_id"].isin(category_marker_set)].copy()

        binary_cat = binary_df[["genome_id"] + category_markers_binary].copy()
        binary_cat = force_binary_values(binary_cat)

        summary_cat = build_category_summary(binary_cat, category)

        if "genome_id" in summary_df.columns:
            extra_cols = [c for c in summary_df.columns if c != "genome_id"]
            summary_cat = summary_cat.merge(
                summary_df[["genome_id"] + extra_cols],
                on="genome_id",
                how="left",
                suffixes=("", "_global"),
            )

        safe_cat = safe_filename(category)

        binary_file = CATEGORY_TSV_DIR / f"{safe_cat}__binary.tsv"
        detail_file = CATEGORY_TSV_DIR / f"{safe_cat}__detail.tsv"
        summary_file = CATEGORY_TSV_DIR / f"{safe_cat}__summary_by_genome.tsv"
        mapping_file = CATEGORY_TSV_DIR / f"{safe_cat}__mapping.tsv"

        binary_cat.to_csv(binary_file, sep="\t", index=False)
        detail_cat.to_csv(detail_file, sep="\t", index=False)
        summary_cat.to_csv(summary_file, sep="\t", index=False)
        category_mapping.to_csv(mapping_file, sep="\t", index=False)

        xlsx_file = ""
        if write_category_xlsx:
            xlsx_path = CATEGORY_XLSX_DIR / f"{safe_cat}__probiosml_results.xlsx"
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                binary_cat.to_excel(writer, sheet_name="binary", index=False)
                detail_cat.to_excel(writer, sheet_name="detail", index=False)
                summary_cat.to_excel(writer, sheet_name="summary_by_genome", index=False)
                category_mapping.to_excel(writer, sheet_name="mapping", index=False)
            xlsx_file = str(xlsx_path)

        split_index_rows.append({
            "category": category,
            "safe_category_name": safe_cat,
            "n_mapping_markers": len(category_markers_all),
            "n_binary_markers": len(category_markers_binary),
            "n_detail_hits": len(detail_cat),
            "n_genomes": len(binary_cat),
            "binary_file": str(binary_file),
            "detail_file": str(detail_file),
            "summary_file": str(summary_file),
            "mapping_file": str(mapping_file),
            "xlsx_file": xlsx_file,
        })

        print(
            f"[OK] {category} | "
            f"{len(category_markers_binary)} binary markers | "
            f"{len(detail_cat)} detail hits",
            flush=True,
        )

    split_index = pd.DataFrame(split_index_rows)
    split_index.to_csv(CATEGORY_INDEX_TSV, sep="\t", index=False)

    write_category_index_workbook(split_index, mapping_df, unmapped_df)

    print(f"[INFO] Category TSV directory  -> {CATEGORY_TSV_DIR}", flush=True)
    print(f"[INFO] Category XLSX directory -> {CATEGORY_XLSX_DIR}", flush=True)
    print(f"[INFO] Category split index    -> {CATEGORY_INDEX_TSV}", flush=True)

    return split_index


# ---------------------------------------------------------------------------
# CLI and main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "ProbioSML screening and category split module. "
            "Can reuse existing global outputs to generate category split files."
        )
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="If global outputs already exist, skip DIAMOND and only generate category split outputs.",
    )
    parser.add_argument(
        "--split-only",
        action="store_true",
        help="Do not run DIAMOND. Read existing global outputs and generate category split outputs only.",
    )
    parser.add_argument(
        "--force-full",
        action="store_true",
        help="Force full DIAMOND screening even if global outputs already exist.",
    )
    parser.add_argument(
        "--skip-category-split",
        action="store_true",
        help="Run only the global ProbioSML screening and do not create category split outputs.",
    )
    parser.add_argument(
        "--mapping",
        default=str(PROBIOSML_MAPPING),
        help=f"ProbioSML marker to category mapping. Default: {PROBIOSML_MAPPING}",
    )
    parser.add_argument(
        "--no-category-xlsx",
        action="store_true",
        help="Write category TSV files only. Do not write per-category XLSX workbooks.",
    )
    parser.add_argument(
        "--include-unmapped",
        action="store_true",
        help="Create an additional Unmapped category for markers absent from the mapping file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()

    mapping_path = Path(args.mapping)

    if args.split_only:
        print("[INFO] Running ProbioSML category split only. DIAMOND will not be launched.", flush=True)
        detail_df, binary_df, summary_df = load_global_outputs_from_tsv_or_workbook()
        split_probiosml_by_category(
            detail_df=detail_df,
            binary_df=binary_df,
            summary_df=summary_df,
            mapping_path=mapping_path,
            write_category_xlsx=not args.no_category_xlsx,
            include_unmapped=args.include_unmapped,
        )
        print("[INFO] Module 11 - ProbioSML category split completed.", flush=True)
        return

    if args.reuse_existing and not args.force_full and (global_tsv_outputs_exist() or global_workbook_exists()):
        print("[INFO] Existing global ProbioSML outputs detected. Reusing them.", flush=True)
        detail_df, binary_df, summary_df = load_global_outputs_from_tsv_or_workbook()
        if not args.skip_category_split:
            split_probiosml_by_category(
                detail_df=detail_df,
                binary_df=binary_df,
                summary_df=summary_df,
                mapping_path=mapping_path,
                write_category_xlsx=not args.no_category_xlsx,
                include_unmapped=args.include_unmapped,
            )
        print("[INFO] Module 11 - ProbioSML reuse mode completed.", flush=True)
        return

    build_diamond_db()

    marker_ids = load_marker_ids()
    manifest_df = load_manifest()

    print(f"[INFO] Genomes to screen : {len(manifest_df)}", flush=True)
    print(f"[INFO] ProbioSML markers : {len(marker_ids)}", flush=True)
    print(
        f"[INFO] DIAMOND thresholds: E-value <= {DIAMOND_EVALUE}, "
        f"identity >= {DIAMOND_IDENTITY}%, "
        f"query-cov >= {DIAMOND_QUERY_COV}%, "
        f"subject-cov >= {DIAMOND_SUBJECT_COV}%",
        flush=True,
    )

    detail_df, binary_df, summary_df = build_outputs(manifest_df, marker_ids)
    write_global_outputs(detail_df, binary_df, summary_df)

    if not args.skip_category_split:
        split_probiosml_by_category(
            detail_df=detail_df,
            binary_df=binary_df,
            summary_df=summary_df,
            mapping_path=mapping_path,
            write_category_xlsx=not args.no_category_xlsx,
            include_unmapped=args.include_unmapped,
        )

    print("[INFO] Module 11 - ProbioSML screening completed.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        sys.exit(1)

