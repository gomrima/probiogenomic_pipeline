#!/usr/bin/env python3

import argparse
from pathlib import Path


FORBIDDEN = [
    "/media/gma",
    "FAST_WORK1",
    "C:\\Users",
    "L14",
    "/home/gma",
    "Dell",
    "Inspiron",
]

RUNTIME_SUFFIXES = {".py", ".sh"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final runtime files for forbidden local paths.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    rows = ["relative_path\tpattern\tline_number\tline"]
    failures = 0

    self_path = Path(__file__).resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in RUNTIME_SUFFIXES:
            continue
        if path.resolve() == self_path:
            # Skip this audit's own source. It necessarily contains the forbidden
            # tokens in its FORBIDDEN list, so scanning it would self-flag and make
            # the audit fail on the package root even when the runtime code is clean.
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in FORBIDDEN:
                if pattern in line:
                    failures += 1
                    rows.append(f"{rel}\t{pattern}\t{line_number}\t{line.strip()}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

