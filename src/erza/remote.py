from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import json
import socket
import textwrap
from contextlib import contextmanager
import re
from typing import Literal
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from erza.model import Component, Link, Screen, Section, Text


REMOTE_WRAP_WIDTH = 72
REMOTE_USER_AGENT = "erza/0.0.1"
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
    def __init__(self, url: str) -> None:
        self.current_url = normalize_remote_url(url)

    @property
    def backend(self):
        return None

    def build_screen(self) -> Screen:
        document = fetch_remote_document(self.current_url)
        return remote_document_to_screen(document)

    def follow_link(self, href: str) -> "RemoteApp":
        return RemoteApp(urljoin(self.current_url, href))


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


def fetch_remote_document(url: str, *, timeout: float = 10.0) -> RemoteDocument:
    request = Request(url, headers={"User-Agent": REMOTE_USER_AGENT})
    try:
        return _fetch_document(request, timeout=timeout)
    except URLError as exc:
        if not _is_dns_resolution_error(exc):
            raise RemoteError(f"failed to fetch remote source: {url}") from exc

        hostname = urlparse(url).hostname
        if not hostname:
            raise RemoteError(f"failed to fetch remote source: {url}") from exc

        resolved_ips = _resolve_hostname_via_doh(hostname)
        if not resolved_ips:
            raise RemoteError(f"failed to fetch remote source: {url}") from exc

        try:
            with _temporary_host_resolution(hostname, resolved_ips):
                return _fetch_document(request, timeout=timeout)
        except URLError as retry_exc:
            raise RemoteError(f"failed to fetch remote source: {url}") from retry_exc


def remote_document_to_screen(document: RemoteDocument) -> Screen:
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


def _fetch_document(request: Request, *, timeout: float) -> RemoteDocument:
    with urlopen(request, timeout=timeout) as response:
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
