from __future__ import annotations

from .db import connect
from .materials import ensure_professors_from_letter_materials, material_actions
from .utils import rows_to_dicts


AUTO_PROFILE_STATUSES = {"已准备套磁信", "待补充"}


def is_auto_professor_record(prof: dict) -> bool:
    note = str(prof.get("note") or "").strip()
    has_profile = any(str(prof.get(field) or "").strip() for field in ["school", "college", "direction", "email", "homepage"])
    is_auto_note = note.startswith("已有关联套磁信：") or note.startswith("由套磁信文件名自动识别：")
    return not has_profile and prof.get("status") in AUTO_PROFILE_STATUSES and is_auto_note


def professor_key(name: str) -> str:
    value = str(name or "").strip().lstrip("-_—－ ").strip()
    for prefix in ["NJUST-", "NJUST_", "NJUST"]:
        if value.startswith(prefix):
            value = value[len(prefix) :].lstrip("-_—－ ").strip()
    return value


def profile_score(prof: dict) -> int:
    fields = ["school", "college", "direction", "email", "homepage"]
    score = sum(1 for field in fields if str(prof.get(field) or "").strip())
    if not is_auto_professor_record(prof):
        score += 3
    if str(prof.get("note") or "").strip() and "已有关联套磁信" not in str(prof.get("note") or ""):
        score += 1
    return score


def merge_professor(existing: dict, candidate: dict) -> dict:
    primary, secondary = (candidate, existing) if profile_score(candidate) > profile_score(existing) else (existing, candidate)
    merged = {**primary, "letters": existing.get("letters", []), "related": existing.get("related", [])}
    for key in ["school", "college", "direction", "email", "homepage", "note"]:
        if not merged.get(key) and secondary.get(key):
            merged[key] = secondary[key]
    merged["name"] = professor_key(merged.get("name")) or merged.get("name") or secondary.get("name")
    return merged


def contact_workspace() -> dict:
    with connect() as conn:
        ensure_professors_from_letter_materials(conn)
        resequence_active_professors(conn)
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
        key = professor_key(prof["name"])
        item = {**prof, "name": key or prof["name"], "letters": [], "related": []}
        by_prof[key] = merge_professor(by_prof[key], item) if key in by_prof else item
    unassigned = {"items": []}
    for item in resources:
        target = professor_key(item["related_professor"])
        item["related_professor"] = target
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
            bucket = "letters" if item["resource_kind"] == "套磁信" else "related"
            by_prof[target][bucket].append(item)
        else:
            unassigned["items"].append(item)
    professors = sorted(by_prof.values(), key=lambda row: (row.get("display_order") or 100000, row.get("name") or ""))
    return {"professors": professors, "unassigned": unassigned}


def resequence_active_professors(conn) -> None:
    rows = conn.execute(
        "select id, display_order from professors where status != '已归档' order by display_order asc, id asc"
    ).fetchall()
    for index, row in enumerate(rows, start=1):
        if row["display_order"] != index:
            conn.execute("update professors set display_order = ? where id = ?", (index, row["id"]))
