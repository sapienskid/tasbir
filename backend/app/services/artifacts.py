"""Output artifact helpers — safe path resolution + delivery.

Artifacts (per-format HTML/PNG) live under ``data/output/{task_id}/``. Files
persist until the hourly TTL sweep deletes the task's output directory.
Downloading does not remove them unless the consumer opts in (?consume=true)
or ``DELETE_ON_DOWNLOAD`` is set.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.config import get_settings

log = logging.getLogger(__name__)


def task_output_dir(task_id: str) -> Path:
    settings = get_settings()
    return Path(settings.output_dir) / task_id


def resolve_output_file(task_id: str, filename: str) -> Path:
    """Resolve ``filename`` inside the task's output dir, rejecting traversal."""
    base = task_output_dir(task_id).resolve()
    path = (base / filename).resolve()
    if base != path.parent or not path.is_file():
        raise FileNotFoundError(filename)
    return path


def list_output_files(task_id: str) -> list[dict]:
    """List remaining artifacts as [{format, ext, size, filename}]."""
    base = task_output_dir(task_id)
    files: list[dict] = []
    if not base.is_dir():
        return files
    for f in sorted(base.iterdir()):
        if f.is_file():
            files.append({
                "format": f.stem,
                "ext": f.suffix.lstrip("."),
                "size": f.stat().st_size,
                "filename": f.name,
            })
    return files


def delete_task_output(task_id: str) -> None:
    """Remove the task's output directory (idempotent, guarded)."""
    base = task_output_dir(task_id)
    output_root = Path(get_settings().output_dir).resolve()
    if base.is_dir() and base.resolve().is_relative_to(output_root):
        shutil.rmtree(base, ignore_errors=True)
        log.info("[artifacts] Removed output dir %s", base)
