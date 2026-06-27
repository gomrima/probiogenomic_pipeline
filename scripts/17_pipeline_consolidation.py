#!/usr/bin/env python3
"""
Module 17 V2_2 - Final Pipeline Consolidation

Difference vs V2:
  - Module 16 ProbML added as an optional external comparator,
    with its auxiliary sheets (summary, model_predictions, failures,
    metadata) added to the final workbook if they exist.
  - All other optional modules are preserved:
    ProbioSML, geNomad prophages, Mobile Safety v3.

Renamed with an underscore (V2_2) rather than a dot (V2.1) to avoid
quoting problems in the shell wrappers.

Integrates the outputs of all active modules, including:
  - Module 11 ProbioSML screening.
  - Module 08 geNomad prophages.
  - Module 09 Mobile Safety Localization v3.
  - Module 16 ProbML, added as an optional external comparator.

Modules marked required=False are skipped without a fatal error when their
files are absent, which ensures compatibility with the LIGHT and STANDARD
modes, or with runs where an optional module did not run.

ProbML is integrated only as an additional comparison result:
its binary indicators are added to the final matrix, and its detailed
tables are added to the final workbook if they exist.

The per-category outputs derived from ProbioSML, when they exist in
results/tsv/probiosml/by_category, are added as auxiliary sheets to the
final workbook. They do not modify final_feature_matrix.tsv, in order to
avoid duplicating the global ProbioSML signal in the final matrix.
"""

import argparse
import re
import sys
from pathlib import Path
from functools import reduce

import pandas as pd


MODULE_SPECS = [
    {
        "module_name":  "markers",
        "input_file":   "results/tsv/markers/marker_presence_absence_binary.tsv",
        "sheet_name":   "markers_binary",
        "count_column": "n_markers",
        "required":     True,
    },
    {
        "module_name":  "virulence",
        "input_file":   "results/tsv/safety/virulence_binary.tsv",
        "sheet_name":   "virulence_binary",
        "count_column": "n_virulence_features",
        "required":     True,
    },
    {
        "module_name":  "amr",
        "input_file":   "results/tsv/safety/amr_binary.tsv",
        "sheet_name":   "amr_binary",
        "count_column": "n_amr_features",
        "required":     True,
    },
    {
        "module_name":  "ta_systems",
        "input_file":   "results/tsv/ta_systems/tasmania_presence_absence_binary.tsv",
        "sheet_name":   "tasmania_binary",
        "count_column": "n_ta_systems",
        "required":     True,
    },
    {
        "module_name":  "crispr",
        "input_file":   "results/tsv/crispr/crispr_presence_absence_binary.tsv",
        "sheet_name":   "crispr_binary",
        "count_column": "n_crispr_features",
        "required":     True,
    },
    {
        "module_name":  "dbeth_toxins",
        "input_file":   "results/tsv/toxins/dbeth_toxins_binary.tsv",
        "sheet_name":   "dbeth_toxins_binary",
        "count_column": "n_dbeth_toxins",
        "required":     True,
    },
    {
        "module_name":  "pat_toxins",
        "input_file":   "results/tsv/toxins/pat_toxins_binary.tsv",
        "sheet_name":   "pat_toxins_binary",
        "count_column": "n_pat_toxins",
        "required":     True,
    },
    {
        "module_name":  "pat_immunity",
        "input_file":   "results/tsv/toxins/pat_immunity_binary.tsv",
        "sheet_name":   "pat_immunity_binary",
        "count_column": "n_pat_immunity_features",
        "required":     True,
    },
    {
        "module_name":  "cazy",
        "input_file":   "results/tsv/cazy/cazy_families_binary.tsv",
        "sheet_name":   "cazy_binary",
        "count_column": "n_cazy_families",
        "required":     True,
    },
    {
        "module_name":  "isescan",
        "input_file":   "results/tsv/mobilome/isescan_family_binary.tsv",
        "sheet_name":   "isescan_binary",
        "count_column": "n_isescan_families",
        "required":     False,
    },
    {
        "module_name":  "mobsuite",
        "input_file":   "results/tsv/mobilome/mobsuite_feature_binary.tsv",
        "sheet_name":   "mobsuite_binary",
        "count_column": "n_mobsuite_features",
        "required":     False,
    },
    {
        "module_name":  "bgc",
        "input_file":   "results/tsv/bgc/antismash_bgc_binary.tsv",
        "sheet_name":   "antismash_binary",
        "count_column": "n_antismash_bgc_features",
        "required":     False,
    },
    {
        "module_name":  "bagel5",
        "input_file":   "results/tsv/bgc/bagel5_bacteriocin_binary.tsv",
        "sheet_name":   "bagel5_binary",
        "count_column": "n_bagel5_bacteriocins",
        "required":     False,
    },
    {
        "module_name":  "epssmash",
        "input_file":   "results/tsv/bgc/epssmash_presence_absence_binary.tsv",
        "sheet_name":   "epssmash_binary",
        "count_column": "n_epssmash_products",
        "required":     False,
    },
    # Module 11 ProbioSML screening (preserved)
    {
        "module_name":  "probiosml",
        "input_file":   "results/tsv/probiosml/probiosml_presence_absence_binary.tsv",
        "sheet_name":   "probiosml_binary",
        "count_column": "n_probiosml_markers",
        "required":     False,
    },
    # Module 16 ProbML screening
    # Optional external comparator based on the 12 XGB_LD3_IITMd models.
    {
        "module_name":  "probml",
        "input_file":   "results/tsv/probml/probml_presence_absence_binary.tsv",
        "sheet_name":   "probml_binary",
        "count_column": "n_probml_indicators",
        "required":     False,
    },
    # Module 08 geNomad prophages (new)
    {
        "module_name":  "genomad",
        "input_file":   "results/tsv/prophages/genomad_prophage_binary.tsv",
        "sheet_name":   "genomad_binary",
        "count_column": "n_genomad_prophage_features",
        "required":     False,
    },
    # Module 09 Mobile Safety Localization v3
    # The integrated matrix is the one of safety features confirmed on
    # mobile elements (IS, plasmid, or prophage) - on_mobile == 1.
    {
        "module_name":  "mobile_safety",
        "input_file":   "results/tsv/mobile_safety/mobile_safety_on_mobile_binary.tsv",
        "sheet_name":   "mobile_safety_binary",
        "count_column": "n_safety_features_on_mobile",
        "required":     False,
    },
]


