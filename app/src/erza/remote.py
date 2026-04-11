from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
import socket
import textwrap
from contextlib import contextmanager
import re
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, OpenerDirector, Request, build_opener, urlopen

from erza.model import Component, Link, Screen, Section, Text
from erza.local_server import SubmitResult
from erza.parser import ParseError, compile_markup


REMOTE_WRAP_WIDTH = 72
REMOTE_USER_AGENT = "erza/0.0.1"
REMOTE_ERZA_CONTENT_TYPES = {"application/erza", "text/erza"}
REMOTE_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)
DOMAIN_RE = re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?:/[^\s]*)?$")


class RemoteError(RuntimeError):
    """Raised when a remote source cannot be fetched or rendered."""


@dataclass(slots=True)
class RemoteDocument:
    url: str
    content_type: str
    body: str


@dataclass(slots=True)
class _Block:
    kind: Literal["header", "paragraph", "link", "code"]
    text: str
    href: str | None = None


class RemoteApp:
    def __init__(self, url: str, *, opener: OpenerDirector | None = None) -> None:
        self.current_url = normalize_remote_url(url)
        self._opener = opener or _build_remote_opener()

    @property
    def backend(self):
        return None

    def build_screen(self) -> Screen:
        document = fetch_remote_document(self.current_url, opener=self._opener)
        return remote_document_to_screen(document)

    def follow_link(self, href: str) -> "RemoteApp":
        return RemoteApp(urljoin(self.current_url, href), opener=self._opener)

    def submit_form(self, action: str, values: dict[str, str]) -> SubmitResult:
        target_url = urljoin(self.current_url, action)
        request = Request(
            target_url,
            data=json.dumps(values).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": REMOTE_USER_AGENT,
            },
            method="POST",
        )
        try:
            document = _fetch_document_with_dns_fallback(request, timeout=10.0, opener=self._opener)
        except (HTTPError, URLError) as exc:
            raise RemoteError(f"failed to submit remote form: {action}") from exc
        if document is None:
            raise RemoteError(f"failed to submit remote form: {action}")

        try:
            payload = json.loads(document.body)
        except json.JSONDecodeError as exc:
            raise RemoteError("remote form submit returned invalid JSON") from exc

        return SubmitResult(
            type=str(payload.get("type", "refresh")),
            href=_optional_string(payload.get("href")),
            message=_optional_string(payload.get("message")),
        )

    def dispatch_action(self, action: str, params: dict[str, object]) -> object:
        request = Request(
            _erza_action_url(self.current_url),
            data=json.dumps({"action": action, "params": params}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": REMOTE_USER_AGENT,
            },
            method="POST",
        )
        try:
            document = _fetch_document_with_dns_fallback(request, timeout=10.0, opener=self._opener)
        except (HTTPError, URLError) as exc:
            raise RemoteError(f"failed to dispatch remote action: {action}") from exc
        if document is None:
            raise RemoteError(f"failed to dispatch remote action: {action}")

        try:
            payload = json.loads(document.body)
        except json.JSONDecodeError as exc:
            raise RemoteError("remote action returned invalid JSON") from exc

        if str(payload.get("type", "refresh")) == "error":
            raise RemoteError(str(payload.get("message", "remote action failed")))
        return payload


def is_remote_source(value: str) -> bool:
    stripped = value.strip()
    return bool(REMOTE_SCHEME_RE.match(stripped) or DOMAIN_RE.match(stripped))


def normalize_remote_url(value: str) -> str:
    stripped = value.strip()
    if REMOTE_SCHEME_RE.match(stripped):
        return stripped
    if DOMAIN_RE.match(stripped):
        return f"https://{stripped}"
    raise RemoteError(f"invalid remote source: {value}")


