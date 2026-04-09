from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from erza.backend import BackendBridge, BackendError, ErrorResult, RedirectResult, bind_request_context


@dataclass(slots=True)
class SubmitResult:
    type: str
    href: str | None = None
    message: str | None = None


class LocalServerError(RuntimeError):
    """Raised when the localhost form server cannot complete a request."""


class LocalFormServer:
    def __init__(self, backend: BackendBridge, session_state: dict[str, Any]) -> None:
        self.backend = backend
        self.session_state = session_state
        self._server = _BackendHttpServer(("127.0.0.1", 0), _BackendRequestHandler, backend, session_state)
        self._thread = Thread(target=self._server.serve_forever, name="erza-local-form-server", daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def submit(self, action: str, data: dict[str, str]) -> SubmitResult:
        target_url = _target_submit_url(self.base_url, action)
        request = Request(
            target_url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise LocalServerError(f"form submit failed: {action}") from exc
        except (URLError, json.JSONDecodeError) as exc:
            raise LocalServerError("failed to talk to local erza form server") from exc

        return SubmitResult(
            type=str(payload.get("type", "refresh")),
            href=_optional_string(payload.get("href")),
            message=_optional_string(payload.get("message")),
        )

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1.0)


class _BackendHttpServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        backend: BackendBridge,
        session_state: dict[str, Any],
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self.backend = backend
        self.session_state = session_state


class _BackendRequestHandler(BaseHTTPRequestHandler):
    server: _BackendHttpServer

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except json.JSONDecodeError:
            self._send_json(400, {"type": "error", "message": "invalid json form body"})
            return

        try:
            with bind_request_context(
                self.server.session_state,
                method="POST",
                path=self.path,
                data=data,
            ):
                result = self.server.backend.dispatch_route("POST", self.path, **data)
        except BackendError as exc:
            self._send_json(404, {"type": "error", "message": str(exc)})
            return
        except Exception as exc:  # pragma: no cover - defensive server boundary
            self._send_json(500, {"type": "error", "message": str(exc)})
            return

        self._send_json(200, _result_payload(result))

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _result_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, RedirectResult):
        return {"type": "redirect", "href": result.href}
    if isinstance(result, ErrorResult):
        return {"type": "error", "message": result.message}
    if isinstance(result, dict):
        return result
    return {"type": "refresh"}


def _target_submit_url(base_url: str, action: str) -> str:
    if action.startswith(("http://", "https://")):
        return action
    return urljoin(f"{base_url}/", action.lstrip("/"))


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
