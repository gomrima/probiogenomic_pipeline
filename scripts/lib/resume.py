#!/usr/bin/env python3

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline_common import ensure_dir


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def status_path(pipe_root: Path, step_id: str, genome_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in genome_id)
    return pipe_root / "work" / "checkpoints" / "genome_status" / step_id / f"{safe}.json"


def write_genome_status(pipe_root: Path, step_id: str, genome_id: str, payload: dict[str, Any]) -> None:
    path = status_path(pipe_root, step_id, genome_id)
    ensure_dir(path.parent)
    record = dict(payload)
    record.setdefault("genome_id", genome_id)
    record.setdefault("step_id", step_id)
    record.setdefault("timestamp_utc", utc_now())
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)

