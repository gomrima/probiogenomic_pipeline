# Command reference

This file lists every command you need to run the pipeline, from first install
through per-module standalone execution. All commands assume:

```bash
export PIPE_ROOT=/path/to/your/pipeline_root
conda activate $PIPE_ROOT/conda/envs/probio_core
```

---

## 0. One-time: prepare marker resources

Run once before the first pipeline execution. Run again if marker database files
change.

```bash
bash $PIPE_ROOT/scripts/01_run_prepare_marker_resources.sh
```

This is not a pipeline step. It builds the DIAMOND and HMM compiled resources
that module 10 requires and does not create a run checkpoint.

---

## 1. Full pipeline — three modes

### LIGHT mode

Modules: 00 → 02 → 03 → 04 → 05 → 10 → 12 → 17

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --input_dir $PIPE_ROOT/input \
  --mode LIGHT \
  --run_name my_run_light
```

### STANDARD mode

Modules: 00 → 02 → 03 → 04 → 05 → 06 → 07 → 10 → 12 → 17

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --input_dir $PIPE_ROOT/input \
  --mode STANDARD \
  --run_name my_run_standard
```

### FULL mode

Modules: 00 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --input_dir $PIPE_ROOT/input \
  --mode FULL \
  --run_name my_run_full
```

### With custom thread count

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --input_dir $PIPE_ROOT/input \
  --mode FULL \
  --run_name my_run_full \
  --threads 4
```

Default is 2. Practical ceiling on an 8 GB machine is 4.

---

## 2. Resume and targeted restart

### Resume an interrupted run

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --mode FULL \
  --resume \
  --run_name my_run_full
```

`--resume` requires `--run_name`. Steps with valid checkpoints are skipped; the
first incomplete step runs and the pipeline continues from there. `work/` and
`results/` are not reset.

### Start from a specific module (skip all earlier steps)

Replace `STEP_ID` with any step ID listed in section 4.

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --mode FULL \
  --resume \
  --run_name my_run_full \
  --from_step 10_run_marker_screening
```

Every step before `10_run_marker_screening` is skipped regardless of checkpoint
state. The step ID must belong to the selected mode; the launcher rejects unknown
IDs.

### Force one step to rerun

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --mode FULL \
  --resume \
  --run_name my_run_full \
  --force_step 17_run_pipeline_consolidation
```

`--force_step` deletes that step's checkpoint before execution. All other steps
follow normal resume logic.

### Rerun from a step and force it

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --mode FULL \
  --resume \
  --run_name my_run_full \
  --from_step 10_run_marker_screening \
  --force_step 10_run_marker_screening
```

`--from_step` skips everything before the target; `--force_step` ensures the
target reruns even if a stale checkpoint exists.

### Delete a specific checkpoint manually

```bash
rm $PIPE_ROOT/work/checkpoints/10_run_marker_screening.done
```

Then resume normally. Equivalent to using `--force_step`.

### List existing checkpoints

```bash
ls $PIPE_ROOT/work/checkpoints/*.done
```

---

## 3. Resume to a specific module — all valid step IDs by mode

### LIGHT — valid `--from_step` / `--force_step` values

| Step ID | Module |
|---|---|
| `00_prepare_inputs` | Input preparation |
| `02_run_safety_abricate` | ABRicate safety screening |
| `03_run_tasmania_screen` | TASmania toxin-antitoxin |
| `04_run_crispr_minced` | CRISPR screening |
| `05_run_bacterial_toxins_screen` | DBETH and PAT toxins |
| `10_run_marker_screening` | Core marker screening |
| `12_run_cazymes_dbcan` | CAZyme screening |
| `17_run_pipeline_consolidation` | Final consolidation |

### STANDARD — valid `--from_step` / `--force_step` values

All LIGHT steps, plus:

| Step ID | Module |
|---|---|
| `06_run_isescan_mobilome` | ISEScan insertion sequences |
| `07_run_mobsuite_plasmids` | MOB-suite plasmids |

