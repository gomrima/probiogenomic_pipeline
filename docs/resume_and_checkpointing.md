# Resume and checkpointing

The final launcher supports step-level resume.

Checkpoint files are stored in:

```text
work/checkpoints/
```

Genome-level resume is implemented where the module has raw per-genome output validation. The final ISEScan and TASmania wrappers reuse valid raw outputs. Modules copied from the source keep their original per-genome behavior unless explicitly refactored.

This implementation therefore improves resume behavior, but end-to-end genome-level resume still requires validation on the target Linux host with real tools and databases.

## Atomic consolidated outputs

The mobilome modules (06 ISEScan, 07 MOB-suite, 08 geNomad) write their
consolidated TSVs to temporary files and move them into place with `os.replace`
only after a full pass completes. An interruption (power loss, Ctrl-C, kill)
therefore never leaves a half-written TSV: the downstream modules (09 mobile-safety
co-occurrence and 17 final consolidation) always read either the previous complete
set or the new complete set. The reusable per-genome evidence (ISEScan CSVs,
geNomad summaries, MOB-suite reports) is what a relaunch rebuilds the TSVs from.

## Module 06 ISEScan: exit codes and partial runs

`06_isescan_mobilome.py` returns:

- **0** when every genome produced a valid result. The launcher writes the step
  checkpoint and the pipeline proceeds.
- **3** when the full pass completed but some genomes failed or timed out. By
  default the launcher does **not** write the checkpoint, so a relaunch reuses the
  valid genomes and reruns only the failed ones. Failed/timed-out genomes appear as
  zero in `isescan_family_binary.tsv` but are listed in `isescan_failures.tsv` and
  `isescan_resume_report.tsv`.

To accept a partial ISEScan result and create the checkpoint anyway (for example
after deciding a genome is hopeless), relaunch the step with `ALLOW_PARTIAL=1`.

Before a long resume you can preview the reuse/rerun decision without running
ISEScan:

```bash
PLAN_ONLY=1 bash scripts/06_run_isescan_mobilome.sh
cat results/tsv/mobilome/isescan_resume_plan.tsv
```

Modules 07 and 08 record per-genome failures and continue (exit 0); their step is
checkpointed on completion. Re-run the individual step (`--force_step`) to retry
failed genomes.

