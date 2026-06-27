#!/usr/bin/env python3
"""
Module 06 ISEScan mobilome - resume-aware, memory-safe, stale-directory-safe,
atomic-output, progress-visible version (aligned with the corrected
07_isescan_mobilome_resume.py reference, 2026-05-30).

What this version guarantees
----------------------------
1. Reuse an existing per-genome ISEScan CSV only if it exists, has the expected
   header and is parseable in streaming mode.
2. If the final CSV is missing or invalid, clean ONLY that genome's ISEScan raw
   directory before rerunning ISEScan, so ISEScan cannot reuse stale partial
   intermediate files left by a power failure or an interrupted run.
3. Stream module TSV outputs to TEMPORARY files and move them into their final
   names ATOMICALLY only after a full pass completes. Downstream modules
   (09 mobile-safety co-occurrence and 17 final consolidation) therefore never
   read a half-written consolidated TSV.
4. Print a per-genome heartbeat while ISEScan runs, so a long-but-healthy genome
   (for example an IS-rich genome) no longer looks like a frozen terminal.
5. Terminate the whole ISEScan process group on timeout, SIGTERM or Ctrl-C, so
   no orphan ISEScan/FragGeneScan/hmmer process keeps burning CPU after the user
   stops the run.
6. Treat a genome where ISEScan exits 0 but produces no CSV as a legitimate
   zero-IS genome (recorded explicitly), instead of a false failure.
7. Exit code: 0 if every genome produced a valid result, 3 if the full pass
   completed but some genomes failed or timed out. This lets the launcher decide
   whether to write the module checkpoint.

Outputs (names and columns kept identical for downstream compatibility):
  - isescan_hits_detail.tsv        (read by module 09: genome_id, seqID, isBegin, isEnd, ...)
  - isescan_family_binary.tsv      (read by module 17: genome_id + 0/1 family columns)
  - isescan_summary_by_genome.tsv
  - isescan_failures.tsv
  - isescan_resume_report.tsv
  - isescan_results.xlsx           (optional, built last, never blocks the TSVs)
  - isescan_resume_plan.tsv        (only in --plan-only mode)
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    from openpyxl import Workbook
except Exception:  # pragma: no cover
    Workbook = None


# ---------------------------------------------------------------------------
# Output schemas (DO NOT change column names: downstream modules depend on them)
# ---------------------------------------------------------------------------

DETAIL_COLUMNS = [
    "genome_id",
    "input_fna",
    "result_csv",
    "seqID",
    "family",
    "cluster",
    "isBegin",
    "isEnd",
    "isLen",
    "ncopy4is",
    "start1",
    "end1",
    "start2",
    "end2",
    "score",
    "irId",
    "irLen",
    "nGaps",
    "orfBegin",
    "orfEnd",
    "strand",
    "orfLen",
    "E-value",
    "E-value4copy",
    "type",
    "ov",
    "tir",
]

ISESCAN_REQUIRED_COLUMNS = [
    "seqID", "family", "cluster", "isBegin", "isEnd", "isLen", "ncopy4is",
    "start1", "end1", "start2", "end2", "score", "irId", "irLen", "nGaps",
    "orfBegin", "orfEnd", "strand", "orfLen", "E-value", "E-value4copy",
    "type", "ov", "tir",
]

SUMMARY_COLUMNS = [
    "genome_id",
    "input_fna",
    "n_total_hits",
    "n_complete_hits",
    "n_partial_hits",
    "n_unique_families",
    "n_unique_clusters",
    "n_contigs_with_hits",
]

FAIL_COLUMNS = [
    "genome_id",
    "input_fna",
    "status",
    "message",
]

RESUME_COLUMNS = [
    "genome_id",
    "input_fna",
    "run_dir",
    "expected_csv",
    "action",
    "status",
    "message",
    "n_total_hits",
    "elapsed_seconds",
]

PLAN_COLUMNS = [
    "genome_id",
    "input_fna",
    "run_dir",
    "expected_csv",
    "decision",
    "reason",
]

EXCEL_MAX_ROWS = 1_048_576

# Name of the completion sentinel this script writes inside a per-genome run dir
# after a successful ISEScan run. It lets us safely reuse a genome that ISEScan
# completed with zero IS (and therefore no CSV) on a later resume.
SENTINEL_NAME = ".isescan_ok"

# Module-level reference to the currently running ISEScan subprocess, used by the
# signal handlers to terminate the whole process group on SIGTERM / Ctrl-C.
_CURRENT_PROC: Optional[subprocess.Popen] = None


# ---------------------------------------------------------------------------
# Small filesystem / string helpers
# ---------------------------------------------------------------------------

def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sanitize_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(name))


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def fsync_file(handle) -> None:
    try:
        handle.flush()
        os.fsync(handle.fileno())
    except Exception:
        pass


def fsync_path(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except Exception:
        pass


def fsync_dir(path: Path) -> None:
    fsync_path(path)


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------

def load_manifest_records(manifest_path: Path) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        required = {"genome_id", "normalized_fna", "status"}
        missing = sorted(required.difference(fieldnames))
        if missing:
            raise ValueError(
                f"Missing required manifest columns: {missing}. "
                f"Found columns: {fieldnames}"
            )
        for row in reader:
            if (row.get("status") or "") != "OK":
                continue
            genome_id = (row.get("genome_id") or "").strip()
            fna = (row.get("normalized_fna") or "").strip()
            if not genome_id or not fna:
                continue
            if not Path(fna).is_file():
                continue
            records.append({"genome_id": genome_id, "normalized_fna": fna})
    return records


# ---------------------------------------------------------------------------
# ISEScan output path resolution and validation
# ---------------------------------------------------------------------------

def expected_isescan_csv(run_dir: Path, input_fna: Path) -> Path:
    # ISEScan writes: <run_dir>/<input_parent_folder_name>/<input_basename>.csv
    # Example: run_dir/normalized_fna/GCF_xxx.fna.csv
    # This mirrors the layout produced by the previous successful runs and is
    # kept unchanged on purpose. locate_isescan_csv() adds a safety fallback.
    return run_dir / input_fna.parent.name / f"{input_fna.name}.csv"


def locate_isescan_csv(run_dir: Path, input_fna: Path) -> Optional[Path]:
    """Return the per-genome ISEScan CSV path if it exists.

    Primary location is expected_isescan_csv(). If that exact path is absent,
    fall back to a bounded search under run_dir for <basename>.csv. This makes
    reuse resilient to minor ISEScan output-path differences without changing
    the primary assumption.
    """
    primary = expected_isescan_csv(run_dir, input_fna)
    if primary.is_file():
        return primary
    if not run_dir.exists():
        return None
    matches = sorted(run_dir.rglob(f"{input_fna.name}.csv"))
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    for candidate in matches:
        if candidate.parent.name == input_fna.parent.name:
            return candidate
    return matches[0]


def isescan_produced_output(run_dir: Path, input_fna: Path) -> bool:
    """True if the run dir contains any recognized ISEScan product for this input.

    Used after a successful (exit 0) run with no CSV to distinguish a real
    zero-IS genome (ISEScan ran and emitted its other artifacts) from a broken
    run (empty directory).
    """
    if not run_dir.exists():
        return False
    pred_dir = run_dir / input_fna.parent.name
    if pred_dir.exists():
        for _ in pred_dir.glob(f"{input_fna.name}.*"):
            return True
    for pattern in ("*.csv", "*.gff", "*.sum", "*.tsv", "*.out", "*.is.fna"):
        for _ in run_dir.rglob(pattern):
            return True
    return False


def read_csv_header(csv_path: Path) -> List[str]:
    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration:
            return []


def validate_isescan_csv_header(csv_path: Path, min_csv_size: int) -> Tuple[bool, str]:
    if not csv_path.is_file():
        return False, "CSV missing"
    size = csv_path.stat().st_size
    if size < min_csv_size:
        return False, f"CSV size below minimum threshold ({size} < {min_csv_size})"
    header = read_csv_header(csv_path)
    missing = [col for col in ISESCAN_REQUIRED_COLUMNS if col not in header]
    if missing:
        return False, f"CSV header missing expected columns: {missing}"
    return True, "CSV header valid"


# ---------------------------------------------------------------------------
# Completion sentinel
# ---------------------------------------------------------------------------

def sentinel_path(run_dir: Path) -> Path:
    return run_dir / SENTINEL_NAME


def write_sentinel(run_dir: Path, genome_id: str) -> None:
    try:
        sentinel_path(run_dir).write_text(
            f"{genome_id}\t{now_stamp()}\n", encoding="utf-8"
        )
    except Exception:
        pass


def has_sentinel(run_dir: Path) -> bool:
    return sentinel_path(run_dir).is_file()


# ---------------------------------------------------------------------------
# CSV parsing (streaming) and per-genome summary
# ---------------------------------------------------------------------------

def normalize_row_value(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def zero_summary(genome_id: str, input_fna: Path) -> Dict[str, str]:
    return {
        "genome_id": genome_id,
        "input_fna": str(input_fna),
        "n_total_hits": "0",
        "n_complete_hits": "0",
        "n_partial_hits": "0",
        "n_unique_families": "0",
        "n_unique_clusters": "0",
        "n_contigs_with_hits": "0",
    }


def parse_isescan_csv_stream(
    csv_path: Path,
    genome_id: str,
    input_fna: Path,
    detail_writer: csv.DictWriter,
) -> Tuple[Dict[str, str], Set[str]]:
    """Parse one ISEScan CSV once, write detail rows, return summary and family set."""
    total = 0
    complete = 0
    partial = 0
    families: Set[str] = set()
    clusters: Set[str] = set()
    contigs: Set[str] = set()

    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [col for col in ISESCAN_REQUIRED_COLUMNS if col not in fieldnames]
        if missing:
            raise ValueError(f"CSV missing expected columns: {missing}")

        for raw in reader:
            total += 1
            family = normalize_row_value(raw.get("family"))
            cluster = normalize_row_value(raw.get("cluster"))
            seqid = normalize_row_value(raw.get("seqID"))
            hit_type = normalize_row_value(raw.get("type"))

            if family:
                families.add(family)
            if cluster:
                clusters.add(cluster)
            if seqid:
                contigs.add(seqid)
            if hit_type == "c":
                complete += 1
            elif hit_type == "p":
                partial += 1

            out = {
                "genome_id": genome_id,
                "input_fna": str(input_fna),
                "result_csv": str(csv_path),
            }
            for col in ISESCAN_REQUIRED_COLUMNS:
                out[col] = normalize_row_value(raw.get(col))
            detail_writer.writerow({col: out.get(col, "") for col in DETAIL_COLUMNS})

    summary = {
        "genome_id": genome_id,
        "input_fna": str(input_fna),
        "n_total_hits": str(total),
        "n_complete_hits": str(complete),
        "n_partial_hits": str(partial),
        "n_unique_families": str(len(families)),
        "n_unique_clusters": str(len(clusters)),
        "n_contigs_with_hits": str(len(contigs)),
    }
    return summary, families


# ---------------------------------------------------------------------------
# Stale directory handling
# ---------------------------------------------------------------------------

def backup_or_remove_run_dir(run_dir: Path, keep_backup: bool) -> Optional[Path]:
    if not run_dir.exists():
        return None
    if keep_backup:
        backup_dir = run_dir.with_name(f"{run_dir.name}.stale_before_resume_{now_stamp()}")
        suffix = 1
        final_backup = backup_dir
        while final_backup.exists():
            final_backup = run_dir.with_name(f"{backup_dir.name}_{suffix}")
            suffix += 1
        run_dir.rename(final_backup)
        return final_backup
    shutil.rmtree(run_dir)
    return None


# ---------------------------------------------------------------------------
# ISEScan execution with heartbeat, timeout and clean process-group teardown
# ---------------------------------------------------------------------------

def terminate_process_tree(proc: subprocess.Popen) -> None:
    try:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=20)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def run_isescan(
    input_fna: Path,
    run_dir: Path,
    threads: int,
    timeout_seconds: int,
    heartbeat_seconds: int,
    genome_id: str,
) -> Tuple[bool, str, float]:
    global _CURRENT_PROC

    cmd = [
        "isescan.py",
        "--seqfile", str(input_fna),
        "--output", str(run_dir),
        "--nthread", str(threads),
    ]
    print(f"[{genome_id}] Running: {' '.join(cmd)}", flush=True)
    start = time.monotonic()
    deadline = (start + timeout_seconds) if timeout_seconds > 0 else None
    heartbeat = max(0, int(heartbeat_seconds))

    try:
        # start_new_session=True puts ISEScan and all its children (FragGeneScan,
        # hmmer, blast) in their own process group so we can kill them together.
        # stdout/stderr are inherited so ISEScan output streams straight to the
        # terminal and the log (no in-memory capture).
        proc = subprocess.Popen(
            cmd,
            stdout=None,
            stderr=None,
            text=True,
            start_new_session=True,
        )
        _CURRENT_PROC = proc

        while True:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    terminate_process_tree(proc)
                    elapsed = time.monotonic() - start
                    return False, f"ISEScan timeout after {int(elapsed)} seconds", elapsed
                wait_for = min(heartbeat, remaining) if heartbeat > 0 else remaining
            elif heartbeat > 0:
                wait_for = heartbeat
            else:
                wait_for = None

            try:
                return_code = proc.wait(timeout=wait_for)
                break
            except subprocess.TimeoutExpired:
                elapsed = time.monotonic() - start
                if deadline is not None and time.monotonic() >= deadline:
                    terminate_process_tree(proc)
                    return False, f"ISEScan timeout after {int(elapsed)} seconds", elapsed
                if heartbeat > 0:
                    print(
                        f"[{genome_id}] ISEScan still running, elapsed {int(elapsed)} s "
                        f"(threads={threads}); waiting...",
                        flush=True,
                    )
            except KeyboardInterrupt:
                terminate_process_tree(proc)
                raise

        elapsed = time.monotonic() - start
        if return_code != 0:
            return False, f"ISEScan exited with non-zero return code: {return_code}", elapsed
        return True, "ISEScan completed", elapsed

    except FileNotFoundError:
        elapsed = time.monotonic() - start
        return False, "isescan.py not found in PATH of the active conda environment", elapsed
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        elapsed = time.monotonic() - start
        return False, f"ISEScan execution error: {exc}", elapsed
    finally:
        _CURRENT_PROC = None


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_tsv(path: Path, columns: Sequence[str], records: Iterable[Dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({col: record.get(col, "") for col in columns})
        fsync_file(handle)


def write_binary_matrix(path: Path, genome_ids: List[str], family_by_genome: Dict[str, Set[str]]) -> List[str]:
    all_families = sorted({fam for fams in family_by_genome.values() for fam in fams if fam})
    columns = ["genome_id"] + all_families
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(columns)
        for genome_id in genome_ids:
            fams = family_by_genome.get(genome_id, set())
            writer.writerow([genome_id] + [1 if fam in fams else 0 for fam in all_families])
        fsync_file(handle)
    return columns


def add_tsv_sheet(wb, sheet_name: str, tsv_path: Path, max_rows: int = EXCEL_MAX_ROWS) -> bool:
    ws = wb.create_sheet(title=sheet_name[:31])
    truncated = False
    with tsv_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for i, row in enumerate(reader, start=1):
            if i > max_rows:
                truncated = True
                break
            ws.append(row)
    return truncated


def write_xlsx(output_xlsx: Path, detail_tsv: Path, binary_tsv: Path, summary_tsv: Path, failures_tsv: Path, resume_tsv: Path) -> None:
    if Workbook is None:
        print("[WARN] openpyxl is not available. XLSX output skipped.", flush=True)
        return
    wb = Workbook(write_only=True)
    any_truncated = False
    any_truncated |= add_tsv_sheet(wb, "isescan_hits_detail", detail_tsv)
    any_truncated |= add_tsv_sheet(wb, "isescan_family_binary", binary_tsv)
    any_truncated |= add_tsv_sheet(wb, "isescan_summary", summary_tsv)
    any_truncated |= add_tsv_sheet(wb, "isescan_failures", failures_tsv)
    any_truncated |= add_tsv_sheet(wb, "resume_report", resume_tsv)
    wb.save(output_xlsx)
    if any_truncated:
        print(
            "[WARN] At least one Excel sheet exceeded the row limit and was truncated. "
            "The TSV files remain complete and are the authoritative outputs.",
            flush=True,
        )


# ---------------------------------------------------------------------------
# Genome classification (shared by --plan-only and the real run)
# ---------------------------------------------------------------------------

def classify_genome(
    run_dir: Path,
    input_fna: Path,
    min_csv_size: int,
    force_rerun: bool,
) -> Tuple[bool, str, str, Optional[Path]]:
    """Decide what to do with a genome before running ISEScan.

    Returns (do_run, action, reason, reusable_csv).
    """
    if force_rerun:
        return True, "RUN_ISESCAN_CLEAN_RERUN", "force rerun requested", None

    csv_found = locate_isescan_csv(run_dir, input_fna)
    if csv_found is not None:
        ok, msg = validate_isescan_csv_header(csv_found, min_csv_size)
        if ok:
            return False, "REUSED_EXISTING_CSV", "valid CSV found", csv_found
        return True, "RUN_ISESCAN_CLEAN_RERUN", f"existing CSV invalid: {msg}", None

    if has_sentinel(run_dir) and isescan_produced_output(run_dir, input_fna):
        return False, "REUSED_ZERO_IS_NO_CSV", "completion sentinel present, no CSV (zero IS)", None

    return True, "RUN_ISESCAN_CLEAN_RERUN", "no valid CSV (and no completion sentinel)", None


# ---------------------------------------------------------------------------
# Plan-only pass (no ISEScan, no consolidated outputs)
# ---------------------------------------------------------------------------

def run_plan_only(
    records: List[Dict[str, str]],
    raw_root: Path,
    output_tsv_dir: Path,
    min_csv_size: int,
    force_rerun: bool,
) -> int:
    plan_out = output_tsv_dir / "isescan_resume_plan.tsv"
    plan_records: List[Dict[str, str]] = []
    n_reuse = 0
    n_rerun = 0

    print("[INFO] PLAN-ONLY mode: classifying genomes, no ISEScan will be executed.", flush=True)
    for idx, row in enumerate(records, start=1):
        genome_id = row["genome_id"]
        input_fna = Path(row["normalized_fna"]).resolve()
        run_dir = raw_root / sanitize_name(genome_id)
        do_run, action, reason, csv_found = classify_genome(
            run_dir, input_fna, min_csv_size, force_rerun
        )
        decision = "RERUN" if do_run else "REUSE"
        if do_run:
            n_rerun += 1
        else:
            n_reuse += 1
        expected = csv_found if csv_found is not None else expected_isescan_csv(run_dir, input_fna)
        plan_records.append({
            "genome_id": genome_id,
            "input_fna": str(input_fna),
            "run_dir": str(run_dir),
            "expected_csv": str(expected),
            "decision": decision,
            "reason": reason,
        })
        print(f"[PLAN] [{idx}/{len(records)}] {genome_id}: {decision} ({reason})", flush=True)

    write_tsv(plan_out, PLAN_COLUMNS, sorted(plan_records, key=lambda r: r["genome_id"]))
    print("", flush=True)
    print(f"[PLAN] Total genomes in manifest : {len(records)}", flush=True)
    print(f"[PLAN] Would REUSE (valid)        : {n_reuse}", flush=True)
    print(f"[PLAN] Would RERUN (missing/bad)  : {n_rerun}", flush=True)
    print(f"[PLAN] Plan written to            : {plan_out}", flush=True)
    return 0


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def _signal_handler(signum, frame):  # noqa: ARG001
    proc = _CURRENT_PROC
    print(f"\n[SIGNAL] Received signal {signum}. Terminating running ISEScan if any...", flush=True)
    if proc is not None and proc.poll() is None:
        terminate_process_tree(proc)
    raise KeyboardInterrupt()


def install_signal_handlers() -> None:
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resume-aware, memory-safe, atomic ISEScan module. Reuses valid CSVs and reruns missing/invalid genomes cleanly."
    )
    parser.add_argument("--manifest", required=True, help="Path to input_manifest.tsv")
    parser.add_argument("--raw-root", required=True, help="Root directory for per-genome ISEScan raw outputs")
    parser.add_argument("--output-tsv-dir", required=True, help="Directory for TSV outputs")
    parser.add_argument("--output-xlsx-dir", required=True, help="Directory for XLSX outputs")
    parser.add_argument("--threads", type=int, default=2, help="Threads for ISEScan; capped at 4 (2 recommended on 8 GB RAM)")
    parser.add_argument("--min-csv-size", type=int, default=1, help="Minimum size in bytes for a reusable CSV")
    parser.add_argument("--force-rerun", action="store_true", help="Ignore existing CSVs and rerun every genome")
    parser.add_argument(
        "--keep-stale-backup",
        action="store_true",
        help="Rename stale per-genome run directories instead of deleting them before rerun",
    )
    parser.add_argument(
        "--per-genome-timeout",
        type=int,
        default=7200,
        help="Maximum seconds allowed for one ISEScan genome run; 0 disables timeout",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=int,
        default=120,
        help="Print a liveness message every N seconds while ISEScan runs; 0 disables it",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Classify genomes (reuse vs rerun) and write isescan_resume_plan.tsv without running ISEScan",
    )
    parser.add_argument(
        "--no-xlsx",
        action="store_true",
        help="Skip the optional Excel workbook (TSV files are the pipeline-critical outputs)",
    )
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Kept for compatibility. Per-genome failures are always recorded and the run continues.",
    )
    return parser.parse_args()


def main() -> int:
    install_signal_handlers()
    args = parse_args()

    manifest_path = Path(args.manifest).resolve()
    raw_root = Path(args.raw_root).resolve()
    output_tsv_dir = Path(args.output_tsv_dir).resolve()
    output_xlsx_dir = Path(args.output_xlsx_dir).resolve()
    threads = max(1, min(int(args.threads), 4))
    timeout_seconds = max(0, int(args.per_genome_timeout))
    heartbeat_seconds = max(0, int(args.heartbeat_seconds))
    make_xlsx = not args.no_xlsx

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    safe_mkdir(raw_root)
    safe_mkdir(output_tsv_dir)
    safe_mkdir(output_xlsx_dir)

    records = load_manifest_records(manifest_path)
    total_genomes = len(records)
    print(f"[INFO] Valid genomes in manifest: {total_genomes}", flush=True)
    print(f"[INFO] ISEScan threads: {threads}", flush=True)
    if threads > 2:
        print(
            "[WARN] More than 2 threads on an 8 GB machine can increase ISEScan overhead. "
            "If the run thrashes or stalls, relaunch with ISESCAN_THREADS=2.",
            flush=True,
        )
    print(f"[INFO] Per-genome timeout: {timeout_seconds if timeout_seconds else 'disabled'} seconds", flush=True)
    print(f"[INFO] Heartbeat interval: {heartbeat_seconds if heartbeat_seconds else 'disabled'} seconds", flush=True)
    print(f"[INFO] Excel workbook: {'enabled' if make_xlsx else 'disabled'}", flush=True)

    if args.plan_only:
        return run_plan_only(records, raw_root, output_tsv_dir, args.min_csv_size, args.force_rerun)

    # Final output paths
    detail_out = output_tsv_dir / "isescan_hits_detail.tsv"
    binary_out = output_tsv_dir / "isescan_family_binary.tsv"
    summary_out = output_tsv_dir / "isescan_summary_by_genome.tsv"
    failures_out = output_tsv_dir / "isescan_failures.tsv"
    resume_out = output_tsv_dir / "isescan_resume_report.tsv"
    xlsx_out = output_xlsx_dir / "isescan_results.xlsx"

    # Temporary output paths (atomically moved into place only on full success)
    tmp_tag = f".tmp_{os.getpid()}"
    detail_tmp = detail_out.with_name(detail_out.name + tmp_tag)
    binary_tmp = binary_out.with_name(binary_out.name + tmp_tag)
    summary_tmp = summary_out.with_name(summary_out.name + tmp_tag)
    failures_tmp = failures_out.with_name(failures_out.name + tmp_tag)
    resume_tmp = resume_out.with_name(resume_out.name + tmp_tag)
    xlsx_tmp = xlsx_out.with_name(xlsx_out.name + tmp_tag)
    all_temps = [detail_tmp, binary_tmp, summary_tmp, failures_tmp, resume_tmp, xlsx_tmp]

    genome_ids: List[str] = []
    family_by_genome: Dict[str, Set[str]] = {}
    summary_records: List[Dict[str, str]] = []
    failure_records: List[Dict[str, str]] = []
    resume_records: List[Dict[str, str]] = []

    n_reused = 0
    n_ran = 0
    n_failed = 0

    detail_handle = None
    finalized = False

    try:
        detail_handle = detail_tmp.open("w", encoding="utf-8", newline="")
        detail_writer = csv.DictWriter(detail_handle, fieldnames=DETAIL_COLUMNS, delimiter="\t")
        detail_writer.writeheader()

        for idx, row in enumerate(records, start=1):
            genome_id = row["genome_id"]
            input_fna = Path(row["normalized_fna"]).resolve()
            run_dir = raw_root / sanitize_name(genome_id)
            genome_ids.append(genome_id)
            family_by_genome[genome_id] = set()

            print(f"\n=== [{idx}/{total_genomes}] Processing genome: {genome_id} ===", flush=True)
            print(f"FNA: {input_fna}", flush=True)
            print(f"ISEScan run directory: {run_dir}", flush=True)

            status = "OK"
            elapsed = 0.0
            reusable_csv: Optional[Path] = None

            try:
                do_run, action, reason, reusable_csv = classify_genome(
                    run_dir, input_fna, args.min_csv_size, args.force_rerun
                )
                message = reason
                print(f"[{genome_id}] Decision: {'RERUN' if do_run else 'REUSE'} ({reason})", flush=True)

                if do_run:
                    if run_dir.exists():
                        backup_dir = backup_or_remove_run_dir(run_dir, keep_backup=args.keep_stale_backup)
                        if backup_dir is not None:
                            print(f"[{genome_id}] Stale run directory renamed before rerun: {backup_dir}", flush=True)
                        else:
                            print(f"[{genome_id}] Stale run directory removed before rerun: {run_dir}", flush=True)
                    safe_mkdir(run_dir)

                    ok, run_msg, elapsed = run_isescan(
                        input_fna=input_fna,
                        run_dir=run_dir,
                        threads=threads,
                        timeout_seconds=timeout_seconds,
                        heartbeat_seconds=heartbeat_seconds,
                        genome_id=genome_id,
                    )
                    n_ran += 1
                    if not ok:
                        raise RuntimeError(run_msg)

                    csv_after = locate_isescan_csv(run_dir, input_fna)
                    if csv_after is not None:
                        ok_hdr, hdr_msg = validate_isescan_csv_header(csv_after, args.min_csv_size)
                        if not ok_hdr:
                            raise RuntimeError(f"ISEScan finished but expected CSV is not valid: {hdr_msg}")
                        reusable_csv = csv_after
                        message = run_msg
                        write_sentinel(run_dir, genome_id)
                    elif isescan_produced_output(run_dir, input_fna):
                        reusable_csv = None
                        action = "RAN_ZERO_IS_NO_CSV"
                        message = f"{run_msg}; no CSV produced, interpreted as zero IS"
                        print(f"[{genome_id}] ISEScan completed with no CSV; recorded as zero IS.", flush=True)
                        write_sentinel(run_dir, genome_id)
                    else:
                        raise RuntimeError("ISEScan exited 0 but produced no recognizable output (csv/gff/sum)")

                if reusable_csv is not None:
                    summary, families = parse_isescan_csv_stream(
                        reusable_csv, genome_id, input_fna, detail_writer
                    )
                else:
                    summary = zero_summary(genome_id, input_fna)
                    families = set()

                if action in ("REUSED_EXISTING_CSV", "REUSED_ZERO_IS_NO_CSV"):
                    n_reused += 1

                family_by_genome[genome_id] = families
                summary_records.append(summary)
                resume_records.append({
                    "genome_id": genome_id,
                    "input_fna": str(input_fna),
                    "run_dir": str(run_dir),
                    "expected_csv": str(reusable_csv) if reusable_csv is not None else str(expected_isescan_csv(run_dir, input_fna)),
                    "action": action,
                    "status": status,
                    "message": message,
                    "n_total_hits": summary["n_total_hits"],
                    "elapsed_seconds": f"{elapsed:.1f}",
                })

            except KeyboardInterrupt:
                print(
                    "\n[FATAL] Interrupted. Consolidated TSVs were NOT modified "
                    "(temporary files only). Per-genome CSVs remain reusable; relaunch to resume.",
                    flush=True,
                )
                raise
            except Exception as exc:
                n_failed += 1
                status = "FAILED"
                message = str(exc)
                print(f"[ERROR] Genome failed: {genome_id}", flush=True)
                print(message, flush=True)
                failure_records.append({
                    "genome_id": genome_id,
                    "input_fna": str(input_fna),
                    "status": "FAILED",
                    "message": message,
                })
                summary_records.append(zero_summary(genome_id, input_fna))
                resume_records.append({
                    "genome_id": genome_id,
                    "input_fna": str(input_fna),
                    "run_dir": str(run_dir),
                    "expected_csv": str(expected_isescan_csv(run_dir, input_fna)),
                    "action": action if 'action' in dir() else "UNSET",
                    "status": status,
                    "message": message,
                    "n_total_hits": "0",
                    "elapsed_seconds": f"{elapsed:.1f}",
                })
                # By design the run continues; the failure is recorded explicitly.

        # Full pass finished. Flush and close the detail temp before finalizing.
        fsync_file(detail_handle)
        detail_handle.close()
        detail_handle = None

        # Write the remaining consolidated outputs to temp files.
        write_tsv(summary_tmp, SUMMARY_COLUMNS, sorted(summary_records, key=lambda r: r["genome_id"]))
        write_tsv(failures_tmp, FAIL_COLUMNS, sorted(failure_records, key=lambda r: r["genome_id"]))
        write_tsv(resume_tmp, RESUME_COLUMNS, sorted(resume_records, key=lambda r: r["genome_id"]))
        write_binary_matrix(binary_tmp, sorted(genome_ids), family_by_genome)

        # Atomic publish: move every temp TSV into its final name.
        os.replace(detail_tmp, detail_out)
        os.replace(binary_tmp, binary_out)
        os.replace(summary_tmp, summary_out)
        os.replace(failures_tmp, failures_out)
        os.replace(resume_tmp, resume_out)
        fsync_dir(output_tsv_dir)
        finalized = True

        # Excel is optional and built last from the finalized TSVs. It can never
        # damage the pipeline-critical TSVs and its failure is non-fatal.
        if make_xlsx:
            print("\n[INFO] Writing optional XLSX workbook (streaming, from finalized TSVs)...", flush=True)
            try:
                write_xlsx(xlsx_tmp, detail_out, binary_out, summary_out, failures_out, resume_out)
                os.replace(xlsx_tmp, xlsx_out)
            except Exception as exc:
                print(f"[WARN] XLSX generation failed (non-fatal): {exc}", flush=True)

        print("\nISEScan mobilome module completed in resume-aware corrected mode.", flush=True)
        print(f"Genomes reused from existing result : {n_reused}", flush=True)
        print(f"Genomes newly processed by ISEScan  : {n_ran}", flush=True)
        print(f"Genomes failed                      : {n_failed}", flush=True)
        print(f"Detail TSV                          : {detail_out}", flush=True)
        print(f"Binary TSV                          : {binary_out}", flush=True)
        print(f"Summary TSV                         : {summary_out}", flush=True)
        print(f"Failures TSV                        : {failures_out}", flush=True)
        print(f"Resume report TSV                   : {resume_out}", flush=True)
        if make_xlsx:
            print(f"Workbook XLSX                       : {xlsx_out}", flush=True)

        if n_failed > 0:
            print(
                "\n[WARN] Some genomes failed or timed out. They appear as zero IS in the "
                "matrix but are listed in isescan_failures.tsv. Decide whether to rerun "
                "them or exclude them before trusting module 09 for those genomes.",
                flush=True,
            )
            return 3
        return 0

    finally:
        if detail_handle is not None:
            try:
                detail_handle.close()
            except Exception:
                pass
        if not finalized:
            # Interrupted or aborted before atomic publish: drop temp files,
            # leave the previous final outputs (if any) untouched.
            for temp in all_temps:
                try:
                    if temp.exists():
                        temp.unlink()
                except Exception:
                    pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[FATAL] Interrupted by user.", file=sys.stderr)
        raise SystemExit(130)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        raise SystemExit(1)
