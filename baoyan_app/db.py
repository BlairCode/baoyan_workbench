from __future__ import annotations

import sqlite3

from .config import DATA_DIR, DB_PATH, DEFAULT_SETTINGS
from .utils import now_text


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = {row["name"] for row in conn.execute(f"pragma table_info({table})")}
    if column not in existing:
        conn.execute(f"alter table {table} add column {column} {ddl}")


def init_db() -> None:
    with connect() as conn:
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
                major text not null default '',
                program_type text not null default '',
                direction text not null default '',
                stage text not null default '准备',
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
        ensure_column(conn, "programs", "major", "text not null default ''")
        ensure_column(conn, "programs", "program_type", "text not null default ''")
        ensure_column(conn, "programs", "direction", "text not null default ''")
        ensure_column(conn, "programs", "display_order", "integer not null default 0")
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "insert or ignore into settings (key, value, updated_at) values (?, ?, ?)",
                (key, value, now_text()),
            )
        conn.execute("delete from settings where key = 'email'")


def seed_tasks() -> None:
    defaults = [
        ("检查并更新简历 PDF/Word 两个版本", "基本材料", "", "高", "待办", "确保材料库中的简历是最新版本。"),
        ("补全夏令营项目状态", "夏令营", "", "中", "待办", "根据学校官网逐个确认报名进度。"),
        ("整理导师主页、研究方向和近期论文", "套磁", "", "高", "待办", "在套磁页把论文归到对应导师下。"),
        ("准备 3 分钟中文自我介绍与英文自我介绍", "面试", "", "中", "待办", "关联现有自我介绍文档。"),
    ]
    with connect() as conn:
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
        ("导师", "为什么选择我的课题组？你对这个方向有哪些了解？", "", "套磁"),
    ]
    with connect() as conn:
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
