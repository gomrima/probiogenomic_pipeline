#!/usr/bin/env python3

import re
import subprocess
import sys
import os
from pathlib import Path

import pandas as pd


PIPE_ROOT = Path(os.environ.get("PIPE_ROOT", Path(__file__).resolve().parent.parent))

MANIFEST_TSV = PIPE_ROOT / "work" / "manifest" / "input_manifest.tsv"

DBETH_FASTA = PIPE_ROOT / "db" / "safety" / "DBETH" / "Human_pathogenic_bacterial_exotoxin.fasta"
PAT_TOXIN_FASTA = PIPE_ROOT / "db" / "safety" / "PAT" / "PAT-prot.fasta"
PAT_IMMUNITY_FASTA = PIPE_ROOT / "db" / "safety" / "PAT" / "IMM-prot.fasta"

DIAMOND_DB_DIR = PIPE_ROOT / "db" / "safety" / "compiled_diamond"
DBETH_DMND = DIAMOND_DB_DIR / "dbeth_exotoxins.dmnd"
PAT_TOXIN_DMND = DIAMOND_DB_DIR / "pat_toxins.dmnd"
PAT_IMMUNITY_DMND = DIAMOND_DB_DIR / "pat_immunity.dmnd"

TMP_DIR = PIPE_ROOT / "work" / "tmp"

RAW_DIR = PIPE_ROOT / "work" / "intermediate" / "toxins" / "diamond_raw"
RESULTS_TSV_DIR = PIPE_ROOT / "results" / "tsv" / "toxins"
RESULTS_XLSX_DIR = PIPE_ROOT / "results" / "xlsx" / "toxins"

DBETH_DETAIL_TSV = RESULTS_TSV_DIR / "dbeth_toxins_detail.tsv"
DBETH_BINARY_TSV = RESULTS_TSV_DIR / "dbeth_toxins_binary.tsv"

PAT_TOXIN_DETAIL_TSV = RESULTS_TSV_DIR / "pat_toxins_detail.tsv"
PAT_TOXIN_BINARY_TSV = RESULTS_TSV_DIR / "pat_toxins_binary.tsv"

PAT_IMMUNITY_DETAIL_TSV = RESULTS_TSV_DIR / "pat_immunity_detail.tsv"
PAT_IMMUNITY_BINARY_TSV = RESULTS_TSV_DIR / "pat_immunity_binary.tsv"

WORKBOOK_XLSX = RESULTS_XLSX_DIR / "bacterial_toxins_screening.xlsx"

DIAMOND_THREADS = 2
DIAMOND_EVALUE = 1e-5
MIN_IDENTITY = 30.0
MIN_QUERY_COVERAGE = 50.0
MIN_SUBJECT_COVERAGE = 50.0


def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required file not found: {path}")


