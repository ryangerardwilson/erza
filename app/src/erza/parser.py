from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
import textwrap
from typing import Any

from erza.model import AsciiAnimation, AsciiArt, Button, ButtonRow, Column, Component, Form, Header, Input, Link, Modal, Row, Screen, Section, SubmitButton, Text


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

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = Element(
            tag=tag.lower(),
            attrs={name: value or "" for name, value in attrs},
        )
        if self.stack:
            self.stack[-1].children.append(element)
            return
        if self.root is not None:
            raise ParseError("rendered .erza markup must have a single root element")
        self.root = element

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
    return Screen(title=title, children=_convert_children(root, parent_tag="screen"))


def _convert_children(
    element: Element,
    *,
    parent_tag: str,
    inside_form: bool = False,
    inside_modal: bool = False,
) -> list[Component]:
    children: list[Component] = []
    for child in element.children:
        if isinstance(child, str):
            if _normalize_text(child):
                children.append(Text(content=_normalize_text(child)))
            continue
        children.append(
            _convert_element(
                child,
                parent_tag=parent_tag,
                inside_form=inside_form,
                inside_modal=inside_modal,
            )
        )
    return children


def _convert_element(
    element: Element,
    *,
    parent_tag: str,
    inside_form: bool = False,
    inside_modal: bool = False,
) -> Component:
    tag = element.tag
    if tag == "section":
        title = element.attrs.get("title", "").strip()
        if not title:
            raise ParseError("<Section> requires a title")
        tone = element.attrs.get("tone", "default").strip() or "default"
        return Section(
            title=title,
            tone=tone,
            tab_order=_parse_section_tab_order(element),
            default_tab=_parse_section_default_tab(element),
            children=_convert_children(
                element,
                parent_tag="section",
                inside_form=inside_form,
                inside_modal=inside_modal,
            ),
        )
    if tag == "modal":
        if parent_tag != "screen":
            raise ParseError("<Modal> may only appear directly inside <Screen>")
        modal_id = element.attrs.get("id", "").strip()
        if not modal_id:
            raise ParseError("<Modal> requires an id")
        title = element.attrs.get("title", "").strip()
        if not title:
            raise ParseError("<Modal> requires a title")
        return Modal(
            modal_id=modal_id,
            title=title,
            children=_convert_children(
                element,
                parent_tag="modal",
                inside_form=inside_form,
                inside_modal=True,
            ),
        )
    if tag == "column":
        return Column(
            children=_convert_children(
                element,
                parent_tag="column",
                inside_form=inside_form,
                inside_modal=inside_modal,
            ),
            gap=_parse_gap(element, default=0),
        )
    if tag == "row":
        return Row(
            children=_convert_children(
                element,
                parent_tag="row",
                inside_form=inside_form,
                inside_modal=inside_modal,
            ),
            gap=_parse_gap(element, default=1),
        )
    if tag == "buttonrow":
        children = _convert_children(
            element,
            parent_tag="buttonrow",
            inside_form=inside_form,
            inside_modal=inside_modal,
        )
        if not children:
            raise ParseError("<ButtonRow> requires at least one child")
        if inside_form:
            if any(not isinstance(child, SubmitButton) for child in children):
                raise ParseError("<ButtonRow> inside <Form> only supports <Submit> children")
        elif any(not isinstance(child, (Button, Link)) for child in children):
            raise ParseError("<ButtonRow> only supports <Action>, <Button>, or <Link> children")
        return ButtonRow(
            children=children,
            gap=_parse_gap(element, default=2),
            align=_parse_alignment(element, default="center"),
        )
    if tag == "form":
        if inside_form:
            raise ParseError("<Form> cannot be nested inside another <Form> in v1")
        if not inside_modal:
            raise ParseError("<Form> may only appear inside <Modal>")
        action = element.attrs.get("action", "").strip()
        if not action:
            raise ParseError("<Form> requires an action")
        method = (element.attrs.get("method", "post").strip() or "post").lower()
        if method != "post":
            raise ParseError("<Form> only supports method=\"post\" in v1")
        submit_button_text = element.attrs.get("submit-button-text", "").strip() or "Submit"
        return Form(
            action=action,
            method=method,
            submit_button_text=submit_button_text,
            children=_convert_children(
                element,
                parent_tag="form",
                inside_form=True,
                inside_modal=inside_modal,
            ),
        )
    if tag == "input":
        if not inside_form:
            raise ParseError("<Input> may only appear inside <Form>")
        name = element.attrs.get("name", "").strip()
        if not name:
            raise ParseError("<Input> requires a name")
        if "placeholder" in element.attrs:
            raise ParseError("<Input> placeholder is not supported")
        input_type = _parse_input_type(element)
        return Input(
            name=name,
            type=input_type,
            value=element.attrs.get("value", ""),
            label=element.attrs.get("label", ""),
            required=_parse_input_required(element),
        )
    if tag == "submit":
        if not inside_form:
            raise ParseError("<Submit> may only appear inside <Form>")
        if parent_tag != "buttonrow":
            raise ParseError("<Submit> may only appear inside <ButtonRow> within <Form>")
        return SubmitButton(
            label=_collect_text(element),
            action=element.attrs.get("action", "").strip(),
        )
    if tag == "text":
        return Text(content=_collect_text(element))
    if tag == "header":
        return Header(content=_collect_text(element))
    if tag == "asciiart":
        return AsciiArt(content=_collect_preserved_text(element))
    if tag == "link":
        href = element.attrs.get("href", "").strip()
        if not href:
            raise ParseError("<Link> requires an href")
        return Link(label=_collect_text(element), href=href)
    if tag == "asciianimation":
        return AsciiAnimation(
            frames=_collect_animation_frames(element),
            fps=_parse_positive_int(element, "fps", default=4),
            loop=_parse_bool(element, "loop", default=True),
            label=element.attrs.get("label", "").strip() or "Animation",
        )
    if tag in {"button", "action"}:
        if inside_form:
            raise ParseError(f"<{element.tag}> is not supported inside <Form> in v1")
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


