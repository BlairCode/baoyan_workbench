from __future__ import annotations

from .config import ROOT, SOURCE_DIR
from .db import connect
from .materials import material_actions
from .taxonomy import CONTACTED_PROFESSOR_STATUSES, PROGRAM_ADMITTED_STATUSES, PROGRAM_APPLIED_STATUSES, PROGRAM_EXCELLENT_STATUSES, PROGRAM_NEGATIVE_STATUSES, REPLIED_PROFESSOR_STATUSES
from .utils import rows_to_dicts


def _count(conn, sql: str, params: tuple = ()) -> int:
    return conn.execute(sql, params).fetchone()["n"]


def summary() -> dict:
    with connect() as conn:
        total_programs = _count(conn, "select count(*) as n from programs")
        camp_total = _count(conn, "select count(*) as n from programs where stage = '夏令营'")
        camp_applied = _count(conn, f"select count(*) as n from programs where stage = '夏令营' and status in ({','.join(['?'] * len(PROGRAM_APPLIED_STATUSES))})", tuple(PROGRAM_APPLIED_STATUSES))
        camp_admitted = _count(conn, f"select count(*) as n from programs where stage = '夏令营' and status in ({','.join(['?'] * len(PROGRAM_ADMITTED_STATUSES))})", tuple(PROGRAM_ADMITTED_STATUSES))
        camp_excellent = _count(conn, f"select count(*) as n from programs where stage = '夏令营' and status in ({','.join(['?'] * len(PROGRAM_EXCELLENT_STATUSES))})", tuple(PROGRAM_EXCELLENT_STATUSES))
        counts = {
            "materials": _count(conn, "select count(*) as n from materials where missing = 0"),
            "programs": total_programs,
            "professors": _count(conn, "select count(*) as n from professors"),
            "tasksOpen": _count(conn, "select count(*) as n from tasks where status != '已完成'"),
            "sent": _count(conn, f"select count(*) as n from professors where status in ({','.join(['?'] * len(CONTACTED_PROFESSOR_STATUSES))})", tuple(CONTACTED_PROFESSOR_STATUSES)),
            "replied": _count(conn, f"select count(*) as n from professors where status in ({','.join(['?'] * len(REPLIED_PROFESSOR_STATUSES))})", tuple(REPLIED_PROFESSOR_STATUSES)),
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
        professor_status = rows_to_dicts(conn.execute("select status as name, count(*) as count from professors group by status order by count desc").fetchall())
        contact_status = [
            {"name": "已准备套磁信", "count": _count(conn, "select count(*) as n from professors where status in ('已准备套磁信')")},
            {"name": "已发送", "count": counts["sent"]},
            {"name": "有回复", "count": counts["replied"]},
            {"name": "面试推进", "count": _count(conn, "select count(*) as n from professors where status in ('约面试', '面试通过')")},
        ]
        stage_breakdown = rows_to_dicts(conn.execute("select stage as name, count(*) as count from programs group by stage order by count desc").fetchall())
        task_breakdown = rows_to_dicts(conn.execute("select status as name, count(*) as count from tasks group by status order by count desc").fetchall())
        recent_materials = rows_to_dicts(conn.execute("select * from materials where missing = 0 order by mtime desc limit 8").fetchall())
        open_tasks = rows_to_dicts(conn.execute("select * from tasks where status != '已完成' order by due_date = '', due_date asc, id desc limit 8").fetchall())
        hot_programs = rows_to_dicts(conn.execute("select * from programs order by case status when '优营' then 10 when '通过' then 20 when '已入营' then 30 when '已参营' then 40 when '候补' then 50 when '已报名' then 60 else 90 end, display_order asc, id desc limit 8").fetchall())
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
        "contactStatus": contact_status,
        "stageBreakdown": stage_breakdown,
        "taskBreakdown": task_breakdown,
        "recentMaterials": recent_materials,
        "openTasks": open_tasks,
        "programs": hot_programs,
        "root": str(ROOT),
        "sourceDir": str(SOURCE_DIR),
    }
