#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd
from Bio import SeqIO


def parse_args():
    parser = argparse.ArgumentParser(description="Run antiSMASH minimal module and consolidate results.")
    parser.add_argument("--manifest", required=True, help="Input manifest TSV")
    parser.add_argument("--raw-root", required=True, help="Root directory for raw antiSMASH outputs")
    parser.add_argument("--db-dir", required=True, help="antiSMASH database root")
    parser.add_argument("--output-tsv-dir", required=True, help="Directory for TSV outputs")
    parser.add_argument("--output-xlsx-dir", required=True, help="Directory for XLSX outputs")
    parser.add_argument("--threads", type=int, default=2, help="Threads for antiSMASH")
    parser.add_argument("--antismash-exec", required=True, help="Path to antiSMASH executable")
    parser.add_argument("--antismash-env-bin", required=True, help="Path to antiSMASH env bin directory")
    return parser.parse_args()


def mkdir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def load_manifest(path):
    df = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    required = {"genome_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Manifest missing required columns: {sorted(missing)}")
    return df


def choose_input_file(row):
    gbff = row["normalized_gbff"] if "normalized_gbff" in row else ""
    fna = row["normalized_fna"] if "normalized_fna" in row else ""

    if gbff and os.path.isfile(gbff):
        return gbff, "gbff"
    if fna and os.path.isfile(fna):
        return fna, "fna"
    return "", ""


def run_antismash(genome_id, input_file, input_type, run_dir, db_dir, antismash_exec, antismash_env_bin, threads):
    print(f"\n=== Processing genome: {genome_id} ===")
    print(f"Input: {input_file}")
    print(f"Input type: {input_type}")
    print(f"antiSMASH run directory: {run_dir}")

    run_path = Path(run_dir)
    if run_path.exists():
        shutil.rmtree(run_path)
    run_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        antismash_exec,
        "--taxon", "bacteria",
        "--cpus", str(threads),
        "--databases", db_dir,
        "--output-dir", run_dir,
    ]

    if input_type == "fna":
        cmd.extend(["--genefinding-tool", "prodigal"])

    cmd.append(input_file)

    env = os.environ.copy()
    env["PATH"] = antismash_env_bin + os.pathsep + env.get("PATH", "")

    print(f"[{genome_id}] Running: {' '.join(cmd)}")

    completed = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    return completed


