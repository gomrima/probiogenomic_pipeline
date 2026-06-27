# Environment notes

The environment files are best-effort portable specifications inferred from the local source scripts.

Package versions were verified on the target Linux host (gma-Inspiron-15-3567, Linux 6.17.0-14-generic) from `pipeline_V4.txt` (2026-05-12) and live terminal checks (2026-06-13). The verified versions are recorded in `docs/tool_versions.md`. The YML files remain best-effort specifications, not conda lockfiles.

The V4 Linux source tree used `conda/envs/antismash_dependencies/bin/epsSMASH`
for module 15. The final wrapper therefore exposes
`ANTISMASH_DEPENDENCIES_ENV`, defaulting to
`$PIPE_ROOT/conda/envs/antismash_dependencies`.

`envs/antismash_dependencies_env.yml` is a best-effort starting specification.
It is not a conda lockfile and does not prove that epsSMASH is installed.
