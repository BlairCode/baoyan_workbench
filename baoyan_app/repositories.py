from __future__ import annotations

import shutil
from datetime import datetime

from .config import DATA_DIR
from .db import connect
from .taxonomy import (
    PROGRAM_STAGES,
    PROGRAM_STATUSES,
    PROFESSOR_STATUSES,
    QUESTION_TOPICS,
    RESOURCE_CATEGORIES,
    TASK_PRIORITIES,
    TASK_STATUSES,
)
from .utils import now_text, rows_to_dicts
from .contact import professor_key

TABLES = {
    "materials": {
        "columns": ["name", "category", "stage", "path", "ext", "size", "mtime", "note", "pinned", "relative_path", "folder", "resource_kind", "related_professor", "related_program", "missing"],
        "search": ["name", "category", "stage", "note", "path", "folder", "resource_kind", "related_professor", "related_program"],
        "order": "missing asc, pinned desc, category asc, folder asc, mtime desc, id desc",
    },
    "programs": {
        "columns": ["school", "abbreviation", "college", "stage", "date_text", "account", "password", "status", "result", "note", "display_order"],
        "search": ["school", "abbreviation", "college", "stage", "status", "result", "note"],
        "order": """
            case status
              when '优营' then 10 when '通过' then 20 when '已入营' then 30
              when '已参营' then 40 when '候补' then 50 when '已报名' then 60
              when '准备材料' then 80 when '关注中' then 90
              when '已放弃' then 100 when '未入营' then 110 when '未通过' then 120
              else 95 end,
            display_order asc, id desc
        """,
    },
    "professors": {
        "columns": ["name", "school", "college", "direction", "email", "homepage", "status", "note", "display_order"],
        "search": ["name", "school", "college", "direction", "email", "status", "note"],
        "order": "display_order asc, id desc",
    },
    "tasks": {
        "columns": ["title", "scope", "due_date", "priority", "status", "note"],
        "search": ["title", "scope", "priority", "status", "note"],
        "order": "case status when '已完成' then 1 else 0 end, due_date = '', due_date asc, id desc",
    },
    "questions": {
        "columns": ["topic", "question", "answer", "tag"],
        "search": ["topic", "question", "answer", "tag"],
        "order": "id desc",
    },
}


def list_table(table: str, query: dict) -> dict:
    meta = TABLES[table]
    q = (query.get("q") or [""])[0].strip()
    where = ""
    params: list[str] = []
    if q:
        where = " where " + " or ".join([f"{col} like ?" for col in meta["search"]])
        params = [f"%{q}%"] * len(meta["search"])
    with connect() as conn:
        rows = conn.execute(f"select * from {table}{where} order by {meta['order']}", params).fetchall()
    return {"items": rows_to_dicts(rows)}


def create_row(table: str, payload: dict) -> dict:
    meta = TABLES[table]
    cols = [col for col in meta["columns"] if col in payload]
    if not cols:
        raise ValueError("没有可保存的字段")
    with connect() as conn:
        cur = conn.execute(
            f"insert into {table} ({', '.join(cols + ['created_at', 'updated_at'])}) values ({', '.join(['?'] * (len(cols) + 2))})",
            [payload.get(col, "") for col in cols] + [now_text(), now_text()],
        )
        row = conn.execute(f"select * from {table} where id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_row(table: str, row_id: int, payload: dict) -> dict:
    meta = TABLES[table]
    cols = [col for col in meta["columns"] if col in payload]
    if not cols:
        raise ValueError("没有可更新的字段")
    sets = ", ".join([f"{col} = ?" for col in cols] + ["updated_at = ?"])
    with connect() as conn:
        conn.execute(f"update {table} set {sets} where id = ?", [payload.get(col, "") for col in cols] + [now_text(), row_id])
        row = conn.execute(f"select * from {table} where id = ?", (row_id,)).fetchone()
    if row is None:
        raise KeyError("记录不存在")
    return dict(row)


def delete_row(table: str, row_id: int) -> dict:
    with connect() as conn:
        if table == "professors":
            row = conn.execute("select name from professors where id = ?", (row_id,)).fetchone()
            if row:
                conn.execute("update materials set related_professor = '' where related_professor = ?", (row["name"],))
        conn.execute(f"delete from {table} where id = ?", (row_id,))
    return {"ok": True}


def move_program(row_id: int, direction: int) -> dict:
    with connect() as conn:
        current = conn.execute("select * from programs where id = ?", (row_id,)).fetchone()
        if current is None:
            raise KeyError("院校记录不存在")
        op = ">" if direction > 0 else "<"
        order = "asc" if direction > 0 else "desc"
        target = conn.execute(
            f"""
            select * from programs
            where status = ? and display_order {op} ?
            order by display_order {order}, id {order}
            limit 1
            """,
            (current["status"], current["display_order"]),
        ).fetchone()
        if target is None:
            return {"ok": True, "moved": False}
        conn.execute("update programs set display_order = ?, updated_at = ? where id = ?", (target["display_order"], now_text(), current["id"]))
        conn.execute("update programs set display_order = ?, updated_at = ? where id = ?", (current["display_order"], now_text(), target["id"]))
    return {"ok": True, "moved": True}


def normalize_program_results() -> None:
    result_to_status = {
        "入营": "已入营",
        "优营": "优营",
        "候补": "候补",
        "未入营": "未入营",
        "通过": "通过",
        "未通过": "未通过",
    }
    with connect() as conn:
        rows = conn.execute("select id, status, result from programs where trim(result) != ''").fetchall()
        for row in rows:
            result = row["result"]
            new_status = row["status"] if result in {"待定", row["status"]} else result_to_status.get(result, result)
            conn.execute("update programs set status = ?, result = '', updated_at = ? where id = ?", (new_status, now_text(), row["id"]))
        legacy_status = {"材料待补": "准备材料", "已结束": "已放弃", "结束": "已放弃"}
        for old, new in legacy_status.items():
            conn.execute("update programs set status = ?, updated_at = ? where status = ?", (new, now_text(), old))


def ensure_program_display_order() -> None:
    with connect() as conn:
        rows = conn.execute("select id, display_order from programs order by display_order asc, id asc").fetchall()
        for index, row in enumerate(rows, start=10):
            if not row["display_order"]:
                conn.execute("update programs set display_order = ? where id = ?", (index * 10, row["id"]))


def app_options() -> dict:
    with connect() as conn:
        professor_rows = conn.execute("select name from professors order by display_order asc, name asc").fetchall()
        programs = [row["school"] for row in conn.execute("select school from programs order by display_order asc, id desc").fetchall()]
    professors = []
    seen_professors = set()
    for row in professor_rows:
        name = professor_key(row["name"])
        if name and name not in seen_professors:
            professors.append(name)
            seen_professors.add(name)
    return {
        "categories": RESOURCE_CATEGORIES,
        "programStages": PROGRAM_STAGES,
        "programStatuses": PROGRAM_STATUSES,
        "professorStatuses": PROFESSOR_STATUSES,
        "taskPriorities": TASK_PRIORITIES,
        "taskStatuses": TASK_STATUSES,
        "questionTopics": QUESTION_TOPICS,
        "professors": professors,
        "programs": programs,
    }


def backup_db() -> dict:
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"app-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    shutil.copy2(DATA_DIR / "app.db", target)
    return {"path": str(target)}
