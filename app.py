# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import sqlite3
import sys
import urllib.parse
import cgi
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "保研准备"
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
DB_PATH = DATA_DIR / "app.db"
HOST = "127.0.0.1"
PORT = int(os.environ.get("BAOYAN_PORT", "8848"))

DEFAULT_SETTINGS = {
    "brandTitle": "推免准备",
    "workspaceName": "本地私有工作台",
    "avatarText": "推",
    "motto": "金鳞岂是池中物，一遇风云便化龙",
    "theme": "default",
}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]


def send_json(handler: BaseHTTPRequestHandler, payload, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_body(handler: BaseHTTPRequestHandler) -> dict:
    size = int(handler.headers.get("Content-Length", "0") or "0")
    if size <= 0:
        return {}
    return json.loads(handler.rfile.read(size).decode("utf-8") or "{}")


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


def folder_level_2(folder: str) -> str:
    if not folder:
        return "保研准备"
    parts = Path(folder).parts
    return str(Path(*parts[:2])) if len(parts) >= 2 else str(Path(*parts))


def ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = {row["name"] for row in conn.execute(f"pragma table_info({table})")}
    if column not in existing:
        conn.execute(f"alter table {table} add column {column} {ddl}")


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            create table if not exists materials (
                id integer primary key autoincrement,
                name text not null,
                category text not null default '其他',
                stage text not null default '通用',
                path text not null unique,
                ext text,
                size integer not null default 0,
                mtime text,
                note text not null default '',
                pinned integer not null default 0,
                created_at text not null,
                updated_at text not null
            );

            create table if not exists programs (
                id integer primary key autoincrement,
                school text not null,
                abbreviation text not null default '',
                college text not null default '',
                stage text not null default '夏令营',
                date_text text not null default '',
                account text not null default '',
                password text not null default '',
                status text not null default '关注中',
                result text not null default '',
                note text not null default '',
                created_at text not null,
                updated_at text not null
            );

            create table if not exists professors (
                id integer primary key autoincrement,
                name text not null,
                school text not null default '',
                college text not null default '',
                direction text not null default '',
                email text not null default '',
                homepage text not null default '',
                status text not null default '未联系',
                note text not null default '',
                created_at text not null,
                updated_at text not null
            );

            create table if not exists tasks (
                id integer primary key autoincrement,
                title text not null,
                scope text not null default '',
                due_date text not null default '',
                priority text not null default '中',
                status text not null default '待办',
                note text not null default '',
                created_at text not null,
                updated_at text not null
            );

            create table if not exists questions (
                id integer primary key autoincrement,
                topic text not null default '综合',
                question text not null,
                answer text not null default '',
                tag text not null default '',
                created_at text not null,
                updated_at text not null
            );

            create table if not exists settings (
                key text primary key,
                value text not null default '',
                updated_at text not null
            );
            """
        )
        ensure_column(conn, "materials", "relative_path", "text not null default ''")
        ensure_column(conn, "materials", "folder", "text not null default ''")
        ensure_column(conn, "materials", "resource_kind", "text not null default '参考资料'")
        ensure_column(conn, "materials", "related_professor", "text not null default ''")
        ensure_column(conn, "materials", "related_program", "text not null default ''")
        ensure_column(conn, "materials", "missing", "integer not null default 0")
        ensure_column(conn, "professors", "display_order", "integer not null default 0")
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "insert or ignore into settings (key, value, updated_at) values (?, ?, ?)",
                (key, value, now_text()),
            )


def normalize_category(value: str) -> str:
    mapping = {
        "申请材料": "基本材料",
        "基础材料": "基本材料",
        "套磁资源": "套磁",
        "导师论文": "套磁",
        "择校参考": "院校",
        "夏令营材料": "院校",
        "科研项目": "项目",
        "项目材料": "项目",
        "面试材料": "面试",
        "参考资料": "参考",
        "其他": "参考",
    }
    return mapping.get(value or "", value or "参考")


def default_stage_for_category(category: str) -> str:
    return {
        "基本材料": "通用",
        "套磁": "套磁",
        "院校": "夏令营",
        "项目": "科研",
        "面试": "面试",
        "参考": "通用",
    }.get(category, "通用")


def clean_professor_name(value: str) -> str:
    name = Path(value).stem
    for prefix in ["套磁信-", "套磁信_"]:
        if name.startswith(prefix):
            name = name[len(prefix) :]
    name = re.sub(r"^[A-Za-z]{2,10}[-_]", "", name)
    return name.strip()


def known_professor_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("select name from professors where trim(name) != ''").fetchall()
    names = sorted({row["name"] for row in rows}, key=len, reverse=True)
    return names


def infer_related_professor(path: Path, kind: str, names: list[str]) -> str:
    stem = path.stem
    if kind == "套磁信":
        name = clean_professor_name(path.name)
        return "" if name in {"套磁信", "模板"} or "模板" in name or "申请书" in name or "自我介绍" in name else name
    for name in names:
        if stem.startswith(name) or f"-{name}" in stem or f"_{name}" in stem:
            return name
    return ""


def classify_material(path: Path, names: list[str]) -> dict:
    rel = relative_text(path)
    parts = path.relative_to(ROOT).parts
    folder = str(Path(*parts[:-1])) if len(parts) > 1 else ""
    joined = "/".join(parts)
    ext = path.suffix.lower()

    category = "参考"
    stage = "通用"
    kind = "参考资料"

    if "套磁信" in joined:
        category, stage, kind = "套磁", "套磁", "套磁信"
    elif "论文" in joined:
        category, stage, kind = "套磁", "套磁", "导师论文"
    elif "项目" in joined:
        category, stage, kind = "项目", "科研", "项目材料"
    elif "夏令营" in joined:
        category, stage, kind = "院校", "夏令营", "夏令营材料"
    elif any(key in path.name for key in ["简历", "成绩", "证明", "证书", "奖励", "四级", "六级"]):
        category, stage, kind = "基本材料", "通用", "基础材料"
    elif ext in {".ppt", ".pptx"} or any(key in path.name for key in ["自我介绍", "面试"]):
        category, stage, kind = "面试", "面试", "面试材料"

    if path.name in {"保研层级.png", "保研高校排行.png", "学科评估.png", "保研.xmind"}:
        category, stage, kind = "院校", "通用", "参考资料"

    return {
        "category": category,
        "stage": stage,
        "kind": kind,
        "folder": folder,
        "relative_path": rel,
        "related_professor": infer_related_professor(path, kind, names),
    }


def scan_materials() -> dict:
    if not SOURCE_DIR.exists():
        return {"inserted": 0, "updated": 0, "missing": 0}
    inserted = 0
    updated = 0
    seen: set[str] = set()
    ignored_dirs = {"data", "web", "__pycache__", ".git"}

    with db() as conn:
        names = known_professor_names(conn)
        conn.execute("update materials set missing = 1 where path like ?", (str(SOURCE_DIR) + "%",))
        for path in SOURCE_DIR.rglob("*"):
            if not path.is_file() or any(part in ignored_dirs for part in path.parts):
                continue
            if path.suffix.lower() in {".tmp", ".crdownload"}:
                continue
            seen.add(str(path))
            stat = path.stat()
            info = classify_material(path, names)
            row = conn.execute("select * from materials where path = ?", (str(path),)).fetchone()
            if row:
                related = row["related_professor"] or info["related_professor"]
                category = normalize_category(row["category"]) if row["category"] else info["category"]
                stage = row["stage"] or default_stage_for_category(category)
                kind = row["resource_kind"] or info["kind"]
                conn.execute(
                    """
                    update materials
                    set name = ?, category = ?, stage = ?, ext = ?, size = ?, mtime = ?,
                        relative_path = ?, folder = ?, resource_kind = ?,
                        related_professor = ?, missing = 0, updated_at = ?
                    where path = ?
                    """,
                    (
                        path.name,
                        category,
                        stage,
                        path.suffix.lower(),
                        stat.st_size,
                        datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        info["relative_path"],
                        info["folder"],
                        kind,
                        related,
                        now_text(),
                        str(path),
                    ),
                )
                updated += 1
            else:
                conn.execute(
                    """
                    insert into materials
                    (name, category, stage, path, ext, size, mtime, note, pinned,
                     relative_path, folder, resource_kind, related_professor, missing,
                     created_at, updated_at)
                    values (?, ?, ?, ?, ?, ?, ?, '', 0, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        path.name,
                        info["category"],
                        info["stage"],
                        str(path),
                        path.suffix.lower(),
                        stat.st_size,
                        datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        info["relative_path"],
                        info["folder"],
                        info["kind"],
                        info["related_professor"],
                        now_text(),
                        now_text(),
                    ),
                )
                inserted += 1
        missing = conn.execute("select count(*) as n from materials where missing = 1").fetchone()["n"]
    return {"inserted": inserted, "updated": updated, "missing": missing}


