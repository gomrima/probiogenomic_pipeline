#!/usr/bin/env python3
"""
Module 09 - Mobile Safety Localization (version 3: prophage integration)

For each resistance (AMR), virulence, or toxicity feature detected by
modules 02, 03 and 05, this module determines whether that feature is
carried by a mobile element (IS, plasmid, or prophage) in the same genome.

VERSION 3 - New features
========================
This version extends v2 by integrating a third type of mobile element:
the prophage regions detected by geNomad (module 08). The localization
logic stays strictly parallel to IS elements and plasmids, ensuring
biological and statistical coherence with the rest of the analysis.

LOCALIZATION LOGIC
==================
Three mobility criteria are evaluated for each safety hit:

  1. on_plasmid  - The contig is classified "plasmid" by MOB-suite (module 07)
  2. near_is     - The hit overlaps or is within IS_WINDOW bp of an IS (module 06)
                   Applicable only to ABRicate hits (coordinates required)
  3. on_prophage - The hit lies within a geNomad prophage region
                   (module 08). Depending on coordinate availability:
                     - ABRicate features: strict interval overlap
                     - protein features: presence of at least one prophage
                       on the derived contig (contig-level resolution)

  on_mobile      = on_plasmid OR near_is OR on_prophage

TWO LOCALIZATION MECHANISMS DEPENDING ON THE SOURCE
====================================================

  A. Coordinate overlap - ABRicate features (module 02)
     virulence_detail.tsv and amr_detail.tsv provide: sequence (contig),
     start, end. All mobility criteria are evaluated at coordinate level.
     Reported method: "coordinate_overlap"

  B. Contig-level resolution - protein features (modules 03/05)
     TASmania, DBETH and PAT return a Prodigal query_id (contig_NNN).
     The parent contig is extracted by stripping the _NNN suffix.
       - on_plasmid : yes/no (MOB-suite classification of the contig)
       - near_is : NO (no genomic coordinates for the protein)
       - on_prophage : yes/no (presence of at least one prophage region
                                on the parent contig)
     Reported method: "contig_level"

OUTPUTS PRODUCED
================
  Main binary matrix:
    Rows    = genomes
    Columns = {category}__{feature_name}
    Value   = 1 if the feature is detected AND on_mobile == 1
              0 otherwise (feature absent OR located on a non-mobile chromosome)

  Detail table:
    One row per evaluated safety hit, with columns:
    genome_id, feature_category, feature_name, contig_id,
    feature_start, feature_end, on_plasmid, near_is, on_prophage,
    on_mobile, prophage_region_id, prophage_taxonomy, localization_method.

  Summary by genome:
    Counts by category and by mobile-element type,
    aggregated risk indicators.

REQUIRED INPUTS
===============
  results/tsv/safety/virulence_detail.tsv          (module 02)
  results/tsv/safety/amr_detail.tsv                (module 02)
  results/tsv/ta_systems/tasmania_detail.tsv       (module 03)
  results/tsv/toxins/dbeth_toxins_detail.tsv       (module 05)
  results/tsv/toxins/pat_toxins_detail.tsv         (module 05)
  results/tsv/toxins/pat_immunity_detail.tsv       (module 05)
  results/tsv/mobilome/isescan_hits_detail.tsv     (module 06)
  work/intermediate/mobilome/mobsuite_raw/<genome>/contig_report.txt  (module 07)

OPTIONAL INPUT (integrated if present)
=======================================
  results/tsv/prophages/genomad_prophage_detail.tsv (module 08)
  If absent: the on_prophage columns stay at 0 and a warning is emitted.
  This ensures backward compatibility with runs where geNomad did not run.
"""

import re
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PIPE_ROOT = Path(os.environ.get("PIPE_ROOT", Path(__file__).resolve().parent.parent))

MANIFEST_TSV = PIPE_ROOT / "work" / "manifest" / "input_manifest.tsv"