# Modules that each execution mode is expected to have produced. A module is
# enforced as required when it is required in the spec OR required by the mode.
# This stops a `full` run from quietly dropping a biological layer. ProbML is
# deliberately left optional in every mode: it is an external comparator and may
# legitimately be unavailable, so its absence warns but never fails consolidation.
MODE_REQUIRED_MODULES = {
    "LIGHT": set(),
    "STANDARD": {"isescan", "mobsuite"},
    "FULL": {
        "isescan", "mobsuite", "genomad", "mobile_safety",
        "probiosml", "bgc", "bagel5", "epssmash",
    },
}


EXTRA_SHEET_SPECS = [
    {
        "input_file": "results/tsv/probml/probml_summary_by_genome.tsv",
        "sheet_name": "probml_summary",
        "required": False,
    },
    {
        "input_file": "results/tsv/probml/probml_model_predictions.tsv",
        "sheet_name": "probml_model_predictions",
        "required": False,
    },
    {
        "input_file": "results/tsv/probml/probml_failures.tsv",
        "sheet_name": "probml_failures",
        "required": False,
    },
    {
        "input_file": "results/tsv/probml/probml_run_metadata.tsv",
        "sheet_name": "probml_metadata",
        "required": False,
    },
]


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required file absent: {path}")


def load_binary_matrix(path: Path, module_name: str) -> pd.DataFrame:
    """
    Load and validate a binary TSV matrix.
    Prefix feature columns with 'module_name__'.
    """
    require_file(path)
    df = pd.read_csv(path, sep="\t")

    if "genome_id" not in df.columns:
        raise ValueError(f"Column 'genome_id' absent in {path}")
    if df["genome_id"].isna().any():
        raise ValueError(f"Missing genome_id values in {path}")
    if df["genome_id"].duplicated().any():
        dupes = df.loc[df["genome_id"].duplicated(), "genome_id"].tolist()
        raise ValueError(f"Duplicate genome_id in {path}: {dupes}")

    df["genome_id"] = df["genome_id"].astype(str)
    feature_cols = [c for c in df.columns if c != "genome_id"]

    for col in feature_cols:
        values = set(df[col].dropna().astype(str))
        non_binary = values - {"0", "1", "0.0", "1.0"}
        if non_binary:
            raise ValueError(
                f"Non-binary values in {path}, column '{col}': {sorted(non_binary)}"
            )
        df[col] = pd.to_numeric(df[col], errors="raise").fillna(0).astype(int)

    rename_map = {col: f"{module_name}__{col}" for col in feature_cols}
    df = df.rename(columns=rename_map)
    ordered = ["genome_id"] + sorted([c for c in df.columns if c != "genome_id"])
    return df[ordered]


