#!/usr/bin/env python3

"""
Module 08 - geNomad: detection of prophage regions
=========================================================
Detects prophage regions (integrated proviruses) in assembled bacterial
genomes using geNomad (Camargo et al., Nature Biotechnology 2023).

Standardized outputs (same logic as ISEScan / MOB-suite):
  - DETAIL TABLE    : one row per prophage region with exact coordinates
  - SUMMARY TABLE   : one row per genome with aggregated metrics
  - BINARY MATRIX   : presence/absence per genome and per viral category
  - FAILURES TABLE  : failed genomes with error message
  - EXTRACTED FASTA : prophage sequences for ABRicate cross-screening
  - XLSX WORKBOOK   : all consolidated tables

ABRicate cross-screening:
  The extracted FASTA files are named with the stable region_id
  (GENOME__phage_NNNN.fna), directly usable with:
    abricate --db vfdb --minid 80 --mincov 80 <region>.fna
    abricate --db card --minid 80 --mincov 80 <region>.fna

Machine constraint: 2 threads maximum, 8 GB RAM.
"""

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

try:
    from Bio import SeqIO
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord
except ImportError:
    print(
        "[FATAL] Biopython is not installed in the active environment.",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# geNomad filtering thresholds
# ---------------------------------------------------------------------------

GENOMAD_MIN_SCORE   = 0.7   # minimum score to keep a region (official recommendation)
GENOMAD_MIN_LENGTH  = 1000  # minimum length in bp for prophage regions

# ---------------------------------------------------------------------------
# Standardized columns, same convention as ISEScan / MOB-suite
# ---------------------------------------------------------------------------

DETAIL_COLUMNS = [
    "genome_id",
    "input_fna",
    "result_dir",
    "contig_id",
    "region_id",
    "start",
    "end",
    "length_bp",
    "genomad_score",
    "topology",
    "taxonomy",
    "n_hallmarks",
    "n_genes",
    "fdr",
    "is_provirus",
    "extracted_fasta",
]

SUMMARY_COLUMNS = [
    "genome_id",
    "input_fna",
    "n_prophage_regions",
    "n_provirus_regions",
    "n_linear_regions",
    "n_unique_taxonomies",
    "total_prophage_bp",
    "extracted_fasta_dir",
]

FAIL_COLUMNS = [
    "genome_id",
    "input_fna",
    "status",
    "message",
]

# High-level taxonomic categories recognized by geNomad
GENOMAD_TAXONOMY_GROUPS = [
    "Caudoviricetes",
    "Inoviridae",
    "Microviridae",
    "Pleolipoviridae",
    "Sphaerolipoviridae",
    "unclassified",
]

EXCEL_MAX_ROWS = 1_048_576


# ---------------------------------------------------------------------------
# Utilitaires communs
# ---------------------------------------------------------------------------

def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sanitize_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(name))


