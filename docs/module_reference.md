# Module reference

| Step | Module | Layer |
|---|---|---|
| 00 | Input preparation | Preparation |
| 01 | Marker resource preparation | Setup only |
| 02 | ABRicate safety screening | Safety |
| 03 | TASmania toxin-antitoxin screening | Safety |
| 04 | MinCED CRISPR screening | Safety and plasticity |
| 05 | DBETH and PAT toxin screening | Safety |
| 06 | ISEScan mobilome screening | Mobility |
| 07 | MOB-suite plasmid screening | Mobility |
| 08 | geNomad prophage screening | Mobility |
| 09 | Mobile-safety co-occurrence | Plasticity |
| 10 | Core marker screening | Probiotic function |
| 11 | ProbioSML marker screening | Probiotic function |
| 12 | dbCAN CAZyme screening | Probiotic function |
| 13 | antiSMASH BGC screening | Probiotic function |
| 14 | BAGEL5 bacteriocin screening | Probiotic function |
| 15 | epsSMASH EPS screening | Probiotic function |
| 16 | ProbML whole-genome classifier | External comparator |
| 17 | Final consolidation | Consolidation |

`01_prepare_marker_resources.py` is a setup utility and is not part of LIGHT,
STANDARD, or FULL mode. Run `scripts/01_run_prepare_marker_resources.sh` once
before runtime modes. It builds the DIAMOND database, presses the HMM database,
copies `markers_DB.xlsx` into `db/compiled/`, and writes marker metadata required
by module 10.

Modules 14 and 15 use parser scripts in the portable V4 Linux path layout:

| Module | Default parser path |
|---|---|
| 14 BAGEL5 | `dev/bagel5_full_integration/parser_design/parse_bagel5_bacteriocins_matrix.py` |
| 15 epsSMASH | `dev/epssmash_full_integration/parser_design/parse_epssmash_products_to_binary_matrix.py` |


## Module 06 probe utility

`06_probe_single_genome.sh` is a diagnostic helper that runs ISEScan on one
genome in complete isolation — no pipeline directories, no resume logic, no
checkpointing. Use it to determine whether a slow or failing genome is a
genome-specific issue or a tool-level issue.

```bash
bash $PIPE_ROOT/scripts/06_probe_single_genome.sh GENOME_ID [THREADS]
```

The genome ID must exist in `work/manifest/input_manifest.tsv` with status `OK`.
Output lands in a timestamped directory under `work/tmp/`. Pipeline raw
directories, consolidated TSVs, and checkpoints are not touched.

| Override | Default | Purpose |
|---|---|---|
| `PROBE_TIMEOUT` | `0` | Seconds before ISEScan is killed (0 = no timeout) |

## Mobilome modules 06–08 (memory-safe, resume-robust)

The three per-genome external-tool aggregators stream their detail tables to TSV,
build the binary/summary matrices from compact per-genome aggregates, write the
Excel workbook in constant memory (openpyxl `write_only`), and publish every
consolidated TSV atomically (temp file + `os.replace`). See `CHANGELOG.md`
(2026-05-30) and `docs/resume_and_checkpointing.md`.

Module 06 (ISEScan) is resume-aware: it reuses a valid per-genome CSV, cleans a
stale per-genome directory before any rerun, runs ISEScan in its own process group
with a per-genome timeout and a heartbeat, and exits 3 (no checkpoint) when the
pass completes with failures so a relaunch retries only those genomes. Its launcher
accepts these environment overrides:

| Variable | Default | Purpose |
|---|---|---|
| `ISESCAN_THREADS` | `THREADS` or 2 | ISEScan threads (capped at 4) |
| `PER_GENOME_TIMEOUT` | 7200 | seconds per genome before ISEScan is killed (0 disables) |
| `HEARTBEAT_SECONDS` | 120 | liveness message interval while ISEScan runs (0 disables) |
| `MIN_CSV_SIZE` | 1 | minimum bytes for a reusable CSV |
| `KEEP_STALE_BACKUP` | 0 | 1 = rename stale dirs instead of deleting them |
| `FORCE_RERUN` | 0 | 1 = ignore existing CSVs and rerun every genome |
| `PLAN_ONLY` | 0 | 1 = classify reuse vs rerun and write `isescan_resume_plan.tsv` only |
| `MAKE_XLSX` | 1 | 0 = skip the optional Excel workbook |
| `ALLOW_PARTIAL` | 0 | 1 = create the checkpoint even if some genomes failed |
