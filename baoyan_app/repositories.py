from __future__ import annotations

import shutil
from datetime import datetime

from .config import DATA_DIR
from .db import connect
from .taxonomy import (
    PROGRAM_STAGES,
    PROGRAM_STATUSES,
    PROGRAM_TYPES,
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
        "columns": ["school", "abbreviation", "college", "major", "program_type", "direction", "stage", "date_text", "account", "password", "status", "result", "note", "display_order"],
        "search": ["school", "abbreviation", "college", "major", "program_type", "direction", "stage", "date_text", "account", "status", "result", "note"],
        "order": "display_order asc, id desc",
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
    raw_limit = (query.get("limit") or [""])[0]
    limit = max(1, min(int(raw_limit), 500)) if str(raw_limit).isdigit() else None
    limit_sql = " limit ?" if limit else ""
    if limit:
        params.append(limit)
    with connect() as conn:
        if table == "programs":
            resequence_table(conn, "programs")
        if table == "professors":
            resequence_table(conn, "professors", "status != '已归档'")
        rows = conn.execute(f"select * from {table}{where} order by {meta['order']}{limit_sql}", params).fetchall()
    return {"items": rows_to_dicts(rows)}


def create_row(table: str, payload: dict) -> dict:
    meta = TABLES[table]
    if table in {"programs", "professors"} and not payload.get("display_order"):
        with connect() as conn:
            where = " where status != '已归档'" if table == "professors" else ""
            max_order = conn.execute(f"select coalesce(max(display_order), 0) as n from {table}{where}").fetchone()["n"]
        payload["display_order"] = int(max_order or 0) + 1
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


def move_program(row_id: int, direction: int = 0, target_position: int | None = None) -> dict:
    return move_ordered_row("programs", row_id, direction, "院校记录不存在", target_position=target_position)


def move_professor(row_id: int, direction: int = 0, target_position: int | None = None) -> dict:
    return move_ordered_row("professors", row_id, direction, "导师记录不存在", "status != '已归档'", target_position=target_position)


def move_ordered_row(table: str, row_id: int, direction: int, missing_message: str, where: str = "", target_position: int | None = None) -> dict:
    with connect() as conn:
        resequence_table(conn, table, where)
        current_where = f"id = ?{f' and {where}' if where else ''}"
        current = conn.execute(f"select * from {table} where {current_where}", (row_id,)).fetchone()
        if current is None:
            raise KeyError(missing_message)
        if target_position is not None:
            return move_row_to_position(conn, table, current["id"], int(target_position), where)
        op = ">" if direction > 0 else "<"
        order = "asc" if direction > 0 else "desc"
        target_where = f"display_order {op} ?{f' and {where}' if where else ''}"
        target = conn.execute(
            f"""
            select * from {table}
            where {target_where}
            order by display_order {order}, id {order}
            limit 1
            """,
            (current["display_order"],),
        ).fetchone()
        if target is None:
            return {"ok": True, "moved": False}
        conn.execute(f"update {table} set display_order = ?, updated_at = ? where id = ?", (target["display_order"], now_text(), current["id"]))
        conn.execute(f"update {table} set display_order = ?, updated_at = ? where id = ?", (current["display_order"], now_text(), target["id"]))
    return {"ok": True, "moved": True}


def move_row_to_position(conn, table: str, row_id: int, target_position: int, where: str = "") -> dict:
    where_sql = f" where {where}" if where else ""
    rows = conn.execute(f"select id from {table}{where_sql} order by display_order asc, id asc").fetchall()
    ids = [row["id"] for row in rows]
    if row_id not in ids:
        return {"ok": True, "moved": False}
    target_index = max(0, min(int(target_position) - 1, len(ids) - 1))
    ids.remove(row_id)
    ids.insert(target_index, row_id)
    for index, item_id in enumerate(ids, start=1):
        conn.execute(f"update {table} set display_order = ?, updated_at = ? where id = ?", (index, now_text(), item_id))
    return {"ok": True, "moved": True}


def normalize_program_results() -> None:
    result_to_status = {
        "入营": "入营",
        "优营": "优营",
        "候补": "通过",
        "未入营": "未通过",
        "通过": "通过",
        "未通过": "未通过",
    }
    with connect() as conn:
        rows = conn.execute("select id, status, result from programs where trim(result) != ''").fetchall()
        for row in rows:
            result = row["result"]
            new_status = row["status"] if result in {"待定", row["status"]} else result_to_status.get(result, result)
            conn.execute("update programs set status = ?, result = '', updated_at = ? where id = ?", (new_status, now_text(), row["id"]))
        legacy_status = {
            "材料待补": "填报中",
            "准备材料": "填报中",
            "已报名": "报名",
            "已入营": "入营",
            "已参营": "参营",
            "候补": "通过",
            "未入营": "未通过",
            "已放弃": "放弃报名",
            "已结束": "放弃报名",
            "结束": "放弃报名",
        }
        for old, new in legacy_status.items():
            conn.execute("update programs set status = ?, updated_at = ? where status = ?", (new, now_text(), old))


def ensure_program_display_order() -> None:
    with connect() as conn:
        resequence_table(conn, "programs")
        resequence_table(conn, "professors", "status != '已归档'")


def resequence_table(conn, table: str, where: str = "") -> None:
    where_sql = f" where {where}" if where else ""
    rows = conn.execute(f"select id, display_order from {table}{where_sql} order by display_order asc, id asc").fetchall()
    for index, row in enumerate(rows, start=1):
        if row["display_order"] != index:
            conn.execute(f"update {table} set display_order = ? where id = ?", (index, row["id"]))


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
        "programTypes": PROGRAM_TYPES,
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
