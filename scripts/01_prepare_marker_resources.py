#!/usr/bin/env python3

import os
import shutil
import subprocess
from pathlib import Path
import pandas as pd

PIPE_ROOT = Path(os.environ.get("PIPE_ROOT", Path(__file__).resolve().parent.parent))

DB_ROOT = PIPE_ROOT / "db"
HMM_DIR = DB_ROOT / "hmm_profiles"
FASTA_DIR = DB_ROOT / "marker_fastas"
ABSENT_FASTA_DIR = FASTA_DIR / "absents de genomes probio_ichnos recuperes depuis projet Anoxybio"
MARKERS_XLSX = DB_ROOT / "markers_DB.xlsx"

COMPILED_DIR = DB_ROOT / "compiled"
DIAMOND_DIR = COMPILED_DIR / "diamond"
HMM_COMPILED_DIR = COMPILED_DIR / "hmm"
META_DIR = COMPILED_DIR / "metadata"

OUT_METADATA_TSV = META_DIR / "marker_metadata.tsv"
OUT_MARKERS_WITH_HMM = META_DIR / "markers_with_hmm.txt"
OUT_MARKERS_DIAMOND_ONLY = META_DIR / "markers_diamond_only.txt"
OUT_MARKERS_MISSING_BOTH = META_DIR / "markers_missing_both.txt"
OUT_ALL_FASTA = DIAMOND_DIR / "all_markers_for_diamond.faa"
OUT_DIAMOND_DB = DIAMOND_DIR / "all_markers_for_diamond.dmnd"
OUT_ALL_HMM = HMM_COMPILED_DIR / "all_markers.hmm"
OUT_MARKERS_XLSX = COMPILED_DIR / "markers_DB.xlsx"


def norm_key(marker_name: str) -> str:
    return str(marker_name).strip().lower()


