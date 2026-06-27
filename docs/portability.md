# Portability

The final runtime code removes the historical fixed root path and resolves paths from `PIPE_ROOT`.

Default root resolution:

```bash
export PIPE_ROOT=/path/to/scripts_probiogenomic_pipeline_final
```

Each wrapper also derives `PIPE_ROOT` from its own location if the variable is not set.

Tool environments can be overridden with:

```text
CORE_ENV
PROBML_ENV
GENOMAD_ENV
ANTISMASH_ENV
BAGEL5_ENV
EPSSMASH_ENV
MOBSUITE_ENV
```

Database paths can be overridden with tool-specific variables documented in the wrappers.


## Default Conda environment names

The table below lists every environment variable, the default path suffix resolved
by `common.sh`, and the name installed on the V4 Linux reference host. When
overriding, pass the full absolute path to the environment directory.

| Variable | Default path (`$PIPE_ROOT/…`) | V4 Linux installed name |
|---|---|---|
| `CORE_ENV` | `conda/envs/probio_core` | `probio_core` |
| `PROBML_ENV` | `conda/envs/probml_env` | `probml_env` |
| `GENOMAD_ENV` | `conda/envs/genomad_env` | `genomad_env` |
| `ANTISMASH_ENV` | `conda/envs/antismash_env` | `antismash_env` |
| `ANTISMASH_DEPENDENCIES_ENV` | `conda/envs/antismash_dependencies` | `antismash_dependencies` |
| `BAGEL5_ENV` | `conda/envs/bagel5_env` | `bagel5_env` |
| `EPSSMASH_ENV` | `conda/envs/epssmash_env` | `epssmash_env` |
| `MOBSUITE_ENV` | `conda/envs/mob_suite_env` | `mob_suite_env` |

> **MOB-suite naming note.** The environment is `mob_suite_env` (underscores,
> matching the `mob_suite` conda package). An earlier `common.sh` used
> `mobsuite_env` by mistake, which caused `EnvironmentLocationNotFound`. The
> current `common.sh` uses the correct name.
