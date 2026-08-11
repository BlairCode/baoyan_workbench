from __future__ import annotations

import cgi
import os
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR, MAX_UPLOAD_BYTES, SOURCE_DIR
from .db import connect
from .taxonomy import default_stage_for_category, normalize_category
from .utils import folder_level, is_safe_path, now_text, relative_text, rows_to_dicts


IGNORED_DIRECTORY_NAMES = {
    ".agents",
    ".cache",
    ".codex",
    ".git",
    ".next",
    ".nuxt",
    ".pnpm-store",
    ".pytest_cache",
    ".turbo",
    ".venv",
    ".wrangler",
    "__pycache__",
    "node_modules",
    "venv",
}
IGNORED_FILE_SUFFIXES = {".tmp", ".crdownload", ".part"}


def is_ignored_material_path(path: Path) -> bool:
    try:
        relative_parts = path.relative_to(SOURCE_DIR).parts
    except ValueError:
        return True
    return any(part.lower() in IGNORED_DIRECTORY_NAMES for part in relative_parts)


def purge_ignored_material_rows(conn: sqlite3.Connection) -> int:
    rows = conn.execute("select id, path from materials").fetchall()
    ignored_ids = [(row["id"],) for row in rows if is_ignored_material_path(Path(row["path"]))]
    if ignored_ids:
        conn.executemany("delete from materials where id = ?", ignored_ids)
    return len(ignored_ids)


def clean_professor_name(value: str) -> str:
    name = Path(value).stem
    name = re.sub(r"^套磁信[\s\-_—－]*", "", name)
    name = re.sub(r"^[A-Za-z]{2,10}[-_]", "", name)
    return name.strip(" \t\r\n-_—－")


def known_professor_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("select name from professors where trim(name) != ''").fetchall()
    return sorted({row["name"] for row in rows}, key=len, reverse=True)


def infer_related_professor(path: Path, kind: str, names: list[str]) -> str:
    stem = path.stem
    if kind == "套磁信":
        name = clean_professor_name(path.name)
        blocked = {"套磁信", "模板", "申请书", "自我介绍"}
        return "" if name in blocked or any(word in name for word in blocked) else name
    for name in names:
        if stem.startswith(name) or f"-{name}" in stem or f"_{name}" in stem:
            return name
    return ""


def classify_material(path: Path, names: list[str]) -> dict:
    rel = relative_text(path)
    parts = path.relative_to(SOURCE_DIR.parent).parts
    folder = str(Path(*parts[:-1])) if len(parts) > 1 else ""
    joined = "/".join(parts)
    ext = path.suffix.lower()

    category, stage, kind = "参考", "通用", "参考资料"
    if "套磁信" in joined:
        category, stage, kind = "套磁", "套磁", "套磁信"
    elif "论文" in joined:
        category, stage, kind = "套磁", "套磁", "导师论文"
    elif "项目" in joined:
        category, stage, kind = "项目", "科研", "项目材料"
    elif "夏令营" in joined:
        category, stage, kind = "院校", "夏令营", "夏令营材料"
    elif any(key in path.name for key in ["简历", "成绩", "证明", "证书", "奖状", "四级", "六级"]):
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
    with connect() as conn:
        purged = purge_ignored_material_rows(conn)
        sanitize_material_paths(conn)

    if not SOURCE_DIR.exists():
        with connect() as conn:
            missing = conn.execute("select count(*) as n from materials where missing = 1").fetchone()["n"]
        return {"inserted": 0, "updated": 0, "missing": missing, "purged": purged}

    inserted = 0
    updated = 0
    with connect() as conn:
        names = known_professor_names(conn)
        conn.execute("update materials set missing = 1 where path like ?", (str(SOURCE_DIR) + "%",))
        for root, directory_names, file_names in os.walk(SOURCE_DIR):
            directory_names[:] = [
                name for name in directory_names if name.lower() not in IGNORED_DIRECTORY_NAMES
            ]
            for file_name in file_names:
                path = Path(root) / file_name
                if path.suffix.lower() in IGNORED_FILE_SUFFIXES or path.name.startswith("~$"):
                    continue
                stat = path.stat()
                info = classify_material(path, names)
                row = conn.execute("select * from materials where path = ?", (str(path),)).fetchone()
                if row:
                    category = normalize_category(row["category"]) if row["category"] else info["category"]
                    stage = row["stage"] or default_stage_for_category(category)
                    related = row["related_professor"] or info["related_professor"]
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
                            row["resource_kind"] or info["kind"],
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
        ensure_professors_from_letter_materials(conn)
        missing = conn.execute("select count(*) as n from materials where missing = 1").fetchone()["n"]
    return {"inserted": inserted, "updated": updated, "missing": missing, "purged": purged}


def sanitize_material_paths(conn: sqlite3.Connection) -> None:
    """Hide stale rows copied from another machine or an older project path."""
    rows = conn.execute("select id, path from materials where missing = 0").fetchall()
    for row in rows:
        path = Path(row["path"])
        if not is_safe_path(path) or not path.exists():
            conn.execute("update materials set missing = 1, updated_at = ? where id = ?", (now_text(), row["id"]))