def fetch_remote_document(
    url: str,
    *,
    timeout: float = 10.0,
    opener: OpenerDirector | None = None,
) -> RemoteDocument:
    erza_request = Request(
        _erza_endpoint_url(url),
        headers={
            "Accept": "application/erza, text/erza;q=0.9, text/plain;q=0.2",
            "User-Agent": REMOTE_USER_AGENT,
        },
    )
    try:
        erza_document = _fetch_document_with_dns_fallback(
            erza_request,
            timeout=timeout,
            allow_http_statuses={404},
            opener=opener,
        )
    except (HTTPError, URLError) as exc:
        raise RemoteError(f"failed to fetch remote source: {url}") from exc

    if erza_document is not None and _is_erza_document(erza_document):
        return erza_document

    request = Request(
        url,
        headers={
            "Accept": "text/html, text/plain;q=0.9, */*;q=0.1",
            "User-Agent": REMOTE_USER_AGENT,
        },
    )
    try:
        document = _fetch_document_with_dns_fallback(request, timeout=timeout, opener=opener)
    except (HTTPError, URLError) as exc:
        raise RemoteError(f"failed to fetch remote source: {url}") from exc

    if document is None:
        raise RemoteError(f"failed to fetch remote source: {url}")
    return document


def remote_document_to_screen(document: RemoteDocument) -> Screen:
    if _is_erza_document(document):
        try:
            return compile_markup(document.body)
        except ParseError as exc:
            raise RemoteError(f"failed to parse remote erza document: {document.url}") from exc

    if document.content_type == "text/plain":
        return _plain_text_to_screen(document.url, document.body)

    parser = _RemoteHtmlParser(document.url)
    parser.feed(document.body)
    return parser.to_screen()


def _plain_text_to_screen(url: str, body: str) -> Screen:
    children: list[Component] = [Text(content=url)]
    for line in body.splitlines():
        for wrapped in _wrap_text(line):
            children.append(Text(content=wrapped))
    return Screen(
        title=_title_from_url(url),
        children=[Section(title="Overview", children=children)],
    )


def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    return url


def _wrap_text(text: str) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    return textwrap.wrap(normalized, width=REMOTE_WRAP_WIDTH) or [normalized]


def _erza_endpoint_url(url: str) -> str:
    parsed = urlparse(url)
    request_path = parsed.path or "/"
    return parsed._replace(
        path="/.well-known/erza",
        params="",
        query=urlencode({"path": request_path}),
        fragment="",
    ).geturl()


def _erza_action_url(url: str) -> str:
    parsed = urlparse(url)
    request_path = parsed.path or "/"
    return parsed._replace(
        path="/.well-known/erza/action",
        params="",
        query=urlencode({"path": request_path}),
        fragment="",
    ).geturl()


def _is_erza_document(document: RemoteDocument) -> bool:
    if document.content_type in REMOTE_ERZA_CONTENT_TYPES:
        return True
    return document.content_type == "text/plain" and document.body.lstrip().startswith("<Screen")


def _fetch_document_with_dns_fallback(
    request: Request,
    *,
    timeout: float,
    allow_http_statuses: set[int] | None = None,
    opener: OpenerDirector | None = None,
) -> RemoteDocument | None:
    allow_http_statuses = allow_http_statuses or set()
    try:
        return _fetch_document(request, timeout=timeout, opener=opener)
    except HTTPError as exc:
        if exc.code in allow_http_statuses:
            exc.close()
            return None
        raise
    except URLError as exc:
        if not _is_dns_resolution_error(exc):
            raise

        hostname = urlparse(request.full_url).hostname
        if not hostname:
            raise

        resolved_ips = _resolve_hostname_via_doh(hostname)
        if not resolved_ips:
            raise

        with _temporary_host_resolution(hostname, resolved_ips):
            try:
                return _fetch_document(request, timeout=timeout, opener=opener)
            except HTTPError as retry_exc:
                if retry_exc.code in allow_http_statuses:
                    retry_exc.close()
                    return None
                raise


