#!/usr/bin/env python3

import re
import subprocess
import os
from pathlib import Path

import pandas as pd

PIPE_ROOT = Path(os.environ.get("PIPE_ROOT", Path(__file__).resolve().parent.parent))

MANIFEST_TSV = PIPE_ROOT / "work" / "manifest" / "input_manifest.tsv"
MARKER_METADATA_TSV = PIPE_ROOT / "db" / "compiled" / "metadata" / "marker_metadata.tsv"
MARKERS_DB_XLSX = PIPE_ROOT / "db" / "compiled" / "markers_DB.xlsx"

DIAMOND_DB = PIPE_ROOT / "db" / "compiled" / "diamond" / "all_markers_for_diamond.dmnd"
HMM_DB = PIPE_ROOT / "db" / "compiled" / "hmm" / "all_markers.hmm"

TMP_DIR = PIPE_ROOT / "work" / "tmp"

DIAMOND_RAW_DIR = PIPE_ROOT / "work" / "intermediate" / "markers" / "diamond_raw"
HMMER_RAW_DIR = PIPE_ROOT / "work" / "intermediate" / "markers" / "hmmer_raw"
MERGED_DIR = PIPE_ROOT / "work" / "intermediate" / "markers" / "merged_tables"

RESULTS_TSV_DIR = PIPE_ROOT / "results" / "tsv" / "markers"
RESULTS_XLSX_DIR = PIPE_ROOT / "results" / "xlsx" / "markers"
CATEGORY_TSV_DIR = RESULTS_TSV_DIR / "by_category"

DETAIL_TSV = RESULTS_TSV_DIR / "marker_detection_detail.tsv"
BINARY_TSV = RESULTS_TSV_DIR / "marker_presence_absence_binary.tsv"
METADATA_USED_TSV = RESULTS_TSV_DIR / "marker_metadata_used.tsv"
CATEGORY_MAPPING_USED_TSV = RESULTS_TSV_DIR / "marker_category_mapping_used.tsv"
CATEGORY_SUMMARY_TSV = RESULTS_TSV_DIR / "marker_category_summary.tsv"
BINARY_XLSX = RESULTS_XLSX_DIR / "marker_presence_absence_binary.xlsx"

DIAMOND_THREADS = 2
HMMER_CPU = 2

DIAMOND_EVALUE = 1e-5
HMMER_EVALUE = 1e-10


CATEGORY_CANONICAL_MAP = {
    "eps production": "Exopolysaccharide production",
    "exopolysaccharide production": "Exopolysaccharide production",
}


def run_command(cmd, stdout_path=None):
    if stdout_path is None:
        subprocess.run(cmd, check=True)
    else:
        with open(stdout_path, "w", encoding="utf-8") as out_fh:
            subprocess.run(cmd, check=True, stdout=out_fh)


def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_category_name(category_name: str) -> str:
    text = safe_text(category_name)
    if not text:
        return ""
    key = re.sub(r"\s+", " ", text).strip().lower()
    return CATEGORY_CANONICAL_MAP.get(key, text)


