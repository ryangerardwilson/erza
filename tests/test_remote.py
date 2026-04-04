from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import URLError

from erza.remote import (
    _resolve_hostname_via_doh,
    fetch_remote_document,
    remote_document_to_screen,
)


class RemoteTests(unittest.TestCase):
    def test_fetch_remote_html_and_compile_screen(self) -> None:
        server = _TestServer()
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


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
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


class _TestServer:
    def __init__(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
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
