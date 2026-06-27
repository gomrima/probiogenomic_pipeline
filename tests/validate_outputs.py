#!/usr/bin/env python3

import argparse
import math
from pathlib import Path

import pandas as pd


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".tsv":
        return pd.read_csv(path, sep="\t", dtype=str).fillna("")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str).fillna("")
    raise ValueError(f"Unsupported table file: {path}")


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    cols = list(df.columns)
    if "genome_id" in cols:
        df = df.sort_values(["genome_id"] + [c for c in cols if c != "genome_id"]).reset_index(drop=True)
    else:
        df = df.sort_values(cols).reset_index(drop=True)
    return df[cols].astype(str).fillna("")


def compare_tsv(legacy: Path, final: Path) -> tuple[bool, str]:
    ldf = normalize(read_table(legacy))
    fdf = normalize(read_table(final))
    if list(ldf.columns) != list(fdf.columns):
        return False, "column mismatch"
    if ldf.shape != fdf.shape:
        return False, f"shape mismatch {ldf.shape} != {fdf.shape}"
    if not ldf.equals(fdf):
        return False, "value mismatch"
    return True, "identical"


def compare_xlsx(legacy: Path, final: Path) -> tuple[bool, str]:
    legacy_book = pd.read_excel(legacy, sheet_name=None, dtype=str)
    final_book = pd.read_excel(final, sheet_name=None, dtype=str)
    if set(legacy_book) != set(final_book):
        return False, "worksheet mismatch"
    for sheet in sorted(legacy_book):
        ldf = normalize(legacy_book[sheet].fillna(""))
        fdf = normalize(final_book[sheet].fillna(""))
        if list(ldf.columns) != list(fdf.columns):
            return False, f"column mismatch in {sheet}"
        if ldf.shape != fdf.shape:
            return False, f"shape mismatch in {sheet}"
        if not ldf.equals(fdf):
            return False, f"value mismatch in {sheet}"
    return True, "identical"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare legacy and final pipeline outputs.")
    parser.add_argument("--legacy_results", required=True)
    parser.add_argument("--final_results", required=True)
    parser.add_argument("--output_report", required=True)
    parser.add_argument("--allow_path_differences", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    legacy_root = Path(args.legacy_results).resolve()
    final_root = Path(args.final_results).resolve()
    report = Path(args.output_report).resolve()
    rows = ["relative_path\tstatus\tnotes"]
    failures = 0

    for legacy in sorted(legacy_root.rglob("*")):
        if not legacy.is_file() or legacy.suffix.lower() not in {".tsv", ".xlsx"}:
            continue
        rel = legacy.relative_to(legacy_root)
        final = final_root / rel
        if not final.is_file():
            rows.append(f"{rel.as_posix()}\tFAIL\tmissing final file")
            failures += 1
            continue
        try:
            if legacy.suffix.lower() == ".xlsx":
                ok, note = compare_xlsx(legacy, final)
            else:
                ok, note = compare_tsv(legacy, final)
        except Exception as exc:
            ok, note = False, str(exc)
        rows.append(f"{rel.as_posix()}\t{'PASS' if ok else 'FAIL'}\t{note}")
        if not ok:
            failures += 1

    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

