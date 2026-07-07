from __future__ import annotations

from .db import init_db, seed_questions, seed_tasks
from .materials import cleanup_generated_records, normalize_existing_materials, scan_materials, seed_professors_from_letters
from .repositories import ensure_program_display_order, normalize_program_results


def bootstrap() -> None:
    init_db()
    seed_professors_from_letters()
    cleanup_generated_records()
    normalize_existing_materials()
    normalize_program_results()
    ensure_program_display_order()
    seed_tasks()
    seed_questions()
    scan_materials()