def slugify(text: str) -> str:
    text = safe_text(text)
    text = text.replace("&", " and ")
    text = re.sub(r"[;/|]+", "_", text)
    text = re.sub(r"[^A-Za-z0-9._ -]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("._ ")
    return text or "unclassified"


def make_unique_sheet_name(base_name: str, used_names: set[str]) -> str:
    cleaned = re.sub(r"[\[\]\:\*\?\/\\]+", "_", base_name).strip()
    if not cleaned:
        cleaned = "sheet"
    candidate = cleaned[:31]
    counter = 2
    while candidate in used_names:
        suffix = f"_{counter}"
        allowed = 31 - len(suffix)
        candidate = cleaned[:allowed] + suffix
        counter += 1
    used_names.add(candidate)
    return candidate


def split_categories(category_value: str) -> list[str]:
    text = safe_text(category_value)
    if not text:
        return []
    parts = [p.strip() for p in text.split(";")]
    parts = [p for p in parts if p]

    seen = set()
    ordered = []
    for part in parts:
        normalized = normalize_category_name(part)
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def load_manifest() -> pd.DataFrame:
    if not MANIFEST_TSV.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_TSV}")

    df = pd.read_csv(MANIFEST_TSV, sep="\t")
    required = ["genome_id", "normalized_faa", "status"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in manifest: {missing}")

    df["normalized_faa"] = df["normalized_faa"].fillna("").astype(str)
    df["status"] = df["status"].fillna("").astype(str)

    df = df[df["normalized_faa"] != ""].copy()
    df["faa_exists"] = df["normalized_faa"].apply(lambda x: Path(x).exists())
    df = df[df["faa_exists"]].copy()
    return df


def load_marker_metadata_base() -> pd.DataFrame:
    if not MARKER_METADATA_TSV.exists():
        raise FileNotFoundError(f"Marker metadata not found: {MARKER_METADATA_TSV}")

    meta = pd.read_csv(MARKER_METADATA_TSV, sep="\t")
    required = ["marker", "function", "category", "sources", "has_fasta", "has_hmm"]
    missing = [c for c in required if c not in meta.columns]
    if missing:
        raise ValueError(f"Missing required columns in marker metadata: {missing}")

    meta["marker"] = meta["marker"].map(safe_text)
    if meta["marker"].duplicated().any():
        dupes = sorted(meta.loc[meta["marker"].duplicated(), "marker"].unique().tolist())
        raise ValueError(f"Duplicated markers in base metadata: {dupes}")

    return meta.copy()


def load_category_mapping_from_xlsx() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not MARKERS_DB_XLSX.exists():
        raise FileNotFoundError(f"Markers database workbook not found: {MARKERS_DB_XLSX}")

    raw = pd.read_excel(MARKERS_DB_XLSX)
    raw.columns = [safe_text(c).lower() for c in raw.columns]

    required = ["marker", "function", "category", "sources"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"Missing required columns in markers_DB.xlsx: {missing}")

    raw["marker"] = raw["marker"].map(safe_text)
    raw["function"] = raw["function"].map(safe_text)
    raw["category"] = raw["category"].map(safe_text)
    raw["sources"] = raw["sources"].map(safe_text)

    raw = raw[raw["marker"] != ""].copy()

    duplicated_markers = raw["marker"][raw["marker"].duplicated()].unique().tolist()
    if duplicated_markers:
        conflicting = []
        for marker in duplicated_markers:
            subset = raw[raw["marker"] == marker].copy()
            unique_rows = subset[["function", "category", "sources"]].drop_duplicates()
            if len(unique_rows) > 1:
                conflicting.append(marker)
        if conflicting:
            raise ValueError(f"Conflicting duplicated markers in markers_DB.xlsx: {sorted(conflicting)}")
        raw = raw.drop_duplicates(subset=["marker"], keep="first").copy()

    expanded_rows = []
    for _, row in raw.iterrows():
        marker = row["marker"]
        category_raw = row["category"]
        categories = split_categories(category_raw)
        if not categories:
            categories = ["Unclassified"]

        for category_name in categories:
            expanded_rows.append(
                {
                    "marker": marker,
                    "function": row["function"],
                    "category": category_name,
                    "category_raw": category_raw if category_raw else "Unclassified",
                    "sources": row["sources"],
                    "category_slug": slugify(category_name),
                }
            )

    expanded_df = pd.DataFrame(expanded_rows)
    if not expanded_df.empty:
        expanded_df = expanded_df.drop_duplicates(subset=["marker", "category"], keep="first").copy()
        expanded_df = expanded_df.sort_values(["category", "marker"], kind="stable").reset_index(drop=True)

    dedup_df = raw.rename(
        columns={
            "function": "function_from_xlsx",
            "category": "category_from_xlsx",
            "sources": "sources_from_xlsx",
        }
    )[["marker", "function_from_xlsx", "category_from_xlsx", "sources_from_xlsx"]].copy()

    return dedup_df, expanded_df


def build_authoritative_marker_metadata() -> tuple[pd.DataFrame, pd.DataFrame]:
    base_meta = load_marker_metadata_base()
    xlsx_dedup, xlsx_expanded = load_category_mapping_from_xlsx()

    merged = base_meta.merge(xlsx_dedup, on="marker", how="left", validate="one_to_one")

    missing_categories = merged.loc[merged["category_from_xlsx"].isna(), "marker"].tolist()
    if missing_categories:
        raise ValueError(
            "Markers present in marker_metadata.tsv but missing in markers_DB.xlsx: "
            + ", ".join(sorted(missing_categories))
        )

    merged["function"] = merged["function_from_xlsx"]
    merged["category"] = merged["category_from_xlsx"].map(normalize_category_name)
    merged["sources"] = merged["sources_from_xlsx"]

    merged = merged.drop(columns=["function_from_xlsx", "category_from_xlsx", "sources_from_xlsx"])
    merged = merged.sort_values(["category", "marker"], kind="stable").reset_index(drop=True)

    xlsx_marker_set = set(xlsx_dedup["marker"].tolist())
    base_marker_set = set(merged["marker"].tolist())
    extra_in_xlsx = sorted(xlsx_marker_set - base_marker_set)
    if extra_in_xlsx:
        print(
            "[WARN] Extra markers found in markers_DB.xlsx but absent from marker_metadata.tsv. "
            f"They were ignored: {', '.join(extra_in_xlsx)}"
        )

    xlsx_expanded = xlsx_expanded[xlsx_expanded["marker"].isin(base_marker_set)].copy()
    xlsx_expanded = xlsx_expanded.sort_values(["category", "marker"], kind="stable").reset_index(drop=True)

    return merged, xlsx_expanded


def run_diamond(genome_id: str, faa_path: Path) -> Path:
    out_path = DIAMOND_RAW_DIR / f"{genome_id}.diamond.tsv"

    cmd = [
        "diamond",
        "blastp",
        "--db", str(DIAMOND_DB),
        "--query", str(faa_path),
        "--out", str(out_path),
        "--outfmt", "6",
        "qseqid", "sseqid", "pident", "length", "qlen", "slen", "qcovhsp", "scovhsp", "evalue", "bitscore",
        "--evalue", str(DIAMOND_EVALUE),
        "--id", "30",
        "--query-cover", "50",
        "--subject-cover", "50",
        "--max-target-seqs", "1",
        "--threads", str(DIAMOND_THREADS),
        "--tmpdir", str(TMP_DIR),
    ]

    run_command(cmd)
    return out_path


def run_hmmscan(genome_id: str, faa_path: Path) -> Path:
    out_tbl = HMMER_RAW_DIR / f"{genome_id}.hmmscan.tblout"
    out_stdout = HMMER_RAW_DIR / f"{genome_id}.hmmscan.stdout.txt"

    cmd = [
        "hmmscan",
        "--cpu", str(HMMER_CPU),
        "--tblout", str(out_tbl),
        "--noali",
        str(HMM_DB),
        str(faa_path),
    ]

    run_command(cmd, stdout_path=out_stdout)
    return out_tbl


def parse_diamond_hits(diamond_tsv: Path) -> set:
    markers = set()

    if not diamond_tsv.exists() or diamond_tsv.stat().st_size == 0:
        return markers

    with open(diamond_tsv, "r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 10:
                continue

            sseqid = parts[1]
            if "__REF_" in sseqid:
                marker = sseqid.split("__REF_")[0]
            else:
                marker = sseqid

            markers.add(marker)

    return markers


def parse_hmmscan_hits(tblout_path: Path) -> set:
    markers = set()

    if not tblout_path.exists() or tblout_path.stat().st_size == 0:
        return markers

    with open(tblout_path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                continue

            parts = line.strip().split()
            if len(parts) < 5:
                continue

            marker = parts[0]
            full_seq_evalue = float(parts[4])

            if full_seq_evalue <= HMMER_EVALUE:
                markers.add(marker)

    return markers


def build_outputs(manifest_df: pd.DataFrame, meta: pd.DataFrame):
    detailed_rows = []

    for _, row in manifest_df.iterrows():
        genome_id = row["genome_id"]
        faa_path = Path(row["normalized_faa"])

        print(f"[INFO] Running DIAMOND for {genome_id}")
        diamond_tsv = run_diamond(genome_id, faa_path)

        print(f"[INFO] Running hmmscan for {genome_id}")
        hmmscan_tbl = run_hmmscan(genome_id, faa_path)

        diamond_hits = parse_diamond_hits(diamond_tsv)
        hmmer_hits = parse_hmmscan_hits(hmmscan_tbl)

        for _, mrow in meta.iterrows():
            marker = mrow["marker"]
            diamond_detected = 1 if marker in diamond_hits else 0
            hmmer_detected = 1 if marker in hmmer_hits else 0
            present = 1 if (diamond_detected == 1 or hmmer_detected == 1) else 0

            if diamond_detected == 1 and hmmer_detected == 1:
                detection_source = "BOTH"
            elif diamond_detected == 1:
                detection_source = "DIAMOND_ONLY"
            elif hmmer_detected == 1:
                detection_source = "HMMER_ONLY"
            else:
                detection_source = "NONE"

            detailed_rows.append(
                {
                    "genome_id": genome_id,
                    "marker": marker,
                    "category": mrow["category"],
                    "function": mrow["function"],
                    "sources": mrow["sources"],
                    "has_fasta": mrow["has_fasta"],
                    "has_hmm": mrow["has_hmm"],
                    "diamond_detected": diamond_detected,
                    "hmmer_detected": hmmer_detected,
                    "detection_source": detection_source,
                    "present": present,
                }
            )

    detail_df = pd.DataFrame(detailed_rows)
    detail_df = detail_df.sort_values(["genome_id", "category", "marker"], kind="stable").reset_index(drop=True)

    binary_df = detail_df.pivot(index="genome_id", columns="marker", values="present").fillna(0).astype(int)

    ordered_markers = meta["marker"].tolist()
    binary_df = binary_df.reindex(columns=ordered_markers, fill_value=0)
    binary_df = binary_df.reset_index()

    return detail_df, binary_df


def build_category_binary_matrices(
    binary_df: pd.DataFrame,
    category_mapping_df: pd.DataFrame,
    ordered_markers: list[str],
) -> dict[str, dict]:
    category_matrices = {}

    category_order_df = category_mapping_df[["category", "category_slug"]].drop_duplicates().copy()
    category_order_df = category_order_df.sort_values(["category"], kind="stable").reset_index(drop=True)

    marker_to_categories = (
        category_mapping_df.groupby("category")["marker"]
        .apply(list)
        .to_dict()
    )

    for _, row in category_order_df.iterrows():
        category_name = row["category"]
        category_slug = row["category_slug"]

        marker_list = marker_to_categories.get(category_name, [])
        marker_set = set(marker_list)
        ordered_category_markers = [m for m in ordered_markers if m in marker_set]

        if not ordered_category_markers:
            continue

        sub_df = binary_df[["genome_id"] + ordered_category_markers].copy()
        category_matrices[category_name] = {
            "slug": category_slug,
            "data": sub_df,
        }

    return category_matrices


def build_category_summary(binary_df: pd.DataFrame, category_mapping_df: pd.DataFrame) -> pd.DataFrame:
    summary_df = pd.DataFrame({"genome_id": binary_df["genome_id"].tolist()})

    categories = (
        category_mapping_df[["category", "category_slug"]]
        .drop_duplicates()
        .sort_values(["category"], kind="stable")
        .reset_index(drop=True)
    )

    for _, row in categories.iterrows():
        category_name = row["category"]
        category_slug = row["category_slug"]

        markers = category_mapping_df.loc[category_mapping_df["category"] == category_name, "marker"].tolist()
        markers = [m for m in markers if m in binary_df.columns]

        count_col = f"n_markers__{category_slug}"
        binary_col = f"has_category__{category_slug}"

        if markers:
            summary_df[count_col] = binary_df[markers].sum(axis=1).astype(int)
            summary_df[binary_col] = (summary_df[count_col] > 0).astype(int)
        else:
            summary_df[count_col] = 0
            summary_df[binary_col] = 0

    ordered_cols = ["genome_id"]
    for _, row in categories.iterrows():
        category_slug = row["category_slug"]
        ordered_cols.append(f"n_markers__{category_slug}")
        ordered_cols.append(f"has_category__{category_slug}")

    return summary_df[ordered_cols]


def write_outputs(
    detail_df: pd.DataFrame,
    binary_df: pd.DataFrame,
    meta: pd.DataFrame,
    category_mapping_df: pd.DataFrame,
    category_summary_df: pd.DataFrame,
    category_matrices: dict[str, dict],
) -> None:
    detail_df.to_csv(DETAIL_TSV, sep="\t", index=False)
    binary_df.to_csv(BINARY_TSV, sep="\t", index=False)
    meta.to_csv(METADATA_USED_TSV, sep="\t", index=False)
    category_mapping_df.to_csv(CATEGORY_MAPPING_USED_TSV, sep="\t", index=False)
    category_summary_df.to_csv(CATEGORY_SUMMARY_TSV, sep="\t", index=False)

    for old_file in CATEGORY_TSV_DIR.glob("marker_presence_absence__*.tsv"):
        old_file.unlink()

    for category_name, payload in category_matrices.items():
        category_slug = payload["slug"]
        category_df = payload["data"]
        out_path = CATEGORY_TSV_DIR / f"marker_presence_absence__{category_slug}.tsv"
        category_df.to_csv(out_path, sep="\t", index=False)

    used_sheet_names = set()

    with pd.ExcelWriter(BINARY_XLSX, engine="openpyxl") as writer:
        sheet_name = make_unique_sheet_name("presence_absence", used_sheet_names)
        binary_df.to_excel(writer, sheet_name=sheet_name, index=False)

        sheet_name = make_unique_sheet_name("detection_detail", used_sheet_names)
        detail_df.to_excel(writer, sheet_name=sheet_name, index=False)

        sheet_name = make_unique_sheet_name("marker_metadata", used_sheet_names)
        meta.to_excel(writer, sheet_name=sheet_name, index=False)

        sheet_name = make_unique_sheet_name("category_mapping", used_sheet_names)
        category_mapping_df.to_excel(writer, sheet_name=sheet_name, index=False)

        sheet_name = make_unique_sheet_name("category_summary", used_sheet_names)
        category_summary_df.to_excel(writer, sheet_name=sheet_name, index=False)

        for category_name, payload in sorted(category_matrices.items(), key=lambda x: x[0]):
            category_df = payload["data"]
            category_slug = payload["slug"]
            desired_sheet = f"cat_{category_slug}"
            sheet_name = make_unique_sheet_name(desired_sheet, used_sheet_names)
            category_df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"[INFO] Detailed marker table written to: {DETAIL_TSV}")
    print(f"[INFO] Binary matrix written to: {BINARY_TSV}")
    print(f"[INFO] Marker metadata copy written to: {METADATA_USED_TSV}")
    print(f"[INFO] Category mapping written to: {CATEGORY_MAPPING_USED_TSV}")
    print(f"[INFO] Category summary written to: {CATEGORY_SUMMARY_TSV}")
    print(f"[INFO] Category-specific matrices directory: {CATEGORY_TSV_DIR}")
    print(f"[INFO] Excel workbook written to: {BINARY_XLSX}")


def main() -> None:
    for d in [DIAMOND_RAW_DIR, HMMER_RAW_DIR, MERGED_DIR, RESULTS_TSV_DIR, RESULTS_XLSX_DIR, CATEGORY_TSV_DIR, TMP_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    if not DIAMOND_DB.exists():
        raise FileNotFoundError(f"DIAMOND database not found: {DIAMOND_DB}")

    if not HMM_DB.exists():
        raise FileNotFoundError(f"HMM database not found: {HMM_DB}")

    manifest_df = load_manifest()
    meta, category_mapping_df = build_authoritative_marker_metadata()

    print(f"[INFO] Genomes with available FAA: {len(manifest_df)}")
    print(f"[INFO] Total markers in metadata: {len(meta)}")
    print(f"[INFO] Total category assignments: {len(category_mapping_df)}")
    print(f"[INFO] Total functional categories: {category_mapping_df['category'].nunique()}")

    detail_df, binary_df = build_outputs(manifest_df, meta)
    ordered_markers = meta["marker"].tolist()

    category_matrices = build_category_binary_matrices(binary_df, category_mapping_df, ordered_markers)
    category_summary_df = build_category_summary(binary_df, category_mapping_df)

    write_outputs(
        detail_df=detail_df,
        binary_df=binary_df,
        meta=meta,
        category_mapping_df=category_mapping_df,
        category_summary_df=category_summary_df,
        category_matrices=category_matrices,
    )


if __name__ == "__main__":
    main()