def seed_programs() -> None:
    # Public template: never seed personal application targets into source code.
    return


def seed_professors_from_letters() -> None:
    letter_dir = SOURCE_DIR / "套磁信"
    if not letter_dir.exists():
        return
    with db() as conn:
        existing = {row["name"] for row in conn.execute("select name from professors").fetchall()}
        for path in sorted(letter_dir.glob("*.docx")):
            name = clean_professor_name(path.name)
            if not name or "模板" in name or "申请书" in name or "自我介绍" in name or name in existing:
                continue
            conn.execute(
                """
                insert into professors
                (name, status, note, created_at, updated_at)
                values (?, '已准备套磁信', ?, ?, ?)
                """,
                (name, f"已有关联套磁信：{path.name}", now_text(), now_text()),
            )
            existing.add(name)


def cleanup_generated_records() -> None:
    with db() as conn:
        conn.execute(
            """
            delete from professors
            where name like '%申请书%' and coalesce(email, '') = '' and coalesce(direction, '') = ''
            """
        )
        conn.execute("update materials set related_professor = '' where related_professor like '%申请书%'")
        conn.execute("delete from professors where name = '自我介绍' and coalesce(email, '') = ''")
        conn.execute(
            """
            update materials
            set category = '面试', stage = '面试', resource_kind = '面试材料', related_professor = ''
            where name like '%自我介绍%'
            """
        )
        conn.execute(
            """
            update materials
            set resource_kind = '申请书'
            where name like '%申请书%'
            """
        )
        conn.execute(
            """
            update materials
            set related_professor = replace(related_professor, 'NJUST-', '')
            where related_professor like 'NJUST-%'
            """
        )
        conn.execute(
            """
            delete from professors
            where name like 'NJUST-%'
              and replace(name, 'NJUST-', '') in (select name from professors)
            """
        )
        conn.execute(
            """
            update professors
            set name = replace(name, 'NJUST-', '')
            where name like 'NJUST-%'
            """
        )


