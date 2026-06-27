# Installation guide

This guide describes a portable Linux installation. The pipeline uses `PIPE_ROOT` as its root directory and does not require a fixed machine path.

## Requirements

- Linux host, preferably a Debian-based distribution such as Ubuntu 22.04 LTS.
- Conda or Mamba.
- Sufficient disk space for databases and intermediate files.
- At least 8 GB RAM for small to moderate screening runs. Larger datasets need more memory.

## Setup

```bash
cd /path/to/scripts_probiogenomic_pipeline_final
export PIPE_ROOT=$(pwd)
```

Create environments from `envs/`. Exact versions must be verified on the target host.

```bash
conda env create -p $PIPE_ROOT/conda/envs/probio_core -f envs/probio_core.yml
conda env create -p $PIPE_ROOT/conda/envs/probml_env -f envs/probml_env.yml
```

Create the other tool environments only for modules you plan to run.

For FULL mode, the V4 Linux source tree used these relevant locations:

```bash
conda env create -p $PIPE_ROOT/conda/envs/bagel5_env -f envs/bagel5_env.yml
conda env create -p $PIPE_ROOT/conda/envs/antismash_dependencies -f envs/antismash_dependencies_env.yml
```

Install BAGEL5 at:

```text
$PIPE_ROOT/external_tools/BAGEL5/src/data/bagel5/scripts/bagel5.py
```

Install or expose epsSMASH at:

```text
$PIPE_ROOT/conda/envs/antismash_dependencies/bin/epsSMASH
```

The final package includes portable parser locations matching the V4 Linux path
layout:

```text
$PIPE_ROOT/dev/bagel5_full_integration/parser_design/parse_bagel5_bacteriocins_matrix.py
$PIPE_ROOT/dev/epssmash_full_integration/parser_design/parse_epssmash_products_to_binary_matrix.py
```

## Line ending fix (mandatory when transferring from Windows)

The package was authored on a Windows host. Any zip transfer, file copy, or git
checkout on a Windows machine may introduce CRLF (`\r\n`) line endings in the
shell and Python scripts. Bash on Linux treats the trailing `\r` as a literal
character and fails with `$'\r': command not found`.

Three protections are in place so this is handled automatically in the common
case, but it is worth understanding each level.

**Level 1 — `.gitattributes` (git-based distribution).** The `.gitattributes`
file at the repository root instructs git to enforce LF line endings on checkout
for all `.sh`, `.py`, `.md`, `.yml`, `.tsv`, and `.txt` files. If you cloned or
checked out this repository with a recent git version, line endings are already
correct and no manual action is needed.

**Level 2 — auto-fix in `run_pipeline_final.sh` (zip-based distribution).** The
launcher silently scans every script in `scripts/` and `scripts/lib/` at startup
and removes any `\r` before sourcing or calling any wrapper. A first launch on a
Windows-transferred zip therefore fixes itself without any intervention. If step 00
completed but printed `$'\r': command not found` at the end, resume with
`--resume` and the issue is gone from that point forward.

**Level 3 — manual fix (pre-launch audit or linting).** If you want to correct
line endings before any launch, for example to run a linter or audit the scripts,
run either of these from `$PIPE_ROOT`:

```bash
# Preferred — if dos2unix is available
find scripts dev -type f \( -name "*.sh" -o -name "*.py" \) | xargs dos2unix

# Universal fallback — no extra tool required
find scripts dev -type f \( -name "*.sh" -o -name "*.py" \) | xargs sed -i 's/\r//'
```

Verify that no CRLF remain:

```bash
grep -rlP '\r' scripts/ dev/ && echo "CRLF found" || echo "All clean"
```

## Databases

Place databases under `db/` or set tool-specific environment variables. The final wrappers allow overrides such as `GENOMAD_DB`, `MOBSUITE_DB`, `DBCAN_DB`, `ANTISMASH_DB`, and `EPSSMASH_DB`.

Database versions were verified on the target Linux host on 2026-05-12 and 2026-06-13. See `docs/database_provenance.md` for the complete record with SHA256 hashes, plus per-database acquisition commands (where to download each database and where to place it under `PIPE_ROOT`).

The module 10 marker database is not bundled with this code repository. It is
distributed on Zenodo under DOI 10.5281/zenodo.20699785
(https://doi.org/10.5281/zenodo.20699785), released under the Creative Commons
Attribution 4.0 International license (CC-BY-4.0). Download the archive from that
record and unzip it so that `db/` contains `markers_DB.xlsx`, `marker_fastas/`,
and `hmm_profiles/`:

```bash
# Download the marker database archive from the Zenodo record above, then:
unzip <downloaded_archive>.zip -d "$PIPE_ROOT/db/"
ls "$PIPE_ROOT/db/"   # expect markers_DB.xlsx, marker_fastas/, hmm_profiles/
```

The database is a separate scientific work (Gomri et al. 2026, World J Microbiol
Biotechnol 42:229); see `docs/marker_database_attribution.md`.

Then prepare the module 10 marker resources:

```bash
bash scripts/01_run_prepare_marker_resources.sh
```

This requires `db/markers_DB.xlsx`, `db/marker_fastas/`, `db/hmm_profiles/`,
DIAMOND, and HMMER. It creates the compiled resources consumed by
`10_marker_screening.py`.