def _fetch_document(
    request: Request,
    *,
    timeout: float,
    opener: OpenerDirector | None = None,
) -> RemoteDocument:
    open_fn = opener.open if opener is not None else urlopen
    with open_fn(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset("utf-8")
        content_type = response.headers.get_content_type()
        body = response.read().decode(charset, errors="replace")
    return RemoteDocument(url=request.full_url, content_type=content_type, body=body)


def _is_dns_resolution_error(exc: URLError) -> bool:
    return isinstance(exc.reason, socket.gaierror)


def _resolve_hostname_via_doh(hostname: str, visited: set[str] | None = None) -> list[str]:
    seen = visited or set()
    if hostname in seen:
        return []
    seen.add(hostname)

    addresses = _query_dns_records(hostname, "A") + _query_dns_records(hostname, "AAAA")
    if addresses:
        return list(dict.fromkeys(addresses))

    for target in _query_dns_records(hostname, "CNAME"):
        nested = _resolve_hostname_via_doh(target.rstrip("."), seen)
        if nested:
            return nested
    return []


def _query_dns_records(hostname: str, record_type: str) -> list[str]:
    query = Request(
        f"https://cloudflare-dns.com/dns-query?name={hostname}&type={record_type}",
        headers={"User-Agent": REMOTE_USER_AGENT, "accept": "application/dns-json"},
    )
    try:
        with urlopen(query, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError):
        return []

    answers = payload.get("Answer", [])
    return [answer["data"] for answer in answers if "data" in answer]


def _build_remote_opener() -> OpenerDirector:
    jar = CookieJar()
    return build_opener(HTTPCookieProcessor(jar))


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


@contextmanager
def _temporary_host_resolution(hostname: str, addresses: list[str]):
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(
        host: str,
        port: int | str | None,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ):
        if host != hostname:
            return original_getaddrinfo(host, port, family, type, proto, flags)

        resolved = []
        for address in addresses:
            resolved.extend(original_getaddrinfo(address, port, family, type, proto, flags))
        return resolved

    socket.getaddrinfo = patched_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo


class _RemoteHtmlParser(HTMLParser):
    def __init__(self, url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.url = url
        self.in_title = False
        self.in_heading = False
        self.in_paragraph = False
        self.in_pre = False
        self.in_anchor = False
        self.current_href: str | None = None
        self.anchor_parts: list[str] = []
        self.title_parts: list[str] = []
        self.blocks: list[_Block] = []
        self.buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name: value or "" for name, value in attrs}
        if tag == "title":
            self._flush()
            self.in_title = True
            return
        if tag in {"h1", "h2", "h3"}:
            self._flush()
            self.in_heading = True
            return
        if tag in {"p", "li"}:
            self._flush()
            self.in_paragraph = True
            return
        if tag == "pre":
            self._flush()
            self.in_pre = True
            return
        if tag == "br":
            self.buffer.append("\n" if self.in_pre else " ")
            return
        if tag == "a":
            self.in_anchor = True
            self.current_href = attrs_dict.get("href") or None
            self.anchor_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._flush()
            self.in_title = False
            return
        if tag in {"h1", "h2", "h3"}:
            self._flush()
            self.in_heading = False
            return
        if tag in {"p", "li"}:
            self._flush()
            self.in_paragraph = False
            return
        if tag == "pre":
            self._flush()
            self.in_pre = False
            return
        if tag == "a":
            self.in_anchor = False
            label = " ".join("".join(self.anchor_parts).split())
            if self.current_href and label:
                self.blocks.append(_Block(kind="link", text=label, href=self.current_href))
            self.current_href = None
            self.anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
            return
        if self.in_anchor:
            self.anchor_parts.append(data)
        if self.in_pre:
            self.buffer.append(data)
            return
        if self.in_heading or self.in_paragraph:
            self.buffer.append(data)

    def to_screen(self) -> Screen:
        self._flush()
        title = " ".join(" ".join(self.title_parts).split()) or _title_from_url(self.url)

        sections: list[Section] = []
        current_title = "Overview"
        current_children: list[Component] = [Text(content=self.url)]

        for block in self.blocks:
            if block.kind == "header":
                if current_children:
                    sections.append(Section(title=current_title, children=current_children))
                current_title = block.text
                current_children = []
                continue
            if block.kind == "link":
                current_children.append(Link(label=block.text, href=block.href or "#"))
                continue
            if block.kind == "code":
                for line in block.text.splitlines():
                    current_children.append(Text(content=line.rstrip()))
                continue
            for line in _wrap_text(block.text):
                current_children.append(Text(content=line))

        if current_children or not sections:
            sections.append(Section(title=current_title, children=current_children))

        return Screen(title=title, children=sections)

    def _flush(self) -> None:
        raw = "".join(self.buffer)
        self.buffer.clear()
        if not raw:
            return

        if self.in_title:
            self.title_parts.append(raw)
            return
        if self.in_pre:
            text = raw.strip("\n")
            if text:
                self.blocks.append(_Block(kind="code", text=text))
            return

        text = " ".join(raw.split())
        if not text:
            return
        if self.in_heading:
            self.blocks.append(_Block(kind="header", text=text))
        elif self.in_paragraph:
            self.blocks.append(_Block(kind="paragraph", text=text))