def seed_professors_from_letters() -> None:
    letter_dir = SOURCE_DIR / "套磁信"
    if not letter_dir.exists():
        return
    with connect() as conn:
        existing = {row["name"] for row in conn.execute("select name from professors").fetchall()}
        for path in sorted(letter_dir.glob("*.docx")):
            name = clean_professor_name(path.name)
            if not name or name in existing or any(word in name for word in ["模板", "申请书", "自我介绍"]):
                continue
            conn.execute(
                """
                insert into professors
                (name, status, note, created_at, updated_at)
                values (?, '待补充', ?, ?, ?)
                """,
                (name, f"已有关联套磁信：{path.name}", now_text(), now_text()),
            )
            existing.add(name)
        ensure_professors_from_letter_materials(conn)


def ensure_professors_from_letter_materials(conn: sqlite3.Connection) -> int:
    created = 0
    rows = conn.execute(
        """
        select related_professor, name
        from materials
        where missing = 0
          and resource_kind = '套磁信'
          and trim(related_professor) != ''
        order by mtime asc, id asc
        """
    ).fetchall()
    existing = {row["name"] for row in conn.execute("select name from professors where trim(name) != ''").fetchall()}
    max_order = conn.execute("select coalesce(max(display_order), 0) as n from professors where status != '已归档'").fetchone()["n"]
    blocked = {"套磁信", "模板", "申请书", "自我介绍"}
    for row in rows:
        name = clean_professor_name(row["related_professor"])
        if not name or name in existing or name in blocked or any(word in name for word in blocked):
            continue
        max_order += 1
        conn.execute(
            """
            insert into professors
            (name, status, note, display_order, created_at, updated_at)
            values (?, '待补充', ?, ?, ?, ?)
            """,
            (name, f"已有关联套磁信：{row['name']}", max_order, now_text(), now_text()),
        )
        existing.add(name)
        created += 1
    return created


def normalize_existing_materials() -> None:
    with connect() as conn:
        rows = conn.execute("select id, category, stage from materials").fetchall()
        for row in rows:
            category = normalize_category(row["category"])
            stage = row["stage"] or default_stage_for_category(category)
            conn.execute("update materials set category = ?, stage = ? where id = ?", (category, stage, row["id"]))


def cleanup_generated_records() -> None:
    with connect() as conn:
        conn.execute("delete from professors where name like '%申请书%' and coalesce(email, '') = '' and coalesce(direction, '') = ''")
        conn.execute("update materials set related_professor = '' where related_professor like '%申请书%'")
        conn.execute("delete from professors where name = '自我介绍' and coalesce(email, '') = ''")
        conn.execute("update materials set category = '面试', stage = '面试', resource_kind = '面试材料', related_professor = '' where name like '%自我介绍%'")
        conn.execute("update materials set resource_kind = '申请书' where name like '%申请书%'")
        conn.execute(
            """
            update professors
            set status = '待补充', updated_at = ?
            where status = '已准备套磁信'
              and note like '已有关联套磁信：%'
              and coalesce(school, '') = ''
              and coalesce(college, '') = ''
              and coalesce(direction, '') = ''
              and coalesce(email, '') = ''
              and coalesce(homepage, '') = ''
            """,
            (now_text(),),
        )
        conn.execute(
            """
            delete from professors
            where status in ('已准备套磁信', '待补充')
              and (note like '已有关联套磁信：%' or note like '由套磁信文件名自动识别：%')
              and coalesce(school, '') = ''
              and coalesce(college, '') = ''
              and coalesce(direction, '') = ''
              and coalesce(email, '') = ''
              and coalesce(homepage, '') = ''
              and exists (
                  select 1
                  from professors as real_prof
                  where real_prof.name = professors.name
                    and real_prof.id != professors.id
                    and (
                        real_prof.status not in ('已准备套磁信', '待补充')
                        or coalesce(real_prof.school, '') != ''
                        or coalesce(real_prof.college, '') != ''
                        or coalesce(real_prof.direction, '') != ''
                        or coalesce(real_prof.email, '') != ''
                        or coalesce(real_prof.homepage, '') != ''
                        or (
                            coalesce(real_prof.note, '') != ''
                            and real_prof.note not like '已有关联套磁信：%'
                            and real_prof.note not like '由套磁信文件名自动识别：%'
                        )
                    )
              )
            """
        )
        conn.execute("update materials set related_professor = replace(related_professor, 'NJUST-', '') where related_professor like 'NJUST-%'")
        conn.execute("delete from professors where name like 'NJUST-%' and replace(name, 'NJUST-', '') in (select name from professors)")
        conn.execute("update professors set name = replace(name, 'NJUST-', '') where name like 'NJUST-%'")
        conn.execute("update materials set related_professor = ltrim(related_professor, '-_—－ ') where related_professor like '-%' or related_professor like '_%' or related_professor like '—%' or related_professor like '－%'")
        conn.execute("update professors set name = ltrim(name, '-_—－ ') where name like '-%' or name like '_%' or name like '—%' or name like '－%'")


