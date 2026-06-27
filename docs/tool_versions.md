# Tool versions

Verified on the target Linux host (gma-Inspiron-15-3567, Linux 6.17.0-14-generic
x86_64) from `pipeline_V4.txt` generated 2026-05-12 and live terminal verification
2026-06-13.

## Core environment (probio_core)

| Tool | Version | Conda channel |
|---|---|---|
| Python | 3.11.9 | conda-forge |
| Prodigal | 2.6.3 | bioconda |
| ABRicate | 1.2.0 | bioconda |
| HMMER (hmmscan/hmmsearch) | 3.4 (Aug 2023) | bioconda |
| DIAMOND | 2.1.10 | bioconda |
| MinCED | 0.4.2 | bioconda |
| ISEScan | 1.7.3 | bioconda |
| BLAST | 2.16.0 | bioconda |
| Biopython | 1.86 | conda-forge |
| pandas | 3.0.1 | conda-forge |
| numpy | 2.4.2 | conda-forge |
| openpyxl | 3.1.5 | conda-forge |
| xlsxwriter | 3.2.9 | conda-forge |
| scipy | 1.17.1 | conda-forge |

## Dedicated environments

| Environment | Tool | Version | Notes |
|---|---|---|---|
| antismash_env | antiSMASH | 8.0.4 | bioconda, Python 3.11.15 |
| antismash_env | DIAMOND | 2.1.24 | bioconda |
| antismash_env | BLAST | 2.17.0 | bioconda |
| mob_suite_env | MOB-suite (mob_recon) | 3.1.9 | bioconda, Python 3.11.9 |
| mob_suite_env | BLAST | 2.15.0 | bioconda |
| genomad_env | geNomad | 1.12.0 | bioconda, Python 3.10.20 |
| genomad_env | XGBoost | 3.2.0 | conda-forge |
| bagel5_env | BLAST | 2.17.0 | bioconda, Python 3.10.20 |
| bagel5_env | DIAMOND | 2.1.24 | bioconda |
| bagel5_env | HMMER | 3.4 | bioconda |
| bagel5_env | Prodigal | 2.6.3 | bioconda |
| epssmash_env | DIAMOND | 2.1.24 | bioconda, Python 3.9.23 |
| epssmash_env | HMMER | 3.4 | bioconda |
| epssmash_env | Prodigal | 2.6.3 | bioconda |
| probml_env | XGBoost | 3.2.0 | pypi, Python 3.11.15 |
| probml_env | numpy | 2.4.4 | pypi |
| probml_env | openpyxl | 3.1.5 | pypi |

## Locally integrated tools

| Tool | Version | Location |
|---|---|---|
| BAGEL5 | local integration (no standalone semantic version) | external_tools/BAGEL5/src/data/bagel5/scripts/bagel5.py |
| epsSMASH | 1.2.1 (based on antiSMASH 7.dev) | conda/envs/antismash_dependencies/bin/epsSMASH |

## Source

Primary evidence: `pipeline_V4.txt` (generated 2026-05-12, host
gma-Inspiron-15-3567). Conda package lists extracted with
`conda list -p ENV | egrep PATTERN`. Direct version commands confirmed for
Prodigal V2.6.3, DIAMOND 2.1.10, HMMER 3.4, ABRicate 1.2.0, ISEScan 1.7.3,
MOB-suite 3.1.9, antiSMASH 8.0.4, geNomad 1.12.0.