### FULL — all valid `--from_step` / `--force_step` values

| Step ID | Module |
|---|---|
| `00_prepare_inputs` | Input preparation |
| `02_run_safety_abricate` | ABRicate safety screening |
| `03_run_tasmania_screen` | TASmania toxin-antitoxin |
| `04_run_crispr_minced` | CRISPR screening |
| `05_run_bacterial_toxins_screen` | DBETH and PAT toxins |
| `06_run_isescan_mobilome` | ISEScan insertion sequences |
| `07_run_mobsuite_plasmids` | MOB-suite plasmids |
| `08_run_genomad_prophages` | geNomad prophage screening |
| `09_run_mobile_safety_cooccurrence` | Mobile safety co-occurrence |
| `10_run_marker_screening` | Core marker screening |
| `11_run_probiosml_screen` | ProbioSML marker screening |
| `12_run_cazymes_dbcan` | CAZyme screening |
| `13_run_antismash_minimal` | antiSMASH BGC screening |
| `14_run_bagel5_full` | BAGEL5 bacteriocin screening |
| `15_run_epssmash_full` | epsSMASH EPS screening |
| `16_run_probml_screen` | ProbML external classifier |
| `17_run_pipeline_consolidation` | Final consolidation |

---

## 4. Per-module standalone execution

Each wrapper reads `PIPE_ROOT` from its own location and sources
`scripts/lib/common.sh`. Set `PIPE_ROOT` if needed, then call the wrapper
directly. The wrappers write to the same `work/`, `results/`, and
`work/checkpoints/` directories as the full launcher.

```bash
# Module 00 — input preparation (requires input directory argument)
bash $PIPE_ROOT/scripts/00_prepare_inputs.sh $PIPE_ROOT/input

# Module 02 — ABRicate safety screening
bash $PIPE_ROOT/scripts/02_run_safety_abricate.sh

# Module 03 — TASmania toxin-antitoxin
bash $PIPE_ROOT/scripts/03_run_tasmania_screen.sh

# Module 04 — CRISPR (MinCED)
bash $PIPE_ROOT/scripts/04_run_crispr_minced.sh

# Module 05 — bacterial toxins (DBETH + PAT)
bash $PIPE_ROOT/scripts/05_run_bacterial_toxins_screen.sh

# Module 06 — ISEScan insertion sequences
bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh

# Module 07 — MOB-suite plasmids
bash $PIPE_ROOT/scripts/07_run_mobsuite_plasmids.sh

# Module 08 — geNomad prophages
bash $PIPE_ROOT/scripts/08_run_genomad_prophages.sh

# Module 09 — mobile safety co-occurrence
bash $PIPE_ROOT/scripts/09_run_mobile_safety_cooccurrence.sh

# Module 10 — core probiotic marker screening
bash $PIPE_ROOT/scripts/10_run_marker_screening.sh

# Module 11 — ProbioSML marker screening
bash $PIPE_ROOT/scripts/11_run_probiosml_screen.sh

# Module 12 — dbCAN CAZyme screening
bash $PIPE_ROOT/scripts/12_run_cazymes_dbcan.sh

# Module 13 — antiSMASH BGC screening
bash $PIPE_ROOT/scripts/13_run_antismash_minimal.sh

# Module 14 — BAGEL5 bacteriocin screening
bash $PIPE_ROOT/scripts/14_run_bagel5_full.sh

# Module 15 — epsSMASH EPS screening
bash $PIPE_ROOT/scripts/15_run_epssmash_full.sh

# Module 16 — ProbML external classifier
bash $PIPE_ROOT/scripts/16_run_probml_screen.sh

# Module 17 — final consolidation
bash $PIPE_ROOT/scripts/17_run_pipeline_consolidation.sh
```

Standalone wrappers skip execution if their checkpoint already exists. To force
rerun a standalone module, remove its checkpoint first:

```bash
rm $PIPE_ROOT/work/checkpoints/12_run_cazymes_dbcan.done
bash $PIPE_ROOT/scripts/12_run_cazymes_dbcan.sh
```

