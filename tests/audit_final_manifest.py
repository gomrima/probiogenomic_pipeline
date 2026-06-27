#!/usr/bin/env python3

import argparse
import hashlib
from pathlib import Path


SELF_FILES = {
    "metadata/FINAL_FILE_MANIFEST.tsv",
    "metadata/FINAL_FILE_MANIFEST.sha256.tsv",
    "metadata/FINAL_FILE_MANIFEST_METADATA.tsv",
    "metadata/FINAL_FILE_MANIFEST_AUDIT.tsv",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError("Empty manifest")
    header = lines[0].split("\t")
    if "relative_path" not in header or "sha256" not in header:
        raise ValueError("Manifest must contain relative_path and sha256 columns")
    rel_i = header.index("relative_path")
    hash_i = header.index("sha256")
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) <= max(rel_i, hash_i):
            continue
        rows[parts[rel_i]] = parts[hash_i]
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit FINAL_FILE_MANIFEST.tsv against the current release tree.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", default="metadata/FINAL_FILE_MANIFEST.tsv")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest_path = (root / args.manifest).resolve()
    rows = load_manifest(manifest_path)

    actual = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in SELF_FILES:
            continue
        actual[rel] = sha256(path)

    output_rows = ["relative_path\tstatus\tnotes"]
    failures = 0

    for rel in sorted(set(rows) | set(actual)):
        if rel not in rows:
            output_rows.append(f"{rel}\tFAIL\tmissing_from_manifest")
            failures += 1
            continue
        if rel not in actual:
            output_rows.append(f"{rel}\tFAIL\tlisted_but_absent")
            failures += 1
            continue
        if rows[rel] != actual[rel]:
            output_rows.append(f"{rel}\tFAIL\tsha256_mismatch")
            failures += 1
            continue
        output_rows.append(f"{rel}\tPASS\tok")

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(output_rows) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
