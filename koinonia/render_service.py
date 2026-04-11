from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
APP_SRC = ROOT / "app" / "src"
if str(APP_SRC) not in sys.path:
    sys.path.insert(0, str(APP_SRC))

from erza.backend import BackendBridge, BackendError, ErrorResult, RedirectResult, bind_request_context
from erza.template import render_template


APP_DIR = Path(__file__).resolve().parent
BACKEND = BackendBridge.from_module_path(APP_DIR / "backend.py")
SESSIONS: dict[str, dict[str, object]] = {}
SESSION_COOKIE = "koinonia_sid"
ROUTES = {
    "/": "index.erza",
    "/index.erza": "index.erza",
}


def _resolve_page(request_path: str) -> Path:
    normalized = request_path or "/"
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    filename = ROUTES.get(normalized)
    if filename is None:
        raise FileNotFoundError(request_path)
    return APP_DIR / filename


def _render_page(request_path: str, session_state: dict[str, object]) -> str:
    page_path = _resolve_page(request_path)
    source = page_path.read_text(encoding="utf-8")
    with bind_request_context(session_state, method="GET", path=request_path):
        return render_template(source, backend=BACKEND)


def _result_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, RedirectResult):
        return {"type": "redirect", "href": result.href}
    if isinstance(result, ErrorResult):
        return {"type": "error", "message": result.message}
    if isinstance(result, dict):
        return result
    return {"type": "refresh"}


class _Handler(BaseHTTPRequestHandler):
    server_version = "koinonia/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._send_bytes(200, b"ok\n", "text/plain; charset=utf-8")
            return

        if parsed.path == "/.well-known/erza":
            request_path = parse_qs(parsed.query).get("path", ["/"])[0]
            _, session_state = self._ensure_session()
            try:
                body = _render_page(request_path, session_state).encode("utf-8")
            except FileNotFoundError:
                self._send_bytes(404, b"not found\n", "text/plain; charset=utf-8")
                return
            self._send_bytes(200, body, "application/erza; charset=utf-8")
            return

        body = self._landing_page().encode("utf-8")
        self._send_bytes(200, body, "text/html; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        raw_body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except json.JSONDecodeError:
            self._send_json(400, {"type": "error", "message": "invalid json body"})
            return

        _, session_state = self._ensure_session()

        if parsed.path == "/.well-known/erza/action":
            request_path = parse_qs(parsed.query).get("path", ["/"])[0]
            action = str(payload.get("action", "")).strip()
            params = payload.get("params", {})
            if not action or not isinstance(params, dict):
                self._send_json(400, {"type": "error", "message": "action and params are required"})
                return
            try:
                with bind_request_context(session_state, method="POST", path=request_path, data=params):
                    result = BACKEND.call(action, **params)
            except (BackendError, TypeError) as exc:
                self._send_json(400, {"type": "error", "message": str(exc)})
                return
            self._send_json(200, _result_payload(result))
            return

        try:
            with bind_request_context(session_state, method="POST", path=parsed.path, data=payload):
                result = BACKEND.dispatch_route("POST", parsed.path, **payload)
        except (BackendError, TypeError) as exc:
            self._send_json(404, {"type": "error", "message": str(exc)})
            return

        self._send_json(200, _result_payload(result))

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _ensure_session(self) -> tuple[str, dict[str, object]]:
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        existing = cookies.get(SESSION_COOKIE)
        if existing is not None and existing.value in SESSIONS:
            return existing.value, SESSIONS[existing.value]

        session_id = secrets.token_hex(16)
        session_state: dict[str, object] = {}
        SESSIONS[session_id] = session_state
        self._new_session_id = session_id
        return session_id, session_state

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if hasattr(self, "_new_session_id"):
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}={self._new_session_id}; Path=/; HttpOnly")
            delattr(self, "_new_session_id")
        self.end_headers()
        self.wfile.write(body)

    def _landing_page(self) -> str:
        routes = "\n".join(
            f'<li><a href="{path}">{path}</a></li>'
            for path in ("/", "/index.erza")
        )
        return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Koinonia</title>
    <style>
      body {{
        max-width: 48rem;
        margin: 3rem auto;
        padding: 0 1rem;
        font-family: ui-monospace, monospace;
        line-height: 1.5;
      }}
      code {{
        background: #f2f2f2;
        padding: 0.1rem 0.3rem;
      }}
    </style>
  </head>
  <body>
    <h1>Koinonia</h1>
    <p>This host serves a single terminal-native <code>index.erza</code> app for the social prototype.</p>
    <p>Use <code>erza run {self.headers.get("Host", "your-render-host")}</code> to open it from the terminal client.</p>
    <p>Available entry paths:</p>
    <ul>
      {routes}
    </ul>
  </body>
</html>"""


def main() -> None:
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    print(f"koinonia listening on :{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