---

## 5. Module 06 ISEScan — advanced controls

Module 06 supports environment variable overrides passed before the wrapper
call.

```bash
# Preview which genomes will be reused vs rerun — no ISEScan executed
PLAN_ONLY=1 bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh
cat $PIPE_ROOT/results/tsv/mobilome/isescan_resume_plan.tsv

# Accept a partial result (some genomes failed) and create the checkpoint
ALLOW_PARTIAL=1 bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh

# Force full rerun ignoring existing per-genome CSVs
FORCE_RERUN=1 bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh

# Increase threads (default 2, capped at 4)
ISESCAN_THREADS=4 bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh

# Set per-genome timeout to 1 hour (default 7200 s; 0 = no timeout)
PER_GENOME_TIMEOUT=3600 bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh

# Disable liveness heartbeat
HEARTBEAT_SECONDS=0 bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh

# Skip Excel workbook generation
MAKE_XLSX=0 bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh

# Combine overrides
ISESCAN_THREADS=4 PER_GENOME_TIMEOUT=3600 ALLOW_PARTIAL=1 \
  bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh
```

### Module 06 probe utility — isolate a single genome

Use this to diagnose a slow or failing genome without touching any pipeline
output.

```bash
# Basic probe at 1 thread, no timeout
bash $PIPE_ROOT/scripts/06_probe_single_genome.sh GENOME_ID

# Probe with 2 threads
bash $PIPE_ROOT/scripts/06_probe_single_genome.sh GENOME_ID 2

# Probe with a 1-hour safety timeout
PROBE_TIMEOUT=3600 bash $PIPE_ROOT/scripts/06_probe_single_genome.sh GENOME_ID 2
```

Replace `GENOME_ID` with the exact `genome_id` value from
`work/manifest/input_manifest.tsv`. Output lands in `work/tmp/isescan_probe_*/`.

---

## 6. Environment and database overrides

Pass these before the launcher or wrapper to override defaults.

### Conda environments

```bash
MOBSUITE_ENV=/path/to/mob_suite_env \
  bash $PIPE_ROOT/scripts/run_pipeline_final.sh --mode FULL --run_name my_run
```

Full list of overridable environment variables and their defaults is in
`docs/portability.md`.

### Database paths

```bash
GENOMAD_DB=/path/to/genomad_db \
DBCAN_DB=/path/to/dbCAN.txt \
ANTISMASH_DB=/path/to/antismash_db \
EPSSMASH_DB=/path/to/epssmash_db \
MOBSUITE_DB=/path/to/mob_suite_db \
  bash $PIPE_ROOT/scripts/run_pipeline_final.sh --mode FULL --run_name my_run
```

---

## 7. Logs and diagnostics

```bash
# Follow the live main run log
tail -f $PIPE_ROOT/results/logs/run_pipeline_final.log

# Follow a module log directly
tail -f $PIPE_ROOT/results/logs/06_run_isescan_mobilome.log

# Check pipeline state (steps started, completed, skipped)
cat $PIPE_ROOT/work/checkpoints/pipeline_state.tsv

# List completed checkpoints
ls $PIPE_ROOT/work/checkpoints/*.done

# Check ISEScan failures and resume plan
cat $PIPE_ROOT/results/tsv/mobilome/isescan_failures.tsv
cat $PIPE_ROOT/results/tsv/mobilome/isescan_resume_plan.tsv
```

---

## 8. Maintenance

```bash
# Validate launcher syntax (static check, no execution)
bash -n $PIPE_ROOT/scripts/run_pipeline_final.sh

# Compile-check all Python scripts
python -m py_compile $(find $PIPE_ROOT/scripts -name '*.py' | sort)

# Fix CRLF on all scripts if transferred from Windows
find $PIPE_ROOT/scripts $PIPE_ROOT/dev \
  -type f \( -name "*.sh" -o -name "*.py" \) | xargs sed -i 's/\r//'
```