# Safety features - modules 02, 03, 05
VIRULENCE_DETAIL    = PIPE_ROOT / "results" / "tsv" / "safety"     / "virulence_detail.tsv"
AMR_DETAIL          = PIPE_ROOT / "results" / "tsv" / "safety"     / "amr_detail.tsv"
TASMANIA_DETAIL     = PIPE_ROOT / "results" / "tsv" / "ta_systems" / "tasmania_detail.tsv"
DBETH_DETAIL        = PIPE_ROOT / "results" / "tsv" / "toxins"     / "dbeth_toxins_detail.tsv"
PAT_TOXIN_DETAIL    = PIPE_ROOT / "results" / "tsv" / "toxins"     / "pat_toxins_detail.tsv"
PAT_IMMUNITY_DETAIL = PIPE_ROOT / "results" / "tsv" / "toxins"     / "pat_immunity_detail.tsv"

# Mobilome - modules 07, 08, 13
ISESCAN_DETAIL     = PIPE_ROOT / "results" / "tsv" / "mobilome"  / "isescan_hits_detail.tsv"
MOBSUITE_RAW_ROOT  = PIPE_ROOT / "work" / "intermediate" / "mobilome" / "mobsuite_raw"
PROPHAGE_DETAIL    = PIPE_ROOT / "results" / "tsv" / "prophages" / "genomad_prophage_detail.tsv"

# Outputs for module 09
RESULTS_TSV  = PIPE_ROOT / "results" / "tsv"  / "mobile_safety"
RESULTS_XLSX = PIPE_ROOT / "results" / "xlsx" / "mobile_safety"

BINARY_TSV   = RESULTS_TSV / "mobile_safety_on_mobile_binary.tsv"
DETAIL_TSV   = RESULTS_TSV / "mobile_safety_on_mobile_detail.tsv"
SUMMARY_TSV  = RESULTS_TSV / "mobile_safety_summary_by_genome.tsv"
WORKBOOK     = RESULTS_XLSX / "mobile_safety_results.xlsx"

# IS proximity window for ABRicate features (in base pairs)
IS_WINDOW = 5_000

# Safety categories processed
SECURITY_CATEGORIES = [
    "amr",
    "virulence",
    "ta_systems",
    "dbeth_toxins",
    "pat_toxins",
    "pat_immunity",
]


# ---------------------------------------------------------------------------
# Classe interne SafetyHit
# ---------------------------------------------------------------------------

class SafetyHit:
    """Normalized representation of a detected safety feature."""

    __slots__ = (
        "genome_id", "category", "feature_name",
        "contig", "start", "end",
    )

    def __init__(
        self,
        genome_id: str,
        category: str,
        feature_name: str,
        contig: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ):
        self.genome_id    = genome_id
        self.category     = category
        self.feature_name = feature_name
        self.contig       = contig
        self.start        = start
        self.end          = end


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required file absent: {path}")


def load_tsv_optional(path: Path, label: str) -> pd.DataFrame:
    """Load a TSV if present, otherwise return an empty DataFrame with a warning."""
    if not path.is_file():
        print(f"[WARN] Absent, skipped ({label}): {path}", flush=True)
        return pd.DataFrame()
    df = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    print(f"[INFO] Loaded {label}: {len(df)} rows", flush=True)
    return df


def safe_int(value) -> Optional[int]:
    """Robust conversion to int, returns None if not possible."""
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def sanitize_name(name: str) -> str:
    """Mirror of the module 07 function to locate the MOB-suite run_dir."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(name))


def extract_contig_from_protein_id(protein_id: str) -> Optional[str]:
    """
    Extract the parent contig name from a Prodigal protein identifier.

    Prodigal names proteins: <contig>_<NUM> (NUM = sequential integer).
    The last _NNN segment is removed to recover the parent contig.
    Returns None if extraction fails.
    """
    pid = str(protein_id).strip()
    if not pid:
        return None
    derived = re.sub(r"_\d+$", "", pid)
    return derived if derived != pid else None


def intervals_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Standard overlap test for two inclusive intervals."""
    # Normalisation : start <= end
    a_lo, a_hi = (a_start, a_end) if a_start <= a_end else (a_end, a_start)
    b_lo, b_hi = (b_start, b_end) if b_start <= b_end else (b_end, b_start)
    return a_lo <= b_hi and a_hi >= b_lo


# ---------------------------------------------------------------------------
# Build mobilome indexes
# ---------------------------------------------------------------------------

