from __future__ import annotations

import json
import mimetypes
import os
import shutil
import sys
import threading
import time
import urllib.parse
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .analytics import summary
from .bootstrap import bootstrap
from .config import HOST, PORT, SOURCE_DIR, WEB_DIR
from .contact import contact_workspace
from .materials import cleanup_generated_records, delete_material_file, get_material, resource_directory, resource_groups, scan_materials, seed_professors_from_letters, upload_material
from .repositories import app_options, backup_db, create_row, delete_row, list_table, move_professor, move_program, update_row
from .settings import avatar_response, read_settings, save_avatar, update_settings
from .utils import is_safe_path, now_text


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


class Handler(BaseHTTPRequestHandler):
    server_version = "BaoyanDesk/1.2"

    def log_message(self, fmt: str, *args) -> None:
        status = int(args[1]) if len(args) > 1 and str(args[1]).isdigit() else 0
        if not self.path.startswith("/api/") and status < 400:
            return
        elapsed_ms = int((time.perf_counter() - getattr(self, "_request_started", time.perf_counter())) * 1000)
        label = "成功" if status < 400 else "失败"
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {self.command:<6} {self.path.split('?', 1)[0]}  {status} {label}  {elapsed_ms}ms\n")

    def handle_one_request(self) -> None:
        self._request_started = time.perf_counter()
        super().handle_one_request()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/summary":
                return send_json(self, summary())
            if path == "/api/contact-workspace":
                return send_json(self, contact_workspace())
            if path == "/api/materials/groups":
                return send_json(self, resource_groups())
            if path == "/api/resources":
                relative_path = (query.get("path") or [""])[0]
                search = (query.get("q") or [""])[0]
                limit = (query.get("limit") or ["200"])[0]
                return send_json(self, resource_directory(relative_path, search, int(limit) if str(limit).isdigit() else 200))
            if path == "/api/options":
                return send_json(self, app_options())
            if path == "/api/settings":
                return send_json(self, read_settings())
            if path == "/api/settings/avatar":
                return self.serve_avatar()
            match = re.fullmatch(r"/api/(materials|programs|professors|tasks|questions)", path)
            if match:
                return send_json(self, list_table(match.group(1), query))
            match = re.fullmatch(r"/files/(\d+)/view", path)
            if match:
                return self.serve_material(int(match.group(1)))
            self.serve_static(path)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/materials/scan":
                return send_json(self, scan_materials())
            if path == "/api/materials/upload":
                return send_json(self, upload_material(self), 201)
            if path == "/api/backup":
                return send_json(self, backup_db())
            if path == "/api/settings/avatar":
                return send_json(self, save_avatar(self))
            if path == "/api/root/open":
                return self.open_path(SOURCE_DIR)
            if path == "/api/folders/open":
                return self.open_path(Path(read_body(self).get("path", "")))
            match = re.fullmatch(r"/api/programs/(\d+)/move", path)
            if match:
                payload = read_body(self)
                target_position = payload.get("target_position")
                return send_json(self, move_program(int(match.group(1)), int(payload.get("direction", 0)), int(target_position) if target_position else None))
            match = re.fullmatch(r"/api/professors/(\d+)/move", path)
            if match:
                payload = read_body(self)
                target_position = payload.get("target_position")
                return send_json(self, move_professor(int(match.group(1)), int(payload.get("direction", 0)), int(target_position) if target_position else None))
            match = re.fullmatch(r"/api/materials/(\d+)/(open|open-folder)", path)
            if match:
                return self.open_material(int(match.group(1)), folder=match.group(2) == "open-folder")
            match = re.fullmatch(r"/api/(materials|programs|professors|tasks|questions)", path)
            if match:
                return send_json(self, create_row(match.group(1), read_body(self)), 201)
            send_json(self, {"error": "Not found"}, 404)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_PATCH(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/settings":
                return send_json(self, update_settings(read_body(self)))
            match = re.fullmatch(r"/api/(materials|programs|professors|tasks|questions)/(\d+)", path)
            if not match:
                return send_json(self, {"error": "Not found"}, 404)
            send_json(self, update_row(match.group(1), int(match.group(2)), read_body(self)))
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            file_match = re.fullmatch(r"/api/materials/(\d+)/file", path)
            if file_match:
                return send_json(self, delete_material_file(int(file_match.group(1))))
            match = re.fullmatch(r"/api/(materials|programs|professors|tasks|questions)/(\d+)", path)
            if not match:
                return send_json(self, {"error": "Not found"}, 404)
            send_json(self, delete_row(match.group(1), int(match.group(2))))
        except Exception as exc:
            send_json(self, {"error": str(exc)}, 500)

    def serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        target = (WEB_DIR / path.lstrip("/")).resolve()
        if not is_safe_path(target) or not target.exists() or not target.is_file():
            return send_json(self, {"error": "Not found"}, 404)
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_material(self, row_id: int) -> None:
        row = get_material(row_id)
        if row is None:
            return send_json(self, {"error": "材料不存在"}, 404)
        path = Path(row["path"])
        if not is_safe_path(path) or not path.exists():
            return send_json(self, {"error": "文件不存在或不在项目目录内"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{urllib.parse.quote(path.name)}")
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with path.open("rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def serve_avatar(self) -> None:
        response = avatar_response()
        if response is None:
            return send_json(self, {"error": "头像不存在"}, 404)
        body, content_type = response
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def open_material(self, row_id: int, folder: bool = False) -> None:
        row = get_material(row_id)
        if row is None:
            return send_json(self, {"error": "材料不存在"}, 404)
        path = Path(row["path"])
        self.open_path(path.parent if folder else path)

    def open_path(self, target: Path) -> None:
        if not is_safe_path(target) or not target.exists():
            return send_json(self, {"error": "路径不存在或不在项目目录内"}, 404)
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.spawnlp(os.P_NOWAIT, "open", "open", str(target))
        else:
            os.spawnlp(os.P_NOWAIT, "xdg-open", "xdg-open", str(target))
        send_json(self, {"ok": True})


def main() -> None:
    bootstrap()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 52)
    print(f"  推免准备系统  http://{HOST}:{PORT}")
    print(f"  资料目录      {SOURCE_DIR}")
    print("  状态          已就绪（资料将在后台同步）")
    print("=" * 52)
    threading.Thread(target=background_material_sync, name="material-sync", daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[系统] 已停止")
    finally:
        server.server_close()


def background_material_sync() -> None:
    started = time.perf_counter()
    try:
        cleanup_generated_records()
        result = scan_materials()
        seed_professors_from_letters()
        elapsed = time.perf_counter() - started
        print(
            f"[同步] 完成  新增 {result['inserted']} · 更新 {result['updated']} · "
            f"清理 {result.get('purged', 0)} · 缺失 {result['missing']}  ({elapsed:.1f}s)"
        )
    except Exception as exc:
        print(f"[同步] 失败  {exc}", file=sys.stderr)