def normalize_existing_materials() -> None:
    with db() as conn:
        rows = conn.execute("select id, category, stage from materials").fetchall()
        for row in rows:
            category = normalize_category(row["category"])
            stage = row["stage"] or default_stage_for_category(category)
            conn.execute(
                "update materials set category = ?, stage = ? where id = ?",
                (category, stage, row["id"]),
            )


def normalize_program_results() -> None:
    result_to_status = {
        "入营": "已入营",
        "优营": "优营",
        "候补": "候补",
        "未入营": "未入营",
        "通过": "通过",
        "未通过": "未通过",
    }
    with db() as conn:
        rows = conn.execute("select id, status, result from programs where trim(result) != ''").fetchall()
        for row in rows:
            result = row["result"]
            if result in {"待定", row["status"]}:
                new_status = row["status"]
            else:
                new_status = result_to_status.get(result, result)
            conn.execute(
                "update programs set status = ?, result = '', updated_at = ? where id = ?",
                (new_status, now_text(), row["id"]),
            )


def seed_professor_profiles() -> None:
    # Public template: profile enrichment belongs in local data, not source code.
    return


def seed_paper_attribution() -> None:
    # Public template: paper-to-professor rules are user-specific local data.
    return


def read_settings() -> dict:
    with db() as conn:
        values = {row["key"]: row["value"] for row in conn.execute("select key, value from settings").fetchall()}
    settings = {**DEFAULT_SETTINGS, **values}
    avatar = DATA_DIR / "avatar"
    for path in DATA_DIR.glob("avatar.*"):
        avatar = path
        break
    if avatar.exists() and avatar.is_file():
        settings["avatarUrl"] = f"/api/settings/avatar?ts={int(avatar.stat().st_mtime)}"
    else:
        settings["avatarUrl"] = ""
    return settings