def get_material(row_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("select * from materials where id = ?", (row_id,)).fetchone()


def material_actions(row: dict) -> dict:
    ext = (row.get("ext") or "").lower()
    can_preview = ext in {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".md", ".csv"}
    return {"canPreview": can_preview, "openUrl": f"/api/materials/{row['id']}/open", "viewUrl": f"/files/{row['id']}/view"}


def resource_groups() -> dict:
    with connect() as conn:
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
        folder_name = folder_level(row["folder"])
        folder_path = str((SOURCE_DIR.parent / folder_name).resolve())
        folders.setdefault(folder_name, {"name": folder_name, "path": folder_path, "count": 0, "items": []})
        folders[folder_name]["count"] += 1
        folders[folder_name]["items"].append(row)
    return {"byCategory": list(groups.values()), "byFolder": list(folders.values())}


def resource_directory(relative_path: str = "", query: str = "", limit: int = 200) -> dict:
    """Return one directory level, or a bounded database search result."""
    limit = max(1, min(int(limit or 200), 300))
    query = str(query or "").strip()
    if query:
        search_columns = ["name", "relative_path", "category", "resource_kind", "related_professor", "related_program", "note"]
        where = " or ".join(f"{column} like ?" for column in search_columns)
        params = [f"%{query}%"] * len(search_columns)
        with connect() as conn:
            rows = rows_to_dicts(
                conn.execute(
                    f"select * from materials where missing = 0 and ({where}) order by pinned desc, mtime desc, id desc limit ?",
                    [*params, limit],
                ).fetchall()
            )
        items = []
        for row in rows:
            if is_ignored_material_path(Path(row["path"])):
                continue
            row["actions"] = material_actions(row)
            items.append(row)
        return {"mode": "search", "query": query, "items": items, "limit": limit, "truncated": len(rows) >= limit}

    relative = Path(str(relative_path or "").replace("/", os.sep))
    current = (SOURCE_DIR / relative).resolve()
    if not is_safe_path(current) or (current != SOURCE_DIR and SOURCE_DIR not in current.parents):
        raise ValueError("资源目录路径不正确")
    if not current.exists() or not current.is_dir():
        raise FileNotFoundError("资源目录不存在")

    directories = []
    for child in sorted((item for item in current.iterdir() if item.is_dir()), key=lambda item: item.name.casefold()):
        if is_ignored_material_path(child):
            continue
        visible_children = 0
        try:
            for entry in os.scandir(child):
                entry_path = Path(entry.path)
                if is_ignored_material_path(entry_path) or entry.name.startswith("~$"):
                    continue
                visible_children += 1
        except OSError:
            pass
        directories.append(
            {
                "name": child.name,
                "relativePath": child.relative_to(SOURCE_DIR).as_posix(),
                "path": str(child),
                "childCount": visible_children,
            }
        )

    folder_key = str(current.relative_to(SOURCE_DIR.parent))
    with connect() as conn:
        rows = rows_to_dicts(
            conn.execute(
                "select * from materials where missing = 0 and folder = ? order by pinned desc, name asc",
                (folder_key,),
            ).fetchall()
        )
    files = []
    for row in rows:
        if is_ignored_material_path(Path(row["path"])):
            continue
        row["actions"] = material_actions(row)
        files.append(row)

    parts = list(relative.parts) if str(relative) not in {"", "."} else []
    breadcrumbs = [{"name": "保研准备", "relativePath": ""}]
    breadcrumbs.extend(
        {"name": part, "relativePath": Path(*parts[: index + 1]).as_posix()}
        for index, part in enumerate(parts)
    )
    return {
        "mode": "directory",
        "relativePath": "" if current == SOURCE_DIR else current.relative_to(SOURCE_DIR).as_posix(),
        "path": str(current),
        "breadcrumbs": breadcrumbs,
        "directories": directories,
        "files": files,
    }


def delete_material_file(row_id: int) -> dict:
    row = get_material(row_id)
    if row is None:
        raise FileNotFoundError("材料不存在")
    path = Path(row["path"])
    if not is_safe_path(path) or not path.exists() or not path.is_file():
        raise FileNotFoundError("文件不存在或不在项目目录内")
    path.unlink()
    with connect() as conn:
        conn.execute("update materials set missing = 1, updated_at = ? where id = ?", (now_text(), row_id))
    return {"ok": True, "deleted": str(path)}


def parse_upload(handler, field_name: str):
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        raise ValueError("请使用文件上传表单")
    size = int(handler.headers.get("Content-Length", "0") or "0")
    if size > MAX_UPLOAD_BYTES:
        raise ValueError("上传文件过大")
    form = cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": str(size),
        },
    )
    field = form[field_name] if field_name in form else None
    if field is None or not getattr(field, "filename", ""):
        raise ValueError("没有选择文件")
    return field


def upload_material(handler) -> dict:
    field = parse_upload(handler, "file")
    upload_dir = SOURCE_DIR / "网页添加"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(field.filename).name
    target = upload_dir / safe_name
    if target.exists():
        target = upload_dir / f"{target.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}{target.suffix}"
    with target.open("wb") as f:
        shutil.copyfileobj(field.file, f)
    return {"path": str(target), **scan_materials()}