def build_plasmid_contig_index(all_genomes: List[str]) -> Dict[str, Set[str]]:
    """
    Read the MOB-suite contig_report.txt files for each genome.
    Returns {genome_id -> set(contig_id)} for contigs classified as plasmid.
    Convention : MOBSUITE_RAW_ROOT / sanitize_name(genome_id) / contig_report.txt
    """
    index: Dict[str, Set[str]] = {}
    n_with_plasmid = 0

    for genome_id in all_genomes:
        report = MOBSUITE_RAW_ROOT / sanitize_name(genome_id) / "contig_report.txt"
        plasmid_contigs: Set[str] = set()

        if report.is_file():
            try:
                df = pd.read_csv(report, sep="\t", dtype=str).fillna("")
                if "molecule_type" in df.columns and "contig_id" in df.columns:
                    mask = (
                        df["molecule_type"]
                        .astype(str).str.strip().str.lower() == "plasmid"
                    )
                    plasmid_contigs = set(
                        df.loc[mask, "contig_id"].astype(str).str.strip().tolist()
                    )
            except Exception as exc:
                print(
                    f"[WARN] Failed to read contig_report.txt for {genome_id}: {exc}",
                    flush=True,
                )

        index[genome_id] = plasmid_contigs
        if plasmid_contigs:
            n_with_plasmid += 1

    print(
        f"[INFO] Plasmid index: {n_with_plasmid}/{len(all_genomes)} genomes "
        f"with at least one plasmid contig",
        flush=True,
    )
    return index


def build_is_location_index(
    isescan_df: pd.DataFrame,
) -> Dict[str, List[Tuple[str, int, int]]]:
    """
    Construit {genome_id -> [(contig, isBegin, isEnd), ...]} depuis
    the isescan_hits_detail.tsv file (module 06).
    """
    index: Dict[str, List[Tuple[str, int, int]]] = {}

    if isescan_df.empty:
        return index

    required = {"genome_id", "seqID", "isBegin", "isEnd"}
    missing = required - set(isescan_df.columns)
    if missing:
        print(
            f"[WARN] Missing columns in ISEScan detail ({missing}), empty IS index.",
            flush=True,
        )
        return index

    for _, row in isescan_df.iterrows():
        gid    = str(row["genome_id"]).strip()
        contig = str(row["seqID"]).strip()
        begin  = safe_int(row["isBegin"])
        end_v  = safe_int(row["isEnd"])

        if not gid or not contig or begin is None or end_v is None:
            continue

        index.setdefault(gid, []).append((contig, begin, end_v))

    n_is = sum(len(v) for v in index.values())
    print(
        f"[INFO] IS index: {n_is} IS elements in {len(index)} genomes",
        flush=True,
    )
    return index


def build_prophage_index(
    prophage_df: pd.DataFrame,
) -> Dict[str, List[Tuple[str, int, int, str, str]]]:
    """
    Construit {genome_id -> [(contig, start, end, region_id, taxonomy), ...]}
    depuis genomad_prophage_detail.tsv (module 13).

    The tuple includes region_id and taxonomy to allow enrichment
    of the detail table with the identity of the detected prophage.

    Regions are kept as is even when is_provirus == 0
    (case of free viruses detected in the assembly: they represent
    also a mobile-element signature in the context of a genome
    bacterien isole).
    """
    index: Dict[str, List[Tuple[str, int, int, str, str]]] = {}

    if prophage_df.empty:
        return index

    required = {"genome_id", "contig_id", "start", "end"}
    missing = required - set(prophage_df.columns)
    if missing:
        print(
            f"[WARN] Missing columns in geNomad detail ({missing}), "
            f"index prophages vide.",
            flush=True,
        )
        return index

    has_region_id = "region_id" in prophage_df.columns
    has_taxonomy  = "taxonomy"  in prophage_df.columns

    for _, row in prophage_df.iterrows():
        gid    = str(row["genome_id"]).strip()
        contig = str(row["contig_id"]).strip()
        start  = safe_int(row["start"])
        end_v  = safe_int(row["end"])

        if not gid or not contig or start is None or end_v is None:
            continue

        region_id = str(row["region_id"]).strip() if has_region_id else ""
        taxonomy  = str(row["taxonomy"]).strip()  if has_taxonomy  else ""

        index.setdefault(gid, []).append((contig, start, end_v, region_id, taxonomy))

    n_proph = sum(len(v) for v in index.values())
    print(
        f"[INFO] Prophage index: {n_proph} prophage regions in "
        f"{len(index)} genomes",
        flush=True,
    )
    return index


