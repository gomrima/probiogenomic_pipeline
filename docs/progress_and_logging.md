# Progress and logging

The final launcher prints a standard header for every step.

```text
================================================================================
[STEP 11/17] ProbioSML marker screening
================================================================================
```

Standard prefixes are:

```text
[INFO]
[WARN]
[ERROR]
[RESUME]
[SKIP]
[DONE]
```

Python progress helpers are ASCII-safe by default. They report percent complete, processed count, elapsed time, estimated remaining time, and the active genome.