def _collect_animation_frames(element: Element) -> list[str]:
    frames: list[str] = []
    for child in element.children:
        if isinstance(child, str):
            if child.strip():
                raise ParseError("<AsciiAnimation> only supports <Frame> children")
            continue
        if child.tag != "frame":
            raise ParseError("<AsciiAnimation> only supports <Frame> children")
        frames.append(_collect_frame_text(child))

    if not frames:
        raise ParseError("<AsciiAnimation> requires at least one <Frame>")
    return frames


def _collect_frame_text(element: Element) -> str:
    parts: list[str] = []
    for child in element.children:
        if not isinstance(child, str):
            raise ParseError("<Frame> only supports raw text")
        parts.append(child)

    raw = textwrap.dedent("".join(parts)).strip("\n")
    if not raw:
        raise ParseError("<Frame> cannot be empty")
    return raw


def _collect_preserved_text(element: Element) -> str:
    parts: list[str] = []
    for child in element.children:
        if not isinstance(child, str):
            raise ParseError(f"<{element.tag}> only supports raw text")
        parts.append(child)
    return "".join(parts).strip("\n")


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


def _parse_section_tab_order(element: Element) -> int | None:
    raw = element.attrs.get("tab-order")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ParseError('tab-order must be an integer on <Section>') from exc


def _parse_section_default_tab(element: Element) -> bool:
    raw = element.attrs.get("default-tab")
    if raw is None:
        return False
    normalized = raw.strip().lower()
    if normalized in {"", "true"}:
        return True
    if normalized == "false":
        return False
    raise ParseError('default-tab must be true or false on <Section>')


def _parse_alignment(element: Element, *, default: str) -> str:
    raw = element.attrs.get("align")
    if raw is None or raw == "":
        return default
    alignment = raw.strip().lower()
    if alignment in {"left", "center", "right"}:
        return alignment
    raise ParseError(f'align must be "left", "center", or "right" on <{element.tag}>')


def _parse_positive_int(element: Element, name: str, *, default: int) -> int:
    raw = element.attrs.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ParseError(f"{name} must be an integer on <{element.tag}>") from exc
    if value <= 0:
        raise ParseError(f"{name} must be positive on <{element.tag}>")
    return value


def _parse_bool(element: Element, name: str, *, default: bool) -> bool:
    raw = element.attrs.get(name)
    if raw is None or raw == "":
        return default
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ParseError(f"{name} must be true or false on <{element.tag}>")


def _parse_input_type(element: Element) -> str:
    input_type = (element.attrs.get("type", "text").strip() or "text").lower()
    if input_type not in {"text", "password", "ascii-art"}:
        raise ParseError("<Input> type must be text, password, or ascii-art in v1")
    return input_type


def _parse_input_required(element: Element) -> bool:
    raw = element.attrs.get("required")
    if raw is None:
        return False
    normalized = raw.strip().lower()
    if normalized in {"", "mandatory", "true"}:
        return True
    if normalized in {"optional", "false"}:
        return False
    raise ParseError('<Input> required must be "mandatory" or "optional"')


def _normalize_param_name(name: str) -> str:
    return name.replace(":", "_").replace("-", "_")


def _coerce_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped.isdigit():
        return int(stripped)
    if stripped in {"true", "false"}:
        return stripped == "true"
    return stripped