# ---------------------------------------------------------------------------
# Load and normalize safety features
# ---------------------------------------------------------------------------

def load_abricate_features(
    df: pd.DataFrame,
    category: str,
) -> List[SafetyHit]:
    """
    Load the ABRicate hits (virulence or AMR).
    Complete genomic coordinates: contig, start, end.
    """
    hits: List[SafetyHit] = []
    if df.empty:
        return hits

    for _, row in df.iterrows():
        genome_id = str(row.get("genome_id", "")).strip()
        gene      = str(row.get("gene",      "")).strip()
        contig    = str(row.get("sequence",  "")).strip() or None
        start     = safe_int(str(row.get("start", "")))
        end_v     = safe_int(str(row.get("end",   "")))

        if not genome_id or not gene:
            continue

        hits.append(SafetyHit(
            genome_id    = genome_id,
            category     = category,
            feature_name = gene,
            contig       = contig,
            start        = start,
            end          = end_v,
        ))

    return hits


def load_protein_features(
    df: pd.DataFrame,
    category: str,
    feature_col: str,
) -> List[SafetyHit]:
    """
    Load the protein hits (TASmania, DBETH, PAT).
    Only the contig is derived from the Prodigal query_id; no coordinates.
    """
    hits: List[SafetyHit] = []
    if df.empty:
        return hits

    for _, row in df.iterrows():
        genome_id    = str(row.get("genome_id",  "")).strip()
        query_id     = str(row.get("query_id",   "")).strip()
        feature_name = str(row.get(feature_col,  "")).strip()

        if not genome_id or not feature_name:
            continue

        contig = extract_contig_from_protein_id(query_id)

        hits.append(SafetyHit(
            genome_id    = genome_id,
            category     = category,
            feature_name = feature_name,
            contig       = contig,
            start        = None,
            end          = None,
        ))

    return hits


# ---------------------------------------------------------------------------
# Evaluation of mobile localization
# ---------------------------------------------------------------------------

def evaluate_hit(
    hit: SafetyHit,
    plasmid_index: Dict[str, Set[str]],
    is_index: Dict[str, List[Tuple[str, int, int]]],
    prophage_index: Dict[str, List[Tuple[str, int, int, str, str]]],
) -> dict:
    """
    Evaluate whether a SafetyHit is carried by a mobile element.

    The three criteria are independent (a hit can be simultaneously
    on a plasmid, near an IS, and in a prophage).
    """
    has_coords = (
        hit.contig is not None
        and hit.start is not None
        and hit.end is not None
    )

    # --- 1. Verification plasmide (contig_id seul suffit) ---
    on_plasmid = 0
    if hit.contig:
        plasmid_contigs = plasmid_index.get(hit.genome_id, set())
        if hit.contig in plasmid_contigs:
            on_plasmid = 1

    # --- 2. IS proximity check (coordinates required) ---
    near_is = 0
    if has_coords:
        is_elements = is_index.get(hit.genome_id, [])
        ext_start = hit.start - IS_WINDOW   # type: ignore[operator]
        ext_end   = hit.end   + IS_WINDOW   # type: ignore[operator]

        for is_contig, is_begin, is_end in is_elements:
            if is_contig != hit.contig:
                continue
            if intervals_overlap(ext_start, ext_end, is_begin, is_end):
                near_is = 1
                break

    # --- 3. Verification prophage ---
    # Mechanism A: strict coordinate overlap (ABRicate features)
    # Mechanism B: presence of at least one prophage on the contig (protein features)
    on_prophage      = 0
    prophage_region  = ""
    prophage_tax     = ""

    if hit.contig:
        prophage_regions = prophage_index.get(hit.genome_id, [])

        for ph_contig, ph_start, ph_end, ph_region_id, ph_taxonomy in prophage_regions:
            if ph_contig != hit.contig:
                continue

            if has_coords:
                # Mechanism A: strict overlap
                if intervals_overlap(hit.start, hit.end, ph_start, ph_end):  # type: ignore[arg-type]
                    on_prophage = 1
                    prophage_region = ph_region_id
                    prophage_tax    = ph_taxonomy
                    break
            else:
                # Mechanism B: presence on the contig (contig-level resolution)
                on_prophage = 1
                prophage_region = ph_region_id
                prophage_tax    = ph_taxonomy
                break

    on_mobile = 1 if (on_plasmid or near_is or on_prophage) else 0
    method    = "coordinate_overlap" if has_coords else "contig_level"

    return {
        "genome_id":           hit.genome_id,
        "feature_category":    hit.category,
        "feature_name":        hit.feature_name,
        "contig_id":           hit.contig or "",
        "feature_start":       hit.start  if hit.start is not None else "",
        "feature_end":         hit.end    if hit.end   is not None else "",
        "on_plasmid":          on_plasmid,
        "near_is":             near_is,
        "on_prophage":         on_prophage,
        "on_mobile":           on_mobile,
        "prophage_region_id":  prophage_region,
        "prophage_taxonomy":   prophage_tax,
        "localization_method": method,
    }


