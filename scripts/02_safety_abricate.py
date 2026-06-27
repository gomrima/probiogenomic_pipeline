#!/usr/bin/env python3

import os
from pathlib import Path
import subprocess
import pandas as pd

PIPE_ROOT = Path(os.environ.get("PIPE_ROOT", Path(__file__).resolve().parent.parent))

MANIFEST_TSV = PIPE_ROOT / "work" / "manifest" / "input_manifest.tsv"
TMP_DIR = PIPE_ROOT / "work" / "tmp"

ABRICATE_RAW_DIR = PIPE_ROOT / "work" / "intermediate" / "safety" / "abricate_raw"
RESULTS_TSV_DIR = PIPE_ROOT / "results" / "tsv" / "safety"
RESULTS_XLSX_DIR = PIPE_ROOT / "results" / "xlsx" / "safety"

VFDB_DETAIL_TSV = RESULTS_TSV_DIR / "virulence_detail.tsv"
CARD_DETAIL_TSV = RESULTS_TSV_DIR / "amr_detail.tsv"

VFDB_BINARY_TSV = RESULTS_TSV_DIR / "virulence_binary.tsv"
CARD_BINARY_TSV = RESULTS_TSV_DIR / "amr_binary.tsv"
SAFETY_COMBINED_TSV = RESULTS_TSV_DIR / "safety_combined_binary.tsv"

SAFETY_XLSX = RESULTS_XLSX_DIR / "safety_abricate_results.xlsx"

# ABRicate honors the pipeline-wide THREADS value (exported by the launcher),
# defaulting to 2 when it is not set. This keeps the global --threads meaningful
# for this module instead of pinning it to a constant.
def _env_threads(default: int = 2) -> int:
    try:
        return max(1, int(os.environ.get("THREADS", str(default)) or default))
    except (TypeError, ValueError):
        return default


ABRICATE_THREADS = _env_threads(2)
ABRICATE_MINID = 80
ABRICATE_MINCOV = 80

DETAIL_COLUMNS = [
    "genome_id",
    "db",
    "gene",
    "sequence",
    "start",
    "end",
    "coverage",
    "identity",
    "accession",
    "product",
    "resistance",
]


def run_command(cmd, stdout_path=None):
    if stdout_path is None:
        subprocess.run(cmd, check=True)
    else:
        with open(stdout_path, "w", encoding="utf-8") as out_fh:
            subprocess.run(cmd, check=True, stdout=out_fh)


