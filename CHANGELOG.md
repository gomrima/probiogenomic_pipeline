# Changelog

## 2026-06-15

### Publication readiness for public GitHub release

Documentation, metadata, and licensing finalized for the public release. No
analytical module code was changed.

- `docs/database_provenance.md` extended from a provenance-only record into a
  combined provenance and acquisition document. Every prior fact (version, date,
  size, SHA256, location) is preserved; per-database Acquisition blocks were added
  giving the download source or command, the target version, and the final
  placement under `PIPE_ROOT`. Acquisition was verified for ABRicate (CARD, VFDB),
  dbCAN V12, MOB-suite, geNomad, antiSMASH 8, ProbML, epsSMASH source, and the
  marker database.
- Acquisition URLs for the remaining databases were supplied by the research team
  on 2026-06-15 and recorded as Verified: TASmania
  (https://shiny.bioinformatics.unibe.ch/apps/tasmania/), DBETH
  (http://www.hpppi.iicb.res.in/btox/cgi-bin2/download-list.cgi?name=download),
  PAT (doi:10.1093/nar/gkac879; http://bioinfo.qd.sdu.edu.cn/PAT/download.html),
  ProbioDB 1.0 (https://zenodo.org/records/14181444), BAGEL5
  (http://ngs.molgenrug.nl/bagel5/), and epsSMASH 1.2.1
  (https://github.com/AOHD/epsSMASH). All acquisition entries in
  `docs/database_provenance.md` are now tagged Verified.
- ProbioDB 1.0 fully documented: DOI 10.5281/zenodo.14181444 (concept DOI
  10.5281/zenodo.14181443), version 1.0 published 2025-06-18, CC-BY-4.0, full
  author citation, Zenodo MD5 for `ProbioDB_1.0.faa`
  (09c7ba01026bc62ba8eb502416d1147e), and a flagged discrepancy between the Zenodo
  description (1,071 genes) and the local FASTA count (1,072). Added a ProbioDB
  entry to `docs/database_references.md`.
- `docs/database_references.md`: PAT reference completed to NAR
  2023;51(D1):D452-D459, doi:10.1093/nar/gkac879, with the database download URL;
  added a cross-reference to the acquisition blocks.
- `docs/installation_guide.md`: Databases section now points to the acquisition
  blocks in `docs/database_provenance.md`.
- Freeze impact: modifying these documentation files invalidates the previous
  `metadata/FINAL_FILE_MANIFEST.sha256.tsv`. The manifest was regenerated on
  2026-06-15 with `regenerate_final_manifest.py`. No script or analytical output
  was modified.

- Python bytecode caches (`__pycache__`, `*.pyc`) confirmed absent from the
  release tree; `audit_packaging_contract` passes.
- Core marker database deposited on Zenodo (DOI 10.5281/zenodo.20699785) under
  the Creative Commons Attribution 4.0 International license (CC-BY-4.0).
  Recorded in `metadata/marker_database_provenance.tsv` (public_deposit_status,
  data_doi, license_or_terms), `README.md`, `docs/installation_guide.md`,
  `docs/marker_database_attribution.md`, `AUTHORS.md`, and `LICENSE_NOTE.md`.
- Marker database citation confirmed against Crossref on 2026-06-15: World J
  Microbiol Biotechnol 2026, volume 42, issue 5, article number 229, DOI
  10.1007/s11274-026-04967-1, published online 2026-04-22.
- `CITATION.cff`: version set to 4.0.0, date-released to 2026-06-13, article
  number 229 and issue 5 added, repository-code set to
  https://github.com/gomrima/probiogenomic_pipeline.
- Third-party licenses named precisely. epsSMASH: AGPL-3.0
  (github.com/AOHD/epsSMASH). ProbML: corrected to the probiotic classifier of
  Arjun (Krishnan) et al. 2025 (Mol Nutr Food Res 69(17):e70025, DOI
  10.1002/mnfr.70025), models distributed as MLG_Dashboard under MIT; this is a
  different project from the `probml/pml-book` textbook. geNomad: LBNL Academic /
  Non-Commercial Use License named explicitly. BAGEL5: cite van Heel et al. 2018
  (BAGEL4, DOI 10.1093/nar/gky383) pending the BAGEL5 publication.
- antiSMASH citation corrected from the 7.0 paper to the installed 8.0.4 version
  (Blin et al. 2025, Nucleic Acids Res 53(W1):W32-W38, DOI 10.1093/nar/gkaf334).
- `.gitattributes`: em-dash in a comment replaced with a hyphen for style
  compliance.
- `metadata/FINAL_FILE_MANIFEST.tsv` regenerated so every SHA256 matches the
  released tree.

## 2026-06-13

### Linux validation and provenance completion

The pipeline was run end to end on Linux Mint 22.3 (kernel 6.17.0-14-generic,
host gma-Inspiron-15-3567) with a 10-genome test set. All 17 FULL-mode modules
completed without error. No code was changed.

Provenance documentation updated from `pipeline_V4.txt` (generated 2026-05-12)
and live terminal verification:

- `docs/tool_versions.md` rewritten with 13 verified tools across 7 conda
  environments, including Python library versions.
- `docs/database_provenance.md` rewritten with sequence counts, dates, and
  SHA256 hashes for all 11 databases (ABRicate CARD/VFDB, TASmania, DBETH, PAT,
  curated markers, dbCAN HMMdb-V12, MOB-suite, geNomad DB v1.9, ProbioSML
  ProbioDB 1.0, antiSMASH, BAGEL5, epsSMASH, ProbML 12 models).
- `metadata/tool_and_database_citations.tsv`: all 22 entries filled with
  local_version and provenance_status = verified.
- `metadata/marker_database_provenance.tsv`: marker count, sequence counts,
  SHA256 hashes, and curator filled from pipeline_V4.txt evidence.
- `metadata/ACCEPTANCE_TESTS.tsv`: T08 reclassified from BLOCKED to
  NOT_APPLICABLE (no legacy outputs exist); T11 added for Linux functional
  validation (PASS).
- `metadata/REGRESSION_VALIDATION_REPORT.md`: rewritten to document
  NOT_APPLICABLE status and functional validation.
- `README.md`: Status section rewritten to reflect Linux validation, verified
  provenance, and release readiness.

Audit corrections applied:

- `envs/mobsuite_env.yml`: env name corrected from `mobsuite_env` to
  `mob_suite_env` to match `scripts/lib/common.sh` MOBSUITE_ENV path.
- `docs/command_reference.md` and `docs/user_manual.md`: hardcoded path
  `/media/gma/FAST_WORK1/probiotic_screening_pipeline` replaced with
  `/path/to/your/pipeline_root`.
- `THIRD_PARTY_NOTICES.md`: resolved `to_verify` markers for VFDB, TASmania,
  PAT, antiSMASH (8.0.4, Blin et al. 2023), BAGEL5. epsSMASH license was still
  pending at this date (later resolved to AGPL-3.0, see 2026-06-15).
- Four stale statements updated in `docs/validation_and_regression.md`,
  `docs/installation_guide.md`, `envs/ENVIRONMENT_NOTES.md`, and
  `metadata/CORRECTION_IMPLEMENTATION_REPORT_20260603.md`.
- Final file manifest regenerated to include all current SHA256 hashes and
  `docs/command_reference.md` (previously missing from manifest).

## 2026-06-04

### Documentation pass after post-Claude verification

No pipeline run was executed and no code, environment, or structure was changed.

- Expanded `docs/limitations.md` with a scientific interpretation limits section:
  outputs are predicted genomic potential only, a binary 0 is not a biological
  absence, results depend on databases and thresholds, feature counts are
  confounded by taxonomy and assembly quality, safety signals override positive
  markers, ProbML is an external comparator, and the pipeline carries no clinical
  or regulatory meaning.
- The final file manifest, its checksum, and its metadata were regenerated so the
  hashes of the changed documentation are recorded. All static audits still pass.

## 2026-06-03

### Static correction pass after independent portage audit

No pipeline run was executed in this correction pass.

- Added `scripts/01_run_prepare_marker_resources.sh` and strengthened
  `01_prepare_marker_resources.py` so module 01 prepares the compiled workbook,
  DIAMOND database, HMM database, and HMMER press files required by module 10.
- Added preflight checks in `10_run_marker_screening.sh` and
  `run_pipeline_final.sh` so missing compiled marker resources fail before a
  biological run starts.
- Restored BAGEL5 and epsSMASH parser defaults to the portable V4 Linux layout:
  `dev/bagel5_full_integration/parser_design/` and
  `dev/epssmash_full_integration/parser_design/`.
- Aligned the epsSMASH default executable path with the V4 Linux source tree:
  `conda/envs/antismash_dependencies/bin/epsSMASH`.
- Added `ANTISMASH_DEPENDENCIES_ENV` and
  `envs/antismash_dependencies_env.yml` as a best-effort Linux setup starting
  point.
- Removed Python bytecode caches, the duplicate extensionless
  `Documentation/README_V4`, and `.dockerignore` because no Dockerfile is
  present.
- Added static packaging and final-manifest audit scripts.
- Updated documentation and provenance notes. Linux end-to-end validation remains
  blocked until the complete target host run is performed.

## 2026-05-31

### Audit corrections (input contract, orchestration, consolidation, attribution)

Implements the feasible, justified items from
`AUDIT_RAPPORT_SCRIPTS_PIPELINE_FINAL_2026-05-31.md`. Items needing a Linux run
(end-to-end regression, conda lockfiles) are out of scope here and stay open.

- **Input contract (module 00, P0)**: `00_prepare_inputs.py` now accepts
  nucleotide FASTA only (`.fna`, `.fa`, `.fasta`, `.fas`, optionally `.gz`).
  Protein FASTA (`.faa`), GenBank, and annotation files are refused with an
  explicit error instead of being staged as genomes. Every accepted genome is
  run through Prodigal, so it carries both the nucleotide and protein files the
  modules read. The module detects `genome_id` collisions and fails on them,
  fails if any genome fails to process, and writes `input_file_mapping.tsv`.
- **Step validation (launcher, P0)**: `run_pipeline_final.sh` validates
  `--from_step` and `--force_step` against the steps of the selected mode and
  fails fast on an unknown step, so a typo can no longer skip every step and end
  the run as if it had completed.
- **Mode-aware consolidation (module 17, P0)**: the launcher exports `MODE` and
  the consolidation enforces the modules each mode is expected to produce. A
  `full` run now fails if a biological layer (ISEScan, MOB-suite, geNomad, mobile
  safety, ProbioSML, antiSMASH/BGC, BAGEL5, epsSMASH) is missing. ProbML stays
  optional as an external comparator.
- **Resume traceability (launcher, P1)**: `--resume` now requires `--run_name`.
- **ABRicate threads (module 02, P1)**: ABRicate reads the pipeline-wide
  `THREADS` value instead of a hardcoded constant.
- **Cache hygiene (P0)**: cache hygiene was intended here, but a later static
  audit found residual `.pyc` files. They were removed in the 2026-06-03
  correction pass.
- **Attribution (P0)**: added `AUTHORS.md`, `THIRD_PARTY_NOTICES.md`,
  `docs/tool_references.md`, `docs/database_references.md`,
  `docs/marker_database_attribution.md`,
  `metadata/tool_and_database_citations.tsv`, and
  `metadata/marker_database_provenance.tsv`. The module-10 marker database is
  attributed to Gomri et al. 2026 (DOI 10.1007/s11274-026-04967-1, verify before
  release). Entries marked `to_verify` must be confirmed at packaging.
- **Docs**: `docs/user_manual.md` now states the nucleotide-FASTA-only input
  contract and the `--run_name` requirement on resume.

## 2026-05-30

### Mobilome modules made memory-safe and resume-robust (modules 06, 07, 08)

Fixed the RAM-saturation / apparent-freeze pattern shared by the three per-genome
external-tool aggregators, and aligned module 06 (ISEScan) with the corrected
reference `07_isescan_mobilome_resume.py`. The TSV outputs (the downstream contract
for modules 09 and 17) are byte-compatible; only the in-memory aggregation and the
workbook serialization changed.

- **Module 06 ISEScan** rewritten as resume-aware, memory-safe and atomic:
  - validates a reusable per-genome CSV by **header only** (no full pandas parse on
    resume) and streams detail rows straight to the TSV (no `all_detail_frames` +
    `pandas.concat`);
  - runs ISEScan in its **own process group** with a per-genome **timeout**, a
    **heartbeat** (so a slow IS-rich genome no longer looks frozen) and clean
    SIGTERM/Ctrl-C teardown (no orphan FragGeneScan/hmmer/blast);
  - **cleans the stale per-genome directory** before a rerun (prevents the
    `addNonORFcopy` hang on intermediate files left by a power failure);
  - treats a genome where ISEScan exits 0 with no CSV as a real **zero-IS** result
    (records it, writes a `.isescan_ok` sentinel for reuse) instead of a failure;
  - publishes every consolidated TSV **atomically** (temp file + `os.replace`) only
    after a full pass, so an interruption never leaves a half-written TSV;
  - **exit code 0** if all genomes are valid, **3** if the pass completed with
    failures/timeouts. Adds `--plan-only` (writes `isescan_resume_plan.tsv`) and
    `--no-xlsx`.
- **Module 06 launcher** no longer uses `conda run` (it buffered child output and
  made an active run look frozen): it calls the environment python directly,
  unbuffered, with the env `bin/` on `PATH` so `isescan.py` resolves. The checkpoint
  is created only on exit 0 (or exit 3 with `ALLOW_PARTIAL=1`). New env overrides:
  `ISESCAN_THREADS` (default = `THREADS` or 2, capped at 4), `PER_GENOME_TIMEOUT`
  (default 7200, 0 disables), `HEARTBEAT_SECONDS` (default 120, 0 disables),
  `MIN_CSV_SIZE`, `KEEP_STALE_BACKUP`, `FORCE_RERUN`, `PLAN_ONLY`, `MAKE_XLSX`,
  `ALLOW_PARTIAL`.
- **Module 07 MOB-suite** and **Module 08 geNomad**: per-genome detail tables are
  now streamed to TSV (no `pandas.concat`), the XLSX workbook is written with
  openpyxl in constant-memory (`write_only`) mode, the subprocess output is no
  longer buffered in Python, and all consolidated TSVs are published atomically.
  Module 07 also removes a stale per-genome directory before rerunning `mob_recon`
  (which refuses to write into an existing directory).
- **`lib/common.sh`**: `run_python_in_env` now uses
  `conda run --no-capture-output ... python -u`, so every long-running module
  streams its progress live instead of looking frozen.
- **Modules 02 (ABRicate) and 12 (dbCAN)**: the milder variant of the same
  pattern. The pandas computation, the TSV outputs and the XLSX sheet
  structure/behavior are **unchanged**; only the workbook serialization now uses
  openpyxl `write_only` (streaming `DataFrame.itertuples`, types preserved,
  inf/NaN → blank, XML-illegal chars stripped, empty-frame and per-sheet
  error handling kept) instead of building the whole workbook in memory.

## 2026-05-29

- Created the final repository layout under `scripts_probiogenomic_pipeline_final`.
- Preserved the source directory as read-only.
- Added source manifests and SHA256 provenance metadata.
- Resolved the source index 13 collision by moving geNomad to 08 and ProbioSML to 11.
- Reordered execution modes without changing mode membership.
- Added `run_pipeline_final.sh` with resume support and run metadata.
- Replaced machine-specific runtime roots with dynamic `PIPE_ROOT` resolution.
- Added shared path, checkpoint, progress, resume, and validation helpers.
- Added static audits for portability, numbering, mode sequence, and output comparison.