def update_settings(payload: dict) -> dict:
    allowed = set(DEFAULT_SETTINGS)
    with db() as conn:
        for key, value in payload.items():
            if key not in allowed:
                continue
            if key == "motto":
                value = re.sub(r"\s+", " ", str(value)).strip()[:28] or DEFAULT_SETTINGS["motto"]
            conn.execute(
                """
                insert into settings (key, value, updated_at) values (?, ?, ?)
                on conflict(key) do update set value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, str(value), now_text()),
            )
    return read_settings()


def save_avatar(handler: BaseHTTPRequestHandler) -> dict:
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        raise ValueError("请使用图片上传表单")
    form = cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": handler.headers.get("Content-Length", "0"),
        },
    )
    field = form["avatar"] if "avatar" in form else None
    if field is None or not getattr(field, "filename", ""):
        raise ValueError("没有选择头像")
    ext = Path(field.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        raise ValueError("头像仅支持 PNG、JPG、GIF、WebP")
    DATA_DIR.mkdir(exist_ok=True)
    for old in DATA_DIR.glob("avatar.*"):
        old.unlink()
    target = DATA_DIR / f"avatar{ext}"
    with target.open("wb") as f:
        shutil.copyfileobj(field.file, f)
    return read_settings()


def seed_tasks() -> None:
    defaults = [
        ("检查并更新简历 PDF/Word 两个版本", "基础材料", "", "高", "待办", "确保材料库中的简历是最新版本。"),
        ("补全夏令营项目状态", "夏令营", "", "中", "待办", "根据表格.xlsx 中的学校逐个确认报名进度。"),
        ("整理导师主页、研究方向和近期论文", "套磁", "", "高", "待办", "在套磁页把论文归到对应导师下。"),
        ("准备 3 分钟中文自我介绍与英文自我介绍", "面试", "", "中", "待办", "关联现有自我介绍文档。"),
    ]
    with db() as conn:
        if conn.execute("select count(*) as n from tasks").fetchone()["n"]:
            return
        for row in defaults:
            conn.execute(
                """
                insert into tasks
                (title, scope, due_date, priority, status, note, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*row, now_text(), now_text()),
            )