def load_antismash_json(run_dir):
    json_files = sorted(Path(run_dir).glob("*.json"))
    if not json_files:
        return None
    with open(json_files[0], "r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_regions_from_json(genome_id, input_file, input_type, data):
    detail_rows = []

    if not data or "records" not in data:
        return detail_rows

    region_counter = 0

    for record in data.get("records", []):
        contig_id = record.get("id", "")
        areas = record.get("areas", [])

        for area in areas:
            region_counter += 1
            products = area.get("products", [])
            product_string = ";".join(products) if isinstance(products, list) else str(products)
            contig_edge = bool(area.get("contig_edge", False))

            start = safe_int(area.get("start", 0), 0)
            end = safe_int(area.get("end", 0), 0)

            protoclusters = area.get("protoclusters", [])
            candidate_clusters = area.get("candidate_clusters", [])

            detail_rows.append({
                "genome_id": genome_id,
                "input_file": input_file,
                "input_type": input_type,
                "contig_id": contig_id,
                "region_number": region_counter,
                "start": start,
                "end": end,
                "product": product_string,
                "contig_edge": contig_edge,
                "n_products": len(products) if isinstance(products, list) else 0,
                "n_protoclusters": len(protoclusters) if isinstance(protoclusters, list) else 0,
                "n_candidate_clusters": len(candidate_clusters) if isinstance(candidate_clusters, list) else 0,
                "record_type": record.get("type", "")
            })

    return detail_rows


def build_binary_matrix(detail_df, genome_ids):
    rows = []

    unique_products = sorted(
        {p for p in detail_df["product"].dropna().astype(str) if p.strip()}
    ) if not detail_df.empty and "product" in detail_df.columns else []

    for genome_id in genome_ids:
        subset = detail_df[detail_df["genome_id"] == genome_id] if not detail_df.empty else pd.DataFrame()
        row = {"genome_id": genome_id}
        row["bgc_present"] = 1 if not subset.empty else 0

        for product in unique_products:
            row[f"product:{product}"] = 1 if ((subset["product"] == product).any()) else 0

        rows.append(row)

    return pd.DataFrame(rows)


def build_summary(detail_df, manifest_df):
    summaries = []

    for _, row in manifest_df.iterrows():
        genome_id = row["genome_id"]
        input_file, input_type = choose_input_file(row)

        subset = detail_df[detail_df["genome_id"] == genome_id] if not detail_df.empty else pd.DataFrame()

        summaries.append({
            "genome_id": genome_id,
            "input_file": input_file,
            "input_type": input_type,
            "n_regions": int(len(subset)),
            "n_contigs_with_regions": int(subset["contig_id"].nunique()) if not subset.empty else 0,
            "n_unique_products": int(subset["product"].nunique()) if not subset.empty else 0,
            "n_edge_regions": int(subset["contig_edge"].astype(bool).sum()) if not subset.empty else 0
        })

    return pd.DataFrame(summaries)


def write_outputs(detail_df, binary_df, summary_df, failures_df, tsv_dir, xlsx_dir):
    mkdir(tsv_dir)
    mkdir(xlsx_dir)

    detail_tsv = os.path.join(tsv_dir, "antismash_regions_detail.tsv")
    binary_tsv = os.path.join(tsv_dir, "antismash_bgc_binary.tsv")
    summary_tsv = os.path.join(tsv_dir, "antismash_summary_by_genome.tsv")
    failures_tsv = os.path.join(tsv_dir, "antismash_failures.tsv")
    xlsx_file = os.path.join(xlsx_dir, "antismash_results.xlsx")

    detail_df.to_csv(detail_tsv, sep="\t", index=False)
    binary_df.to_csv(binary_tsv, sep="\t", index=False)
    summary_df.to_csv(summary_tsv, sep="\t", index=False)
    failures_df.to_csv(failures_tsv, sep="\t", index=False)

    with pd.ExcelWriter(xlsx_file, engine="openpyxl") as writer:
        detail_df.to_excel(writer, sheet_name="regions_detail", index=False)
        binary_df.to_excel(writer, sheet_name="bgc_binary", index=False)
        summary_df.to_excel(writer, sheet_name="summary_by_genome", index=False)
        failures_df.to_excel(writer, sheet_name="failures", index=False)

    print("\nantiSMASH minimal module completed.")
    print(f"Detail TSV   : {detail_tsv}")
    print(f"Binary TSV   : {binary_tsv}")
    print(f"Summary TSV  : {summary_tsv}")
    print(f"Failures TSV : {failures_tsv}")
    print(f"Workbook XLSX: {xlsx_file}")
    print()


def main():
    args = parse_args()

    manifest_df = load_manifest(args.manifest)
    genome_ids = manifest_df["genome_id"].tolist()

    mkdir(args.raw_root)
    mkdir(args.output_tsv_dir)
    mkdir(args.output_xlsx_dir)

    all_detail_rows = []
    failure_rows = []

    real_failures = 0

    for _, row in manifest_df.iterrows():
        genome_id = row["genome_id"]
        input_file, input_type = choose_input_file(row)

        if not input_file:
            failure_rows.append({
                "genome_id": genome_id,
                "input_file": "",
                "input_type": "",
                "status": "SKIPPED",
                "message": "No valid normalized_gbff or normalized_fna input file found"
            })
            continue

        run_dir = os.path.join(args.raw_root, genome_id)

        completed = run_antismash(
            genome_id=genome_id,
            input_file=input_file,
            input_type=input_type,
            run_dir=run_dir,
            db_dir=args.db_dir,
            antismash_exec=args.antismash_exec,
            antismash_env_bin=args.antismash_env_bin,
            threads=args.threads
        )

        if completed.returncode != 0:
            message = "STDERR:\n" + (completed.stderr.strip() if completed.stderr.strip() else "antiSMASH failed without stderr")
            print(f"[ERROR] Genome failed: {genome_id}")
            print(message)

            failure_rows.append({
                "genome_id": genome_id,
                "input_file": input_file,
                "input_type": input_type,
                "status": "FAILED",
                "message": message
            })
            real_failures += 1
            continue

        try:
            data = load_antismash_json(run_dir)
            detail_rows = extract_regions_from_json(genome_id, input_file, input_type, data)
            all_detail_rows.extend(detail_rows)
        except Exception as exc:
            message = f"Post-processing failed: {exc}"
            print(f"[ERROR] Genome parsing failed: {genome_id}")
            print(message)
            failure_rows.append({
                "genome_id": genome_id,
                "input_file": input_file,
                "input_type": input_type,
                "status": "FAILED",
                "message": message
            })
            real_failures += 1

    detail_columns = [
        "genome_id", "input_file", "input_type", "contig_id", "region_number",
        "start", "end", "product", "contig_edge", "n_products",
        "n_protoclusters", "n_candidate_clusters", "record_type"
    ]

    detail_df = pd.DataFrame(all_detail_rows, columns=detail_columns)
    failures_df = pd.DataFrame(
        failure_rows,
        columns=["genome_id", "input_file", "input_type", "status", "message"]
    )
    binary_df = build_binary_matrix(detail_df, genome_ids)
    summary_df = build_summary(detail_df, manifest_df)

    write_outputs(detail_df, binary_df, summary_df, failures_df, args.output_tsv_dir, args.output_xlsx_dir)

    if real_failures > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

