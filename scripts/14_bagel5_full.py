#!/usr/bin/env python3

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd


FAIL_COLUMNS = ["genome_id", "input_fna", "status", "message"]


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def safe_name(name: str) -> str:
    name = safe_text(name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


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


def stage_inputs(valid_df: pd.DataFrame, staged_input_dir: Path) -> pd.DataFrame:
    if staged_input_dir.exists():
        shutil.rmtree(staged_input_dir)
    safe_mkdir(staged_input_dir)

    records = []
    seen = set()

    for _, row in valid_df.iterrows():
        genome_id = safe_text(row["genome_id"])
        input_fna = Path(row["input_fna"]).resolve()

        staged_name = safe_name(genome_id) or "genome"
        staged_name = f"{staged_name}.fna"

        base = staged_name
        counter = 2
        while staged_name in seen:
            stem = Path(base).stem
            suffix = Path(base).suffix
            staged_name = f"{stem}_{counter}{suffix}"
            counter += 1

        seen.add(staged_name)
        dst = staged_input_dir / staged_name
        shutil.copy2(input_fna, dst)

        records.append(
            {
                "genome_id": genome_id,
                "input_fna": str(input_fna),
                "staged_name": staged_name,
                "staged_path": str(dst),
            }
        )

    return pd.DataFrame(records)


def read_parser_matrix(parser_tsv: Path) -> pd.DataFrame:
    if not parser_tsv.is_file():
        return pd.DataFrame()

    df = pd.read_csv(parser_tsv, sep="\t")
    if df.empty:
        return pd.DataFrame()

    first_col = df.columns[0]
    df = df.rename(columns={first_col: "staged_name"})
    return df


def parser_df_to_feature_map(
    parser_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
) -> dict[str, set[str]]:
    feature_map: dict[str, set[str]] = {}

    if parser_df.empty:
        return feature_map

    name_map = dict(zip(mapping_df["staged_name"], mapping_df["genome_id"]))
    basename_map = {
        Path(staged_name).name: genome_id
        for staged_name, genome_id in zip(mapping_df["staged_name"], mapping_df["genome_id"])
    }
    stem_map = {
        Path(staged_name).stem: genome_id
        for staged_name, genome_id in zip(mapping_df["staged_name"], mapping_df["genome_id"])
    }

    feature_cols = [c for c in parser_df.columns if c != "staged_name"]

    for _, row in parser_df.iterrows():
        staged_name = safe_text(row["staged_name"])
        genome_id = name_map.get(staged_name, "")
        if not genome_id:
            genome_id = basename_map.get(Path(staged_name).name, "")
        if not genome_id:
            genome_id = stem_map.get(Path(staged_name).stem, "")
        if not genome_id:
            continue

        if genome_id not in feature_map:
            feature_map[genome_id] = set()

        for col in feature_cols:
            value = pd.to_numeric(pd.Series([row[col]]), errors="coerce").fillna(0).astype(int).iloc[0]
            if value == 1:
                feature_map[genome_id].add(col)

    return feature_map


def merge_feature_maps(feature_maps: list[dict[str, set[str]]]) -> dict[str, set[str]]:
    merged: dict[str, set[str]] = {}

    for fmap in feature_maps:
        for genome_id, features in fmap.items():
            if genome_id not in merged:
                merged[genome_id] = set()
            merged[genome_id].update(features)

    return merged


def feature_map_to_binary_df(
    feature_map: dict[str, set[str]],
    all_genomes: list[str],
) -> pd.DataFrame:
    all_features = sorted({feature for features in feature_map.values() for feature in features})

    if not all_features:
        return pd.DataFrame({"genome_id": all_genomes})

    rows = []
    for genome_id in all_genomes:
        present = feature_map.get(genome_id, set())
        row = {"genome_id": genome_id}
        for feature in all_features:
            row[feature] = 1 if feature in present else 0
        rows.append(row)

    df = pd.DataFrame(rows)
    for col in df.columns:
        if col != "genome_id":
            df[col] = pd.to_numeric(df[col], errors="raise").astype(int)
    return df


def build_summary(binary_df: pd.DataFrame, manifest_df: pd.DataFrame) -> pd.DataFrame:
    feature_cols = [c for c in binary_df.columns if c != "genome_id"]

    rows = []
    for _, row in manifest_df.iterrows():
        genome_id = safe_text(row["genome_id"])
        input_fna = safe_text(row.get("normalized_fna", ""))

        sub = binary_df.loc[binary_df["genome_id"] == genome_id]
        if sub.empty:
            n_bagel5_bacteriocins = 0
        else:
            n_bagel5_bacteriocins = int(sub[feature_cols].sum(axis=1).iloc[0]) if feature_cols else 0

        rows.append(
            {
                "genome_id": genome_id,
                "input_fna": input_fna,
                "n_bagel5_bacteriocins": n_bagel5_bacteriocins,
                "bagel5_any_hit": 1 if n_bagel5_bacteriocins > 0 else 0,
            }
        )

    return pd.DataFrame(rows)


def write_outputs(
    binary_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    failure_df: pd.DataFrame,
    output_tsv_dir: Path,
    output_xlsx_dir: Path,
) -> None:
    safe_mkdir(output_tsv_dir)
    safe_mkdir(output_xlsx_dir)

    binary_tsv = output_tsv_dir / "bagel5_bacteriocin_binary.tsv"
    summary_tsv = output_tsv_dir / "bagel5_summary_by_genome.tsv"
    failures_tsv = output_tsv_dir / "bagel5_failures.tsv"
    workbook = output_xlsx_dir / "bagel5_results.xlsx"

    binary_df.to_csv(binary_tsv, sep="\t", index=False)
    summary_df.to_csv(summary_tsv, sep="\t", index=False)
    failure_df.to_csv(failures_tsv, sep="\t", index=False)

    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        binary_df.to_excel(writer, sheet_name="bagel5_binary", index=False)
        summary_df.to_excel(writer, sheet_name="bagel5_summary", index=False)
        failure_df.to_excel(writer, sheet_name="bagel5_failures", index=False)

    print("BAGEL5 FULL module completed.", flush=True)
    print(f"Binary TSV   : {binary_tsv}", flush=True)
    print(f"Summary TSV  : {summary_tsv}", flush=True)
    print(f"Failures TSV : {failures_tsv}", flush=True)
    print(f"Workbook XLSX: {workbook}", flush=True)


def try_parse_session(
    parser_script: Path,
    session_dir: Path,
    staged_dir: Path,
    parser_tmp_dir: Path,
    mapping_df: pd.DataFrame,
) -> tuple[bool, dict[str, set[str]], str]:
    if parser_tmp_dir.exists():
        shutil.rmtree(parser_tmp_dir)
    safe_mkdir(parser_tmp_dir)

    parser_cmd = [
        sys.executable,
        str(parser_script),
        str(session_dir),
        str(staged_dir),
        str(parser_tmp_dir),
    ]
    completed = run_command(parser_cmd)
    if completed.returncode != 0:
        message_parts = []
        if completed.stdout.strip():
            message_parts.append(f"STDOUT:\n{completed.stdout.strip()}")
        if completed.stderr.strip():
            message_parts.append(f"STDERR:\n{completed.stderr.strip()}")
        return False, {}, "\n\n".join(message_parts) if message_parts else "BAGEL5 parser failed"

    parser_tsv = parser_tmp_dir / "bagel5_bacteriocin_matrix.tsv"
    if not parser_tsv.is_file():
        return True, {}, ""

    parser_df = read_parser_matrix(parser_tsv)
    if parser_df.empty:
        return True, {}, ""

    return True, parser_df_to_feature_map(parser_df, mapping_df), ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run BAGEL5 FULL module with per-genome resume logic and produce a binary bacteriocin matrix."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--staged-input-dir", required=True)
    parser.add_argument("--output-tsv-dir", required=True)
    parser.add_argument("--output-xlsx-dir", required=True)
    parser.add_argument("--bagel5-env", required=True)
    parser.add_argument("--bagel5-script", required=True)
    parser.add_argument("--parser-script", required=True)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--session", default="bagel5_full_module")
    args = parser.parse_args()

    manifest = Path(args.manifest).resolve()
    raw_root = Path(args.raw_root).resolve()
    staged_input_dir = Path(args.staged_input_dir).resolve()
    output_tsv_dir = Path(args.output_tsv_dir).resolve()
    output_xlsx_dir = Path(args.output_xlsx_dir).resolve()
    bagel5_env = Path(args.bagel5_env).resolve()
    bagel5_script = Path(args.bagel5_script).resolve()
    parser_script = Path(args.parser_script).resolve()
    threads = max(1, min(args.threads, 2))

    safe_mkdir(raw_root)
    safe_mkdir(staged_input_dir)
    safe_mkdir(output_tsv_dir)
    safe_mkdir(output_xlsx_dir)

    if not manifest.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest}")
    if not bagel5_env.is_dir():
        raise FileNotFoundError(f"BAGEL5 environment not found: {bagel5_env}")
    if not bagel5_script.is_file():
        raise FileNotFoundError(f"BAGEL5 script not found: {bagel5_script}")
    if not parser_script.is_file():
        raise FileNotFoundError(f"BAGEL5 parser script not found: {parser_script}")

    manifest_df = load_manifest(manifest)
    all_genomes = manifest_df["genome_id"].astype(str).tolist()
    valid_df, failure_rows = split_valid_inputs(manifest_df)
    failure_df = pd.DataFrame(failure_rows, columns=FAIL_COLUMNS)

    if valid_df.empty:
        binary_df = pd.DataFrame({"genome_id": all_genomes})
        summary_df = build_summary(binary_df, manifest_df)
        write_outputs(binary_df, summary_df, failure_df, output_tsv_dir, output_xlsx_dir)
        return

    mapping_df = stage_inputs(valid_df, staged_input_dir)

    feature_maps: list[dict[str, set[str]]] = []
    completed_genomes: set[str] = set()

    single_stage_root = raw_root / "_resume_single_genome_inputs"
    parser_root = raw_root / "_resume_parser_tmp"
    safe_mkdir(single_stage_root)
    safe_mkdir(parser_root)

    for _, row in mapping_df.iterrows():
        genome_id = safe_text(row["genome_id"])
        input_fna = safe_text(row["input_fna"])
        staged_name = safe_text(row["staged_name"])
        staged_path = Path(safe_text(row["staged_path"])).resolve()

        genome_token = safe_name(genome_id) or "genome"
        session_name = f"{args.session}__{genome_token}"
        session_dir = raw_root / session_name

        one_stage_dir = single_stage_root / genome_token
        if one_stage_dir.exists():
            shutil.rmtree(one_stage_dir)
        safe_mkdir(one_stage_dir)

        one_stage_path = one_stage_dir / staged_name
        shutil.copy2(staged_path, one_stage_path)

        if session_dir.is_dir():
            print(f"[INFO] Existing per-genome BAGEL5 session found for {genome_id}: {session_dir}", flush=True)
        else:
            print(f"[INFO] Running BAGEL5 for genome: {genome_id}", flush=True)
            bagel5_cmd = [
                "conda", "run",
                "-p", str(bagel5_env),
                "python", str(bagel5_script),
                "-query", str(one_stage_dir),
                "-outdir", str(raw_root),
                "-session", session_name,
                "-mode", "A",
                "-cpu", str(threads),
            ]
            completed = run_command(bagel5_cmd)
            if completed.returncode != 0:
                message_parts = []
                if completed.stdout.strip():
                    message_parts.append(f"STDOUT:\n{completed.stdout.strip()}")
                if completed.stderr.strip():
                    message_parts.append(f"STDERR:\n{completed.stderr.strip()}")

                failure_df = pd.concat(
                    [
                        failure_df,
                        pd.DataFrame(
                            [
                                {
                                    "genome_id": genome_id,
                                    "input_fna": input_fna,
                                    "status": "FAILED",
                                    "message": "\n\n".join(message_parts) if message_parts else "BAGEL5 execution failed",
                                }
                            ],
                            columns=FAIL_COLUMNS,
                        ),
                    ],
                    ignore_index=True,
                )
                print(f"[WARNING] BAGEL5 failed for genome: {genome_id}", flush=True)
                continue

        parser_tmp_dir = parser_root / genome_token
        ok, feature_map, message = try_parse_session(
            parser_script=parser_script,
            session_dir=session_dir,
            staged_dir=one_stage_dir,
            parser_tmp_dir=parser_tmp_dir,
            mapping_df=mapping_df,
        )

        if not ok:
            failure_df = pd.concat(
                [
                    failure_df,
                    pd.DataFrame(
                        [
                            {
                                "genome_id": genome_id,
                                "input_fna": input_fna,
                                "status": "FAILED",
                                "message": message,
                            }
                        ],
                        columns=FAIL_COLUMNS,
                    ),
                ],
                ignore_index=True,
            )
            print(f"[WARNING] BAGEL5 parser failed for genome: {genome_id}", flush=True)
            continue

        feature_maps.append(feature_map)
        completed_genomes.add(genome_id)

    merged_feature_map = merge_feature_maps(feature_maps)
    binary_df = feature_map_to_binary_df(merged_feature_map, all_genomes)
    summary_df = build_summary(binary_df, manifest_df)

    failure_df = failure_df.fillna("")
    write_outputs(binary_df, summary_df, failure_df, output_tsv_dir, output_xlsx_dir)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        sys.exit(1)

