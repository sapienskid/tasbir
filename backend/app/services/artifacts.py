"""Output artifact helpers — safe path resolution + delivery.

Artifacts (per-format HTML/PNG) live under ``data/output/{task_id}/``. Files
persist until the hourly TTL sweep deletes the task's output directory.
Downloading does not remove them unless the consumer opts in (?consume=true)
or ``DELETE_ON_DOWNLOAD`` is set.
"""

from __future__ import annotations

import logging
import os
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


def atomic_write(path: str | Path, data: bytes | str) -> None:
    """Write ``data`` to ``path`` so readers never see a half-written file.

    Writes ``<path>.tmp`` (fsynced), then ``os.replace``s it over the target;
    the temp file is removed if anything fails, leaving the old file intact.
    """
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    payload = data.encode("utf-8") if isinstance(data, str) else data
    try:
        with open(tmp, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# Files that live next to a task's artifacts but are not deliverable formats:
# in-flight atomic-write temp files and the pre-conversion designer backup.
_AUX_SUFFIXES = (".tmp", ".designer.html")


def list_output_files(task_id: str) -> list[dict]:
    """List remaining artifacts as [{format, ext, size, filename}]."""
    base = task_output_dir(task_id)
    files: list[dict] = []
    if not base.is_dir():
        return files
    for f in sorted(base.iterdir()):
        if f.is_file() and not f.name.endswith(_AUX_SUFFIXES):
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