# ---------------------------------------------------------------------------
# Build output matrices
# ---------------------------------------------------------------------------

def build_all_outputs(
    all_hits: List[SafetyHit],
    plasmid_index: Dict[str, Set[str]],
    is_index: Dict[str, List[Tuple[str, int, int]]],
    prophage_index: Dict[str, List[Tuple[str, int, int, str, str]]],
    all_genomes: List[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Evaluate all hits and produce detail_df, binary_df, summary_df.
    """
    detail_rows: List[dict] = []
    on_mobile_map: Dict[str, Dict[str, int]] = {g: {} for g in all_genomes}

    for hit in all_hits:
        result = evaluate_hit(hit, plasmid_index, is_index, prophage_index)
        detail_rows.append(result)

        if result["on_mobile"] == 1 and hit.genome_id in on_mobile_map:
            col = f"{hit.category}__{hit.feature_name}"
            on_mobile_map[hit.genome_id][col] = 1

    # --- Detail table ---
    detail_columns = [
        "genome_id", "feature_category", "feature_name", "contig_id",
        "feature_start", "feature_end", "on_plasmid", "near_is",
        "on_prophage", "on_mobile", "prophage_region_id",
        "prophage_taxonomy", "localization_method",
    ]

    if detail_rows:
        detail_df = (
            pd.DataFrame(detail_rows)
            [detail_columns]
            .sort_values(["genome_id", "feature_category", "feature_name"], kind="stable")
            .reset_index(drop=True)
        )
    else:
        detail_df = pd.DataFrame(columns=detail_columns)

    # --- Binary matrix ---
    all_feature_cols = sorted(
        {col for gd in on_mobile_map.values() for col in gd}
    )

    binary_rows: List[dict] = []
    for gid in all_genomes:
        row = {"genome_id": gid}
        gd = on_mobile_map.get(gid, {})
        for col in all_feature_cols:
            row[col] = gd.get(col, 0)
        binary_rows.append(row)

    binary_df = pd.DataFrame(binary_rows)
    for col in all_feature_cols:
        binary_df[col] = (
            pd.to_numeric(binary_df[col], errors="coerce")
            .fillna(0).clip(upper=1).astype(int)
        )

    # --- Summary by genome ---
    summary_rows: List[dict] = []

    for gid in all_genomes:
        gdf = (
            detail_df[detail_df["genome_id"] == gid].copy()
            if "genome_id" in detail_df.columns and not detail_df.empty
            else pd.DataFrame()
        )

        n_detected   = len(gdf)
        n_on_mobile  = int(gdf["on_mobile"].astype(int).sum())   if "on_mobile"   in gdf.columns else 0
        n_on_plasmid = int(gdf["on_plasmid"].astype(int).sum())  if "on_plasmid"  in gdf.columns else 0
        n_near_is    = int(gdf["near_is"].astype(int).sum())     if "near_is"     in gdf.columns else 0
        n_on_proph   = int(gdf["on_prophage"].astype(int).sum()) if "on_prophage" in gdf.columns else 0

        entry: dict = {
            "genome_id":                          gid,
            "has_plasmid_contigs":                int(bool(plasmid_index.get(gid))),
            "has_is_elements":                    int(bool(is_index.get(gid))),
            "has_prophage_regions":               int(bool(prophage_index.get(gid))),
            "n_plasmid_contigs":                  len(plasmid_index.get(gid, set())),
            "n_is_elements":                      len(is_index.get(gid, [])),
            "n_prophage_regions":                 len(prophage_index.get(gid, [])),
            "n_safety_features_detected":         n_detected,
            "n_safety_features_on_mobile":        n_on_mobile,
            "n_safety_features_on_plasmid":       n_on_plasmid,
            "n_safety_features_near_is":          n_near_is,
            "n_safety_features_on_prophage":      n_on_proph,
        }

        # Counts by safety category
        for cat in SECURITY_CATEGORIES:
            cat_df = (
                gdf[gdf["feature_category"] == cat]
                if "feature_category" in gdf.columns else pd.DataFrame()
            )
            entry[f"n_{cat}_on_mobile"] = (
                int(cat_df["on_mobile"].astype(int).sum())
                if "on_mobile" in cat_df.columns else 0
            )
            entry[f"n_{cat}_on_prophage"] = (
                int(cat_df["on_prophage"].astype(int).sum())
                if "on_prophage" in cat_df.columns else 0
            )

        # Composite risk indicators
        entry["has_any_safety_on_mobile"] = int(n_on_mobile > 0)
        entry["has_amr_or_virulence_on_mobile"] = int(
            entry["n_amr_on_mobile"] > 0 or entry["n_virulence_on_mobile"] > 0
        )
        entry["has_amr_or_virulence_on_prophage"] = int(
            entry["n_amr_on_prophage"] > 0 or entry["n_virulence_on_prophage"] > 0
        )

        summary_rows.append(entry)

    summary_df = pd.DataFrame(summary_rows)

    return detail_df, binary_df, summary_df


# ---------------------------------------------------------------------------
# Write output files
# ---------------------------------------------------------------------------

def write_outputs(
    detail_df: pd.DataFrame,
    binary_df: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> None:
    detail_df.to_csv(DETAIL_TSV,   sep="\t", index=False)
    binary_df.to_csv(BINARY_TSV,   sep="\t", index=False)
    summary_df.to_csv(SUMMARY_TSV, sep="\t", index=False)

    with pd.ExcelWriter(WORKBOOK, engine="openpyxl") as writer:
        binary_df.to_excel(writer,  sheet_name="on_mobile_binary",  index=False)
        detail_df.to_excel(writer,  sheet_name="on_mobile_detail",  index=False)
        summary_df.to_excel(writer, sheet_name="summary_by_genome", index=False)

    n_feat    = len([c for c in binary_df.columns if c != "genome_id"])
    n_geno    = len(binary_df)
    feat_cols = [c for c in binary_df.columns if c != "genome_id"]
    n_present = int(binary_df[feat_cols].values.sum()) if feat_cols else 0

    print(f"[INFO] Binary matrix  -> {BINARY_TSV}",  flush=True)
    print(f"[INFO] Detail table  -> {DETAIL_TSV}",  flush=True)
    print(f"[INFO] Summary genomes   -> {SUMMARY_TSV}", flush=True)
    print(f"[INFO] Excel workbook   -> {WORKBOOK}",    flush=True)
    print(
        f"[INFO] Result: {n_geno} genomes x {n_feat} features on mobile | "
        f"{n_present} total presences",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    safe_mkdir(RESULTS_TSV)
    safe_mkdir(RESULTS_XLSX)

    # Load the manifest
    require_file(MANIFEST_TSV)
    manifest    = pd.read_csv(MANIFEST_TSV, sep="\t", dtype=str).fillna("")
    all_genomes = manifest["genome_id"].astype(str).str.strip().tolist()
    print(f"[INFO] Genomes in the manifest: {len(all_genomes)}", flush=True)

    # Build mobilome indexes
    print("[INFO] Reading plasmid contigs (MOB-suite)...", flush=True)
    plasmid_index = build_plasmid_contig_index(all_genomes)

    print("[INFO] Reading IS elements (ISEScan)...", flush=True)
    isescan_df = load_tsv_optional(ISESCAN_DETAIL, "ISEScan hits detail (module 07)")
    is_index   = build_is_location_index(isescan_df)

    print("[INFO] Reading prophage regions (geNomad)...", flush=True)
    prophage_df    = load_tsv_optional(PROPHAGE_DETAIL, "geNomad prophage detail (module 08)")
    prophage_index = build_prophage_index(prophage_df)

    if prophage_df.empty:
        print(
            "[WARN] geNomad module absent from the current run. The "
            "on_prophage columns will all be 0. Run the geNomad module to enable "
            "prophage detection.",
            flush=True,
        )

    # Load safety features
    print("[INFO] Loading safety features...", flush=True)
    all_hits: List[SafetyHit] = []

    vir_df = load_tsv_optional(VIRULENCE_DETAIL, "Virulence ABRicate (module 02)")
    all_hits.extend(load_abricate_features(vir_df, "virulence"))

    amr_df = load_tsv_optional(AMR_DETAIL, "AMR ABRicate (module 02)")
    all_hits.extend(load_abricate_features(amr_df, "amr"))

    tas_df = load_tsv_optional(TASMANIA_DETAIL, "TASmania TA (module 03)")
    all_hits.extend(load_protein_features(tas_df, "ta_systems", "marker"))

    dbeth_df = load_tsv_optional(DBETH_DETAIL, "DBETH exotoxines (module 05)")
    all_hits.extend(load_protein_features(dbeth_df, "dbeth_toxins", "feature_name"))

    pat_tox_df = load_tsv_optional(PAT_TOXIN_DETAIL, "PAT toxines (module 05)")
    all_hits.extend(load_protein_features(pat_tox_df, "pat_toxins", "feature_name"))

    pat_imm_df = load_tsv_optional(PAT_IMMUNITY_DETAIL, "PAT immunite (module 05)")
    all_hits.extend(load_protein_features(pat_imm_df, "pat_immunity", "feature_name"))

    print(f"[INFO] Total safety features to localize: {len(all_hits)}", flush=True)

    if not all_hits:
        print(
            "[WARN] No safety feature loaded. "
            "Check that modules 02, 03 and 05 have been executed.",
            flush=True,
        )
        empty_detail_columns = [
            "genome_id", "feature_category", "feature_name", "contig_id",
            "feature_start", "feature_end", "on_plasmid", "near_is",
            "on_prophage", "on_mobile", "prophage_region_id",
            "prophage_taxonomy", "localization_method",
        ]
        detail_df  = pd.DataFrame(columns=empty_detail_columns)
        binary_df  = pd.DataFrame({"genome_id": all_genomes})
        summary_df = pd.DataFrame({"genome_id": all_genomes})
        write_outputs(detail_df, binary_df, summary_df)
        return

    print(
        f"[INFO] IS proximity window: +/-{IS_WINDOW} bp "
        f"(applicable only to ABRicate features with genomic coordinates)",
        flush=True,
    )
    print("[INFO] Localisation en cours...", flush=True)

    detail_df, binary_df, summary_df = build_all_outputs(
        all_hits, plasmid_index, is_index, prophage_index, all_genomes,
    )

    # Summary statistics
    n_total      = len(all_genomes)
    n_risk       = int((summary_df["has_any_safety_on_mobile"]            == 1).sum())
    n_hi_mobile  = int((summary_df["has_amr_or_virulence_on_mobile"]      == 1).sum())
    n_hi_proph   = int((summary_df["has_amr_or_virulence_on_prophage"]    == 1).sum())

    print(
        f"[INFO] Genomes with >= 1 safety feature on a mobile element: {n_risk}/{n_total}",
        flush=True,
    )
    print(
        f"[INFO] Genomes with AMR or virulence on a mobile element: {n_hi_mobile}/{n_total}",
        flush=True,
    )
    print(
        f"[INFO] Genomes with AMR or virulence on a prophage: {n_hi_proph}/{n_total}",
        flush=True,
    )

    if "localization_method" in detail_df.columns and len(detail_df) > 0:
        for method, cnt in detail_df["localization_method"].value_counts().items():
            print(f"[INFO]   Method '{method}': {cnt} hits analyzed", flush=True)

    write_outputs(detail_df, binary_df, summary_df)
    print("[INFO] Module 09 v3 (IS + plasmids + prophages) completed.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        sys.exit(1)

