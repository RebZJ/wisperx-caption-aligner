from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .io import write_json
from .validate import validate_captions


@dataclass(frozen=True)
class EditorProject:
    audio_path: Path
    captions_path: Path
    output_path: Path


def read_captions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing captions file: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError("Captions JSON must be a list.")
    return payload


def create_handler(project: EditorProject):
    class CaptionEditorHandler(BaseHTTPRequestHandler):
        server_version = "WisperXCaptionEditor/0.1"

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/":
                self.send_asset("editor.html", "text/html; charset=utf-8")
                return
            if path in {"/editor.html", "/app.js", "/style.css"}:
                content_type = {
                    "/editor.html": "text/html; charset=utf-8",
                    "/app.js": "text/javascript; charset=utf-8",
                    "/style.css": "text/css; charset=utf-8",
                }[path]
                self.send_asset(path.removeprefix("/"), content_type)
                return
            if path == "/api/project":
                self.send_json(
                    {
                        "audioFileName": project.audio_path.name,
                        "audioUrl": "/media/audio",
                        "captionsPath": str(project.captions_path),
                        "outputPath": str(project.output_path),
                        "captions": read_captions(project.captions_path),
                    }
                )
                return
            if path == "/media/audio":
                self.send_file(project.audio_path)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/api/save":
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                captions = payload.get("captions")
                if not isinstance(captions, list):
                    raise ValueError("Payload must include a captions list.")

                errors = validate_captions(captions, expected_words=None, max_duration_ms=None)
                if errors:
                    raise ValueError("; ".join(errors))

                write_json(project.output_path, captions)
                self.send_json({"ok": True, "path": str(project.output_path), "count": len(captions)})
            except Exception as error:  # pragma: no cover - exercised through manual UI
                self.send_json({"ok": False, "error": str(error)}, status=HTTPStatus.BAD_REQUEST)

        def send_asset(self, name: str, content_type: str) -> None:
            package_root = resources.files("wisperx_caption_aligner").joinpath("web")
            payload = package_root.joinpath(name).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def send_file(self, path: Path) -> None:
            if not path.exists():
                self.send_error(HTTPStatus.NOT_FOUND, "Missing media")
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            payload = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(payload)

        def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return CaptionEditorHandler


def serve_editor(
    *,
    audio_path: Path,
    captions_path: Path,
    output_path: Path,
    host: str,
    port: int,
    open_browser: bool,
) -> None:
    project = EditorProject(
        audio_path=audio_path.expanduser().resolve(),
        captions_path=captions_path.expanduser().resolve(),
        output_path=output_path.expanduser().resolve(),
    )
    if not project.audio_path.exists():
        raise FileNotFoundError(f"Missing audio: {project.audio_path}")
    read_captions(project.captions_path)

    server = ThreadingHTTPServer((host, port), create_handler(project))
    actual_port = server.server_address[1]
    url = f"http://{host}:{actual_port}/"

    if open_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()

    print(f"Caption editor: {url}")
    print(f"Audio: {project.audio_path}")
    print(f"Captions: {project.captions_path}")
    print(f"Save target: {project.output_path}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped editor.")
    finally:
        server.server_close()
