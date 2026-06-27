#!/usr/bin/env python3

import json
from pathlib import Path

import pandas as pd


def is_valid_tsv(path: Path, required_columns: list[str] | None = None, allow_empty: bool = False) -> bool:
    if not path.exists():
        return False
    if path.stat().st_size == 0:
        return allow_empty
    try:
        head = pd.read_csv(path, sep="\t", nrows=5)
    except Exception:
        return False
    if required_columns:
        return all(col in head.columns for col in required_columns)
    return True


def is_valid_csv(path: Path, required_columns: list[str] | None = None, allow_empty: bool = False) -> bool:
    if not path.exists():
        return False
    if path.stat().st_size == 0:
        return allow_empty
    try:
        head = pd.read_csv(path, nrows=5)
    except Exception:
        return False
    if required_columns:
        return all(col in head.columns for col in required_columns)
    return True


def is_valid_json(path: Path, allow_empty: bool = False) -> bool:
    if not path.exists():
        return False
    if path.stat().st_size == 0:
        return allow_empty
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return True

