from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from urllib.parse import parse_qs, urlparse
import unittest
from unittest.mock import patch

from _test_bootstrap import ensure_test_paths

ensure_test_paths()

from erza.remote import (
    _resolve_hostname_via_doh,
    RemoteApp,
    fetch_remote_document,
    remote_document_to_screen,
)


class RemoteTests(unittest.TestCase):
    def test_fetch_remote_erza_and_compile_screen(self) -> None:
        server = _TestServer(_ErzaHandler)
        try:
            document = fetch_remote_document(server.url)
            screen = remote_document_to_screen(document)
        finally:
            server.close()

        self.assertEqual(document.content_type, "application/erza")
        self.assertEqual(screen.title, "Remote Docs")
        self.assertEqual(screen.children[0].title, "Overview")
        self.assertTrue(
            any(getattr(child, "href", "") == "components" for child in screen.children[1].children)
        )

    def test_fetch_remote_html_and_compile_screen(self) -> None:
        server = _TestServer(_HtmlHandler)
        try:
            document = fetch_remote_document(server.url)
            screen = remote_document_to_screen(document)
        finally:
            server.close()

        self.assertEqual(screen.title, "Remote Docs")
        self.assertEqual(screen.children[0].title, "Overview")
        self.assertEqual(screen.children[1].title, "Remote Docs")
        self.assertTrue(
            any(getattr(child, "href", "") == "https://example.com/spec" for child in screen.children[1].children)
        )

    def test_dns_resolution_fallback_follows_cname_chain(self) -> None:
        answers = {
            ("erza.example.com", "A"): [],
            ("erza.example.com", "AAAA"): [],
            ("erza.example.com", "CNAME"): ["edge.example.net."],
            ("edge.example.net", "A"): ["203.0.113.10"],
            ("edge.example.net", "AAAA"): [],
        }

        with patch("erza.remote._query_dns_records", side_effect=lambda host, kind: answers.get((host, kind), [])):
            resolved = _resolve_hostname_via_doh("erza.example.com")

        self.assertEqual(resolved, ["203.0.113.10"])

    def test_remote_app_supports_cookie_backed_forms_and_actions(self) -> None:
        _RemoteMutationHandler.reset()
        server = _TestServer(_RemoteMutationHandler)
        try:
            app = RemoteApp(server.url)
            screen = app.build_screen()
            self.assertEqual(screen.title, "Remote Account")

            result = app.submit_form("/auth/login", {"username": "alpha", "password": "pw"})
            self.assertEqual(result.type, "redirect")
            self.assertEqual(result.href, "index.erza")

            app = app.follow_link(result.href or "index.erza")
            screen = app.build_screen()
            self.assertEqual(screen.children[0].children[1].content, "Signed in as @alpha.")

            app.dispatch_action("feed.like", {"post_id": 1})
            screen = app.build_screen()
            self.assertEqual(screen.children[1].children[0].content, "Signals: 1")
        finally:
            server.close()


class _HtmlHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/.well-known/erza"):
            self.send_response(404)
            self.end_headers()
            return

        body = """<!DOCTYPE html>
<html>
  <head><title>Remote Docs</title></head>
  <body>
    <h1>Remote Docs</h1>
    <p>Rendered through erza.</p>
    <p><a href="https://example.com/spec">Spec</a></p>
  </body>
</html>"""
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


class _ErzaHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/.well-known/erza":
            request_path = parse_qs(parsed.query).get("path", ["/"])[0]
            if request_path != "/":
                self.send_response(404)
                self.end_headers()
                return

            body = """<Screen title="Remote Docs">
  <Section title="Overview">
    <Header>Remote Docs</Header>
    <Text>Served as raw .erza from the same host.</Text>
  </Section>
  <Section title="Pages">
    <Link href="components">Components</Link>
  </Section>
</Screen>"""
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/erza; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        body = "<html><head><title>Remote Docs</title></head><body><p>fallback</p></body></html>"
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


class _RemoteMutationHandler(BaseHTTPRequestHandler):
    sessions: dict[str, dict[str, object]] = {}
    next_session_id = 1

    @classmethod
    def reset(cls) -> None:
        cls.sessions = {}
        cls.next_session_id = 1

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/.well-known/erza":
            self.send_response(404)
            self.end_headers()
            return

        request_path = parse_qs(parsed.query).get("path", ["/"])[0]
        if request_path not in {"/", "/index.erza"}:
            self.send_response(404)
            self.end_headers()
            return

        _, state = self._session()
        body = f"""<Screen title="Remote Account">
  <Section title="Auth">
    <Header>Remote</Header>
    <Text>{state.get("status", "Guest")}</Text>
  </Section>
  <Section title="Feed">
    <Text>Signals: {state.get("signals", 0)}</Text>
  </Section>
</Screen>"""
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/erza; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if hasattr(self, "_new_session_id"):
            self.send_header("Set-Cookie", f"sid={self._new_session_id}; Path=/")
            delattr(self, "_new_session_id")
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        _, state = self._session()
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        payload = json.loads(raw.decode("utf-8")) if raw else {}

        if parsed.path == "/auth/login":
            state["status"] = f"Signed in as @{payload['username']}."
            return self._send_json({"type": "redirect", "href": "index.erza"})

        if parsed.path == "/.well-known/erza/action":
            state["signals"] = int(state.get("signals", 0)) + 1
            return self._send_json({"type": "refresh"})

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return

    def _session(self) -> tuple[str, dict[str, object]]:
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        existing = cookies.get("sid")
        if existing is not None and existing.value in self.sessions:
            return existing.value, self.sessions[existing.value]

        session_id = str(self.__class__.next_session_id)
        self.__class__.next_session_id += 1
        state: dict[str, object] = {"status": "Guest", "signals": 0}
        self.__class__.sessions[session_id] = state
        self._new_session_id = session_id
        return session_id, state

    def _send_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if hasattr(self, "_new_session_id"):
            self.send_header("Set-Cookie", f"sid={self._new_session_id}; Path=/")
            delattr(self, "_new_session_id")
        self.end_headers()
        self.wfile.write(body)


class _TestServer:
    def __init__(self, handler: type[BaseHTTPRequestHandler]) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
