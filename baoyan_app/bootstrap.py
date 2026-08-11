from __future__ import annotations

from .db import init_db, seed_questions, seed_tasks
from .repositories import ensure_program_display_order, normalize_program_results


def bootstrap() -> None:
    init_db()
    normalize_program_results()
    ensure_program_display_order()
    seed_tasks()
    seed_questions()
