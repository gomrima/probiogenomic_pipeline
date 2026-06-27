#!/usr/bin/env python3
"""
Module 00 - input preparation.

Input contract (enforced)
-------------------------
The pipeline accepts only nucleotide genome assemblies in FASTA form. Every
downstream layer that matters for a safety-first probiogenomic screen (AMR,
virulence, toxins, CRISPR, insertion sequences, plasmids, prophages, mobile
safety) needs nucleotide sequence, so a protein-only input would silently drop a
genome from those layers and bias the final matrix.

Accepted extensions (case-insensitive), optionally gzip-compressed (.gz):
    .fna  .fa  .fasta  .fas

Explicitly refused, with a clear error (so a genome is never silently skipped):
    .faa  (protein FASTA)
    .gbff .gbk .gb  (GenBank)
    .gff  .gff3     (annotation only)

For each accepted genome the module copies the nucleotide FASTA to
work/normalized_fna and calls Prodigal to produce the normalized proteome and
GFF, so every genome carries the nucleotide and protein files the modules need.

The module fails (non-zero exit) if:
    * an input directory contains a refused genome-like file;
    * two inputs normalize to the same genome_id (collision);
    * any accepted genome fails to process.

A failure here means the launcher does not write the step checkpoint, so the run
stops instead of continuing on an incomplete genome set.
"""

import gzip
import re
import shutil
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Dict, Tuple

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord

PIPE_ROOT = Path(os.environ.get("PIPE_ROOT", Path(__file__).resolve().parent.parent))
NORMALIZED_FAA = PIPE_ROOT / "work" / "normalized_faa"
NORMALIZED_FNA = PIPE_ROOT / "work" / "normalized_fna"
NORMALIZED_GBFF = PIPE_ROOT / "work" / "normalized_gbff"
NORMALIZED_GFF = PIPE_ROOT / "work" / "normalized_gff"
MANIFEST_DIR = PIPE_ROOT / "work" / "manifest"
TMP_DIR = PIPE_ROOT / "work" / "tmp"

# Accepted nucleotide FASTA extensions and the genome-like extensions we refuse.
NUCLEOTIDE_FASTA_EXTENSIONS = {".fna", ".fa", ".fasta", ".fas"}
REFUSED_GENOME_EXTENSIONS = {".faa", ".gbff", ".gbk", ".gb", ".gff", ".gff3", ".gtf"}


def classify_extension(path: Path) -> Tuple[str, bool]:
    """Return (core_extension, is_gzip). For 'x.fna.gz' -> ('.fna', True)."""
    name = path.name.lower()
    is_gz = name.endswith(".gz")
    core = name[:-3] if is_gz else name
    return Path(core).suffix, is_gz


