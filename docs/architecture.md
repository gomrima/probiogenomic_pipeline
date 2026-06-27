# Architecture

The final pipeline keeps the source scientific modules and changes the runtime architecture around them.

## Layers

1. Preparation.
2. Safety screening.
3. Mobile element screening.
4. Mobile-safety co-occurrence.
5. Probiotic function screening.
6. External ProbML comparator.
7. Final consolidation.

The co-occurrence module runs after both safety and mobility modules because it consumes their outputs.

## Shared helpers

`scripts/lib/common.sh` centralizes shell path resolution, logging, checkpoint helpers, and Python execution.

`scripts/lib/pipeline_common.py`, `progress.py`, `resume.py`, and `validation.py` provide Python helpers for portable paths, progress, status sidecars, and file validation.

