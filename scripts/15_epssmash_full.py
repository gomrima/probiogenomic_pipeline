#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd


DETAIL_COLUMNS = ["genome_id", "json_file", "record_name", "product_raw", "product_normalized"]
SUMMARY_COLUMNS = ["genome_id", "n_detected_products", "detected_products"]
FAIL_COLUMNS = ["genome_id", "input_fna", "status", "message"]


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def load_manifest(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    required = ["genome_id", "status"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required manifest columns: {missing}")
    return df[df["status"].astype(str) == "OK"].copy()


def split_valid_inputs(manifest_df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    valid_rows = []
    failure_rows = []

    for _, row in manifest_df.iterrows():
        genome_id = safe_text(row["genome_id"])
        input_fna = safe_text(row.get("normalized_fna", ""))

        if not input_fna or not Path(input_fna).is_file():
            failure_rows.append(
                {
                    "genome_id": genome_id,
                    "input_fna": input_fna,
                    "status": "SKIPPED",
                    "message": "Missing normalized_fna file",
                }
            )
            continue

        valid_rows.append({"genome_id": genome_id, "input_fna": input_fna})

    return pd.DataFrame(valid_rows), failure_rows


def find_single_json_file(run_dir: Path) -> Path:
    json_files = sorted(run_dir.glob("*.json"))
    if len(json_files) == 0:
        raise FileNotFoundError(f"No JSON file found in {run_dir}")
    if len(json_files) > 1:
        raise RuntimeError(f"Multiple JSON files found in {run_dir}: {[p.name for p in json_files]}")
    return json_files[0]


def load_binary_table(path: Path, all_genomes: list[str]) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame({"genome_id": all_genomes})

    df = pd.read_csv(path, sep="\t")
    if "genome_id" not in df.columns:
        raise ValueError(f"'genome_id' column missing in {path}")

    feature_cols = [c for c in df.columns if c != "genome_id"]
    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    merged = pd.DataFrame({"genome_id": all_genomes}).merge(df, on="genome_id", how="left").fillna(0)
    for col in merged.columns:
        if col != "genome_id":
            merged[col] = merged[col].astype(int)

    ordered_cols = ["genome_id"] + sorted([c for c in merged.columns if c != "genome_id"])
    return merged[ordered_cols]


def load_detail_table(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    df = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    for col in DETAIL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[DETAIL_COLUMNS].copy()


def load_summary_table(path: Path, all_genomes: list[str]) -> pd.DataFrame:
    if path.is_file():
        df = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=SUMMARY_COLUMNS)

    for col in SUMMARY_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    if not df.empty:
        df["n_detected_products"] = pd.to_numeric(df["n_detected_products"], errors="coerce").fillna(0).astype(int)

    merged = pd.DataFrame({"genome_id": all_genomes}).merge(df[SUMMARY_COLUMNS], on="genome_id", how="left")
    merged["n_detected_products"] = pd.to_numeric(merged["n_detected_products"], errors="coerce").fillna(0).astype(int)
    merged["detected_products"] = merged["detected_products"].fillna("")
    return merged[SUMMARY_COLUMNS]


def write_outputs(binary_df: pd.DataFrame, detail_df: pd.DataFrame, summary_df: pd.DataFrame, failure_df: pd.DataFrame, output_tsv_dir: Path, output_xlsx_dir: Path) -> None:
    safe_mkdir(output_tsv_dir)
    safe_mkdir(output_xlsx_dir)

    binary_tsv = output_tsv_dir / "epssmash_presence_absence_binary.tsv"
    detail_tsv = output_tsv_dir / "epssmash_product_detail.tsv"
    summary_tsv = output_tsv_dir / "epssmash_summary_by_genome.tsv"
    failures_tsv = output_tsv_dir / "epssmash_failures.tsv"
    workbook = output_xlsx_dir / "epssmash_results.xlsx"

    binary_df.to_csv(binary_tsv, sep="\t", index=False)
    detail_df.to_csv(detail_tsv, sep="\t", index=False)
    summary_df.to_csv(summary_tsv, sep="\t", index=False)
    failure_df.to_csv(failures_tsv, sep="\t", index=False)

    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        binary_df.to_excel(writer, sheet_name="epssmash_binary", index=False)
        detail_df.to_excel(writer, sheet_name="epssmash_detail", index=False)
        summary_df.to_excel(writer, sheet_name="epssmash_summary", index=False)
        failure_df.to_excel(writer, sheet_name="epssmash_failures", index=False)

    print("epsSMASH FULL module completed.", flush=True)
    print(f"Binary TSV   : {binary_tsv}", flush=True)
    print(f"Detail TSV   : {detail_tsv}", flush=True)
    print(f"Summary TSV  : {summary_tsv}", flush=True)
    print(f"Failures TSV : {failures_tsv}", flush=True)
    print(f"Workbook XLSX: {workbook}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run epsSMASH FULL module and produce a binary EPS product matrix.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--json-dir", required=True)
    parser.add_argument("--output-tsv-dir", required=True)
    parser.add_argument("--output-xlsx-dir", required=True)
    parser.add_argument("--epssmash-exec", required=True)
    parser.add_argument("--db-dir", required=True)
    parser.add_argument("--parser-script", required=True)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()

    manifest = Path(args.manifest).resolve()
    raw_root = Path(args.raw_root).resolve()
    json_dir = Path(args.json_dir).resolve()
    output_tsv_dir = Path(args.output_tsv_dir).resolve()
    output_xlsx_dir = Path(args.output_xlsx_dir).resolve()
    epssmash_exec = Path(args.epssmash_exec).resolve()
    db_dir = Path(args.db_dir).resolve()
    parser_script = Path(args.parser_script).resolve()
    threads = max(1, min(args.threads, 2))

    safe_mkdir(raw_root)
    safe_mkdir(json_dir)
    safe_mkdir(output_tsv_dir)
    safe_mkdir(output_xlsx_dir)

    if not manifest.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest}")
    if not epssmash_exec.is_file():
        raise FileNotFoundError(f"epsSMASH executable not found: {epssmash_exec}")
    if not db_dir.is_dir():
        raise FileNotFoundError(f"epsSMASH database directory not found: {db_dir}")
    if not parser_script.is_file():
        raise FileNotFoundError(f"epsSMASH parser script not found: {parser_script}")

    manifest_df = load_manifest(manifest)
    all_genomes = manifest_df["genome_id"].astype(str).tolist()
    valid_df, failure_rows = split_valid_inputs(manifest_df)

    real_failures = 0

    if json_dir.exists():
        shutil.rmtree(json_dir)
    safe_mkdir(json_dir)

    if valid_df.empty:
        failure_df = pd.DataFrame(failure_rows, columns=FAIL_COLUMNS)
        write_outputs(
            pd.DataFrame({"genome_id": all_genomes}),
            pd.DataFrame(columns=DETAIL_COLUMNS),
            pd.DataFrame({"genome_id": all_genomes, "n_detected_products": 0, "detected_products": ""}),
            failure_df,
            output_tsv_dir,
            output_xlsx_dir,
        )
        return

    for _, row in valid_df.iterrows():
        genome_id = safe_text(row["genome_id"])
        input_fna = Path(row["input_fna"]).resolve()
        run_dir = raw_root / genome_id

        if run_dir.exists():
            shutil.rmtree(run_dir)
        safe_mkdir(run_dir)

        cmd = [
            str(epssmash_exec),
            "--databases", str(db_dir),
            "--taxon", "bacteria",
            "--cpus", str(threads),
            "--genefinding-tool", "prodigal",
            "--output-dir", str(run_dir),
            str(input_fna),
        ]
        completed = run_command(cmd)

        if completed.returncode != 0:
            message_parts = []
            if completed.stdout.strip():
                message_parts.append(f"STDOUT:\n{completed.stdout.strip()}")
            if completed.stderr.strip():
                message_parts.append(f"STDERR:\n{completed.stderr.strip()}")
            failure_rows.append(
                {
                    "genome_id": genome_id,
                    "input_fna": str(input_fna),
                    "status": "FAILED",
                    "message": "\n\n".join(message_parts) if message_parts else "epsSMASH execution failed",
                }
            )
            real_failures += 1
            continue

        try:
            json_file = find_single_json_file(run_dir)
            shutil.copy2(json_file, json_dir / f"{genome_id}.json")
        except Exception as exc:
            failure_rows.append(
                {
                    "genome_id": genome_id,
                    "input_fna": str(input_fna),
                    "status": "FAILED",
                    "message": f"JSON collection failed: {exc}",
                }
            )
            real_failures += 1

    parser_tmp_dir = raw_root / "parser_tmp"
    if parser_tmp_dir.exists():
        shutil.rmtree(parser_tmp_dir)
    safe_mkdir(parser_tmp_dir)

    if any(json_dir.glob("*.json")):
        parser_cmd = [sys.executable, str(parser_script), "--input-dir", str(json_dir), "--output-dir", str(parser_tmp_dir)]
        completed = run_command(parser_cmd)
        if completed.returncode != 0:
            message_parts = []
            if completed.stdout.strip():
                message_parts.append(f"STDOUT:\n{completed.stdout.strip()}")
            if completed.stderr.strip():
                message_parts.append(f"STDERR:\n{completed.stderr.strip()}")
            raise RuntimeError("\n\n".join(message_parts) if message_parts else "epsSMASH parser failed")

    binary_df = load_binary_table(parser_tmp_dir / "epssmash_presence_absence_binary.tsv", all_genomes)
    detail_df = load_detail_table(parser_tmp_dir / "epssmash_detected_products_long.tsv")
    summary_df = load_summary_table(parser_tmp_dir / "epssmash_parser_summary.tsv", all_genomes)
    failure_df = pd.DataFrame(failure_rows, columns=FAIL_COLUMNS)

    write_outputs(binary_df, detail_df, summary_df, failure_df, output_tsv_dir, output_xlsx_dir)

    if real_failures > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        sys.exit(1)

