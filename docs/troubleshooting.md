# Troubleshooting

## `$'\r': command not found` errors (Windows line endings)

**Symptom.** The pipeline launches and step 00 appears to complete, but the last
line of the step prints `$'\r': command not found`.

**Cause.** The scripts were transferred from a Windows host. Windows uses CRLF
(`\r\n`) line endings. Bash on Linux treats the trailing `\r` as a literal
character in command names and fails with the error above.

**Fix.** `run_pipeline_final.sh` detects and silently removes CRLF from all
pipeline scripts at startup. On a first Windows-transferred install, resume
the interrupted run:

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --mode FULL --resume --run_name my_run
```

The launcher corrects every script before sourcing anything, skips the
already-completed step, and continues. To fix proactively before any launch:

```bash
find scripts dev -type f \( -name "*.sh" -o -name "*.py" \) | xargs sed -i 's/\r//'
```

## `EnvironmentLocationNotFound` on module 07 (MOB-suite)

**Symptom.**

```
EnvironmentLocationNotFound: Not a conda environment: .../conda/envs/mobsuite_env
```

**Cause.** The MOB-suite environment is named `mob_suite_env` on the V4 Linux
host. An earlier version of `scripts/lib/common.sh` defaulted `MOBSUITE_ENV` to
`mobsuite_env` (wrong name), which Conda cannot find.

**Fix.** `common.sh` now defaults to `mob_suite_env`. Verify:

```bash
grep "MOBSUITE_ENV" $PIPE_ROOT/scripts/lib/common.sh
# Expected: MOBSUITE_ENV="${MOBSUITE_ENV:-$PIPE_ROOT/conda/envs/mob_suite_env}"
```

Confirm the environment exists:

```bash
ls $PIPE_ROOT/conda/envs/mob_suite_env
```

If your environment uses a different name, override at launch:

```bash
MOBSUITE_ENV=/path/to/your/env bash $PIPE_ROOT/scripts/run_pipeline_final.sh ...
```

## A module is skipped unexpectedly

The step checkpoint exists. Remove it and resume, or use `--force_step`:

```bash
rm $PIPE_ROOT/work/checkpoints/10_run_marker_screening.done
bash $PIPE_ROOT/scripts/run_pipeline_final.sh --mode FULL --resume --run_name my_run
# or equivalently:
bash $PIPE_ROOT/scripts/run_pipeline_final.sh --mode FULL --resume --run_name my_run \
  --force_step 10_run_marker_screening
```

## Resume skips too many steps

Check `work/checkpoints/` and `work/checkpoints/pipeline_state.tsv` to see which
checkpoints exist.

```bash
ls $PIPE_ROOT/work/checkpoints/*.done
```

## A database is missing

Set the appropriate override variable or place the database under the default
`db/` location. Override variables are documented in `docs/portability.md` and
in the individual wrappers.

## A long module looks frozen (no terminal output)

Plain `conda run` buffers child output, so a run can appear frozen for many
minutes. All wrappers now use `conda run --no-capture-output` with unbuffered
Python (`-u`). Module 06 bypasses `conda run` entirely and calls the environment
Python directly so output is always live.

If a single ISEScan genome runs for a long time (IS-rich genomes such as
*Bordetella pertussis* are legitimately slow), module 06 prints a heartbeat every
`HEARTBEAT_SECONDS` (default 120 s). To isolate a suspected genome:

```bash
bash $PIPE_ROOT/scripts/06_probe_single_genome.sh GENOME_ID [THREADS]
```

## ISEScan genome timeout or partial pass (module 06)

When `06_isescan_mobilome.py` exits with code 3, some genomes failed or timed
out. No checkpoint is created by default, so a relaunch retries only those
genomes. To preview which genomes will be retried without running anything:

```bash
PLAN_ONLY=1 bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh
cat $PIPE_ROOT/results/tsv/mobilome/isescan_resume_plan.tsv
```

To accept the partial result and let the pipeline continue past module 06:

```bash
ALLOW_PARTIAL=1 bash $PIPE_ROOT/scripts/06_run_isescan_mobilome.sh
```

## Memory saturation during mobilome modules (06, 07, 08)

This was caused by accumulating per-genome detail tables in RAM before writing.
Modules 06, 07, and 08 now stream detail rows to TSV and write Excel with
openpyxl in constant-memory (`write_only`) mode. Keep `ISESCAN_THREADS=2` on an
8 GB machine.
