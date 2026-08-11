from __future__ import annotations

from collections import Counter

from .config import ROOT, SOURCE_DIR
from .contact import merge_professor, professor_key
from .db import connect
from .materials import material_actions
from .taxonomy import CONTACTED_PROFESSOR_STATUSES, PROGRAM_ADMITTED_STATUSES, PROGRAM_APPLIED_STATUSES, PROGRAM_EXCELLENT_STATUSES, PROGRAM_NEGATIVE_STATUSES, REPLIED_PROFESSOR_STATUSES
from .utils import rows_to_dicts


def _count(conn, sql: str, params: tuple = ()) -> int:
    return conn.execute(sql, params).fetchone()["n"]


def _logical_professors(conn) -> list[dict]:
    rows = rows_to_dicts(
        conn.execute(
            "select * from professors where status != '已归档' order by display_order asc, id asc"
        ).fetchall()
    )
    by_prof: dict[str, dict] = {}
    for prof in rows:
        key = professor_key(prof["name"])
        item = {**prof, "name": key or prof["name"], "letters": [], "related": []}
        by_prof[key] = merge_professor(by_prof[key], item) if key in by_prof else item
    return list(by_prof.values())


def _status_breakdown(rows: list[dict]) -> list[dict]:
    counts = Counter((row.get("status") or "未填写").strip() or "未填写" for row in rows)
    return [{"name": name, "count": count} for name, count in counts.most_common()]


def _count_statuses(rows: list[dict], statuses: set[str]) -> int:
    return sum(1 for row in rows if row.get("status") in statuses)


def summary() -> dict:
    with connect() as conn:
        logical_professors = _logical_professors(conn)
        total_programs = _count(conn, "select count(*) as n from programs")
        camp_total = _count(conn, "select count(*) as n from programs where stage = '夏令营'")
        camp_applied = _count(conn, f"select count(*) as n from programs where stage = '夏令营' and status in ({','.join(['?'] * len(PROGRAM_APPLIED_STATUSES))})", tuple(PROGRAM_APPLIED_STATUSES))
        camp_admitted = _count(conn, f"select count(*) as n from programs where stage = '夏令营' and status in ({','.join(['?'] * len(PROGRAM_ADMITTED_STATUSES))})", tuple(PROGRAM_ADMITTED_STATUSES))
        camp_excellent = _count(conn, f"select count(*) as n from programs where stage = '夏令营' and status in ({','.join(['?'] * len(PROGRAM_EXCELLENT_STATUSES))})", tuple(PROGRAM_EXCELLENT_STATUSES))
        counts = {
            "materials": _count(conn, "select count(*) as n from materials where missing = 0"),
            "programs": total_programs,
            "professors": len(logical_professors),
            "tasksOpen": _count(conn, "select count(*) as n from tasks where status != '已完成'"),
            "sent": _count_statuses(logical_professors, CONTACTED_PROFESSOR_STATUSES),
            "replied": _count_statuses(logical_professors, REPLIED_PROFESSOR_STATUSES),
            "totalLetters": _count(conn, "select count(*) as n from materials where missing = 0 and resource_kind = '套磁信'"),
            "campInterested": camp_total,
            "campApplied": camp_applied,
            "campAdmitted": camp_admitted,
            "campExcellent": camp_excellent,
            "programNegative": _count(conn, f"select count(*) as n from programs where status in ({','.join(['?'] * len(PROGRAM_NEGATIVE_STATUSES))})", tuple(PROGRAM_NEGATIVE_STATUSES)),
        }
        categories = rows_to_dicts(conn.execute("select category, count(*) as count from materials where missing = 0 group by category order by count desc").fetchall())
        resource_kinds = rows_to_dicts(conn.execute("select resource_kind as name, count(*) as count from materials where missing = 0 group by resource_kind order by count desc limit 8").fetchall())
        program_status = rows_to_dicts(conn.execute("select status as name, count(*) as count from programs group by status order by count desc").fetchall())
        professor_status = _status_breakdown(logical_professors)
        stage_breakdown = rows_to_dicts(conn.execute("select stage as name, count(*) as count from programs group by stage order by count desc").fetchall())
        task_breakdown = rows_to_dicts(conn.execute("select status as name, count(*) as count from tasks group by status order by count desc").fetchall())
        recent_materials = rows_to_dicts(conn.execute("select * from materials where missing = 0 order by mtime desc limit 8").fetchall())
        open_tasks = rows_to_dicts(conn.execute("select * from tasks where status != '已完成' order by due_date = '', due_date asc, id desc limit 8").fetchall())
        hot_programs = rows_to_dicts(conn.execute("select * from programs order by display_order asc, id desc limit 8").fetchall())
    for row in recent_materials:
        row["actions"] = material_actions(row)
    return {
        "counts": counts,
        "rates": {
            "campApplyRate": round(camp_applied / camp_total * 100, 1) if camp_total else 0,
            "campAdmitRate": round(camp_admitted / camp_applied * 100, 1) if camp_applied else 0,
            "replyRate": round(counts["replied"] / counts["sent"] * 100, 1) if counts["sent"] else 0,
        },
        "categories": categories,
        "resourceKinds": resource_kinds,
        "programStatus": program_status,
        "professorStatus": professor_status,
        "stageBreakdown": stage_breakdown,
        "taskBreakdown": task_breakdown,
        "recentMaterials": recent_materials,
        "openTasks": open_tasks,
        "programs": hot_programs,
        "root": str(ROOT),
        "sourceDir": str(SOURCE_DIR),
    }