def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def run_command(cmd: List[str], log_prefix: str = "") -> Tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    print(f"{log_prefix}Running: {' '.join(str(c) for c in cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def load_manifest(manifest_path: Path) -> pd.DataFrame:
    """Load the manifest and keep valid entries that have an existing FNA."""
    df = pd.read_csv(manifest_path, sep="\t", dtype=str).fillna("")

    required_cols = ["genome_id", "normalized_fna", "status"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in the manifest: {missing}")

    df = df[df["status"] == "OK"].copy()
    df = df[df["normalized_fna"].str.strip() != ""].copy()
    df = df[df["normalized_fna"].apply(lambda x: Path(x).is_file())].copy()

    return df


# ---------------------------------------------------------------------------
# Locate the geNomad results file
# ---------------------------------------------------------------------------

def find_genomad_summary(run_dir: Path, genome_id: str) -> Path:
    """
    Locate the viral summary file produced by geNomad.

    geNomad (versions 1.4+) writes a single summary file containing both
    free viruses and integrated proviruses:
      run_dir/
        {stem}_summary/
          {stem}_virus_summary.tsv     -> ALL viruses (free + proviruses)
          {stem}_virus.fna             -> nucleotide sequences
          {stem}_virus_proteins.faa    -> protein sequences
          {stem}_virus_genes.tsv       -> gene-by-gene annotation

    Proviruses (integrated prophages) have:
      - topology = "Provirus"
      - seq_name = "CONTIG|provirus_START_END"
      - coordinates = "START-END"

    We first look for *_virus_summary.tsv (modern format), then
    *_provirus_summary.tsv as a fallback (older geNomad versions).
    """

    # Recherche prioritaire : virus_summary (format actuel)
    for summary_dir in sorted(run_dir.glob("*_summary")):
        virus_tsv = next(summary_dir.glob("*_virus_summary.tsv"), None)
        if virus_tsv and virus_tsv.is_file():
            return virus_tsv

    # Fallback: provirus_summary (hypothetical format for older versions)
    for summary_dir in sorted(run_dir.glob("*_summary")):
        provirus_tsv = next(summary_dir.glob("*_provirus_summary.tsv"), None)
        if provirus_tsv and provirus_tsv.is_file():
            return provirus_tsv

    raise FileNotFoundError(
        f"No *_virus_summary.tsv file found in {run_dir}. "
        "Check that geNomad ran correctly (summary module)."
    )


# ---------------------------------------------------------------------------
# Parse the geNomad results file
# ---------------------------------------------------------------------------

def parse_genomad_summary(
    summary_tsv: Path,
    genome_id: str,
    input_fna: Path,
    run_dir: Path,
    fasta_out_dir: Path,
    min_score: float,
    min_length: int,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse the *_provirus_summary.tsv file produced by geNomad.

    Key columns of the geNomad file:
      seq_name     -> contig identifier + coordinates for proviruses
                     Provirus format: "CONTIG|provirus_START_END"
                     Virus format   : "CONTIG"
      length       -> region length in bp
      topology     -> Provirus / Linear / Circular
      coordinates  : "start|end" for proviruses, "" for free viruses
      n_genes      -> number of predicted genes
      virus_score  -> geNomad score (0-1)
      fdr          -> false discovery rate
      n_hallmarks  -> number of viral hallmark genes
      taxonomy     -> viral taxonomy (e.g., "Viruses;Duplodnaviria;...")

    Returns a DETAIL DataFrame and the list of sequences to extract.
    """

    if not summary_tsv.is_file() or summary_tsv.stat().st_size == 0:
        return [], []

    try:
        df = pd.read_csv(summary_tsv, sep="\t", dtype=str).fillna("")
    except Exception as exc:
        raise RuntimeError(f"Error reading {summary_tsv}: {exc}")

    # Normalize column names (robustness across geNomad versions)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Flexible mapping of column names
    col_map = {
        "seq_name":    ["seq_name", "sequence_name", "contig", "name"],
        "length":      ["length", "seq_length", "length_bp"],
        "topology":    ["topology", "type"],
        "coordinates": ["coordinates", "coords", "provirus_coordinates"],
        "n_genes":     ["n_genes", "genes", "gene_count"],
        "score":       ["virus_score", "score", "genomad_score", "max_score"],
        "fdr":         ["fdr", "false_discovery_rate"],
        "n_hallmarks": ["n_hallmarks", "hallmarks", "hallmark_count"],
        "taxonomy":    ["taxonomy", "viral_taxonomy", "classification"],
    }

    def find_col(candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    col_seq_name    = find_col(col_map["seq_name"])
    col_length      = find_col(col_map["length"])
    col_topology    = find_col(col_map["topology"])
    col_coordinates = find_col(col_map["coordinates"])
    col_n_genes     = find_col(col_map["n_genes"])
    col_score       = find_col(col_map["score"])
    col_fdr         = find_col(col_map["fdr"])
    col_n_hallmarks = find_col(col_map["n_hallmarks"])
    col_taxonomy    = find_col(col_map["taxonomy"])

    if not col_seq_name or not col_score:
        raise RuntimeError(
            f"Required columns (seq_name, virus_score) are absent in "
            f"{summary_tsv}. Columns found: {list(df.columns)}"
        )

    rows = []
    extraction_requests = []

    for idx, row in df.iterrows():

        seq_name_raw = safe_text(row[col_seq_name])
        if not seq_name_raw:
            continue

        # --- Score ---
        try:
            score = float(row[col_score]) if col_score else 0.0
        except (ValueError, TypeError):
            score = 0.0

        if score < min_score:
            continue

        # --- Length ---
        try:
            length_bp = int(float(row[col_length])) if col_length else 0
        except (ValueError, TypeError):
            length_bp = 0

        if length_bp < min_length:
            continue

        # --- Parse seq_name to extract contig_id and coordinates ---
        #
        # geNomad encodes proviruses as:
        #   "CONTIG|provirus_START_END"  (ex: "NZ_CP01234|provirus_10000_85000")
        # and free viruses as:
        #   "CONTIG"
        #
        is_provirus = 0
        contig_id   = seq_name_raw
        start       = 0
        end         = length_bp

        provirus_pattern = re.search(
            r"^(.+?)\|provirus_(\d+)_(\d+)$", seq_name_raw
        )

        if provirus_pattern:
            contig_id   = provirus_pattern.group(1)
            start       = int(provirus_pattern.group(2))
            end         = int(provirus_pattern.group(3))
            is_provirus = 1
            length_bp   = max(0, end - start)
        else:
            # Try to read coordinates from the dedicated column if it exists
            if col_coordinates:
                coord_str = safe_text(row[col_coordinates])
                coord_match = re.match(r"(\d+)\|(\d+)", coord_str)
                if coord_match:
                    start       = int(coord_match.group(1))
                    end         = int(coord_match.group(2))
                    is_provirus = 1
                    length_bp   = max(0, end - start)

        if length_bp < min_length:
            continue

        # --- Metadata ---
        try:
            n_hallmarks = int(float(row[col_n_hallmarks])) if col_n_hallmarks else 0
        except (ValueError, TypeError):
            n_hallmarks = 0

        try:
            n_genes = int(float(row[col_n_genes])) if col_n_genes else 0
        except (ValueError, TypeError):
            n_genes = 0

        try:
            fdr = float(row[col_fdr]) if col_fdr else None
        except (ValueError, TypeError):
            fdr = None

        topology = safe_text(row[col_topology]) if col_topology else "unknown"
        if not topology:
            topology = "Provirus" if is_provirus else "unknown"

        # Taxonomy: keep only the highest useful family/order level
        taxonomy_raw = safe_text(row[col_taxonomy]) if col_taxonomy else ""
        taxonomy = _extract_taxonomy_group(taxonomy_raw)

        # --- Stable region identifier (usable by ABRicate) ---
        region_id = f"{sanitize_name(genome_id)}__phage_{idx:04d}"

        # Path of the extracted FASTA
        fasta_filename   = f"{region_id}.fna"
        extracted_fasta  = str(fasta_out_dir / fasta_filename)

        rows.append({
            "genome_id":       genome_id,
            "input_fna":       str(input_fna),
            "result_dir":      str(run_dir),
            "contig_id":       contig_id,
            "region_id":       region_id,
            "start":           start,
            "end":             end,
            "length_bp":       length_bp,
            "genomad_score":   round(score, 6),
            "topology":        topology,
            "taxonomy":        taxonomy,
            "n_hallmarks":     n_hallmarks,
            "n_genes":         n_genes,
            "fdr":             round(fdr, 6) if fdr is not None else "",
            "is_provirus":     is_provirus,
            "extracted_fasta": extracted_fasta,
        })

        extraction_requests.append({
            "contig_id":      contig_id,
            "start":          start,
            "end":            end,
            "is_provirus":    is_provirus,
            "region_id":      region_id,
            "fasta_out_path": extracted_fasta,
        })

    return rows, extraction_requests


def _extract_taxonomy_group(taxonomy_str: str) -> str:
    """
    Extract the high-level taxonomic group from the geNomad string.
    Example: "Viruses;Duplodnaviria;Heunggongvirae;Uroviricota;Caudoviricetes"
              -> "Caudoviricetes"
    """
    if not taxonomy_str:
        return "unclassified"

    parts = [p.strip() for p in taxonomy_str.split(";") if p.strip()]

    # Find the most precise known group
    for group in GENOMAD_TAXONOMY_GROUPS:
        if any(group.lower() in p.lower() for p in parts):
            return group

    # Return the last available taxonomic level
    return parts[-1] if parts else "unclassified"


# ---------------------------------------------------------------------------
# Extract prophage sequences (for ABRicate)
# ---------------------------------------------------------------------------

def extract_prophage_sequences(
    input_fna: Path,
    extraction_requests: List[Dict],
    fasta_out_dir: Path,
    genome_id: str,
) -> int:
    """
    Extract prophage sequences from the genome FNA.
    Produces one FASTA file per region in fasta_out_dir.

    For proviruses (is_provirus=1): extraction of the chromosomal
    subsequence between the start and end coordinates.

    For free viral sequences (is_provirus=0): copy of the full contig.

    The produced files are directly usable by ABRicate:
      abricate --db vfdb --minid 80 --mincov 80 GENOME__phage_NNNN.fna
      abricate --db card --minid 80 --mincov 80 GENOME__phage_NNNN.fna

    The join with virsorter2_prophage_detail.tsv is done via the
    region_id column that matches exactly the FASTA ID of the extracted file.

    Returns the number of sequences successfully extracted.
    """

    if not extraction_requests:
        return 0

    try:
        genome_seqs: Dict[str, SeqRecord] = SeqIO.to_dict(
            SeqIO.parse(str(input_fna), "fasta")
        )
    except Exception as exc:
        raise RuntimeError(f"Unable to read {input_fna} : {exc}")

    n_extracted = 0

    for req in extraction_requests:
        contig_id      = req["contig_id"]
        start          = req["start"]
        end            = req["end"]
        is_provirus    = req["is_provirus"]
        region_id      = req["region_id"]
        fasta_out_path = Path(req["fasta_out_path"])

        # Search the contig (exact then partial match)
        seq_record = genome_seqs.get(contig_id)

        if seq_record is None:
            for key in genome_seqs:
                if key.startswith(contig_id) or contig_id.startswith(key):
                    seq_record = genome_seqs[key]
                    break

        if seq_record is None:
            print(
                f"[WARN] Contig '{contig_id}' not found in {input_fna.name} "
                f"for region {region_id}. Extraction skipped.",
                flush=True,
            )
            continue

        full_len = len(seq_record.seq)

        if is_provirus and (start > 0 or end < full_len):
            # Extract the prophage subsequence
            # geNomad gives 1-based coordinates, convert to 0-based
            start_0 = max(0, start - 1)
            end_0   = min(full_len, end)

            if start_0 >= end_0:
                print(
                    f"[WARN] Invalid coordinates ({start}-{end}) "
                    f"for {region_id}. Skipped.",
                    flush=True,
                )
                continue

            subseq = seq_record.seq[start_0:end_0]
            description_extra = (
                f"provirus contig={contig_id} start={start} end={end} "
                f"length={end_0 - start_0}"
            )
        else:
            # Virus libre : contig complet
            subseq = seq_record.seq
            description_extra = f"virus contig={contig_id} length={full_len}"

        extracted_record = SeqRecord(
            seq=Seq(str(subseq)),
            id=region_id,
            name=region_id,
            description=(
                f"genomad_prophage genome={genome_id} {description_extra}"
            ),
        )

        try:
            SeqIO.write(extracted_record, str(fasta_out_path), "fasta")
            n_extracted += 1
        except Exception as exc:
            print(f"[WARN] Impossible d'Acrire {fasta_out_path} : {exc}", flush=True)

    return n_extracted


# ---------------------------------------------------------------------------
# Build the BINARY MATRIX
# ---------------------------------------------------------------------------

def write_tsv(path: Path, columns: List[str], records: List[Dict]) -> None:
    """Write a list of dict records to a TSV with a fixed column order."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({col: record.get(col, "") for col in columns})


def write_genomad_binary_matrix(
    path: Path,
    genome_order: List[str],
    genome_prophage: Dict[str, bool],
    genome_provirus: Dict[str, bool],
    genome_taxonomies: Dict[str, set],
) -> None:
    """Write the genome x feature binary matrix from small in-memory aggregates.

    Columns: genome_id, prophage_present, provirus_present, then one
    genomad_<taxon> column per taxonomic group observed (unioned with the known
    geNomad groups), sorted. Values are strict 0/1. This reproduces the previous
    pandas pivot output without ever holding the full detail table in memory.
    """
    seen_tax = {t for taxset in genome_taxonomies.values() for t in taxset if t}
    all_tax = sorted(seen_tax.union(GENOMAD_TAXONOMY_GROUPS))
    columns = ["genome_id", "prophage_present", "provirus_present"] + [f"genomad_{t}" for t in all_tax]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(columns)
        for genome_id in genome_order:
            taxset = genome_taxonomies.get(genome_id, set())
            row = [
                genome_id,
                1 if genome_prophage.get(genome_id) else 0,
                1 if genome_provirus.get(genome_id) else 0,
            ]
            row.extend(1 if t in taxset else 0 for t in all_tax)
            writer.writerow(row)


def _stream_tsv_into_sheet(ws, tsv_path: Path, max_rows: int = EXCEL_MAX_ROWS) -> bool:
    truncated = False
    with tsv_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for i, record in enumerate(reader, start=1):
            if i > max_rows:
                truncated = True
                break
            ws.append(record)
    return truncated


def write_workbook_lowmem(xlsx_path: Path, sheet_specs: List[Tuple[str, Path]]) -> None:
    """Write the workbook in constant memory (openpyxl write_only), streaming each TSV."""
    try:
        from openpyxl import Workbook
    except Exception as exc:  # pragma: no cover - environment guard
        note = xlsx_path.with_suffix(xlsx_path.suffix + ".NOT_CREATED.txt")
        note.write_text(
            f"XLSX workbook was not created because openpyxl could not be imported: {exc}\n"
            f"All TSV outputs remain valid and complete.\n",
            encoding="utf-8",
        )
        print(f"[WARN] XLSX not created. See: {note}", flush=True)
        return

    workbook = Workbook(write_only=True)
    truncated_sheets: List[str] = []
    for title, tsv_path in sheet_specs:
        ws = workbook.create_sheet(title=title[:31])
        if tsv_path.is_file():
            if _stream_tsv_into_sheet(ws, tsv_path):
                truncated_sheets.append(title)
        else:
            ws.append(["(missing TSV)", str(tsv_path)])

    if truncated_sheets:
        ws = workbook.create_sheet(title="xlsx_notes")
        ws.append(["sheet", "message"])
        for sheet in truncated_sheets:
            ws.append([sheet, "Truncated at the Excel row limit; the complete data are in the corresponding TSV."])

    workbook.save(str(xlsx_path))


# ---------------------------------------------------------------------------
# Write empty outputs
# ---------------------------------------------------------------------------

def write_empty_outputs(output_tsv_dir: Path, output_xlsx_dir: Path) -> None:
    """Write correctly structured empty output files (memory-safe)."""

    detail_out  = output_tsv_dir / "genomad_prophage_detail.tsv"
    summary_out = output_tsv_dir / "genomad_summary_by_genome.tsv"
    fail_out    = output_tsv_dir / "genomad_failures.tsv"
    binary_out  = output_tsv_dir / "genomad_prophage_binary.tsv"
    xlsx_out    = output_xlsx_dir / "genomad_results.xlsx"

    write_tsv(detail_out,  DETAIL_COLUMNS,  [])
    write_tsv(summary_out, SUMMARY_COLUMNS, [])
    write_tsv(fail_out,    FAIL_COLUMNS,    [])
    write_tsv(binary_out,  ["genome_id", "prophage_present", "provirus_present"], [])

    write_workbook_lowmem(
        xlsx_out,
        [
            ("prophage_detail",   detail_out),
            ("prophage_binary",   binary_out),
            ("summary_by_genome", summary_out),
            ("failures",          fail_out),
        ],
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> int:
    # 1. Declare global variables at the top
    global GENOMAD_MIN_SCORE, GENOMAD_MIN_LENGTH

    parser = argparse.ArgumentParser(
        description=(
            "geNomad module: detection of prophage regions, "
            "sequence extraction and construction of binary matrices."
        )
    )
    parser.add_argument("--manifest",        required=True,
                        help="Path to input_manifest.tsv")
    parser.add_argument("--raw-root",        required=True,
                        help="Root directory for raw geNomad outputs")
    parser.add_argument("--fasta-out-root",  required=True,
                        help="Root directory for extracted prophage sequences")
    parser.add_argument("--output-tsv-dir",  required=True,
                        help="Directory for TSV outputs")
    parser.add_argument("--output-xlsx-dir", required=True,
                        help="Directory for XLSX outputs")
    parser.add_argument("--genomad-env",     required=True,
                        help="Path to the geNomad conda environment")
    parser.add_argument("--genomad-db",      required=True,
                        help="Path to the geNomad database")
    parser.add_argument("--threads",         type=int, default=2)
    parser.add_argument("--min-score",       type=float, default=GENOMAD_MIN_SCORE,
                        help=f"Minimum geNomad score (default: {GENOMAD_MIN_SCORE})")
    parser.add_argument("--min-length",      type=int, default=GENOMAD_MIN_LENGTH,
                        help=f"Minimum length in bp (default: {GENOMAD_MIN_LENGTH})")
    parser.add_argument("--splits",          type=int, default=8,
                        help="MMseqs2 search splits to limit RAM usage "
                             "(default: 8, required for 8 GB RAM)")
    parser.add_argument("--no-cleanup",      action="store_true",
                        help="Do not delete intermediate geNomad files "
                             "(by default, --cleanup is enabled to save disk space)")
    args = parser.parse_args()

    # 2. Update thresholds (the global declaration is no longer here)
    GENOMAD_MIN_SCORE  = args.min_score
    GENOMAD_MIN_LENGTH = args.min_length

    manifest_path   = Path(args.manifest).resolve()
    raw_root        = Path(args.raw_root).resolve()
    fasta_out_root  = Path(args.fasta_out_root).resolve()
    output_tsv_dir  = Path(args.output_tsv_dir).resolve()
    output_xlsx_dir = Path(args.output_xlsx_dir).resolve()
    genomad_env     = Path(args.genomad_env).resolve()
    genomad_db      = Path(args.genomad_db).resolve()
    threads         = max(1, min(args.threads, 2))   # contrainte machine : 2 threads max
    splits          = max(1, args.splits)
    cleanup_enabled = not args.no_cleanup

    safe_mkdir(raw_root)
    safe_mkdir(fasta_out_root)
    safe_mkdir(output_tsv_dir)
    safe_mkdir(output_xlsx_dir)

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    if not genomad_env.is_dir():
        raise FileNotFoundError(f"geNomad environment not found: {genomad_env}")
    if not genomad_db.is_dir():
        raise FileNotFoundError(f"geNomad database not found: {genomad_db}")

    manifest_df = load_manifest(manifest_path)

    if manifest_df.empty:
        print("[WARN] No valid genome in the manifest. Writing empty outputs.",
              flush=True)
        write_empty_outputs(output_tsv_dir, output_xlsx_dir)
        return 0

    print(f"[INFO] Genomes to analyze: {len(manifest_df)}", flush=True)
    print(f"[INFO] Score minimum       : {GENOMAD_MIN_SCORE}", flush=True)
    print(f"[INFO] Minimum length     : {GENOMAD_MIN_LENGTH} bp", flush=True)
    print(f"[INFO] Threads             : {threads}", flush=True)
    print(f"[INFO] Splits MMseqs2      : {splits} (RAM-safe)", flush=True)
    print(f"[INFO] Cleanup auto        : {cleanup_enabled}", flush=True)
    
    detail_out  = output_tsv_dir  / "genomad_prophage_detail.tsv"
    binary_out  = output_tsv_dir  / "genomad_prophage_binary.tsv"
    summary_out = output_tsv_dir  / "genomad_summary_by_genome.tsv"
    fail_out    = output_tsv_dir  / "genomad_failures.tsv"
    xlsx_out    = output_xlsx_dir / "genomad_results.xlsx"

    # Consolidated outputs are written to temp files and published atomically
    # (os.replace) only after the full pass, so an interruption never leaves a
    # half-written TSV for the downstream modules (09 co-occurrence, 17 final).
    detail_tmp  = detail_out.with_name(detail_out.name + ".tmp")
    binary_tmp  = binary_out.with_name(binary_out.name + ".tmp")
    summary_tmp = summary_out.with_name(summary_out.name + ".tmp")
    fail_tmp    = fail_out.with_name(fail_out.name + ".tmp")
    xlsx_tmp    = xlsx_out.with_name(xlsx_out.name + ".tmp")

    summary_records   : List[Dict]      = []
    failure_records   : List[Dict]      = []
    genome_order      : List[str]       = []
    genome_prophage   : Dict[str, bool] = {}
    genome_provirus   : Dict[str, bool] = {}
    genome_taxonomies : Dict[str, set]  = {}

    detail_handle = detail_tmp.open("w", encoding="utf-8", newline="")
    detail_writer = csv.DictWriter(detail_handle, fieldnames=DETAIL_COLUMNS, delimiter="\t", extrasaction="ignore")
    detail_writer.writeheader()

    for _, row in manifest_df.iterrows():

        genome_id = row["genome_id"]
        input_fna = Path(row["normalized_fna"]).resolve()
        run_dir   = raw_root / sanitize_name(genome_id)
        fasta_dir = fasta_out_root / sanitize_name(genome_id)

        print(f"\n=== Processing genome: {genome_id} ===", flush=True)
        print(f"FNA : {input_fna}", flush=True)
        print(f"OUT : {run_dir}", flush=True)

        genome_order.append(genome_id)
        genome_prophage.setdefault(genome_id, False)
        genome_provirus.setdefault(genome_id, False)
        genome_taxonomies.setdefault(genome_id, set())

        try:
            # -----------------------------------------------------------
            # Step 1: run geNomad (with checkpointed resume)
            # -----------------------------------------------------------
            summary_tsv_path = None
            try:
                summary_tsv_path = find_genomad_summary(run_dir, genome_id)
                print(
                    f"[INFO] geNomad results already present for {genome_id}. "
                    "Direct parsing without re-execution.",
                    flush=True,
                )
            except FileNotFoundError:
                pass

            if summary_tsv_path is None:
                # Preventive cleanup
                if run_dir.exists():
                    shutil.rmtree(run_dir)
                safe_mkdir(run_dir)

                # Build the geNomad command
                # Official reference: https://portal.nersc.gov/genomad/quickstart.html
                #
                # Critical parameters for this context (8 GB RAM, 1103 genomes):
                #   --splits 8     : splits the MMseqs2 search into blocks (RAM-safe)
                #   --cleanup      : removes intermediate files after each genome
                #   --min-score    : post-classification score threshold
                #
                # NB : on n'utilise volontairement PAS --conservative ni --relaxed.
                # The default filtering (post_classification_filtering) is already
                # suited for bacterial isolates. --conservative is too aggressive
                # for a probiotic safety screening (risk of missing
                # vrais prophages).
                cmd_genomad = [
                    "conda", "run", "-p", str(genomad_env),
                    "genomad", "end-to-end",
                    "--min-score",  str(GENOMAD_MIN_SCORE),
                    "--threads",    str(threads),
                    "--splits",     str(splits),
                ]
                if cleanup_enabled:
                    cmd_genomad.append("--cleanup")

                cmd_genomad.extend([
                    str(input_fna),
                    str(run_dir),
                    str(genomad_db),
                ])

                rc, stdout, stderr = run_command(
                    cmd_genomad, log_prefix=f"[{genome_id}] "
                )

                if rc != 0:
                    msg_parts = []
                    if stdout.strip():
                        msg_parts.append(f"STDOUT:\n{stdout.strip()}")
                    if stderr.strip():
                        msg_parts.append(f"STDERR:\n{stderr.strip()}")
                    raise RuntimeError(
                        "\n\n".join(msg_parts)
                        if msg_parts
                        else "geNomad failed without an error message."
                    )

                summary_tsv_path = find_genomad_summary(run_dir, genome_id)

            # -----------------------------------------------------------
            # Step 2: parse the results file
            # -----------------------------------------------------------
            safe_mkdir(fasta_dir)

            detail_rows, extraction_requests = parse_genomad_summary(
                summary_tsv  = summary_tsv_path,
                genome_id    = genome_id,
                input_fna    = input_fna,
                run_dir      = run_dir,
                fasta_out_dir= fasta_dir,
                min_score    = GENOMAD_MIN_SCORE,
                min_length   = GENOMAD_MIN_LENGTH,
            )

            # -----------------------------------------------------------
            # Step 3: extract prophage sequences
            # -----------------------------------------------------------
            n_extracted = 0
            if extraction_requests:
                n_extracted = extract_prophage_sequences(
                    input_fna           = input_fna,
                    extraction_requests = extraction_requests,
                    fasta_out_dir       = fasta_dir,
                    genome_id           = genome_id,
                )
                print(
                    f"[INFO] {n_extracted}/{len(extraction_requests)} sequences "
                    f"extracted into {fasta_dir}",
                    flush=True,
                )
            else:
                print(
                    f"[INFO] No prophage region retained for {genome_id} "
                    f"(score >= {GENOMAD_MIN_SCORE}, length >= {GENOMAD_MIN_LENGTH} bp).",
                    flush=True,
                )

            # -----------------------------------------------------------
            # Step 4: stream detail rows to the temp TSV and accumulate only
            #         small per-genome aggregates (memory-safe).
            # -----------------------------------------------------------
            n_provirus_regions = 0
            n_linear_regions   = 0
            taxonomies: set    = set()
            total_bp           = 0
            for drow in detail_rows:
                detail_writer.writerow({col: drow.get(col, "") for col in DETAIL_COLUMNS})
                if int(drow.get("is_provirus", 0) or 0) == 1:
                    n_provirus_regions += 1
                if str(drow.get("topology", "")).lower() == "linear":
                    n_linear_regions += 1
                tax = str(drow.get("taxonomy", "")).strip()
                if tax:
                    taxonomies.add(tax)
                try:
                    total_bp += int(drow.get("length_bp", 0) or 0)
                except (ValueError, TypeError):
                    pass

            if detail_rows:
                genome_prophage[genome_id] = True
            if n_provirus_regions > 0:
                genome_provirus[genome_id] = True
            genome_taxonomies[genome_id] = taxonomies

            summary_records.append({
                "genome_id":            genome_id,
                "input_fna":            str(input_fna),
                "n_prophage_regions":   len(detail_rows),
                "n_provirus_regions":   n_provirus_regions,
                "n_linear_regions":     n_linear_regions,
                "n_unique_taxonomies":  len(taxonomies),
                "total_prophage_bp":    total_bp,
                "extracted_fasta_dir":  str(fasta_dir) if fasta_dir.is_dir() else "",
            })

        except Exception as exc:
            failure_records.append({
                "genome_id": genome_id,
                "input_fna": str(input_fna),
                "status":    "FAILED",
                "message":   str(exc),
            })
            summary_records.append({
                "genome_id":           genome_id,
                "input_fna":           str(input_fna),
                "n_prophage_regions":  0,
                "n_provirus_regions":  0,
                "n_linear_regions":    0,
                "n_unique_taxonomies": 0,
                "total_prophage_bp":   0,
                "extracted_fasta_dir": "",
            })
            print(f"[ERROR] Failed genome: {genome_id}", flush=True)
            print(str(exc), flush=True)

    # -----------------------------------------------------------------------
    # Consolidate outputs (detail already streamed to the temp TSV). Everything
    # is written to temp files and published atomically with os.replace.
    # -----------------------------------------------------------------------
    detail_handle.close()

    write_tsv(summary_tmp, SUMMARY_COLUMNS, sorted(summary_records, key=lambda r: str(r.get("genome_id", ""))))
    write_tsv(fail_tmp,    FAIL_COLUMNS,    sorted(failure_records, key=lambda r: str(r.get("genome_id", ""))))
    write_genomad_binary_matrix(
        binary_tmp, sorted(genome_order), genome_prophage, genome_provirus, genome_taxonomies
    )

    os.replace(detail_tmp,  detail_out)
    os.replace(binary_tmp,  binary_out)
    os.replace(summary_tmp, summary_out)
    os.replace(fail_tmp,    fail_out)

    try:
        write_workbook_lowmem(
            xlsx_tmp,
            [
                ("prophage_detail",   detail_out),
                ("prophage_binary",   binary_out),
                ("summary_by_genome", summary_out),
                ("failures",          fail_out),
            ],
        )
        os.replace(xlsx_tmp, xlsx_out)
    except Exception as exc:
        print(f"[WARN] XLSX generation failed (non-fatal): {exc}", flush=True)

    # -----------------------------------------------------------------------
    # Rapport final
    # -----------------------------------------------------------------------

    n_with_phage   = sum(1 for r in summary_records if int(r.get("n_prophage_regions", 0) or 0) > 0)
    n_total_phages = sum(int(r.get("n_prophage_regions", 0) or 0) for r in summary_records)
    n_proviruses   = sum(int(r.get("n_provirus_regions", 0) or 0) for r in summary_records)
    n_failed       = len(failure_records)

    print("\n" + "=" * 60, flush=True)
    print("Module geNomad terminA.", flush=True)
    print(f"Genomes processed          : {len(manifest_df)}", flush=True)
    print(f"Genomes with prophage   : {n_with_phage}", flush=True)
    print(f"Regions detected        : {n_total_phages}", flush=True)
    print(f"  dont proviruses        : {n_proviruses}", flush=True)
    print(f"Failed genomes          : {n_failed}", flush=True)
    print(f"Detail TSV               : {detail_out}", flush=True)
    print(f"Binary TSV               : {binary_out}", flush=True)
    print(f"Summary TSV              : {summary_out}", flush=True)
    print(f"Failures TSV             : {fail_out}", flush=True)
    print(f"Workbook XLSX            : {xlsx_out}", flush=True)
    print(
        f"Prophage sequences      : {fasta_out_root}\n"
        "  usable with ABRicate (--db vfdb / --db card)",
        flush=True,
    )
    print("=" * 60, flush=True)

    if n_failed > 0:
        print(
            "\n[WARN] Some genomes failed (see genomad_failures.tsv). They appear as "
            "zero in the matrix. The full pass completed; re-run module 08 to retry them.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        sys.exit(1)

