#!/usr/bin/env python3
"""
Module 16 - ProbML genome classifier.

This module runs the 12 ProbML XGB_LD3_IITMd models distributed with
MLG_Dashboard on nucleotide genome assemblies. It is designed as an optional
external comparator for the probiogenomic pipeline and FCE scoring step.

Inputs:
  - pipeline manifest with normalized_fna paths, or a directory of nucleotide
    FASTA assemblies
  - MLG_Dashboard models directory containing Model1.json to Model12.json and
    TF_Model1.txt to TF_Model12.txt

Outputs:
  - probml_presence_absence_binary.tsv, compatible with final consolidation
  - probml_model_predictions.tsv, one row per genome and model
  - probml_summary_by_genome.tsv, one row per genome
  - probml_failures.tsv
  - probml_results.xlsx when openpyxl is installed
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Iterable


MODEL_SET_BY_ID = {
    1: 'RS4658',
    2: 'RS4658',
    3: 'RS4658',
    4: 'RS4658',
    5: 'RS4658',
    6: 'RS4658',
    7: 'RS6331',
    8: 'RS6331',
    9: 'RS6331',
    10: 'RS6331',
    11: 'RS6331',
    12: 'RS6331',
}

BASE_TO_BITS = {
    'A': 0,
    'C': 1,
    'G': 2,
    'T': 3,
}

FASTA_EXTENSIONS = (
    '.fna',
    '.fa',
    '.fasta',
    '.fna.gz',
    '.fa.gz',
    '.fasta.gz',
)


@dataclass(frozen=True)
class InputGenome:
    genome_id: str
    fasta_path: Path
    source: str


@dataclass(frozen=True)
class ModelSpec:
    model_id: int
    model_set: str
    model_path: Path
    feature_path: Path
    features: list[str]
    model_sha256: str
    feature_sha256: str
    xgboost_json_version: str
    xgboost_objective: str


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def clean_text(value: object) -> str:
    if value is None:
        return ''
    return str(value).strip()


def sanitize_genome_id(name: str) -> str:
    cleaned = re.sub(r'\.(fna|fa|fasta)(\.gz)?$', '', name, flags=re.IGNORECASE)
    cleaned = re.sub(r'[^A-Za-z0-9._-]+', '_', cleaned)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned or 'genome'


def parse_model_selection(value: str) -> list[int]:
    if value.strip().lower() == 'all':
        return list(range(1, 13))

    selected: list[int] = []
    for part in value.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            model_id = int(part)
        except ValueError as exc:
            raise ValueError(f'Invalid model id: {part}') from exc
        if model_id < 1 or model_id > 12:
            raise ValueError(f'Model id out of range 1..12: {model_id}')
        if model_id not in selected:
            selected.append(model_id)

    if not selected:
        raise ValueError('No ProbML model selected.')
    return selected


def load_feature_file(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(f'Feature file not found: {path}')
    features = path.read_text(encoding='utf-8', errors='replace').split()
    if not features:
        raise ValueError(f'Feature file is empty: {path}')
    invalid = [f for f in features if not set(f).issubset({'A', 'C', 'G', 'T'})]
    if invalid:
        preview = ', '.join(invalid[:5])
        raise ValueError(f'Invalid non ACGT features in {path}: {preview}')
    return features


def load_model_specs(models_dir: Path, model_ids: list[int]) -> list[ModelSpec]:
    specs: list[ModelSpec] = []

    for model_id in model_ids:
        model_path = models_dir / f'Model{model_id}.json'
        feature_path = models_dir / f'TF_Model{model_id}.txt'

        if not model_path.is_file():
            raise FileNotFoundError(f'ProbML model not found: {model_path}')

        features = load_feature_file(feature_path)

        with open(model_path, 'r', encoding='utf-8', errors='replace') as handle:
            model_json = json.load(handle)

        learner = model_json.get('learner', {})
        json_features = learner.get('feature_names', [])
        objective = learner.get('objective', {}).get('name', '')
        version = '.'.join(str(x) for x in model_json.get('version', []))

        if json_features and list(json_features) != features:
            if set(json_features) != set(features):
                raise ValueError(
                    f'Feature mismatch between {model_path.name} and {feature_path.name}'
                )
            features = list(json_features)

        specs.append(
            ModelSpec(
                model_id=model_id,
                model_set=MODEL_SET_BY_ID[model_id],
                model_path=model_path,
                feature_path=feature_path,
                features=features,
                model_sha256=sha256_file(model_path),
                feature_sha256=sha256_file(feature_path),
                xgboost_json_version=version,
                xgboost_objective=objective,
            )
        )

    return specs


def load_manifest(path: Path) -> tuple[list[InputGenome], list[dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(f'Manifest not found: {path}')

    genomes: list[InputGenome] = []
    failures: list[dict[str, str]] = []

    with open(path, 'r', encoding='utf-8', errors='replace', newline='') as handle:
        reader = csv.DictReader(handle, delimiter='\t')
        if reader.fieldnames is None:
            raise ValueError(f'Manifest has no header: {path}')

        required = {'genome_id', 'normalized_fna'}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f'Missing required manifest columns: {sorted(missing)}')

        seen: set[str] = set()
        for row in reader:
            genome_id = clean_text(row.get('genome_id'))
            fasta_raw = clean_text(row.get('normalized_fna'))
            status = clean_text(row.get('status'))

            if not genome_id:
                failures.append({
                    'genome_id': '',
                    'input_fasta': fasta_raw,
                    'status': 'FAILED',
                    'message': 'Missing genome_id in manifest.',
                })
                continue

            if genome_id in seen:
                raise ValueError(f'Duplicated genome_id in manifest: {genome_id}')
            seen.add(genome_id)

            if status and status != 'OK':
                failures.append({
                    'genome_id': genome_id,
                    'input_fasta': fasta_raw,
                    'status': 'FAILED',
                    'message': f'Manifest status is {status}.',
                })
                continue

            if not fasta_raw:
                failures.append({
                    'genome_id': genome_id,
                    'input_fasta': '',
                    'status': 'FAILED',
                    'message': 'normalized_fna is empty.',
                })
                continue

            fasta_path = Path(fasta_raw)
            if not fasta_path.is_file():
                failures.append({
                    'genome_id': genome_id,
                    'input_fasta': str(fasta_path),
                    'status': 'FAILED',
                    'message': 'normalized_fna file does not exist.',
                })
                continue

            genomes.append(InputGenome(genome_id, fasta_path, 'manifest'))

    if not genomes and not failures:
        raise ValueError(f'No genome rows found in manifest: {path}')

    return genomes, failures


def load_input_dir(path: Path) -> tuple[list[InputGenome], list[dict[str, str]]]:
    if not path.is_dir():
        raise FileNotFoundError(f'Input directory not found: {path}')

    files: list[Path] = []
    for item in sorted(path.iterdir()):
        if not item.is_file():
            continue
        lower = item.name.lower()
        if any(lower.endswith(ext) for ext in FASTA_EXTENSIONS):
            files.append(item)

    if not files:
        raise ValueError(f'No nucleotide FASTA files found in: {path}')

    genomes: list[InputGenome] = []
    seen: set[str] = set()
    for file_path in files:
        genome_id = sanitize_genome_id(file_path.name)
        if genome_id in seen:
            raise ValueError(f'Duplicated sanitized genome_id: {genome_id}')
        seen.add(genome_id)
        genomes.append(InputGenome(genome_id, file_path.resolve(), 'input_dir'))

    return genomes, []


def encode_kmer(kmer: str) -> int:
    code = 0
    for base in kmer:
        code = (code << 2) | BASE_TO_BITS[base]
    return code


def compile_selected_codes(features: Iterable[str]) -> dict[int, dict[int, str]]:
    selected: dict[int, dict[int, str]] = {}
    for feature in sorted(set(features), key=lambda x: (len(x), x)):
        k = len(feature)
        selected.setdefault(k, {})[encode_kmer(feature)] = feature
    return selected


def count_selected_kmers(
    fasta_path: Path,
    union_features: list[str],
    selected_codes: dict[int, dict[int, str]],
) -> dict[str, int]:
    counts = {feature: 0 for feature in union_features}
    k_values = sorted(selected_codes)
    masks = {k: (1 << (2 * k)) - 1 for k in k_values}
    rolling = {k: 0 for k in k_values}
    valid_len = 0
    saw_sequence = False

    opener = gzip.open if fasta_path.name.lower().endswith('.gz') else open

    with opener(fasta_path, 'rt', encoding='utf-8', errors='replace') as handle:
        for raw_line in handle:
            if raw_line.startswith('>'):
                rolling = {k: 0 for k in k_values}
                valid_len = 0
                continue

            line = raw_line.strip().upper()
            if not line:
                continue
            saw_sequence = True

            for base in line:
                value = BASE_TO_BITS.get(base)
                if value is None:
                    valid_len = 0
                    rolling = {k: 0 for k in k_values}
                    continue

                valid_len += 1
                for k in k_values:
                    rolling[k] = ((rolling[k] << 2) | value) & masks[k]
                    if valid_len >= k:
                        feature = selected_codes[k].get(rolling[k])
                        if feature is not None:
                            counts[feature] += 1

    if not saw_sequence:
        raise ValueError(f'No sequence found in FASTA file: {fasta_path}')

    return counts


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def round_float(value: float | str, digits: int = 6) -> str:
    if value == '':
        return ''
    return f'{float(value):.{digits}f}'


def write_tsv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, '') for col in columns})


def write_workbook(
    path: Path,
    sheets: list[tuple[str, list[dict[str, object]], list[str]]],
) -> bool:
    try:
        from openpyxl import Workbook
    except ImportError:
        return False

    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    for sheet_name, rows, columns in sheets:
        worksheet = workbook.create_sheet(title=sheet_name[:31])
        worksheet.append(columns)
        for row in rows:
            worksheet.append([row.get(col, '') for col in columns])

    workbook.save(path)
    return True


def require_prediction_dependencies():
    try:
        import numpy as np
        import xgboost as xgb
    except ImportError as exc:
        raise RuntimeError(
            'Missing ProbML prediction dependency. Install numpy and xgboost '
            'in the ProbML conda environment.'
        ) from exc

    # ProbML model JSON files are saved with XGBoost JSON format version [2, 0, 3].
    # XGBoost < 2.0 cannot read them and will silently produce wrong predictions
    # or raise a confusing error. Fail early with a clear message.
    try:
        xgb_version = tuple(int(part) for part in xgb.__version__.split('.')[:2])
    except (AttributeError, ValueError):
        xgb_version = (0, 0)

    if xgb_version < (2, 0):
        raise RuntimeError(
            f'XGBoost {xgb.__version__} is too old for ProbML model JSON v[2,0,3]. '
            'Install XGBoost >= 2.0 in the ProbML conda environment '
            '(pip install --upgrade "xgboost>=2.0").'
        )

    print(f'[INFO] numpy {np.__version__}, xgboost {xgb.__version__} loaded.', flush=True)
    return np, xgb


def predict_with_models(
    model_specs: list[ModelSpec],
    genomes: list[InputGenome],
    counts_by_genome: dict[str, dict[str, int]],
    threshold: float,
    threads: int,
) -> list[dict[str, object]]:
    np, xgb = require_prediction_dependencies()
    prediction_rows: list[dict[str, object]] = []

    # Build the union of features across all selected models.
    # We construct the count matrix ONCE for the union, then slice per model.
    # This avoids rebuilding the same large numpy array 12 times.
    union_features = sorted(
        {feature for spec in model_specs for feature in spec.features},
        key=lambda x: (len(x), x),
    )
    union_index = {feature: idx for idx, feature in enumerate(union_features)}

    print(
        f'[INFO] Building unified count matrix: {len(genomes)} genomes x '
        f'{len(union_features)} features',
        flush=True,
    )
    union_matrix = np.zeros((len(genomes), len(union_features)), dtype=np.float32)
    for row_idx, genome in enumerate(genomes):
        counts = counts_by_genome[genome.genome_id]
        for feature, count in counts.items():
            if count:
                col_idx = union_index.get(feature)
                if col_idx is not None:
                    union_matrix[row_idx, col_idx] = float(count)

    for spec_idx, spec in enumerate(model_specs, start=1):
        print(
            f'[INFO] [{spec_idx}/{len(model_specs)}] Loading Model{spec.model_id} '
            f'({spec.model_set}, {len(spec.features)} features)',
            flush=True,
        )
        booster = xgb.Booster(model_file=str(spec.model_path))
        booster.set_param({'nthread': max(1, int(threads))})

        # Slice the union matrix into the column order expected by this model.
        col_indices = [union_index[feature] for feature in spec.features]
        matrix = union_matrix[:, col_indices]

        dmatrix = xgb.DMatrix(matrix, feature_names=spec.features)
        raw_margins = booster.predict(dmatrix, output_margin=True, validate_features=True)

        for genome, raw_margin in zip(genomes, raw_margins):
            probiotic_probability = sigmoid(float(raw_margin))
            predicted_is_probiotic = int(probiotic_probability >= threshold)
            prediction_rows.append({
                'genome_id': genome.genome_id,
                'model_id': f'Model{spec.model_id}',
                'model_number': spec.model_id,
                'model_set': spec.model_set,
                'model_file': str(spec.model_path),
                'feature_file': str(spec.feature_path),
                'n_model_features': len(spec.features),
                'raw_margin': round_float(float(raw_margin)),
                'probiotic_probability': round_float(probiotic_probability),
                'non_probiotic_probability': round_float(1.0 - probiotic_probability),
                'prediction_threshold': threshold,
                'predicted_category': 'Probiotic' if predicted_is_probiotic else 'Non-probiotic',
                'predicted_binary_probiotic': predicted_is_probiotic,
            })

    return prediction_rows


def build_summary_and_binary(
    all_genome_ids: list[str],
    prediction_rows: list[dict[str, object]],
    failure_rows: list[dict[str, str]],
    model_count: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    predictions_by_genome: dict[str, list[dict[str, object]]] = {gid: [] for gid in all_genome_ids}
    for row in prediction_rows:
        predictions_by_genome.setdefault(str(row['genome_id']), []).append(row)

    failed_ids = {row['genome_id'] for row in failure_rows if row.get('genome_id')}

    summary_rows: list[dict[str, object]] = []
    binary_rows: list[dict[str, object]] = []

    for genome_id in all_genome_ids:
        rows = sorted(
            predictions_by_genome.get(genome_id, []),
            key=lambda row: int(row['model_number']),
        )

        if not rows:
            summary_rows.append({
                'genome_id': genome_id,
                'probml_status': 'FAILED' if genome_id in failed_ids else 'NO_PREDICTION',
                'n_models': 0,
                'n_probiotic_votes': 0,
                'n_non_probiotic_votes': 0,
                'n_rs4658_probiotic_votes': 0,
                'n_rs6331_probiotic_votes': 0,
                'vote_fraction_probiotic': '',
                'mean_probiotic_probability': '',
                'median_probiotic_probability': '',
                'min_probiotic_probability': '',
                'max_probiotic_probability': '',
                'sd_probiotic_probability': '',
                'majority_category': '',
                'consensus_category': 'prediction_failed',
            })
            base_binary = {
                'genome_id': genome_id,
                'unanimous_probiotic': 0,
                'majority_probiotic': 0,
                'any_probiotic_vote': 0,
                'discordant_prediction': 0,
                'unanimous_non_probiotic': 0,
                'rs4658_consensus_probiotic': 0,
                'rs6331_consensus_probiotic': 0,
                'rs_set_majority_disagreement': 0,
            }
            for model_id in range(1, 13):
                base_binary[f'model_{model_id:02d}_probiotic'] = 0
            binary_rows.append(base_binary)
            continue

        votes = [int(row['predicted_binary_probiotic']) for row in rows]
        probabilities = [float(row['probiotic_probability']) for row in rows]
        vote_sum = sum(votes)
        non_vote_sum = len(votes) - vote_sum
        rs4658_votes = sum(
            int(row['predicted_binary_probiotic'])
            for row in rows
            if row['model_set'] == 'RS4658'
        )
        rs6331_votes = sum(
            int(row['predicted_binary_probiotic'])
            for row in rows
            if row['model_set'] == 'RS6331'
        )

        if vote_sum == len(votes):
            consensus_category = 'probiotic_consensus_all_models'
        elif vote_sum == 0:
            consensus_category = 'non_probiotic_consensus_all_models'
        else:
            consensus_category = 'discordant_probml_prediction'

        majority_category = (
            'Probiotic'
            if vote_sum > (len(votes) / 2)
            else 'Non-probiotic'
        )

        rs4658_majority = rs4658_votes > 3
        rs6331_majority = rs6331_votes > 3

        summary_rows.append({
            'genome_id': genome_id,
            'probml_status': 'OK',
            'n_models': len(votes),
            'n_probiotic_votes': vote_sum,
            'n_non_probiotic_votes': non_vote_sum,
            'n_rs4658_probiotic_votes': rs4658_votes,
            'n_rs6331_probiotic_votes': rs6331_votes,
            'vote_fraction_probiotic': round_float(vote_sum / len(votes)),
            'mean_probiotic_probability': round_float(mean(probabilities)),
            'median_probiotic_probability': round_float(median(probabilities)),
            'min_probiotic_probability': round_float(min(probabilities)),
            'max_probiotic_probability': round_float(max(probabilities)),
            'sd_probiotic_probability': round_float(pstdev(probabilities) if len(probabilities) > 1 else 0.0),
            'majority_category': majority_category,
            'consensus_category': consensus_category,
        })

        base_binary = {
            'genome_id': genome_id,
            'unanimous_probiotic': int(vote_sum == model_count),
            'majority_probiotic': int(vote_sum > (len(votes) / 2)),
            'any_probiotic_vote': int(vote_sum > 0),
            'discordant_prediction': int(0 < vote_sum < len(votes)),
            'unanimous_non_probiotic': int(vote_sum == 0),
            'rs4658_consensus_probiotic': int(rs4658_votes == 6),
            'rs6331_consensus_probiotic': int(rs6331_votes == 6),
            'rs_set_majority_disagreement': int(rs4658_majority != rs6331_majority),
        }

        vote_by_model = {
            int(row['model_number']): int(row['predicted_binary_probiotic'])
            for row in rows
        }
        for model_id in range(1, 13):
            base_binary[f'model_{model_id:02d}_probiotic'] = vote_by_model.get(model_id, 0)
        binary_rows.append(base_binary)

    return summary_rows, binary_rows


def build_metadata_rows(
    args: argparse.Namespace,
    model_specs: list[ModelSpec],
    n_genomes_requested: int,
    n_genomes_predicted: int,
    n_failures: int,
    workbook_written: bool,
) -> list[dict[str, object]]:
    rows = [
        {'key': 'module_name', 'value': 'ProbML optional comparator module'},
        {'key': 'pipeline_root', 'value': str(Path(args.pipeline_root).resolve()) if args.pipeline_root else ''},
        {'key': 'manifest', 'value': str(Path(args.manifest).resolve()) if args.manifest else ''},
        {'key': 'input_dir', 'value': str(Path(args.input_dir).resolve()) if args.input_dir else ''},
        {'key': 'models_dir', 'value': str(Path(args.models_dir).resolve())},
        {'key': 'models_selected', 'value': ','.join(str(spec.model_id) for spec in model_specs)},
        {'key': 'prediction_threshold', 'value': args.threshold},
        {'key': 'n_genomes_requested', 'value': n_genomes_requested},
        {'key': 'n_genomes_predicted', 'value': n_genomes_predicted},
        {'key': 'n_failures', 'value': n_failures},
        {'key': 'workbook_written', 'value': int(workbook_written)},
        {'key': 'probml_paper', 'value': 'Orkkatteri Krishnan A, Mudgal LN, Soni V, Prakash T. 2025. DOI 10.1002/mnfr.70025'},
        {'key': 'mlg_dashboard_repository', 'value': 'https://github.com/sysbio-iitmandi/MLG_Dashboard'},
        {'key': 'implementation_note', 'value': 'This module fixes per-genome probability reporting and does not use ProbML as ground truth.'},
    ]

    for spec in model_specs:
        rows.extend([
            {'key': f'model_{spec.model_id:02d}_set', 'value': spec.model_set},
            {'key': f'model_{spec.model_id:02d}_features', 'value': len(spec.features)},
            {'key': f'model_{spec.model_id:02d}_objective', 'value': spec.xgboost_objective},
            {'key': f'model_{spec.model_id:02d}_json_version', 'value': spec.xgboost_json_version},
            {'key': f'model_{spec.model_id:02d}_sha256', 'value': spec.model_sha256},
            {'key': f'tf_model_{spec.model_id:02d}_sha256', 'value': spec.feature_sha256},
        ])

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Run the 12 ProbML XGBoost models on nucleotide genomes.'
    )
    parser.add_argument('--pipeline-root', default='')
    parser.add_argument('--manifest', default='')
    parser.add_argument('--input-dir', default='')
    parser.add_argument('--models-dir', required=True)
    parser.add_argument('--output-tsv-dir', required=True)
    parser.add_argument('--output-xlsx-dir', required=True)
    parser.add_argument('--models', default='all')
    parser.add_argument('--threshold', type=float, default=0.5)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--write-kmer-matrix', action='store_true')
    args = parser.parse_args()

    if not args.manifest and not args.input_dir:
        if args.pipeline_root:
            args.manifest = str(Path(args.pipeline_root) / 'work' / 'manifest' / 'input_manifest.tsv')
        else:
            raise ValueError('Provide --manifest, --input-dir, or --pipeline-root.')

    output_tsv_dir = Path(args.output_tsv_dir).resolve()
    output_xlsx_dir = Path(args.output_xlsx_dir).resolve()
    models_dir = Path(args.models_dir).resolve()
    safe_mkdir(output_tsv_dir)
    safe_mkdir(output_xlsx_dir)

    model_ids = parse_model_selection(args.models)
    model_specs = load_model_specs(models_dir, model_ids)
    union_features = sorted(
        {feature for spec in model_specs for feature in spec.features},
        key=lambda x: (len(x), x),
    )
    selected_codes = compile_selected_codes(union_features)

    if args.manifest:
        genomes, failure_rows = load_manifest(Path(args.manifest).resolve())
    else:
        genomes, failure_rows = load_input_dir(Path(args.input_dir).resolve())

    all_genome_ids = [genome.genome_id for genome in genomes] + [
        row['genome_id'] for row in failure_rows if row.get('genome_id')
    ]
    all_genome_ids = sorted(dict.fromkeys(all_genome_ids))

    print(f'[INFO] ProbML models loaded      : {len(model_specs)}', flush=True)
    print(f'[INFO] Selected k-mer features   : {len(union_features)}', flush=True)
    print(f'[INFO] Genomes ready for ProbML  : {len(genomes)}', flush=True)
    print(f'[INFO] Genomes failed pre-check  : {len(failure_rows)}', flush=True)

    counts_by_genome: dict[str, dict[str, int]] = {}
    count_failure_rows = list(failure_rows)
    valid_genomes: list[InputGenome] = []

    n_total = len(genomes)
    progress_interval = max(1, n_total // 20)  # ~20 progress lines total

    for index, genome in enumerate(genomes, start=1):
        if index == 1 or index == n_total or index % progress_interval == 0:
            print(
                f'[INFO] Counting selected k-mers {index}/{n_total}: {genome.genome_id}',
                flush=True,
            )
        try:
            counts_by_genome[genome.genome_id] = count_selected_kmers(
                genome.fasta_path,
                union_features,
                selected_codes,
            )
            valid_genomes.append(genome)
        except Exception as exc:
            count_failure_rows.append({
                'genome_id': genome.genome_id,
                'input_fasta': str(genome.fasta_path),
                'status': 'FAILED',
                'message': str(exc),
            })

    prediction_rows: list[dict[str, object]] = []
    if valid_genomes:
        prediction_rows = predict_with_models(
            model_specs,
            valid_genomes,
            counts_by_genome,
            args.threshold,
            args.threads,
        )

    summary_rows, binary_rows = build_summary_and_binary(
        all_genome_ids,
        prediction_rows,
        count_failure_rows,
        model_count=len(model_specs),
    )

    binary_columns = [
        'genome_id',
        'unanimous_probiotic',
        'majority_probiotic',
        'any_probiotic_vote',
        'discordant_prediction',
        'unanimous_non_probiotic',
        'rs4658_consensus_probiotic',
        'rs6331_consensus_probiotic',
        'rs_set_majority_disagreement',
    ] + [f'model_{model_id:02d}_probiotic' for model_id in range(1, 13)]

    prediction_columns = [
        'genome_id',
        'model_id',
        'model_number',
        'model_set',
        'model_file',
        'feature_file',
        'n_model_features',
        'raw_margin',
        'probiotic_probability',
        'non_probiotic_probability',
        'prediction_threshold',
        'predicted_category',
        'predicted_binary_probiotic',
    ]

    summary_columns = [
        'genome_id',
        'probml_status',
        'n_models',
        'n_probiotic_votes',
        'n_non_probiotic_votes',
        'n_rs4658_probiotic_votes',
        'n_rs6331_probiotic_votes',
        'vote_fraction_probiotic',
        'mean_probiotic_probability',
        'median_probiotic_probability',
        'min_probiotic_probability',
        'max_probiotic_probability',
        'sd_probiotic_probability',
        'majority_category',
        'consensus_category',
    ]

    failure_columns = ['genome_id', 'input_fasta', 'status', 'message']

    binary_path = output_tsv_dir / 'probml_presence_absence_binary.tsv'
    prediction_path = output_tsv_dir / 'probml_model_predictions.tsv'
    summary_path = output_tsv_dir / 'probml_summary_by_genome.tsv'
    failure_path = output_tsv_dir / 'probml_failures.tsv'
    metadata_path = output_tsv_dir / 'probml_run_metadata.tsv'

    write_tsv(binary_path, binary_rows, binary_columns)
    write_tsv(prediction_path, prediction_rows, prediction_columns)
    write_tsv(summary_path, summary_rows, summary_columns)
    write_tsv(failure_path, count_failure_rows, failure_columns)

    workbook_path = output_xlsx_dir / 'probml_results.xlsx'
    workbook_written = write_workbook(
        workbook_path,
        [
            ('probml_binary', binary_rows, binary_columns),
            ('model_predictions', prediction_rows, prediction_columns),
            ('summary_by_genome', summary_rows, summary_columns),
            ('failures', count_failure_rows, failure_columns),
        ],
    )

    metadata_rows = build_metadata_rows(
        args,
        model_specs,
        n_genomes_requested=len(all_genome_ids),
        n_genomes_predicted=len(valid_genomes),
        n_failures=len(count_failure_rows),
        workbook_written=workbook_written,
    )
    metadata_columns = ['key', 'value']
    write_tsv(metadata_path, metadata_rows, metadata_columns)

    if args.write_kmer_matrix:
        kmer_path = output_tsv_dir / 'probml_selected_kmer_counts.tsv'
        kmer_columns = ['genome_id'] + union_features
        kmer_rows = [
            {'genome_id': genome.genome_id, **counts_by_genome[genome.genome_id]}
            for genome in valid_genomes
        ]
        write_tsv(kmer_path, kmer_rows, kmer_columns)
        print(f'[INFO] Selected k-mer matrix    : {kmer_path}', flush=True)

    print(f'[INFO] Binary matrix            : {binary_path}', flush=True)
    print(f'[INFO] Model predictions        : {prediction_path}', flush=True)
    print(f'[INFO] Summary by genome        : {summary_path}', flush=True)
    print(f'[INFO] Failures                 : {failure_path}', flush=True)
    print(f'[INFO] Run metadata             : {metadata_path}', flush=True)
    if workbook_written:
        print(f'[INFO] Workbook                 : {workbook_path}', flush=True)
    else:
        print('[WARN] openpyxl is not installed. XLSX workbook skipped.', flush=True)

    # Classification distribution summary
    consensus_counts: dict[str, int] = {}
    for row in summary_rows:
        category = str(row.get('consensus_category', '')) or 'unknown'
        consensus_counts[category] = consensus_counts.get(category, 0) + 1

    print('[INFO] ProbML classification distribution:', flush=True)
    for category in sorted(consensus_counts):
        n = consensus_counts[category]
        pct = 100.0 * n / max(1, len(summary_rows))
        print(f'[INFO]   {category:<40s} : {n:5d} ({pct:5.1f} %)', flush=True)

    print('[INFO] ProbML module completed.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'[FATAL] {exc}', file=sys.stderr)
        sys.exit(1)