def build_feature_catalog(
    module_tables: dict,
    active_specs: list,
) -> pd.DataFrame:
    rows = []
    for spec in active_specs:
        mn = spec["module_name"]
        df = module_tables.get(mn)
        if df is None:
            continue
        for col in df.columns:
            if col == "genome_id":
                continue
            original = col.split("__", 1)[1] if "__" in col else col
            rows.append({
                "module_name":           mn,
                "final_feature_name":    col,
                "original_feature_name": original,
            })
    if not rows:
        return pd.DataFrame(
            columns=["module_name", "final_feature_name", "original_feature_name"]
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["module_name", "original_feature_name"])
        .reset_index(drop=True)
    )


def build_module_summary(
    module_tables: dict,
    active_specs: list,
) -> pd.DataFrame:
    all_genomes = sorted(
        set().union(*[set(df["genome_id"].tolist()) for df in module_tables.values()])
    )
    summary = pd.DataFrame({"genome_id": all_genomes})

    for spec in active_specs:
        mn        = spec["module_name"]
        count_col = spec["count_column"]
        df = module_tables.get(mn)
        if df is None:
            continue
        feature_cols = [c for c in df.columns if c != "genome_id"]
        tmp = df[["genome_id"]].copy()
        tmp[count_col] = df[feature_cols].sum(axis=1).astype(int) if feature_cols else 0
        summary = summary.merge(tmp, on="genome_id", how="left")

    count_cols = [
        spec["count_column"]
        for spec in active_specs
        if spec["module_name"] in module_tables
    ]
    for col in count_cols:
        if col in summary.columns:
            summary[col] = summary[col].fillna(0).astype(int)

    present_counts = [c for c in count_cols if c in summary.columns]
    summary["n_total_features"] = summary[present_counts].sum(axis=1).astype(int)

    return summary[["genome_id"] + present_counts + ["n_total_features"]]


def merge_all_matrices(
    module_tables: dict,
    active_specs: list,
) -> pd.DataFrame:
    tables = [
        module_tables[spec["module_name"]]
        for spec in active_specs
        if spec["module_name"] in module_tables
    ]
    if not tables:
        return pd.DataFrame(columns=["genome_id"])

    merged = reduce(
        lambda left, right: pd.merge(left, right, on="genome_id", how="outer"),
        tables,
    )
    merged = merged.fillna(0)
    for col in merged.columns:
        if col != "genome_id":
            merged[col] = pd.to_numeric(merged[col], errors="raise").astype(int)

    ordered = ["genome_id"] + sorted([c for c in merged.columns if c != "genome_id"])
    return merged[ordered]



def _clean_sheet_token(value: object) -> str:
    """Clean a label to produce a robust Excel sheet name."""
    if value is None or pd.isna(value):
        text = ""
    else:
        text = str(value).strip()
    text = re.sub(r"[\\/*?:\[\]]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_ .")
    return text or "sheet"


def _unique_sheet_name(base: str, used_names: set) -> str:
    """Return a unique Excel sheet name limited to 31 characters."""
    cleaned = _clean_sheet_token(base)
    max_len = 31
    candidate = cleaned[:max_len]
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    idx = 2
    while True:
        suffix = f"_{idx}"
        candidate = f"{cleaned[:max_len - len(suffix)]}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        idx += 1


