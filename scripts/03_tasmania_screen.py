#!/usr/bin/env python3

import os
from pathlib import Path
import pandas as pd

PIPE_ROOT = Path(os.environ.get("PIPE_ROOT", Path(__file__).resolve().parent.parent))

MANIFEST_TSV = PIPE_ROOT / "work" / "manifest" / "input_manifest.tsv"
RAW_DIR = PIPE_ROOT / "work" / "intermediate" / "ta_systems" / "hmmer_raw"
RESULTS_TSV_DIR = PIPE_ROOT / "results" / "tsv" / "ta_systems"
RESULTS_XLSX_DIR = PIPE_ROOT / "results" / "xlsx" / "ta_systems"

DETAIL_TSV = RESULTS_TSV_DIR / "tasmania_detail.tsv"
BINARY_TSV = RESULTS_TSV_DIR / "tasmania_presence_absence_binary.tsv"
SUMMARY_TSV = RESULTS_TSV_DIR / "tasmania_summary_by_genome.tsv"
NOHIT_TSV = RESULTS_TSV_DIR / "tasmania_nohit_genomes.tsv"
XLSX_FILE = RESULTS_XLSX_DIR / "tasmania_results.xlsx"

HMMER_EVALUE = 1e-5


def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def load_manifest() -> pd.DataFrame:
    if not MANIFEST_TSV.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_TSV}")

    df = pd.read_csv(MANIFEST_TSV, sep="\t")

    required = ["genome_id", "normalized_faa"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in manifest: {missing}")

    df["genome_id"] = df["genome_id"].map(safe_text)
    df["normalized_faa"] = df["normalized_faa"].fillna("").astype(str)

    df = df[df["genome_id"] != ""].copy()
    df = df[df["normalized_faa"] != ""].copy()

    if df["genome_id"].duplicated().any():
        dupes = sorted(df.loc[df["genome_id"].duplicated(), "genome_id"].unique().tolist())
        raise ValueError(f"Duplicated genome_id values in manifest: {dupes}")

    return df


def parse_domtblout(domtbl_path: Path) -> list[dict]:
    rows = []

    if not domtbl_path.exists() or domtbl_path.stat().st_size == 0:
        return rows

    with open(domtbl_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue

            parts = line.strip().split()
            if len(parts) < 23:
                continue

            target_name = parts[0]
            target_accession = parts[1]
            query_name = parts[3]
            query_accession = parts[4]

            try:
                full_seq_evalue = float(parts[6])
                full_seq_score = float(parts[7])
                domain_ievalue = float(parts[12])
                domain_score = float(parts[13])
                hmm_from = int(parts[15])
                hmm_to = int(parts[16])
                ali_from = int(parts[17])
                ali_to = int(parts[18])
                env_from = int(parts[19])
                env_to = int(parts[20])
                acc = float(parts[21])
            except ValueError:
                continue

            description = " ".join(parts[22:]) if len(parts) > 22 else ""

            if full_seq_evalue <= HMMER_EVALUE:
                rows.append(
                    {
                        "marker": target_name,
                        "marker_accession": target_accession,
                        "query_id": query_name,
                        "query_accession": query_accession,
                        "full_seq_evalue": full_seq_evalue,
                        "full_seq_score": full_seq_score,
                        "domain_ievalue": domain_ievalue,
                        "domain_score": domain_score,
                        "hmm_from": hmm_from,
                        "hmm_to": hmm_to,
                        "ali_from": ali_from,
                        "ali_to": ali_to,
                        "env_from": env_from,
                        "env_to": env_to,
                        "acc": acc,
                        "description": description,
                    }
                )

    return rows


def main() -> None:
    RESULTS_TSV_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_XLSX_DIR.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest()
    all_genomes = manifest["genome_id"].tolist()

    detail_rows = []

    for _, row in manifest.iterrows():
        genome_id = row["genome_id"]
        domtbl = RAW_DIR / f"{genome_id}.tasmania.domtblout"

        parsed_hits = parse_domtblout(domtbl)

        for hit in parsed_hits:
            detail_rows.append(
                {
                    "genome_id": genome_id,
                    "marker": hit["marker"],
                    "marker_accession": hit["marker_accession"],
                    "query_id": hit["query_id"],
                    "query_accession": hit["query_accession"],
                    "full_seq_evalue": hit["full_seq_evalue"],
                    "full_seq_score": hit["full_seq_score"],
                    "domain_ievalue": hit["domain_ievalue"],
                    "domain_score": hit["domain_score"],
                    "hmm_from": hit["hmm_from"],
                    "hmm_to": hit["hmm_to"],
                    "ali_from": hit["ali_from"],
                    "ali_to": hit["ali_to"],
                    "env_from": hit["env_from"],
                    "env_to": hit["env_to"],
                    "acc": hit["acc"],
                    "description": hit["description"],
                    "present": 1,
                }
            )

    if detail_rows:
        detail_df = pd.DataFrame(detail_rows)
        detail_df = detail_df.sort_values(
            ["genome_id", "marker", "query_id", "full_seq_evalue", "domain_ievalue"],
            kind="stable"
        ).reset_index(drop=True)

        binary_seed = detail_df[["genome_id", "marker", "present"]].drop_duplicates()

        binary_df = (
            binary_seed.pivot(index="genome_id", columns="marker", values="present")
            .fillna(0)
            .astype(int)
            .reset_index()
        )

        binary_df.columns.name = None
    else:
        print("[WARN] No TASmania hits detected in any genome")
        detail_df = pd.DataFrame(
            columns=[
                "genome_id", "marker", "marker_accession", "query_id", "query_accession",
                "full_seq_evalue", "full_seq_score", "domain_ievalue", "domain_score",
                "hmm_from", "hmm_to", "ali_from", "ali_to", "env_from", "env_to",
                "acc", "description", "present"
            ]
        )
        binary_df = pd.DataFrame({"genome_id": all_genomes})

    # Force full genome representation
    full_binary = pd.DataFrame({"genome_id": all_genomes}).merge(binary_df, on="genome_id", how="left")
    for col in full_binary.columns:
        if col != "genome_id":
            full_binary[col] = pd.to_numeric(full_binary[col], errors="coerce").fillna(0).astype(int)

    marker_cols = sorted([c for c in full_binary.columns if c != "genome_id"])
    full_binary = full_binary[["genome_id"] + marker_cols]

    # Summary
    if marker_cols:
        full_binary["n_tasmania_markers"] = full_binary[marker_cols].sum(axis=1)
    else:
        full_binary["n_tasmania_markers"] = 0

    summary_df = full_binary[["genome_id", "n_tasmania_markers"]].copy()
    summary_df["tasmania_any_hit"] = (summary_df["n_tasmania_markers"] > 0).astype(int)

    nohit_df = summary_df[summary_df["tasmania_any_hit"] == 0].copy()

    # Write outputs
    detail_df.to_csv(DETAIL_TSV, sep="\t", index=False)
    full_binary.drop(columns=["n_tasmania_markers"]).to_csv(BINARY_TSV, sep="\t", index=False)
    summary_df.to_csv(SUMMARY_TSV, sep="\t", index=False)
    nohit_df.to_csv(NOHIT_TSV, sep="\t", index=False)

    with pd.ExcelWriter(XLSX_FILE, engine="openpyxl") as writer:
        detail_df.to_excel(writer, sheet_name="detail", index=False)
        full_binary.drop(columns=["n_tasmania_markers"]).to_excel(writer, sheet_name="binary", index=False)
        summary_df.to_excel(writer, sheet_name="summary_by_genome", index=False)
        nohit_df.to_excel(writer, sheet_name="nohit_genomes", index=False)

    print(f"[INFO] TASmania detail table written to: {DETAIL_TSV}")
    print(f"[INFO] TASmania binary matrix written to: {BINARY_TSV}")
    print(f"[INFO] TASmania summary table written to: {SUMMARY_TSV}")
    print(f"[INFO] TASmania no-hit genome table written to: {NOHIT_TSV}")
    print(f"[INFO] TASmania workbook written to: {XLSX_FILE}")


if __name__ == "__main__":
    main()