def seed_questions() -> None:
    rows = [
        ("自我介绍", "请用 1-3 分钟介绍一下自己。", "", "通用"),
        ("项目", "介绍一个你最熟悉的项目，重点讲清楚问题、方法、结果和你的贡献。", "", "项目"),
        ("科研", "你读过的论文里，哪一篇对你影响最大？为什么？", "", "论文"),
        ("套磁", "为什么选择我的课题组？你对这个方向有哪些了解？", "", "导师"),
    ]
    with db() as conn:
        if conn.execute("select count(*) as n from questions").fetchone()["n"]:
            return
        for row in rows:
            conn.execute(
                """
                insert into questions
                (topic, question, answer, tag, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (*row, now_text(), now_text()),
            )


def bootstrap() -> None:
    init_db()
    seed_programs()
    seed_professors_from_letters()
    cleanup_generated_records()
    normalize_existing_materials()
    normalize_program_results()
    seed_professor_profiles()
    seed_tasks()
    seed_questions()
    scan_materials()
    seed_paper_attribution()


TABLES = {
    "materials": {
        "columns": [
            "name",
            "category",
            "stage",
            "path",
            "ext",
            "size",
            "mtime",
            "note",
            "pinned",
            "relative_path",
            "folder",
            "resource_kind",
            "related_professor",
            "related_program",
            "missing",
        ],
        "search": ["name", "category", "stage", "note", "path", "folder", "resource_kind", "related_professor", "related_program"],
        "order": "missing asc, pinned desc, category asc, folder asc, mtime desc, id desc",
    },
    "programs": {
        "columns": ["school", "abbreviation", "college", "stage", "date_text", "account", "password", "status", "result", "note"],
        "search": ["school", "abbreviation", "college", "stage", "status", "result", "note"],
        "order": "id desc",
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
    with db() as conn:
        rows = conn.execute(f"select * from {table}{where} order by {meta['order']}", params).fetchall()
    return {"items": rows_to_dicts(rows)}


def create_row(table: str, payload: dict) -> dict:
    meta = TABLES[table]
    cols = [col for col in meta["columns"] if col in payload]
    if not cols:
        raise ValueError("没有可保存的字段")
    with db() as conn:
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
    with db() as conn:
        conn.execute(f"update {table} set {sets} where id = ?", [payload.get(col, "") for col in cols] + [now_text(), row_id])
        row = conn.execute(f"select * from {table} where id = ?", (row_id,)).fetchone()
    if row is None:
        raise KeyError("记录不存在")
    return dict(row)


def delete_row(table: str, row_id: int) -> dict:
    with db() as conn:
        if table == "professors":
            row = conn.execute("select name from professors where id = ?", (row_id,)).fetchone()
            if row:
                conn.execute("update materials set related_professor = '' where related_professor = ?", (row["name"],))
        conn.execute(f"delete from {table} where id = ?", (row_id,))
    return {"ok": True}


def delete_material_file(row_id: int) -> dict:
    row = get_material(row_id)
    if row is None:
        raise FileNotFoundError("材料不存在")
    path = Path(row["path"])
    if not is_safe_path(path) or not path.exists() or not path.is_file():
        raise FileNotFoundError("文件不存在或不在项目目录中")
    path.unlink()
    with db() as conn:
        conn.execute(
            "update materials set missing = 1, updated_at = ? where id = ?",
            (now_text(), row_id),
        )
    return {"ok": True, "deleted": str(path)}


def get_material(row_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("select * from materials where id = ?", (row_id,)).fetchone()


def material_actions(row: dict) -> dict:
    ext = (row.get("ext") or "").lower()
    can_preview = ext in {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".md", ".csv"}
    return {"canPreview": can_preview, "openUrl": f"/api/materials/{row['id']}/open", "viewUrl": f"/files/{row['id']}/view"}


def contact_workspace() -> dict:
    with db() as conn:
        professors = rows_to_dicts(conn.execute("select * from professors where status != '已归档' order by display_order asc, name asc").fetchall())
        resources = rows_to_dicts(
            conn.execute(
                """
                select * from materials
                where missing = 0 and (category = '套磁' or related_professor != '')
                order by related_professor = '', related_professor asc, resource_kind asc, mtime desc
                """
            ).fetchall()
        )
    for row in resources:
        row["actions"] = material_actions(row)
    by_prof: dict[str, dict] = {}
    for prof in professors:
        by_prof[prof["name"]] = {**prof, "letters": [], "related": []}
    unassigned = {"items": []}
    for item in resources:
        target = item["related_professor"]
        if target and target not in by_prof:
            by_prof[target] = {
                "id": None,
                "name": target,
                "school": "",
                "college": "",
                "direction": "",
                "email": "",
                "homepage": "",
                "status": "待补充",
                "note": "由文件名自动识别，尚未建立导师记录。",
                "letters": [],
                "related": [],
            }
        if target:
            if item["resource_kind"] == "套磁信":
                by_prof[target]["letters"].append(item)
            else:
                by_prof[target]["related"].append(item)
        else:
            unassigned["items"].append(item)
    return {"professors": list(by_prof.values()), "unassigned": unassigned}


def resource_groups() -> dict:
    with db() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                select * from materials
                where missing = 0
                order by missing asc, category asc, folder asc, resource_kind asc, name asc
                """
            ).fetchall()
        )
    groups: dict[str, dict] = {}
    folders: dict[str, dict] = {}
    for row in rows:
        row["actions"] = material_actions(row)
        groups.setdefault(row["category"], {"name": row["category"], "count": 0, "items": []})
        groups[row["category"]]["count"] += 1
        groups[row["category"]]["items"].append(row)
        folder_name = folder_level_2(row["folder"])
        folder_path = str((ROOT / folder_name).resolve())
        folders.setdefault(folder_name, {"name": folder_name, "path": folder_path, "count": 0, "items": []})
        folders[folder_name]["count"] += 1
        folders[folder_name]["items"].append(row)
    return {"byCategory": list(groups.values()), "byFolder": list(folders.values())}


