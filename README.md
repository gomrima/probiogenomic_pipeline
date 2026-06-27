# Probiogenomic Pipeline V4 final repository

This repository contains the finalized source layout for Probiogenomic Pipeline V4. It is a portable source package prepared from the read-only source folder `scripts_probiogenomic_pipeline`.

The final pipeline preserves the source analytical logic while changing the execution order, file numbering, path handling, checkpoint behavior, logging, and documentation.

## Main entry point

Prepare the module 10 marker resources once before any LIGHT, STANDARD, or FULL
run:

```bash
bash scripts/01_run_prepare_marker_resources.sh
```

This setup step builds `db/compiled/diamond/all_markers_for_diamond.dmnd`,
presses `db/compiled/hmm/all_markers.hmm`, copies `markers_DB.xlsx` into
`db/compiled/`, and writes marker metadata used by module 10.

The marker database is not bundled with this code repository. Download it from
Zenodo (DOI 10.5281/zenodo.20699785, https://doi.org/10.5281/zenodo.20699785),
unzip it into `db/`, then run the setup step above. The database is released
under the Creative Commons Attribution 4.0 International license (CC-BY-4.0) and
is published as Gomri et al. 2026 (see `docs/marker_database_attribution.md`).

```bash
bash scripts/run_pipeline_final.sh --input_dir /path/to/genomes --mode FULL
```

Resume an interrupted run (resume requires `--run_name`, the name of the
interrupted run):

```bash
bash scripts/run_pipeline_final.sh --mode FULL --resume --run_name my_run
```

## Execution modes

LIGHT:

```text
00 -> 02 -> 03 -> 04 -> 05 -> 10 -> 12 -> 17
```

STANDARD:

```text
00 -> 02 -> 03 -> 04 -> 05 -> 06 -> 07 -> 10 -> 12 -> 17
```

FULL:

```text
00 -> 02 -> 03 -> 04 -> 05 -> 06 -> 07 -> 08 -> 09 -> 10 -> 11 -> 12 -> 13 -> 14 -> 15 -> 16 -> 17
```

## Input formats

The pipeline accepts nucleotide genome assemblies in FASTA form only: `.fna`, `.fa`, `.fasta`, `.fas`, optionally gzip-compressed (`.gz`). Protein FASTA (`.faa`), GenBank, and annotation files are refused at input, because the safety and mobility modules need nucleotide sequence. See `docs/user_manual.md`.

## Authorship and rights

The pipeline is owned and authored by Dr. Mohamed Amine Gomri (Associate Professor, Department of Biotechnology, INATAA, University of Constantine 1 Frères Mentouri, Constantine, Algeria; ORCID 0000-0003-0347-3412; https://github.com/gomrima). The MIT license in `LICENSE` holds the copyright in his name and covers the pipeline code only.

The core marker database used by module 10 is a separate scientific work (Gomri et al. 2026, *World Journal of Microbiology and Biotechnology* 42:229, DOI 10.1007/s11274-026-04967-1), which has its own co-authors. It is distributed on Zenodo (DOI 10.5281/zenodo.20699785) under the Creative Commons Attribution 4.0 International license (CC-BY-4.0). Third-party tools, reference databases, and external models keep their own licenses and terms. See `AUTHORS.md`, `CITATION.cff`, `LICENSE_NOTE.md`, `THIRD_PARTY_NOTICES.md`, `docs/tool_references.md`, `docs/database_references.md`, and `docs/marker_database_attribution.md`.

## Status and limits

The package passes static validation (Windows 2026-06-03) and has been validated end to end on Linux Mint 22.3 (kernel 6.17.0-14-generic, host gma-Inspiron-15-3567) with a 10-genome test set on 2026-06-13. All 17 FULL-mode modules completed without error. Static audits (Python syntax, Bash syntax, portability, numbering, mode sequences, packaging contract, final manifest) all pass. The input contract, step validation, mode-aware consolidation, resume traceability, and attribution items from the 2026-05-31 audit are implemented; the mobilome modules are memory-safe with atomic outputs. See `CHANGELOG.md` for the full list.

Tool versions and database provenance have been verified on the Linux host from `pipeline_V4.txt` (generated 2026-05-12) and live terminal checks. See `docs/tool_versions.md` and `docs/database_provenance.md` for the complete verified records. All entries in `metadata/tool_and_database_citations.tsv` have provenance_status = verified.

FULL mode expects BAGEL5 and epsSMASH resources at portable versions of the Linux
paths recorded in the V4 source tree:

```text
external_tools/BAGEL5/src/data/bagel5/scripts/bagel5.py
dev/bagel5_full_integration/parser_design/parse_bagel5_bacteriocins_matrix.py
conda/envs/antismash_dependencies/bin/epsSMASH
db/epssmash
dev/epssmash_full_integration/parser_design/parse_epssmash_products_to_binary_matrix.py
```

These defaults can be overridden with `BAGEL5_SCRIPT`, `BAGEL5_PARSER_SCRIPT`,
`EPSSMASH_EXEC`, `EPSSMASH_DB`, and `EPSSMASH_PARSER_SCRIPT`.

Numeric regression against a legacy output set is not possible because no legacy V4 result directory exists under the final module numbering. This is documented in `metadata/REGRESSION_VALIDATION_REPORT.md` (status: NOT_APPLICABLE). The package is considered structurally and functionally validated for release.
