# User manual

## One-time setup: prepare marker resources

Run this once before the first pipeline execution, and again any time the marker
database files change.

```bash
export PIPE_ROOT=/path/to/your/pipeline_root
bash $PIPE_ROOT/scripts/01_run_prepare_marker_resources.sh
```

This builds the DIAMOND database, presses the HMM database, and writes the
metadata that module 10 reads. It does not create a run checkpoint and is not
part of any mode sequence.

## Basic run

```bash
export PIPE_ROOT=/path/to/your/pipeline_root
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --input_dir $PIPE_ROOT/input \
  --mode STANDARD \
  --run_name my_run
```

`--input_dir` defaults to `$PIPE_ROOT/input` when not set. If you have already
placed genomes there, you can omit it.

## All launcher options

| Option | Default | Description |
|---|---|---|
| `--input_dir PATH` | `$PIPE_ROOT/input` | Genome input directory |
| `--mode MODE` | `STANDARD` | `LIGHT`, `STANDARD`, or `FULL` |
| `--run_name NAME` | timestamp + mode | Name used for logs and run directory |
| `--resume` | off | Skip completed steps; do not reset `work/` or `results/` |
| `--from_step STEP_ID` | — | Skip all steps before STEP_ID in the current mode |
| `--force_step STEP_ID` | — | Delete checkpoint for STEP_ID and rerun it |
| `--threads N` | `2` | Thread count passed to all module wrappers |
| `--unicode-progress` | off | Enable Unicode characters in Python progress output |

`--resume` requires `--run_name` so the resumed run stays traceable.

## Resume an interrupted run

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --mode FULL \
  --resume \
  --run_name my_run
```

Completed steps are skipped; the first step whose checkpoint is missing runs
normally and the pipeline continues from there.

## Start from a specific step

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --mode FULL \
  --resume \
  --run_name my_run \
  --from_step 13_run_antismash_minimal
```

Every step before `13_run_antismash_minimal` is skipped regardless of checkpoint
state. Use this when you know all earlier outputs are valid and you only want to
run from a given point forward. `--from_step` must be a step ID that exists in
the selected mode; the launcher rejects unknown IDs.

## Force one step to rerun

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --mode FULL \
  --resume \
  --run_name my_run \
  --force_step 17_run_pipeline_consolidation
```

`--force_step` deletes that step's checkpoint before execution. All other
completed steps are skipped normally. Combine with `--from_step` to rerun a
range: `--from_step` skips everything before it, `--force_step` ensures the
target step reruns even if checkpointed.

## Increase thread count

```bash
bash $PIPE_ROOT/scripts/run_pipeline_final.sh \
  --input_dir $PIPE_ROOT/input \
  --mode STANDARD \
  --run_name my_run \
  --threads 4
```

The default is 2. On an 8 GB machine, 4 threads is the practical ceiling for
most modules. ISEScan (module 06) caps independently at 4 regardless of this
value.

## Input formats

The pipeline accepts nucleotide genome assemblies in FASTA form only. Accepted
extensions are `.fna`, `.fa`, `.fasta`, and `.fas`, case-insensitive, optionally
gzip-compressed (`.gz`).

Protein FASTA (`.faa`), GenBank (`.gbff`, `.gbk`, `.gb`), and annotation files
(`.gff`) are not accepted as genome input. The safety and mobility modules need
nucleotide sequence, so a protein-only or annotation-only input would drop that
genome from those layers and bias the final matrix.

Module 00 copies each accepted assembly to `work/normalized_fna` and runs
Prodigal to produce the proteome and GFF, so every genome carries the nucleotide
and protein files the downstream modules read. Module 00 stops the run with an
error if the input directory holds a refused genome file, if two inputs normalize
to the same `genome_id`, or if any genome fails to process. It writes
`work/manifest/input_file_mapping.tsv` recording the decision and reason for
every input file.

## Output locations

```text
work/          intermediate files, manifest, checkpoints
results/       TSV and XLSX outputs organized by module, plus logs
runs/          per-run staged inputs, archived previous state, metadata, exports
```

Run metadata and the archived pre-run state are stored under `runs/<run_name>/`.