def load_manifest() -> pd.DataFrame:
    if not MANIFEST_TSV.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_TSV}")

    df = pd.read_csv(MANIFEST_TSV, sep="\t")
    required = ["genome_id", "normalized_fna"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in manifest: {missing}")

    df["normalized_fna"] = df["normalized_fna"].fillna("").astype(str)
    df = df[df["normalized_fna"] != ""].copy()
    df["fna_exists"] = df["normalized_fna"].apply(lambda x: Path(x).exists())
    df = df[df["fna_exists"]].copy()

    if df.empty:
        raise ValueError("No valid genomes with normalized_fna were found in the manifest.")

    return df


def run_abricate(genome_id: str, fna_path: Path, db_name: str) -> Path:
    out_path = ABRICATE_RAW_DIR / f"{genome_id}.{db_name}.tsv"

    cmd = [
        "abricate",
        "--db", db_name,
        "--threads", str(ABRICATE_THREADS),
        "--minid", str(ABRICATE_MINID),
        "--mincov", str(ABRICATE_MINCOV),
        str(fna_path),
    ]

    run_command(cmd, stdout_path=out_path)
    return out_path


def empty_detail_df() -> pd.DataFrame:
    return pd.DataFrame(columns=DETAIL_COLUMNS)


def sanitize_abricate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure ABRicate output has unique columns and map only one coverage field
    to the final 'coverage' column.
    """
    df = df.copy()

    # Remove exact duplicate column names if present
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()].copy()

    # Build final standardized columns safely
    standardized = pd.DataFrame(index=df.index)

    standardized["sequence"] = df["SEQUENCE"] if "SEQUENCE" in df.columns else ""
    standardized["start"] = df["START"] if "START" in df.columns else ""
    standardized["end"] = df["END"] if "END" in df.columns else ""
    standardized["gene"] = df["GENE"] if "GENE" in df.columns else ""

    if "%COVERAGE" in df.columns:
        standardized["coverage"] = df["%COVERAGE"]
    elif "COVERAGE" in df.columns:
        standardized["coverage"] = df["COVERAGE"]
    else:
        standardized["coverage"] = ""

    standardized["identity"] = df["%IDENTITY"] if "%IDENTITY" in df.columns else ""
    standardized["accession"] = df["ACCESSION"] if "ACCESSION" in df.columns else ""
    standardized["product"] = df["PRODUCT"] if "PRODUCT" in df.columns else ""
    standardized["resistance"] = df["RESISTANCE"] if "RESISTANCE" in df.columns else ""

    return standardized


def parse_abricate_hits(tsv_path: Path, genome_id: str, db_name: str) -> pd.DataFrame:
    if not tsv_path.exists() or tsv_path.stat().st_size == 0:
        return empty_detail_df()

    try:
        df = pd.read_csv(tsv_path, sep="\t", dtype=str)
    except pd.errors.EmptyDataError:
        return empty_detail_df()

    if df.empty:
        return empty_detail_df()

    df = sanitize_abricate_columns(df)

    df = df.fillna("")

    df["genome_id"] = genome_id
    df["db"] = db_name

    # Reorder exactly and guarantee unique columns
    df = df[DETAIL_COLUMNS].copy()

    if df.columns.duplicated().any():
        raise ValueError(
            f"Duplicate columns detected after parsing {tsv_path}: {list(df.columns[df.columns.duplicated()])}"
        )

    return df


def concat_detail_tables(df_list: list[pd.DataFrame]) -> pd.DataFrame:
    if not df_list:
        return empty_detail_df()

    cleaned = []
    for i, df in enumerate(df_list, start=1):
        if df is None:
            continue
        if df.columns.duplicated().any():
            raise ValueError(
                f"Duplicate columns detected in detail dataframe #{i}: "
                f"{list(df.columns[df.columns.duplicated()])}"
            )
        cleaned.append(df[DETAIL_COLUMNS].copy())

    if not cleaned:
        return empty_detail_df()

    return pd.concat(cleaned, ignore_index=True)


def build_binary_matrix(detail_df: pd.DataFrame, genome_ids: list[str]) -> pd.DataFrame:
    all_genomes_df = pd.DataFrame({"genome_id": genome_ids})

    if detail_df.empty:
        return all_genomes_df.copy()

    detected = detail_df.copy()
    detected["gene"] = detected["gene"].fillna("").astype(str).str.strip()
    detected = detected[detected["gene"] != ""].copy()

    if detected.empty:
        return all_genomes_df.copy()

    detected["present"] = 1

    binary_df = detected.pivot_table(
        index="genome_id",
        columns="gene",
        values="present",
        aggfunc="max",
        fill_value=0
    ).reset_index()

    binary_df = all_genomes_df.merge(binary_df, on="genome_id", how="left").fillna(0)

    for col in binary_df.columns:
        if col != "genome_id":
            binary_df[col] = binary_df[col].astype(int)

    return binary_df


def merge_binary_tables(vfdb_binary_df: pd.DataFrame, card_binary_df: pd.DataFrame) -> pd.DataFrame:
    combined_df = vfdb_binary_df.merge(
        card_binary_df,
        on="genome_id",
        how="outer",
        suffixes=("", "_amr")
    ).fillna(0)

    for col in combined_df.columns:
        if col != "genome_id":
            combined_df[col] = combined_df[col].astype(int)

    return combined_df


def write_xlsx_writeonly(xlsx_path: Path, sheets: "list[tuple[str, pd.DataFrame]]") -> None:
    """Write a multi-sheet workbook in constant memory (openpyxl write_only).

    `sheets` is a list of (sheet_name, DataFrame). Cell values and types match
    what DataFrame.to_excel(index=False) would write, but rows are streamed to
    disk row by row instead of being accumulated in an in-memory workbook (which
    is what made the openpyxl detail sheets a memory risk). The computed
    DataFrames and the TSV outputs are unchanged.
    """
    try:
        from openpyxl import Workbook
    except Exception as exc:  # pragma: no cover - environment guard
        note = xlsx_path.with_suffix(xlsx_path.suffix + ".NOT_CREATED.txt")
        note.write_text(
            f"XLSX workbook was not created because openpyxl could not be imported: {exc}\n"
            f"All TSV outputs remain valid and complete.\n",
            encoding="utf-8",
        )
        print(f"[WARN] XLSX not created. See: {note}")
        return

    def _cell(val):
        # Match to_excel: inf / NaN floats become blank cells.
        if isinstance(val, float) and (val != val or val == float("inf") or val == float("-inf")):
            return None
        return val

    wb = Workbook(write_only=True)
    for sheet_name, df in sheets:
        ws = wb.create_sheet(title=str(sheet_name)[:31])
        ws.append([str(c) for c in df.columns])
        for record in df.itertuples(index=False, name=None):
            ws.append([_cell(v) for v in record])
    wb.save(str(xlsx_path))


def main() -> None:
    for d in [TMP_DIR, ABRICATE_RAW_DIR, RESULTS_TSV_DIR, RESULTS_XLSX_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    manifest_df = load_manifest()
    genome_ids = manifest_df["genome_id"].tolist()

    print(f"[INFO] Genomes with available FNA: {len(manifest_df)}")

    vfdb_details = []
    card_details = []

    for _, row in manifest_df.iterrows():
        genome_id = row["genome_id"]
        fna_path = Path(row["normalized_fna"])

        print(f"[INFO] Running ABRicate VFDB for {genome_id}")
        vfdb_out = run_abricate(genome_id, fna_path, "vfdb")
        vfdb_df = parse_abricate_hits(vfdb_out, genome_id, "vfdb")
        vfdb_details.append(vfdb_df)

        print(f"[INFO] Running ABRicate CARD for {genome_id}")
        card_out = run_abricate(genome_id, fna_path, "card")
        card_df = parse_abricate_hits(card_out, genome_id, "card")
        card_details.append(card_df)

    vfdb_detail_df = concat_detail_tables(vfdb_details)
    card_detail_df = concat_detail_tables(card_details)

    vfdb_binary_df = build_binary_matrix(vfdb_detail_df, genome_ids)
    card_binary_df = build_binary_matrix(card_detail_df, genome_ids)

    combined_df = merge_binary_tables(vfdb_binary_df, card_binary_df)

    vfdb_detail_df.to_csv(VFDB_DETAIL_TSV, sep="\t", index=False)
    card_detail_df.to_csv(CARD_DETAIL_TSV, sep="\t", index=False)

    vfdb_binary_df.to_csv(VFDB_BINARY_TSV, sep="\t", index=False)
    card_binary_df.to_csv(CARD_BINARY_TSV, sep="\t", index=False)
    combined_df.to_csv(SAFETY_COMBINED_TSV, sep="\t", index=False)

    write_xlsx_writeonly(SAFETY_XLSX, [
        ("virulence_binary", vfdb_binary_df),
        ("amr_binary", card_binary_df),
        ("safety_combined", combined_df),
        ("virulence_detail", vfdb_detail_df),
        ("amr_detail", card_detail_df),
    ])

    print(f"[INFO] Virulence detail written to: {VFDB_DETAIL_TSV}")
    print(f"[INFO] AMR detail written to: {CARD_DETAIL_TSV}")
    print(f"[INFO] Virulence binary written to: {VFDB_BINARY_TSV}")
    print(f"[INFO] AMR binary written to: {CARD_BINARY_TSV}")
    print(f"[INFO] Safety combined binary written to: {SAFETY_COMBINED_TSV}")
    print(f"[INFO] Safety Excel workbook written to: {SAFETY_XLSX}")


if __name__ == "__main__":
    main()