def _read_optional_sheet(
    path: Path,
    sheet_name: str,
    warnings: list,
) -> pd.DataFrame | None:
    """Load an optional TSV sheet. Return None when absent."""
    if not path.is_file():
        warnings.append(
            f"[WARN] Optional sheet '{sheet_name}' skipped (file absent): {path}"
        )
        return None
    try:
        return pd.read_csv(path, sep="\t")
    except Exception as exc:
        warnings.append(
            f"[WARN] Optional sheet '{sheet_name}' skipped (read error): {exc}"
        )
        return None


def _resolve_probiosml_category_path(
    raw_value: object,
    pipeline_root: Path,
    category_dir: Path,
) -> Path | None:
    """
    Convert a path into a usable Path object.

    The paths in 00_split_index.tsv can be absolute or relative depending on
    the version of the split script. Relative paths beginning with
    'results/' are resolved against pipeline_root. Others are resolved
    against the by_category directory.
    """
    if raw_value is None or pd.isna(raw_value):
        return None
    raw_text = str(raw_value).strip()
    if not raw_text:
        return None

    raw_path = Path(raw_text)
    if raw_path.is_absolute():
        return raw_path

    if raw_text.startswith("results/") or raw_text.startswith("results\\"):
        return pipeline_root / raw_path

    return category_dir / raw_path


def load_configured_extra_sheets(
    pipeline_root: Path,
    warnings: list,
    used_sheet_names: set,
) -> dict:
    """
    Load the auxiliary tables explicitly declared in EXTRA_SHEET_SPECS.
    These tables do not modify the final binary matrix.
    """
    extra_sheets = {}
    for spec in EXTRA_SHEET_SPECS:
        path = pipeline_root / spec["input_file"]
        requested_sheet_name = spec["sheet_name"]
        required = spec.get("required", False)

        if not path.is_file():
            if required:
                raise FileNotFoundError(
                    f"Required file absent for sheet '{requested_sheet_name}': {path}"
                )
            warnings.append(
                f"[WARN] Optional sheet '{requested_sheet_name}' skipped (file absent): {path}"
            )
            continue

        try:
            sheet_name = _unique_sheet_name(requested_sheet_name, used_sheet_names)
            extra_sheets[sheet_name] = pd.read_csv(path, sep="\t")
            print(
                f"[INFO] Optional sheet '{sheet_name}' loaded: {path}",
                flush=True,
            )
        except Exception as exc:
            if required:
                raise
            warnings.append(
                f"[WARN] Optional sheet '{requested_sheet_name}' skipped (read error): {exc}"
            )

    return extra_sheets