def run_command(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def load_manifest() -> pd.DataFrame:
    require_file(MANIFEST_TSV)

    df = pd.read_csv(MANIFEST_TSV, sep="\t")

    required = ["genome_id", "normalized_faa"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in manifest: {missing}")

    df["genome_id"] = df["genome_id"].map(safe_text)
    df["normalized_faa"] = df["normalized_faa"].map(safe_text)

    df = df[(df["genome_id"] != "") & (df["normalized_faa"] != "")].copy()
    df["faa_exists"] = df["normalized_faa"].apply(lambda x: Path(x).is_file())
    df = df[df["faa_exists"]].copy()

    if df.empty:
        raise ValueError("No genomes with available FAA were found in the manifest")

    if df["genome_id"].duplicated().any():
        dupes = sorted(df.loc[df["genome_id"].duplicated(), "genome_id"].unique().tolist())
        raise ValueError(f"Duplicated genome_id values in manifest: {dupes}")

    return df[["genome_id", "normalized_faa"]].reset_index(drop=True)


def sanitize_feature_name(text: str) -> str:
    text = safe_text(text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9._:+-]+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("._")
    return text or "unknown_feature"


def parse_fasta_headers(fasta_path: Path, db_label: str, feature_type: str) -> pd.DataFrame:
    require_file(fasta_path)

    rows = []
    with open(fasta_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith(">"):
                continue

            raw_header = line[1:].strip()
            seq_id = raw_header.split()[0]

            description = raw_header
            feature_name = sanitize_feature_name(seq_id)

            if db_label == "DBETH":
                if " GN=" in raw_header:
                    gn_part = raw_header.split(" GN=", 1)[1]
                    gene_name = gn_part.split()[0]
                    if gene_name:
                        feature_name = sanitize_feature_name(gene_name)
                elif len(raw_header.split()) > 1:
                    feature_name = sanitize_feature_name(raw_header.split()[1])

            rows.append(
                {
                    "sseqid": seq_id,
                    "db_label": db_label,
                    "feature_type": feature_type,
                    "feature_name": feature_name,
                    "header": raw_header,
                    "description": description,
                }
            )

    if not rows:
        raise ValueError(f"No FASTA headers found in: {fasta_path}")

    meta = pd.DataFrame(rows)

    if meta["sseqid"].duplicated().any():
        dupes = meta.loc[meta["sseqid"].duplicated(), "sseqid"].tolist()
        raise ValueError(f"Duplicated sequence identifiers found in {fasta_path}: {dupes[:10]}")

    return meta


def build_diamond_db(input_fasta: Path, output_dmnd: Path) -> None:
    require_file(input_fasta)
    output_dmnd.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "diamond",
        "makedb",
        "--in", str(input_fasta),
        "--db", str(output_dmnd),
    ]
    run_command(cmd)


def run_diamond_search(genome_id: str, faa_path: Path, db_path: Path, output_path: Path) -> None:
    cmd = [
        "diamond",
        "blastp",
        "--db", str(db_path),
        "--query", str(faa_path),
        "--out", str(output_path),
        "--outfmt", "6",
        "qseqid", "sseqid", "pident", "length", "qlen", "slen", "qcovhsp", "scovhsp", "evalue", "bitscore",
        "--evalue", str(DIAMOND_EVALUE),
        "--id", str(MIN_IDENTITY),
        "--query-cover", str(MIN_QUERY_COVERAGE),
        "--subject-cover", str(MIN_SUBJECT_COVERAGE),
        "--max-target-seqs", "1",
        "--threads", str(DIAMOND_THREADS),
        "--tmpdir", str(TMP_DIR),
    ]
    run_command(cmd)


def collect_hits_for_database(
    manifest_df: pd.DataFrame,
    fasta_meta_df: pd.DataFrame,
    db_path: Path,
    raw_prefix: str,
) -> pd.DataFrame:
    detailed_rows = []

    meta_by_sseqid = fasta_meta_df.set_index("sseqid").to_dict(orient="index")

    for _, row in manifest_df.iterrows():
        genome_id = row["genome_id"]
        faa_path = Path(row["normalized_faa"])
        out_path = RAW_DIR / f"{genome_id}.{raw_prefix}.tsv"

        print(f"[INFO] Running DIAMOND for {genome_id} against {raw_prefix}", flush=True)
        run_diamond_search(genome_id, faa_path, db_path, out_path)

        if not out_path.exists() or out_path.stat().st_size == 0:
            continue

        with open(out_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 10:
                    continue

                qseqid, sseqid, pident, length, qlen, slen, qcovhsp, scovhsp, evalue, bitscore = parts

                if sseqid not in meta_by_sseqid:
                    continue

                meta = meta_by_sseqid[sseqid]

                detailed_rows.append(
                    {
                        "genome_id": genome_id,
                        "query_id": qseqid,
                        "subject_id": sseqid,
                        "feature_name": meta["feature_name"],
                        "feature_type": meta["feature_type"],
                        "db_label": meta["db_label"],
                        "header": meta["header"],
                        "description": meta["description"],
                        "pident": float(pident),
                        "alignment_length": int(float(length)),
                        "query_length": int(float(qlen)),
                        "subject_length": int(float(slen)),
                        "query_coverage": float(qcovhsp),
                        "subject_coverage": float(scovhsp),
                        "evalue": float(evalue),
                        "bitscore": float(bitscore),
                    }
                )

    if not detailed_rows:
        return pd.DataFrame(
            columns=[
                "genome_id", "query_id", "subject_id", "feature_name", "feature_type", "db_label",
                "header", "description", "pident", "alignment_length", "query_length",
                "subject_length", "query_coverage", "subject_coverage", "evalue", "bitscore",
            ]
        )

    detail_df = pd.DataFrame(detailed_rows)

    detail_df = (
        detail_df.sort_values(
            by=["genome_id", "feature_name", "bitscore", "pident", "query_coverage", "subject_coverage"],
            ascending=[True, True, False, False, False, False],
            kind="stable",
        )
        .drop_duplicates(subset=["genome_id", "feature_name"], keep="first")
        .reset_index(drop=True)
    )

    return detail_df


def build_binary_matrix(manifest_df: pd.DataFrame, detail_df: pd.DataFrame) -> pd.DataFrame:
    genomes = manifest_df["genome_id"].tolist()
    binary_df = pd.DataFrame({"genome_id": genomes})

    if detail_df.empty:
        return binary_df

    presence = (
        detail_df.assign(present=1)
        .pivot(index="genome_id", columns="feature_name", values="present")
        .fillna(0)
        .astype(int)
        .reset_index()
    )

    feature_cols = sorted([c for c in presence.columns if c != "genome_id"])
    presence = presence[["genome_id"] + feature_cols]

    binary_df = binary_df.merge(presence, on="genome_id", how="left").fillna(0)

    for col in binary_df.columns:
        if col != "genome_id":
            binary_df[col] = pd.to_numeric(binary_df[col], errors="raise").astype(int)

    return binary_df


def write_outputs(
    dbeth_detail_df: pd.DataFrame,
    dbeth_binary_df: pd.DataFrame,
    pat_toxins_detail_df: pd.DataFrame,
    pat_toxins_binary_df: pd.DataFrame,
    pat_immunity_detail_df: pd.DataFrame,
    pat_immunity_binary_df: pd.DataFrame,
) -> None:
    dbeth_detail_df.to_csv(DBETH_DETAIL_TSV, sep="\t", index=False)
    dbeth_binary_df.to_csv(DBETH_BINARY_TSV, sep="\t", index=False)

    pat_toxins_detail_df.to_csv(PAT_TOXIN_DETAIL_TSV, sep="\t", index=False)
    pat_toxins_binary_df.to_csv(PAT_TOXIN_BINARY_TSV, sep="\t", index=False)

    pat_immunity_detail_df.to_csv(PAT_IMMUNITY_DETAIL_TSV, sep="\t", index=False)
    pat_immunity_binary_df.to_csv(PAT_IMMUNITY_BINARY_TSV, sep="\t", index=False)

    with pd.ExcelWriter(WORKBOOK_XLSX, engine="openpyxl") as writer:
        dbeth_detail_df.to_excel(writer, sheet_name="dbeth_detail", index=False)
        dbeth_binary_df.to_excel(writer, sheet_name="dbeth_binary", index=False)

        pat_toxins_detail_df.to_excel(writer, sheet_name="pat_toxins_detail", index=False)
        pat_toxins_binary_df.to_excel(writer, sheet_name="pat_toxins_binary", index=False)

        pat_immunity_detail_df.to_excel(writer, sheet_name="pat_immunity_detail", index=False)
        pat_immunity_binary_df.to_excel(writer, sheet_name="pat_immunity_binary", index=False)

    print(f"[INFO] DBETH detail written to: {DBETH_DETAIL_TSV}", flush=True)
    print(f"[INFO] DBETH binary written to: {DBETH_BINARY_TSV}", flush=True)
    print(f"[INFO] PAT toxins detail written to: {PAT_TOXIN_DETAIL_TSV}", flush=True)
    print(f"[INFO] PAT toxins binary written to: {PAT_TOXIN_BINARY_TSV}", flush=True)
    print(f"[INFO] PAT immunity detail written to: {PAT_IMMUNITY_DETAIL_TSV}", flush=True)
    print(f"[INFO] PAT immunity binary written to: {PAT_IMMUNITY_BINARY_TSV}", flush=True)
    print(f"[INFO] Excel workbook written to: {WORKBOOK_XLSX}", flush=True)


def main() -> None:
    for d in [DIAMOND_DB_DIR, TMP_DIR, RAW_DIR, RESULTS_TSV_DIR, RESULTS_XLSX_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    require_file(DBETH_FASTA)
    require_file(PAT_TOXIN_FASTA)
    require_file(PAT_IMMUNITY_FASTA)

    manifest_df = load_manifest()
    print(f"[INFO] Genomes with available FAA: {len(manifest_df)}", flush=True)

    print("[INFO] Parsing DBETH FASTA metadata", flush=True)
    dbeth_meta = parse_fasta_headers(DBETH_FASTA, db_label="DBETH", feature_type="exotoxin")
    print(f"[INFO] DBETH curated exotoxins: {len(dbeth_meta)}", flush=True)

    print("[INFO] Parsing PAT toxin FASTA metadata", flush=True)
    pat_toxin_meta = parse_fasta_headers(PAT_TOXIN_FASTA, db_label="PAT", feature_type="antimicrobial_toxin")
    print(f"[INFO] PAT toxins: {len(pat_toxin_meta)}", flush=True)

    print("[INFO] Parsing PAT immunity FASTA metadata", flush=True)
    pat_immunity_meta = parse_fasta_headers(PAT_IMMUNITY_FASTA, db_label="PAT", feature_type="immunity_protein")
    print(f"[INFO] PAT immunity proteins: {len(pat_immunity_meta)}", flush=True)

    print("[INFO] Building DIAMOND database for DBETH curated exotoxins", flush=True)
    build_diamond_db(DBETH_FASTA, DBETH_DMND)

    print("[INFO] Building DIAMOND database for PAT toxins", flush=True)
    build_diamond_db(PAT_TOXIN_FASTA, PAT_TOXIN_DMND)

    print("[INFO] Building DIAMOND database for PAT immunity proteins", flush=True)
    build_diamond_db(PAT_IMMUNITY_FASTA, PAT_IMMUNITY_DMND)

    dbeth_detail_df = collect_hits_for_database(
        manifest_df=manifest_df,
        fasta_meta_df=dbeth_meta,
        db_path=DBETH_DMND,
        raw_prefix="dbeth",
    )
    dbeth_binary_df = build_binary_matrix(manifest_df, dbeth_detail_df)

    pat_toxins_detail_df = collect_hits_for_database(
        manifest_df=manifest_df,
        fasta_meta_df=pat_toxin_meta,
        db_path=PAT_TOXIN_DMND,
        raw_prefix="pat_toxins",
    )
    pat_toxins_binary_df = build_binary_matrix(manifest_df, pat_toxins_detail_df)

    pat_immunity_detail_df = collect_hits_for_database(
        manifest_df=manifest_df,
        fasta_meta_df=pat_immunity_meta,
        db_path=PAT_IMMUNITY_DMND,
        raw_prefix="pat_immunity",
    )
    pat_immunity_binary_df = build_binary_matrix(manifest_df, pat_immunity_detail_df)

    write_outputs(
        dbeth_detail_df=dbeth_detail_df,
        dbeth_binary_df=dbeth_binary_df,
        pat_toxins_detail_df=pat_toxins_detail_df,
        pat_toxins_binary_df=pat_toxins_binary_df,
        pat_immunity_detail_df=pat_immunity_detail_df,
        pat_immunity_binary_df=pat_immunity_binary_df,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        sys.exit(1)