def app_options() -> dict:
    with db() as conn:
        professors = [row["name"] for row in conn.execute("select name from professors order by display_order asc, name asc").fetchall()]
        programs = [row["school"] for row in conn.execute("select school from programs order by id asc").fetchall()]
    return {
        "categories": ["基本材料", "套磁", "院校", "项目", "面试", "参考"],
        "professors": professors,
        "programs": programs,
    }


def backup_db() -> dict:
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"app-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    shutil.copy2(DB_PATH, target)
    return {"path": str(target)}


def upload_material(handler: BaseHTTPRequestHandler) -> dict:
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        raise ValueError("请使用文件上传表单")
    form = cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": handler.headers.get("Content-Length", "0"),
        },
    )
    field = form["file"] if "file" in form else None
    if field is None or not getattr(field, "filename", ""):
        raise ValueError("没有选择文件")
    upload_dir = SOURCE_DIR / "网页添加"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(field.filename).name
    target = upload_dir / safe_name
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        target = upload_dir / f"{stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}{suffix}"
    with target.open("wb") as f:
        shutil.copyfileobj(field.file, f)
    result = scan_materials()
    return {"path": str(target), **result}


def summary() -> dict:
    with db() as conn:
        total_letters = conn.execute(
            "select count(*) as n from materials where missing = 0 and resource_kind = '套磁信'"
        ).fetchone()["n"]
        contacted = conn.execute(
            """
            select count(*) as n from professors
            where status in ('已发送', '官回', '养鱼', '已回复', '约面试', '面试通过', '无回复', '默拒', '拒绝')
            """
        ).fetchone()["n"]
        camp_applied = conn.execute(
            """
            select count(*) as n from programs
            where stage = '夏令营' and status in ('已报名', '已入营', '已参营', '结束')
            """
        ).fetchone()["n"]
        camp_total = conn.execute("select count(*) as n from programs where stage = '夏令营'").fetchone()["n"]
        counts = {
            "materials": conn.execute("select count(*) as n from materials where missing = 0").fetchone()["n"],
            "programs": conn.execute("select count(*) as n from programs").fetchone()["n"],
            "professors": conn.execute("select count(*) as n from professors").fetchone()["n"],
            "tasksOpen": conn.execute("select count(*) as n from tasks where status != '已完成'").fetchone()["n"],
            "unassignedPapers": conn.execute(
                "select count(*) as n from materials where missing = 0 and resource_kind = '导师论文' and related_professor = ''"
            ).fetchone()["n"],
            "contacted": contacted,
            "totalLetters": total_letters,
            "campApplied": camp_applied,
            "campTotal": camp_total,
        }
        categories = rows_to_dicts(
            conn.execute(
                "select category, count(*) as count from materials where missing = 0 group by category order by count desc"
            ).fetchall()
        )
        recent_materials = rows_to_dicts(
            conn.execute("select * from materials where missing = 0 order by mtime desc limit 8").fetchall()
        )
        open_tasks = rows_to_dicts(
            conn.execute(
                "select * from tasks where status != '已完成' order by due_date = '', due_date asc, id desc limit 8"
            ).fetchall()
        )
        programs = rows_to_dicts(conn.execute("select * from programs order by id desc limit 8").fetchall())
    for row in recent_materials:
        row["actions"] = material_actions(row)
    return {
        "counts": counts,
        "categories": categories,
        "recentMaterials": recent_materials,
        "openTasks": open_tasks,
        "programs": programs,
        "root": str(ROOT),
        "sourceDir": str(SOURCE_DIR),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "BaoyanDesk/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (now_text(), fmt % args))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/summary":
                send_json(self, summary())
                return
            if path == "/api/contact-workspace":
                send_json(self, contact_workspace())
                return
            if path == "/api/materials/groups":
                send_json(self, resource_groups())
                return
            if path == "/api/options":
                send_json(self, app_options())
                return
            if path == "/api/settings":
                send_json(self, read_settings())
                return
            if path == "/api/settings/avatar":
                self.serve_avatar()
                return
            match = re.fullmatch(r"/api/(materials|programs|professors|tasks|questions)", path)
            if match:
                send_json(self, list_table(match.group(1), query))
                return
            match = re.fullmatch(r"/files/(\d+)/view", path)
            if match:
                self.serve_material(int(match.group(1)))
                return
            self.serve_static(path)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/materials/scan":
                send_json(self, scan_materials())
                return
            if path == "/api/materials/upload":
                send_json(self, upload_material(self), 201)
                return
            if path == "/api/backup":
                send_json(self, backup_db())
                return
            if path == "/api/settings/avatar":
                send_json(self, save_avatar(self))
                return
            if path == "/api/root/open":
                self.open_path(SOURCE_DIR)
                return
            if path == "/api/folders/open":
                payload = read_body(self)
                target = Path(payload.get("path", ""))
                self.open_path(target)
                return
            match = re.fullmatch(r"/api/materials/(\d+)/(open|open-folder)", path)
            if match:
                self.open_material(int(match.group(1)), folder=match.group(2) == "open-folder")
                return
            match = re.fullmatch(r"/api/(materials|programs|professors|tasks|questions)", path)
            if match:
                send_json(self, create_row(match.group(1), read_body(self)), 201)
                return
            send_json(self, {"error": "Not found"}, 404)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_PATCH(self) -> None:
        parsed_path = urllib.parse.urlparse(self.path).path
        if parsed_path == "/api/settings":
            try:
                send_json(self, update_settings(read_body(self)))
            except Exception as exc:
                send_json(self, {"error": str(exc)}, 500)
            return
        match = re.fullmatch(r"/api/(materials|programs|professors|tasks|questions)/(\d+)", parsed_path)
        if not match:
            send_json(self, {"error": "Not found"}, 404)
            return
        try:
            send_json(self, update_row(match.group(1), int(match.group(2)), read_body(self)))
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_DELETE(self) -> None:
        match = re.fullmatch(r"/api/(materials|programs|professors|tasks|questions)/(\d+)", urllib.parse.urlparse(self.path).path)
        file_match = re.fullmatch(r"/api/materials/(\d+)/file", urllib.parse.urlparse(self.path).path)
        if file_match:
            try:
                send_json(self, delete_material_file(int(file_match.group(1))))
            except Exception as exc:
                send_json(self, {"error": str(exc)}, 500)
            return
        if not match:
            send_json(self, {"error": "Not found"}, 404)
            return
        try:
            send_json(self, delete_row(match.group(1), int(match.group(2))))
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        target = (WEB_DIR / path.lstrip("/")).resolve()
        if not is_safe_path(target) or not target.exists() or not target.is_file():
            send_json(self, {"error": "Not found"}, 404)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_material(self, row_id: int) -> None:
        row = get_material(row_id)
        if row is None:
            send_json(self, {"error": "材料不存在"}, 404)
            return
        path = Path(row["path"])
        if not is_safe_path(path) or not path.exists():
            send_json(self, {"error": "文件不存在或不在项目目录中"}, 404)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = urllib.parse.quote(path.name)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{encoded}")
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with path.open("rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def serve_avatar(self) -> None:
        avatar = None
        for path in DATA_DIR.glob("avatar.*"):
            avatar = path
            break
        if avatar is None or not avatar.exists():
            send_json(self, {"error": "头像不存在"}, 404)
            return
        content_type = mimetypes.guess_type(avatar.name)[0] or "image/png"
        body = avatar.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def open_material(self, row_id: int, folder: bool = False) -> None:
        row = get_material(row_id)
        if row is None:
            send_json(self, {"error": "材料不存在"}, 404)
            return
        path = Path(row["path"])
        target = path.parent if folder else path
        if not is_safe_path(target) or not target.exists():
            send_json(self, {"error": "文件不存在或不在项目目录中"}, 404)
            return
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.spawnlp(os.P_NOWAIT, "open", "open", str(target))
        else:
            os.spawnlp(os.P_NOWAIT, "xdg-open", "xdg-open", str(target))
        send_json(self, {"ok": True})

    def open_path(self, target: Path) -> None:
        if not is_safe_path(target) or not target.exists():
            send_json(self, {"error": "路径不存在或不在项目目录中"}, 404)
            return
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.spawnlp(os.P_NOWAIT, "open", "open", str(target))
        else:
            os.spawnlp(os.P_NOWAIT, "xdg-open", "xdg-open", str(target))
        send_json(self, {"ok": True})


def main() -> None:
    bootstrap()
    print(f"推免准备系统已启动：http://{HOST}:{PORT}")
    print(f"资料目录：{SOURCE_DIR}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