def load_probiosml_category_sheets(
    pipeline_root: Path,
    warnings: list,
    used_sheet_names: set,
) -> dict:
    """
    Add the sheets derived from the ProbioSML split to the final workbook.

    Main expected input:
      results/tsv/probiosml/by_category/00_split_index.tsv

    The sheets are added only to the final Excel workbook. They are
    never integrated into final_feature_matrix.tsv, to avoid duplicating
    the columns already represented by probiosml_presence_absence_binary.tsv.
    """
    extra_sheets = {}
    category_dir = pipeline_root / "results" / "tsv" / "probiosml" / "by_category"
    split_index_path = category_dir / "00_split_index.tsv"

    if not split_index_path.is_file():
        warnings.append(
            f"[WARN] ProbioSML per-category sheets skipped (index absent): {split_index_path}"
        )
        return extra_sheets

    try:
        split_index = pd.read_csv(split_index_path, sep="\t")
    except Exception as exc:
        warnings.append(
            f"[WARN] ProbioSML per-category sheets skipped (index read error): {exc}"
        )
        return extra_sheets

    index_sheet = _unique_sheet_name("probiosml_cat_index", used_sheet_names)
    extra_sheets[index_sheet] = split_index
    print(
        f"[INFO] ProbioSML categories sheet '{index_sheet}' loaded: {split_index_path}",
        flush=True,
    )

    for static_file, requested_sheet in [
        (category_dir / "00_mapping_used.tsv", "probiosml_cat_mapping"),
        (category_dir / "00_unmapped_markers.tsv", "probiosml_cat_unmapped"),
    ]:
        df = _read_optional_sheet(static_file, requested_sheet, warnings)
        if df is not None:
            sheet_name = _unique_sheet_name(requested_sheet, used_sheet_names)
            extra_sheets[sheet_name] = df
            print(
                f"[INFO] ProbioSML categories sheet '{sheet_name}' loaded: {static_file}",
                flush=True,
            )

    required_columns = {"category", "safe_category_name"}
    missing = required_columns - set(split_index.columns)
    if missing:
        warnings.append(
            f"[WARN] ProbioSML per-category sheets skipped: columns absent in 00_split_index.tsv: {sorted(missing)}"
        )
        return extra_sheets

    file_columns = [
        ("binary_file", "bin"),
        ("summary_file", "sum"),
        ("detail_file", "det"),
        ("mapping_file", "map"),
    ]

    for _, row in split_index.iterrows():
        safe_category = _clean_sheet_token(row.get("safe_category_name", row.get("category", "category")))
        safe_category = safe_category[:20]

        for file_col, suffix in file_columns:
            if file_col not in split_index.columns:
                continue
            path = _resolve_probiosml_category_path(row.get(file_col), pipeline_root, category_dir)
            if path is None:
                continue
            if not path.is_file():
                warnings.append(
                    f"[WARN] ProbioSML category sheet skipped (file absent): {path}"
                )
                continue

            requested_sheet = f"pSML_{safe_category}_{suffix}"
            sheet_name = _unique_sheet_name(requested_sheet, used_sheet_names)
            try:
                extra_sheets[sheet_name] = pd.read_csv(path, sep="\t")
                print(
                    f"[INFO] ProbioSML category sheet '{sheet_name}' loaded: {path}",
                    flush=True,
                )
            except Exception as exc:
                warnings.append(
                    f"[WARN] ProbioSML category sheet '{sheet_name}' skipped (read error): {exc}"
                )

    return extra_sheets


def load_extra_sheets(
    pipeline_root: Path,
    warnings: list,
    used_sheet_names: set,
) -> dict:
    """
    Load all auxiliary sheets of the final workbook.

    This function adds:
      - the ProbML auxiliary sheets if the TSV files exist;
      - the ProbioSML per-category sheets if the by_category split exists.

    No auxiliary sheet modifies the final TSV matrix.
    """
    extra_sheets = {}
    extra_sheets.update(
        load_configured_extra_sheets(pipeline_root, warnings, used_sheet_names)
    )
    extra_sheets.update(
        load_probiosml_category_sheets(pipeline_root, warnings, used_sheet_names)
    )
    return extra_sheets