def load_marker_table(xlsx_path: Path) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path)
    required = ["marker", "function", "category", "sources"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in markers_DB.xlsx: {missing}")

    df = df[required].copy()
    df["marker"] = df["marker"].astype(str).str.strip()
    df["function"] = df["function"].astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip()
    df["sources"] = df["sources"].astype(str).str.strip()
    df["marker_key"] = df["marker"].map(norm_key)
    return df


def collect_fasta_files() -> dict:
    fasta_map = {}

    for faa in sorted(FASTA_DIR.glob("*.faa")):
        marker_key = norm_key(faa.stem)
        fasta_map[marker_key] = faa

    if ABSENT_FASTA_DIR.exists():
        for faa in sorted(ABSENT_FASTA_DIR.glob("*.faa")):
            marker_key = norm_key(faa.stem)
            fasta_map[marker_key] = faa

    return fasta_map


def collect_hmm_files() -> dict:
    hmm_map = {}
    for hmm in sorted(HMM_DIR.glob("*.hmm")):
        marker_key = norm_key(hmm.stem)
        hmm_map[marker_key] = hmm
    return hmm_map


def build_metadata(df: pd.DataFrame, fasta_map: dict, hmm_map: dict) -> pd.DataFrame:
    rows = []

    for _, row in df.iterrows():
        marker = row["marker"]
        marker_key = row["marker_key"]

        fasta_path = fasta_map.get(marker_key)
        hmm_path = hmm_map.get(marker_key)

        rows.append({
            "marker": marker,
            "marker_key": marker_key,
            "function": row["function"],
            "category": row["category"],
            "sources": row["sources"],
            "has_fasta": 1 if fasta_path else 0,
            "has_hmm": 1 if hmm_path else 0,
            "fasta_path": str(fasta_path) if fasta_path else "",
            "hmm_path": str(hmm_path) if hmm_path else "",
        })

    meta = pd.DataFrame(rows)
    meta = meta.sort_values(["category", "marker"], kind="stable").reset_index(drop=True)
    return meta


def write_marker_lists(meta: pd.DataFrame) -> None:
    with open(OUT_MARKERS_WITH_HMM, "w", encoding="utf-8") as fh:
        for marker in meta.loc[meta["has_hmm"] == 1, "marker"]:
            fh.write(f"{marker}\n")

    with open(OUT_MARKERS_DIAMOND_ONLY, "w", encoding="utf-8") as fh:
        for marker in meta.loc[(meta["has_fasta"] == 1) & (meta["has_hmm"] == 0), "marker"]:
            fh.write(f"{marker}\n")

    with open(OUT_MARKERS_MISSING_BOTH, "w", encoding="utf-8") as fh:
        for marker in meta.loc[(meta["has_fasta"] == 0) & (meta["has_hmm"] == 0), "marker"]:
            fh.write(f"{marker}\n")


def build_concat_fasta(meta: pd.DataFrame) -> None:
    with open(OUT_ALL_FASTA, "w", encoding="utf-8") as out_fh:
        for _, row in meta.iterrows():
            marker = row["marker"]
            fasta_path = row["fasta_path"]

            if not fasta_path:
                continue

            fasta_path = Path(fasta_path)
            seq_idx = 0

            with open(fasta_path, "r", encoding="utf-8") as in_fh:
                for line in in_fh:
                    if line.startswith(">"):
                        seq_idx += 1
                        out_fh.write(f">{marker}__REF_{seq_idx:06d}\n")
                    else:
                        out_fh.write(line.strip() + "\n")


def build_concat_hmm(meta: pd.DataFrame) -> None:
    with open(OUT_ALL_HMM, "w", encoding="utf-8") as out_fh:
        for _, row in meta.iterrows():
            marker = row["marker"]
            hmm_path = row["hmm_path"]

            if not hmm_path:
                continue

            hmm_path = Path(hmm_path)

            last_line = ""
            with open(hmm_path, "r", encoding="utf-8") as in_fh:
                for line in in_fh:
                    last_line = line
                    if line.startswith("NAME  "):
                        out_fh.write(f"NAME  {marker}\n")
                    else:
                        out_fh.write(line)

            if last_line and not last_line.rstrip().endswith("//"):
                out_fh.write("\n")


def run_checked(cmd: list[str]) -> None:
    print(f"[INFO] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def require_tool(tool_name: str) -> str:
    resolved = shutil.which(tool_name)
    if not resolved:
        raise FileNotFoundError(
            f"{tool_name} not found on PATH. Run this setup in the probio_core "
            "environment or set PATH before preparing marker resources."
        )
    return resolved


def build_diamond_database() -> None:
    if not OUT_ALL_FASTA.exists() or OUT_ALL_FASTA.stat().st_size == 0:
        raise RuntimeError(f"Cannot build DIAMOND database from empty FASTA: {OUT_ALL_FASTA}")

    diamond = require_tool("diamond")
    run_checked([
        diamond,
        "makedb",
        "--in", str(OUT_ALL_FASTA),
        "-d", str(OUT_DIAMOND_DB.with_suffix("")),
    ])

    if not OUT_DIAMOND_DB.exists():
        raise FileNotFoundError(f"DIAMOND makedb did not create expected file: {OUT_DIAMOND_DB}")


def press_hmm_database() -> None:
    if not OUT_ALL_HMM.exists() or OUT_ALL_HMM.stat().st_size == 0:
        raise RuntimeError(f"Cannot run hmmpress on empty HMM file: {OUT_ALL_HMM}")

    hmmpress = require_tool("hmmpress")
    run_checked([hmmpress, "-f", str(OUT_ALL_HMM)])

    missing = [
        suffix
        for suffix in [".h3f", ".h3i", ".h3m", ".h3p"]
        if not OUT_ALL_HMM.with_suffix(OUT_ALL_HMM.suffix + suffix).exists()
    ]
    if missing:
        raise FileNotFoundError(
            f"hmmpress did not create all expected HMMER index files for {OUT_ALL_HMM}: {missing}"
        )


def main() -> None:
    for d in [DIAMOND_DIR, HMM_COMPILED_DIR, META_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    if not MARKERS_XLSX.exists():
        raise FileNotFoundError(f"markers_DB.xlsx not found: {MARKERS_XLSX}")

    if not FASTA_DIR.exists():
        raise FileNotFoundError(f"marker_fastas directory not found: {FASTA_DIR}")

    if not HMM_DIR.exists():
        raise FileNotFoundError(f"hmm_profiles directory not found: {HMM_DIR}")

    df = load_marker_table(MARKERS_XLSX)
    fasta_map = collect_fasta_files()
    hmm_map = collect_hmm_files()

    meta = build_metadata(df, fasta_map, hmm_map)
    meta.to_csv(OUT_METADATA_TSV, sep="\t", index=False)

    write_marker_lists(meta)
    build_concat_fasta(meta)
    build_concat_hmm(meta)
    shutil.copy2(MARKERS_XLSX, OUT_MARKERS_XLSX)
    build_diamond_database()
    press_hmm_database()

    n_total = len(meta)
    n_fasta = int((meta["has_fasta"] == 1).sum())
    n_hmm = int((meta["has_hmm"] == 1).sum())
    n_diamond_only = int(((meta["has_fasta"] == 1) & (meta["has_hmm"] == 0)).sum())
    n_missing_both = int(((meta["has_fasta"] == 0) & (meta["has_hmm"] == 0)).sum())

    print(f"[INFO] Metadata table written to: {OUT_METADATA_TSV}")
    print(f"[INFO] Marker list with HMM written to: {OUT_MARKERS_WITH_HMM}")
    print(f"[INFO] Marker list for DIAMOND-only written to: {OUT_MARKERS_DIAMOND_ONLY}")
    print(f"[INFO] Marker list missing both FASTA and HMM written to: {OUT_MARKERS_MISSING_BOTH}")
    print(f"[INFO] Concatenated FASTA written to: {OUT_ALL_FASTA}")
    print(f"[INFO] DIAMOND database written to: {OUT_DIAMOND_DB}")
    print(f"[INFO] Concatenated HMM written to: {OUT_ALL_HMM}")
    print(f"[INFO] Compiled marker workbook copied to: {OUT_MARKERS_XLSX}")
    print(f"[INFO] Total markers in metadata: {n_total}")
    print(f"[INFO] Markers with FASTA: {n_fasta}")
    print(f"[INFO] Markers with HMM: {n_hmm}")
    print(f"[INFO] Markers DIAMOND-only: {n_diamond_only}")
    print(f"[INFO] Markers missing both FASTA and HMM: {n_missing_both}")


if __name__ == "__main__":
    main()

