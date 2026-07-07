from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import ROOT


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def rows_to_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]


def is_safe_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
        return resolved == ROOT or ROOT in resolved.parents
    except OSError:
        return False


def relative_text(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def folder_level(folder: str, depth: int = 2) -> str:
    if not folder:
        return "保研准备"
    parts = Path(folder).parts
    return str(Path(*parts[:depth])) if len(parts) >= depth else str(Path(*parts))