def sanitize_genome_id(filename: str) -> str:
    name = filename
    if name.lower().endswith(".gz"):
        name = name[:-3]
    name = re.sub(r"\.(fna|fa|fasta|fas)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def ensure_dirs() -> None:
    for d in [NORMALIZED_FAA, NORMALIZED_FNA, NORMALIZED_GBFF, NORMALIZED_GFF, MANIFEST_DIR, TMP_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def scan_input_dir(input_dir: Path) -> Tuple[List[Path], List[Path]]:
    """Return (accepted_nucleotide_fasta, refused_genome_files)."""
    accepted: List[Path] = []
    refused: List[Path] = []
    for p in sorted(input_dir.iterdir()):
        if not p.is_file():
            continue
        ext, _ = classify_extension(p)
        if ext in NUCLEOTIDE_FASTA_EXTENSIONS:
            accepted.append(p)
        elif ext in REFUSED_GENOME_EXTENSIONS:
            refused.append(p)
        # Anything else (README, csv, etc.) is ignored silently.
    return accepted, refused


def materialize_fna(infile: Path, is_gz: bool, outfile: Path) -> None:
    """Place the nucleotide FASTA at outfile, decompressing gzip if needed."""
    if is_gz:
        with gzip.open(infile, "rb") as fin, open(outfile, "wb") as fout:
            shutil.copyfileobj(fin, fout)
    else:
        shutil.copy2(infile, outfile)


def validate_nucleotide_fasta(path: Path) -> int:
    """Quick structural check: at least one record and a nucleotide alphabet.

    Returns the number of records. Raises ValueError if the file is empty or
    looks like a protein FASTA mislabelled as nucleotide.
    """
    n_records = 0
    non_nucleotide = 0
    sampled = 0
    nucleotide_alphabet = set("ACGTUNRYSWKMBDHVacgtunryswkmbdhv-.*")
    for rec in SeqIO.parse(str(path), "fasta"):
        n_records += 1
        if sampled < 5:
            seq = str(rec.seq)[:2000]
            if seq:
                bad = sum(1 for c in seq if c not in nucleotide_alphabet)
                if bad / len(seq) > 0.15:
                    non_nucleotide += 1
            sampled += 1
    if n_records == 0:
        raise ValueError("no FASTA records found (empty or not FASTA)")
    if sampled > 0 and non_nucleotide == sampled:
        raise ValueError("sequences do not look like nucleotides (possible protein FASTA)")
    return n_records


def run_prodigal(genome_id: str, in_fna: Path, out_faa: Path, out_gff: Path) -> int:
    tmp_faa = TMP_DIR / f"{genome_id}.prodigal_raw.faa"
    tmp_gff = TMP_DIR / f"{genome_id}.prodigal_raw.gff"

    cmd = [
        "prodigal",
        "-i", str(in_fna),
        "-a", str(tmp_faa),
        "-f", "gff",
        "-o", str(tmp_gff),
        "-p", "single",
        "-q",
    ]
    subprocess.run(cmd, check=True)

    records = []
    for idx, rec in enumerate(SeqIO.parse(str(tmp_faa), "fasta"), start=1):
        new_id = f"{genome_id}__PROT_{idx:06d}"
        records.append(SeqRecord(rec.seq, id=new_id, name=new_id, description=""))

    SeqIO.write(records, str(out_faa), "fasta")
    shutil.copy2(tmp_gff, out_gff)
    return len(records)


def write_manifest(rows: List[Dict[str, str]], manifest_path: Path) -> None:
    header = [
        "genome_id", "original_file", "detected_format",
        "normalized_faa", "normalized_fna", "normalized_gbff", "normalized_gff",
        "n_proteins", "status",
    ]
    with open(manifest_path, "w", encoding="utf-8") as fh:
        fh.write("\t".join(header) + "\n")
        for row in rows:
            fh.write("\t".join(str(row.get(col, "")) for col in header) + "\n")


def write_mapping_report(rows: List[Dict[str, str]], path: Path) -> None:
    header = ["original_file", "genome_id", "detected_format", "decision", "reason"]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\t".join(header) + "\n")
        for row in rows:
            fh.write("\t".join(str(row.get(col, "")) for col in header) + "\n")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python 00_prepare_inputs.py /path/to/input_dir", file=sys.stderr)
        sys.exit(1)

    input_dir = Path(sys.argv[1]).resolve()
    if not input_dir.is_dir():
        print(f"ERROR: input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    ensure_dirs()
    accepted, refused = scan_input_dir(input_dir)

    mapping_rows: List[Dict[str, str]] = []

    # 1. Refuse protein/GenBank/annotation genome inputs outright.
    if refused:
        for p in refused:
            ext, _ = classify_extension(p)
            mapping_rows.append({
                "original_file": str(p), "genome_id": "", "detected_format": ext,
                "decision": "REFUSED",
                "reason": "only nucleotide FASTA (.fna/.fa/.fasta/.fas, optionally .gz) is accepted",
            })
        write_mapping_report(mapping_rows, MANIFEST_DIR / "input_file_mapping.tsv")
        print(
            "ERROR: the input directory contains genome files in unsupported formats.\n"
            "       The pipeline accepts only nucleotide FASTA (.fna, .fa, .fasta, .fas, optionally .gz).\n"
            "       Protein FASTA (.faa) and GenBank (.gbff/.gbk/.gb) are not accepted as genome input\n"
            "       because the safety and mobility modules need nucleotide sequence.\n"
            "       Refused files:",
            file=sys.stderr,
        )
        for p in refused:
            print(f"         - {p}", file=sys.stderr)
        sys.exit(1)

    if not accepted:
        print(
            "ERROR: no nucleotide FASTA genome found in the input directory.\n"
            "       Expected one of: .fna, .fa, .fasta, .fas (optionally .gz).",
            file=sys.stderr,
        )
        sys.exit(1)

    # 2. Detect genome_id collisions before writing anything.
    id_to_files: Dict[str, List[Path]] = {}
    for p in accepted:
        gid = sanitize_genome_id(p.name)
        id_to_files.setdefault(gid, []).append(p)
    collisions = {gid: files for gid, files in id_to_files.items() if len(files) > 1}
    if collisions:
        for gid, files in collisions.items():
            for p in files:
                ext, _ = classify_extension(p)
                mapping_rows.append({
                    "original_file": str(p), "genome_id": gid, "detected_format": ext,
                    "decision": "COLLISION",
                    "reason": f"multiple input files normalize to genome_id '{gid}'",
                })
        write_mapping_report(mapping_rows, MANIFEST_DIR / "input_file_mapping.tsv")
        print("ERROR: genome_id collisions detected. Rename the conflicting inputs.", file=sys.stderr)
        for gid, files in collisions.items():
            print(f"         genome_id '{gid}' <- {[str(p) for p in files]}", file=sys.stderr)
        sys.exit(1)

    # 3. Process each accepted nucleotide FASTA.
    manifest_rows: List[Dict[str, str]] = []
    n_failed = 0

    for infile in accepted:
        genome_id = sanitize_genome_id(infile.name)
        ext, is_gz = classify_extension(infile)
        fna_out = NORMALIZED_FNA / f"{genome_id}.fna"
        faa_out = NORMALIZED_FAA / f"{genome_id}.faa"
        gff_out = NORMALIZED_GFF / f"{genome_id}.gff"

        row = {
            "genome_id": genome_id, "original_file": str(infile),
            "detected_format": ext + (".gz" if is_gz else ""),
            "normalized_faa": "", "normalized_fna": "", "normalized_gbff": "",
            "normalized_gff": "", "n_proteins": 0, "status": "OK",
        }
        print(f"[INFO] Processing {infile.name} as genome_id={genome_id}")

        try:
            materialize_fna(infile, is_gz, fna_out)
            validate_nucleotide_fasta(fna_out)
            n_prot = run_prodigal(genome_id, fna_out, faa_out, gff_out)
            row["normalized_fna"] = str(fna_out)
            row["normalized_faa"] = str(faa_out)
            row["normalized_gff"] = str(gff_out)
            row["n_proteins"] = n_prot
        except Exception as exc:
            row["status"] = f"ERROR:{exc}"
            n_failed += 1
            print(f"[ERROR] Genome failed: {genome_id}: {exc}", file=sys.stderr)

        manifest_rows.append(row)
        mapping_rows.append({
            "original_file": str(infile), "genome_id": genome_id,
            "detected_format": ext + (".gz" if is_gz else ""),
            "decision": "ACCEPTED", "reason": row["status"],
        })

    manifest_path = MANIFEST_DIR / "input_manifest.tsv"
    write_manifest(manifest_rows, manifest_path)
    write_mapping_report(mapping_rows, MANIFEST_DIR / "input_file_mapping.tsv")

    print(f"[INFO] Manifest written to: {manifest_path}")
    print(f"[INFO] Genomes accepted: {len(accepted)} | failed: {n_failed}")

    if n_failed > 0:
        print(
            f"ERROR: {n_failed} genome(s) failed during preparation. "
            "See the status column in input_manifest.tsv. The pipeline will not proceed "
            "on an incomplete genome set.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("[INFO] Input preparation finished successfully")


if __name__ == "__main__":
    main()
