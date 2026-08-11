from __future__ import annotations

import json
import mimetypes
import re
import shutil
from pathlib import Path

from .config import DATA_DIR, DEFAULT_SETTINGS, MAX_AVATAR_BYTES
from .db import connect
from .materials import parse_upload
from .utils import now_text

ALLOWED_AVATAR_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def avatar_path() -> Path | None:
    for path in DATA_DIR.glob("avatar.*"):
        if path.is_file():
            return path
    return None


def read_settings() -> dict:
    with connect() as conn:
        values = {row["key"]: row["value"] for row in conn.execute("select key, value from settings").fetchall()}
    settings = {key: values.get(key, value) for key, value in DEFAULT_SETTINGS.items()}
    settings["github"] = DEFAULT_SETTINGS["github"]
    try:
        school_colors = json.loads(settings.get("schoolColors") or "{}")
    except (TypeError, json.JSONDecodeError):
        school_colors = {}
    settings["schoolColors"] = {
        str(school).strip(): str(color).upper()
        for school, color in school_colors.items()
        if str(school).strip() and HEX_COLOR_RE.fullmatch(str(color))
    } if isinstance(school_colors, dict) else {}
    avatar = avatar_path()
    settings["avatarUrl"] = f"/api/settings/avatar?ts={int(avatar.stat().st_mtime)}" if avatar else ""
    return settings


def update_settings(payload: dict) -> dict:
    allowed = set(DEFAULT_SETTINGS)
    with connect() as conn:
        for key, value in payload.items():
            if key not in allowed:
                continue
            if key == "schoolColors":
                if not isinstance(value, dict):
                    raise ValueError("学校配色格式不正确")
                colors = {}
                for school, color in value.items():
                    school = re.sub(r"\s+", " ", str(school)).strip()[:80]
                    color = str(color).strip().upper()
                    if school and HEX_COLOR_RE.fullmatch(color):
                        colors[school] = color
                text = json.dumps(colors, ensure_ascii=False, separators=(",", ":"))
                conn.execute(
                    """
                    insert into settings (key, value, updated_at) values (?, ?, ?)
                    on conflict(key) do update set value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (key, text, now_text()),
                )
                continue
            text = re.sub(r"\s+", " ", str(value)).strip()
            if key == "motto":
                text = text[:42]
            elif key == "avatarText":
                text = text[:2]
            elif key in {"brandTitle", "workspaceName"}:
                text = text[:32]
            elif key == "github":
                text = DEFAULT_SETTINGS[key]
            elif key == "avatarMode" and text not in {"text", "upload"}:
                text = "text"
            conn.execute(
                """
                insert into settings (key, value, updated_at) values (?, ?, ?)
                on conflict(key) do update set value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, text, now_text()),
            )
    return read_settings()


def save_avatar(handler) -> dict:
    size = int(handler.headers.get("Content-Length", "0") or "0")
    if size > MAX_AVATAR_BYTES:
        raise ValueError("头像文件过大，请控制在 5MB 以内")
    field = parse_upload(handler, "avatar")
    ext = Path(field.filename).suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTS:
        raise ValueError("头像仅支持 PNG、JPG、GIF、WebP")
    DATA_DIR.mkdir(exist_ok=True)
    for old in DATA_DIR.glob("avatar.*"):
        old.unlink()
    target = DATA_DIR / f"avatar{ext}"
    with target.open("wb") as f:
        shutil.copyfileobj(field.file, f)
    return update_settings({"avatarMode": "upload"})


def avatar_response() -> tuple[bytes, str] | None:
    path = avatar_path()
    if not path:
        return None
    return path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/png"
