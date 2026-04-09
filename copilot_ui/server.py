"""Local HTTP server for the RAG copilot GUI."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
import webbrowser

from copilot_ui.models import UploadedFilePayload
from copilot_ui.services import CopilotApplicationService, QueryOptions


STATIC_DIR = Path(__file__).resolve().parent / "static"


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0"))
    raw_body = handler.rfile.read(content_length) if content_length else b"{}"
    if not raw_body:
        return {}
    return json.loads(raw_body.decode("utf-8"))


class CopilotRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler bound to a single application service instance."""

    service: CopilotApplicationService

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if self.path == "/static/styles.css":
            self._serve_static("styles.css", "text/css; charset=utf-8")
            return
        if self.path == "/static/app.js":
            self._serve_static("app.js", "application/javascript; charset=utf-8")
            return
        if self.path == "/api/state":
            _json_response(self, HTTPStatus.OK, {"ok": True, "state": self.service.snapshot().to_dict()})
            return
        if self.path == "/api/health":
            _json_response(self, HTTPStatus.OK, {"ok": True})
            return
        _json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "Route not found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = _read_json(self)
            if self.path == "/api/documents/upload":
                files = [UploadedFilePayload.from_dict(item) for item in payload.get("files", [])]
                state = self.service.add_uploaded_files(files, clear_existing=bool(payload.get("clear_existing")))
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {"ok": True, "state": state.to_dict(), "message": self.service.last_upload_message()},
                )
                return
            if self.path == "/api/documents/remove":
                state = self.service.remove_document(str(payload.get("document_id", "")))
                _json_response(self, HTTPStatus.OK, {"ok": True, "state": state.to_dict()})
                return
            if self.path == "/api/documents/clear":
                state = self.service.clear_documents()
                _json_response(self, HTTPStatus.OK, {"ok": True, "state": state.to_dict()})
                return
            if self.path == "/api/chat":
                options = QueryOptions(
                    mode=str(payload.get("mode", "hybrid")),
                    top_k=int(payload.get("top_k", 4)),
                    source_types=tuple(str(item) for item in payload.get("source_types", [])),
                    debug=bool(payload.get("debug", False)),
                )
                state = self.service.ask(str(payload.get("message", "")), options=options)
                _json_response(self, HTTPStatus.OK, {"ok": True, "state": state.to_dict()})
                return
            if self.path == "/api/chat/reset":
                state = self.service.clear_chat()
                _json_response(self, HTTPStatus.OK, {"ok": True, "state": state.to_dict()})
                return
            if self.path == "/api/settings/ollama":
                state = self.service.update_ollama_settings(
                    chat_model=str(payload.get("chat_model", "")).strip() or None,
                    embedding_model=str(payload.get("embedding_model", "")).strip() or None,
                )
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "state": state.to_dict(),
                        "message": (
                            "Ollama models updated. If you typed a model name that was not installed, "
                            "the app pulled it first."
                        ),
                    },
                )
                return
            if self.path == "/api/settings/ollama/refresh":
                state = self.service.refresh_ollama_models()
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {"ok": True, "state": state.to_dict(), "message": "Refreshed local Ollama models."},
                )
                return
            _json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "Route not found"})
        except Exception as exc:  # noqa: BLE001
            _json_response(
                self,
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": str(exc)},
            )

    def log_message(self, format: str, *args: Any) -> None:
        del format, args

    def _serve_static(self, file_name: str, content_type: str) -> None:
        file_path = STATIC_DIR / file_name
        if not file_path.exists():
            _json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "Asset not found"})
            return
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_handler(service: CopilotApplicationService):
    """Bind a handler class to a concrete service instance."""

    return type(
        "BoundCopilotRequestHandler",
        (CopilotRequestHandler,),
        {"service": service},
    )


def run_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
    service: CopilotApplicationService | None = None,
) -> None:
    """Run the local copilot web server."""

    app_service = service or CopilotApplicationService()
    server = ThreadingHTTPServer((host, port), make_handler(app_service))
    url = f"http://{host}:{port}"
    print(f"Copilot UI running at {url}")
    print("Press Ctrl+C to stop the server.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Copilot UI server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server(open_browser=False)