def write_outputs(
    raw_module_tables: dict,
    extra_sheets: dict,
    final_matrix: pd.DataFrame,
    module_summary: pd.DataFrame,
    feature_catalog: pd.DataFrame,
    active_specs: list,
    output_tsv_dir: Path,
    output_xlsx_dir: Path,
) -> None:
    final_matrix.to_csv(   output_tsv_dir / "final_feature_matrix.tsv",   sep="\t", index=False)
    module_summary.to_csv( output_tsv_dir / "final_module_summary.tsv",   sep="\t", index=False)
    feature_catalog.to_csv(output_tsv_dir / "final_feature_catalog.tsv",  sep="\t", index=False)

    workbook = output_xlsx_dir / "probiogenomic_screening_results.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        for spec in active_specs:
            mn = spec["module_name"]
            raw = raw_module_tables.get(mn)
            if raw is None:
                continue
            raw.to_excel(writer, sheet_name=spec["sheet_name"], index=False)

        for sheet_name, df in extra_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

        final_matrix.to_excel(   writer, sheet_name="final_matrix",    index=False)
        module_summary.to_excel( writer, sheet_name="module_summary",  index=False)
        feature_catalog.to_excel(writer, sheet_name="feature_catalog", index=False)

    n_feat = len([c for c in final_matrix.columns if c != "genome_id"])
    n_geno = len(final_matrix)
    print("Final consolidation completed.", flush=True)
    print(f"Final matrix: {n_geno} genomes x {n_feat} features", flush=True)
    print(f"TSV final      : {output_tsv_dir / 'final_feature_matrix.tsv'}", flush=True)
    print(f"XLSX workbook  : {workbook}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Final consolidation of the probiogenomic pipeline."
    )
    parser.add_argument("--pipeline-root",   required=True)
    parser.add_argument("--output-tsv-dir",  required=True)
    parser.add_argument("--output-xlsx-dir", required=True)
    parser.add_argument(
        "--mode", default="",
        help="Execution mode (LIGHT/STANDARD/FULL). When set, the modules that "
             "the mode is expected to produce are enforced as required.",
    )
    args = parser.parse_args()

    pipeline_root   = Path(args.pipeline_root).resolve()
    output_tsv_dir  = Path(args.output_tsv_dir).resolve()
    output_xlsx_dir = Path(args.output_xlsx_dir).resolve()
    mode            = (args.mode or "").strip().upper()
    mode_required   = MODE_REQUIRED_MODULES.get(mode, set())
    if mode:
        print(f"[INFO] Consolidation mode: {mode} "
              f"(mode-required modules: {sorted(mode_required) if mode_required else 'none beyond base'})",
              flush=True)

    safe_mkdir(output_tsv_dir)
    safe_mkdir(output_xlsx_dir)

    raw_module_tables:      dict = {}
    prefixed_module_tables: dict = {}
    active_specs:           list = []
    warnings:               list = []

    for spec in MODULE_SPECS:
        input_path = pipeline_root / spec["input_file"]
        mn         = spec["module_name"]
        required   = spec.get("required", True) or (mn in mode_required)

        if not input_path.is_file():
            if required:
                why = "required by mode " + mode if mn in mode_required else "required"
                raise FileNotFoundError(
                    f"Module '{mn}' is {why} but its output is absent: {input_path}"
                )
            warnings.append(
                f"[WARN] Module '{mn}' skipped (file absent): {input_path}"
            )
            continue

        print(f"[INFO] Loading '{mn}' ...", flush=True)
        try:
            raw_df = pd.read_csv(input_path, sep="\t")
            if "genome_id" not in raw_df.columns:
                raise ValueError(f"'genome_id' absent in {input_path}")

            raw_module_tables[mn]      = raw_df
            prefixed_module_tables[mn] = load_binary_matrix(input_path, mn)
            active_specs.append(spec)

            n_feat = len([c for c in raw_df.columns if c != "genome_id"])
            n_geno = len(raw_df)
            print(f"[INFO]   -> {n_geno} genomes, {n_feat} features", flush=True)

        except Exception as exc:
            if required:
                raise
            warnings.append(
                f"[WARN] Module '{mn}' skipped (read error): {exc}"
            )
            continue

    used_sheet_names = {spec["sheet_name"] for spec in active_specs}
    used_sheet_names.update({"final_matrix", "module_summary", "feature_catalog"})
    extra_sheets = load_extra_sheets(pipeline_root, warnings, used_sheet_names)

    if warnings:
        print("", flush=True)
        for w in warnings:
            print(w, flush=True)
        print("", flush=True)

    if not active_specs:
        raise RuntimeError("No module loaded. Consolidation impossible.")

    active_names = [s["module_name"] for s in active_specs]
    print(
        f"[INFO] Active modules ({len(active_specs)}): {', '.join(active_names)}",
        flush=True,
    )

    feature_catalog = build_feature_catalog(prefixed_module_tables, active_specs)
    module_summary  = build_module_summary(prefixed_module_tables,  active_specs)
    final_matrix    = merge_all_matrices(prefixed_module_tables,    active_specs)

    write_outputs(
        raw_module_tables,
        extra_sheets,
        final_matrix,
        module_summary,
        feature_catalog,
        active_specs,
        output_tsv_dir,
        output_xlsx_dir,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        sys.exit(1)

