from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
from typing import Any

from erza.model import Button, Column, Component, Header, Link, Row, Screen, Section, Text


class ParseError(RuntimeError):
    """Raised when rendered .erza markup cannot be compiled into a UI tree."""


WHITESPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class Element:
    tag: str
    attrs: dict[str, str]
    children: list["Element | str"] = field(default_factory=list)


class _MarkupParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: Element | None = None
        self.stack: list[Element] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = Element(
            tag=tag.lower(),
            attrs={name: value or "" for name, value in attrs},
        )
        if self.stack:
            self.stack[-1].children.append(element)
        elif self.root is not None:
            raise ParseError("rendered .erza markup must have a single root element")
        else:
            self.root = element
        self.stack.append(element)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            raise ParseError(f"unexpected closing tag: {tag}")
        current = self.stack.pop()
        if current.tag != tag.lower():
            raise ParseError(f"mismatched closing tag: expected </{current.tag}>")

    def handle_data(self, data: str) -> None:
        if not self.stack:
            if data.strip():
                raise ParseError("text outside the root element is not allowed")
            return
        self.stack[-1].children.append(data)

    def close(self) -> Element:
        super().close()
        if self.stack:
            raise ParseError(f"unclosed tag: <{self.stack[-1].tag}>")
        if self.root is None:
            raise ParseError("rendered .erza markup is empty")
        return self.root


def compile_markup(markup: str) -> Screen:
    parser = _MarkupParser()
    parser.feed(markup)
    root = parser.close()
    if root.tag != "screen":
        raise ParseError("the root .erza component must be <Screen>")
    title = root.attrs.get("title", "erza")
    return Screen(title=title, children=_convert_children(root))


def _convert_children(element: Element) -> list[Component]:
    children: list[Component] = []
    for child in element.children:
        if isinstance(child, str):
            if _normalize_text(child):
                children.append(Text(content=_normalize_text(child)))
            continue
        children.append(_convert_element(child))
    return children


def _convert_element(element: Element) -> Component:
    tag = element.tag
    if tag == "section":
        title = element.attrs.get("title", "").strip()
        if not title:
            raise ParseError("<Section> requires a title")
        tone = element.attrs.get("tone", "default").strip() or "default"
        return Section(title=title, tone=tone, children=_convert_children(element))
    if tag == "column":
        return Column(children=_convert_children(element), gap=_parse_gap(element, default=0))
    if tag == "row":
        return Row(children=_convert_children(element), gap=_parse_gap(element, default=1))
    if tag == "text":
        return Text(content=_collect_text(element))
    if tag == "header":
        return Header(content=_collect_text(element))
    if tag == "link":
        href = element.attrs.get("href", "").strip()
        if not href:
            raise ParseError("<Link> requires an href")
        return Link(label=_collect_text(element), href=href)
    if tag in {"button", "action"}:
        action = element.attrs.get("on:press", "").strip()
        if not action:
            raise ParseError(f"<{element.tag}> requires an on:press handler")
        params = {
            _normalize_param_name(name): _coerce_scalar(value)
            for name, value in element.attrs.items()
            if name != "on:press"
        }
        return Button(label=_collect_text(element), action=action, params=params)
    raise ParseError(f"unsupported component tag in v0: <{element.tag}>")


def _collect_text(element: Element) -> str:
    parts: list[str] = []
    for child in element.children:
        if isinstance(child, str):
            parts.append(child)
        else:
            parts.append(_collect_text(child))
    text = _normalize_text(" ".join(parts))
    if not text:
        raise ParseError(f"<{element.tag}> cannot be empty in v0")
    return text


def _normalize_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def _parse_gap(element: Element, *, default: int) -> int:
    raw = element.attrs.get("gap")
    if raw is None or raw == "":
        return default
    try:
        gap = int(raw)
    except ValueError as exc:
        raise ParseError(f"gap must be an integer on <{element.tag}>") from exc
    if gap < 0:
        raise ParseError(f"gap cannot be negative on <{element.tag}>")
    return gap


def _normalize_param_name(name: str) -> str:
    return name.replace(":", "_").replace("-", "_")


def _coerce_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped.isdigit():
        return int(stripped)
    if stripped in {"true", "false"}:
        return stripped == "true"
    return stripped
