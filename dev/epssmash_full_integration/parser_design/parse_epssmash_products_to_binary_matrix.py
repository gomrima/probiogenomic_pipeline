#!/usr/bin/env python3

import argparse
import csv
import json
import re
from pathlib import Path


DETAIL_COLUMNS = ["genome_id", "json_file", "record_name", "product_raw", "product_normalized"]


def slugify(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80]


def as_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(as_strings(item))
        return out
    return []


def record_name_from_context(stack: list[object]) -> str:
    for item in reversed(stack):
        if isinstance(item, dict):
            for key in ["name", "id", "record_id", "locus_tag", "accession"]:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return ""


def collect_products(data: object) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []

    def walk(obj: object, stack: list[object]) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_norm = slugify(key)
                collect_key = (
                    "product" in key_norm
                    or "polysaccharide" in key_norm
                    or "exopolysaccharide" in key_norm
                    or key_norm in {"kind", "category"}
                )
                if collect_key:
                    for raw in as_strings(value):
                        raw_norm = slugify(raw)
                        if raw_norm and raw_norm not in {"none", "unknown", "na", "n_a"}:
                            rows.append((record_name_from_context(stack + [obj]), raw))
                walk(value, stack + [obj])
        elif isinstance(obj, list):
            for item in obj:
                walk(item, stack)

    walk(data, [])
    return rows


def parse_json_file(path: Path) -> list[tuple[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    return collect_products(data)


def write_outputs(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_files = sorted(input_dir.glob("*.json"))

    detail_rows: list[dict[str, str]] = []
    product_by_genome: dict[str, set[str]] = {}

    for json_file in json_files:
        genome_id = json_file.stem
        product_by_genome.setdefault(genome_id, set())
        for record_name, product_raw in parse_json_file(json_file):
            product_norm = slugify(product_raw)
            if not product_norm:
                continue
            feature = f"epssmash__{product_norm}"
            product_by_genome[genome_id].add(feature)
            detail_rows.append(
                {
                    "genome_id": genome_id,
                    "json_file": json_file.name,
                    "record_name": record_name,
                    "product_raw": product_raw,
                    "product_normalized": feature,
                }
            )

    all_features = sorted({feature for features in product_by_genome.values() for feature in features})

    binary_path = output_dir / "epssmash_presence_absence_binary.tsv"
    with binary_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["genome_id", *all_features])
        for genome_id in sorted(product_by_genome):
            present = product_by_genome[genome_id]
            writer.writerow([genome_id, *[1 if feature in present else 0 for feature in all_features]])

    detail_path = output_dir / "epssmash_detected_products_long.tsv"
    with detail_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=DETAIL_COLUMNS, delimiter="\t")
        writer.writeheader()
        for row in sorted(detail_rows, key=lambda r: (r["genome_id"], r["product_normalized"])):
            writer.writerow(row)

    summary_path = output_dir / "epssmash_parser_summary.tsv"
    with summary_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["genome_id", "n_detected_products", "detected_products"])
        for genome_id in sorted(product_by_genome):
            features = sorted(product_by_genome[genome_id])
            writer.writerow([genome_id, len(features), ";".join(features)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse epsSMASH JSON files into binary product matrices.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    write_outputs(input_dir, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
