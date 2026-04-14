from __future__ import annotations

from collections.abc import Callable
import curses
from dataclasses import dataclass, field
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import threading
import textwrap
import time

from erza.backend import BackendBridge, bind_request_context
from erza.local_server import LocalFormServer, LocalServerError, SubmitResult
from erza.model import AsciiAnimation, AsciiArt, Button, ButtonRow, Column, Component, Form, Header, Input, Link, Modal, Row, Screen, Section, Splash, SplashAnimation, SubmitButton, Text
from erza.parser import compile_markup, validate_screen_structure
from erza.remote import RemoteApp, is_remote_source, normalize_remote_url
from erza.source import SourceResolutionError, resolve_local_source_path, resolve_relative_source
from erza.template import render_template


CTRL_D = 4
CTRL_E = 5
CTRL_U = 21
CTRL_A = 1
CTRL_W = 23
ALT_B = -1001
ALT_F = -1002
EDIT_ESCAPE_SEQUENCE_TIMEOUT_MS = 25
DISPLAY_WIDTH = 79
TOP_LEVEL_SECTION_INNER_WIDTH = DISPLAY_WIDTH - 6
NESTED_SECTION_INNER_WIDTH = TOP_LEVEL_SECTION_INNER_WIDTH - 4
FORM_FIELD_INDENT = 4
MIN_ANIMATION_INTERVAL_MS = 50
HELP_MODAL_MAX_WIDTH = 67
HEADER_CELL_GAP = 2
HEADER_CELL_ROW_HEIGHT = 3
LOADING_MODAL_MAX_WIDTH = 28
INTERACTIVE_MODAL_INNER_WIDTH = 51
LOADING_FRAME_INTERVAL_MS = 90
LOADING_DISPLAY_DELAY_SECONDS = 0.12
LOADING_MATRIX_ROWS = 4
LOADING_MATRIX_MIN_WIDTH = 14
LOADING_MATRIX_MAX_WIDTH = 18
LOADING_MATRIX_HEADS = "01+x"
LOADING_MATRIX_TRAILS = ":."
LOADING_MATRIX_NOISE = ".'"
HELP_SHORTCUTS = [
    ("Header h / k / arrows", "Move across the header strip with hjkl or the arrow keys."),
    ("Enter", "Focus the current section body."),
    ("Header gg / G", "Jump to the first or last section."),
    ("Backspace", "Go back one page."),
    ("Section j / k / arrows", "Move line by line inside the current section."),
    ("Section h / l / arrows", "Move across buttons on the current button row."),
    ("Section Ctrl+D / Ctrl+U", "Move by half a page."),
    ("Section Enter", "Edit the current input or open the current link/action."),
    ("Edit type", "Insert text into the current input."),
    ("Edit Ctrl+A / Ctrl+E", "Move to the start or end of the field."),
    ("Edit Ctrl+W", "Delete the previous word."),
    ("Edit Alt+B / Alt+F", "Move backward or forward by word."),
    ("Edit Enter", "Commit the current input edit."),
    ("Edit Esc", "Cancel the current input edit."),
    ("Esc", "Leave section mode and return to the header."),
    ("?", "Toggle the shortcuts modal."),
    ("q", "Exit erza cleanly."),
]


@dataclass(slots=True)
class Segment:
    x: int
    text: str
    style: str


@dataclass(slots=True)
class ActionableTarget:
    x: int
    y: int
    width: int
    label_text: str
    actionable: Button | Link | "InputControl" | "SubmitControl"
    action_group: str | None = None
    action_align: str | None = None


@dataclass(slots=True)
class SectionTarget:
    title: str
    x: int
    y: int
    width: int
    height: int
    title_text: str
    block: "Block"
    actionables: list[ActionableTarget]


@dataclass(slots=True)
class ModalTarget:
    modal_id: str
    title: str
    block: "Block"
    actionables: list[ActionableTarget]


@dataclass(slots=True)
class Block:
    width: int
    height: int
    lines: list[list[Segment]] = field(default_factory=list)
    actionables: list[ActionableTarget] = field(default_factory=list)
    animation_interval_ms: int | None = None


@dataclass(slots=True)
class RenderPlan:
    title: str
    lines: list[list[Segment]]
    sections: list[SectionTarget]
    default_section_index: int = 0
    modals: dict[str, ModalTarget] = field(default_factory=dict)
    form_defaults: dict[str, dict[str, str]] = field(default_factory=dict)
    form_requirements: dict[str, dict[str, str]] = field(default_factory=dict)
    form_validations: dict[str, dict[str, "InputValidation"]] = field(default_factory=dict)
    animation_interval_ms: int | None = None


@dataclass(slots=True)
class HeaderGridLayout:
    cell_inner_width: int
    cell_width: int
    visible_slots: int


@dataclass(slots=True)
class InputControl:
    form_key: str
    input_name: str
    input_type: str
    initial_value: str


@dataclass(slots=True)
class SubmitControl:
    form_key: str
    action: str


@dataclass(slots=True)
class EditState:
    form_key: str
    input_name: str
    cursor_index: int
    original_value: str


@dataclass(slots=True)
class RenderState:
    form_values: dict[str, dict[str, str]]
    edit_state: EditState | None = None
    next_form_index: int = 0
    form_defaults: dict[str, dict[str, str]] = field(default_factory=dict)
    form_requirements: dict[str, dict[str, str]] = field(default_factory=dict)
    form_validations: dict[str, dict[str, "InputValidation"]] = field(default_factory=dict)


@dataclass(slots=True)
class InputValidation:
    label: str
    max_cols: int | None = None


class ErzaApp:
    def __init__(
        self,
        source_path: str | Path,
        backend: BackendBridge | None = None,
        backend_path: Path | None = None,
        session_state: dict[str, object] | None = None,
        form_server: LocalFormServer | None = None,
    ) -> None:
        self.current_source_path = resolve_local_source_path(Path(source_path))
        self.explicit_backend_path = backend_path.resolve() if backend_path else None
        self.backend_path = self.explicit_backend_path or _infer_backend_path(self.current_source_path)
        self.session_state: dict[str, object] = session_state if session_state is not None else {}
        self._form_server = form_server
        if backend is not None:
            self.backend = backend
        elif self.backend_path is not None:
            self.backend = BackendBridge.from_module_path(self.backend_path)
        else:
            self.backend = BackendBridge.empty()

    def build_screen(self) -> Screen:
        source = self.current_source_path.read_text(encoding="utf-8")
        with bind_request_context(self.session_state):
            markup = render_template(source, backend=self.backend)
        return compile_markup(markup)

    def dispatch_action(self, action: str, params: dict[str, object]) -> object:
        with bind_request_context(self.session_state):
            return self.backend.call(action, **params)

    def submit_form(self, action: str, values: dict[str, str]) -> SubmitResult:
        if self._form_server is None:
            self._form_server = LocalFormServer(self.backend, self.session_state)
        return self._form_server.submit(action, values)

    def follow_link(self, href: str) -> "ErzaApp | RemoteApp":
        if href.startswith(("http://", "https://")):
            return RemoteApp(normalize_remote_url(href))

        try:
            target = resolve_relative_source(self.current_source_path, href)
        except SourceResolutionError as exc:
            if is_remote_source(href):
                return RemoteApp(normalize_remote_url(href))
            raise RuntimeError(str(exc)) from exc

        target_backend_path = self.explicit_backend_path or _infer_backend_path(target)
        if target_backend_path is not None and self.backend_path == target_backend_path:
            backend = self.backend
        elif target_backend_path is not None:
            backend = BackendBridge.from_module_path(target_backend_path)
        else:
            backend = BackendBridge.empty()

        return ErzaApp(
            target,
            backend=backend,
            backend_path=self.explicit_backend_path,
            session_state=self.session_state,
            form_server=self._form_server if backend is self.backend else None,
        )


class StaticScreenApp:
    def __init__(self, screen: Screen) -> None:
        self.screen = screen
        self.backend = BackendBridge.empty()

    def build_screen(self) -> Screen:
        return self.screen

    def dispatch_action(self, action: str, params: dict[str, object]) -> object:
        return self.backend.call(action, **params)

    def submit_form(self, action: str, values: dict[str, str]) -> SubmitResult:
        raise RuntimeError("forms are not supported in static screens")

    def follow_link(self, href: str) -> "ErzaApp | RemoteApp":
        raise RuntimeError(f"static screen cannot follow link: {href}")


def run_curses_app(app: ErzaApp | RemoteApp | StaticScreenApp) -> None:
    session = _RuntimeSession(app)
    curses.wrapper(session.run)


def build_render_plan(
    screen: Screen,
    *,
    animation_time: float = 0.0,
    form_values: dict[str, dict[str, str]] | None = None,
    edit_state: EditState | None = None,
    modal_messages: dict[str, str] | None = None,
) -> RenderPlan:
    validate_screen_structure(screen, error_type=TypeError)
    sections = _normalize_sections(screen.children)
    default_section_index = _default_section_index(sections)
    modals = _collect_modals(screen.children)
    render_state = RenderState(form_values=form_values or {}, edit_state=edit_state)
    lines = [
        [Segment(x=0, text=screen.title, style="title")],
        [],
    ]
    section_targets: list[SectionTarget] = []
    modal_targets: dict[str, ModalTarget] = {}
    cursor_y = 2
    animation_interval_ms: int | None = None

    for index, section in enumerate(sections):
        block = _build_section_block(section, animation_time=animation_time, render_state=render_state)
        while len(lines) < cursor_y + block.height:
            lines.append([])

        for line_index, segments in enumerate(block.lines):
            destination = lines[cursor_y + line_index]
            destination.extend(segments)

        section_targets.append(
            SectionTarget(
                title=section.title,
                x=0,
                y=cursor_y,
                width=block.width,
                height=block.height,
                title_text=block.lines[0][0].text if block.lines and block.lines[0] else "",
                block=block,
                actionables=[
                    ActionableTarget(
                        x=item.x,
                        y=item.y + cursor_y,
                        width=item.width,
                        label_text=item.label_text,
                        actionable=item.actionable,
                        action_group=item.action_group,
                        action_align=item.action_align,
                    )
                    for item in block.actionables
                ],
            )
        )
        animation_interval_ms = _merge_animation_interval(
            animation_interval_ms,
            block.animation_interval_ms,
        )
        cursor_y += block.height
        if index != len(sections) - 1:
            lines.append([])
            cursor_y += 1

    for modal in modals:
        if modal.modal_id in modal_targets:
            raise RuntimeError(f"duplicate modal id: {modal.modal_id}")
        block = _build_modal_block(
            modal,
            animation_time=animation_time,
            render_state=render_state,
            message=(modal_messages or {}).get(modal.modal_id, "").strip(),
        )
        modal_targets[modal.modal_id] = ModalTarget(
            modal_id=modal.modal_id,
            title=modal.title,
            block=block,
            actionables=[
                ActionableTarget(
                    x=item.x,
                    y=item.y,
                    width=item.width,
                    label_text=item.label_text,
                    actionable=item.actionable,
                    action_group=item.action_group,
                    action_align=item.action_align,
                )
                for item in block.actionables
            ],
        )
        animation_interval_ms = _merge_animation_interval(animation_interval_ms, block.animation_interval_ms)

    return RenderPlan(
        title=screen.title,
        lines=lines,
        sections=section_targets,
        default_section_index=default_section_index,
        modals=modal_targets,
        form_defaults=render_state.form_defaults,
        form_requirements=render_state.form_requirements,
        form_validations=render_state.form_validations,
        animation_interval_ms=animation_interval_ms,
    )


def next_section_index(plan: RenderPlan, current_index: int, delta: int) -> int:
    if not plan.sections:
        return 0
    return min(max(current_index + delta, 0), len(plan.sections) - 1)


def _decode_edit_key(stdscr: curses.window, key: int) -> int:
    if key != 27:
        return key

    stdscr.timeout(EDIT_ESCAPE_SEQUENCE_TIMEOUT_MS)
    next_key = stdscr.getch()
    if next_key in {ord("b"), ord("B")}:
        return ALT_B
    if next_key in {ord("f"), ord("F")}:
        return ALT_F
    return key


def _move_cursor_backward_word(value: str, cursor: int) -> int:
    cursor = min(max(cursor, 0), len(value))
    while cursor > 0 and value[cursor - 1].isspace():
        cursor -= 1
    while cursor > 0 and not value[cursor - 1].isspace():
        cursor -= 1
    return cursor


def _move_cursor_forward_word(value: str, cursor: int) -> int:
    cursor = min(max(cursor, 0), len(value))
    while cursor < len(value) and value[cursor].isspace():
        cursor += 1
    while cursor < len(value) and not value[cursor].isspace():
        cursor += 1
    return cursor


def next_section_line_index(section: SectionTarget, current_index: int, delta: int) -> int:
    line_count = _section_content_line_count(section)
    if line_count <= 0:
        return 0
    return min(max(current_index + delta, 0), line_count - 1)


def draw_plan(
    stdscr: curses.window,
    plan: RenderPlan,
    header_section_index: int | None,
    body_section_index: int | None,
    scroll_offset: int,
    footer: str = "",
) -> None:
    stdscr.erase()
    height, terminal_width = stdscr.getmaxyx()
    visible_height = _viewport_height(height)
    display_width = _display_width(terminal_width)
    origin_x = _display_origin_x(terminal_width)
    styles = _styles()

    if not plan.sections:
        if footer and height > 0:
            _safe_addnstr(stdscr, height - 1, origin_x, footer, display_width, styles["status"])
        stdscr.refresh()
        return

    body_start_y = _draw_header_grid(
        stdscr,
        plan,
        header_section_index if header_section_index is not None else 0,
        scroll_offset,
        visible_height,
        display_width,
        origin_x,
        styles,
    )
    active_section = plan.sections[body_section_index if body_section_index is not None else 0]
    _draw_section_body(
        stdscr,
        active_section,
        start_y=body_start_y,
        available_height=max(visible_height - body_start_y, 0),
        origin_x=origin_x,
        display_width=display_width,
        styles=styles,
        highlight_active_line=False,
        line_index=0,
        action_index=0,
        scroll_offset=0,
    )

    if footer and height > 0:
        _safe_addnstr(
            stdscr,
            height - 1,
            origin_x,
            footer,
            display_width,
            styles["status"],
        )

    stdscr.refresh()


def draw_splash_screen(
    stdscr: curses.window,
    splash: Splash,
    *,
    animation_time: float,
    footer: str = "",
) -> int | None:
    stdscr.erase()
    height, terminal_width = stdscr.getmaxyx()
    visible_height = _viewport_height(height)
    display_width = _display_width(terminal_width)
    origin_x = _display_origin_x(terminal_width)
    styles = _styles()
    render_state = RenderState(form_values={})
    block = _build_column_like(
        splash.children,
        gap=1,
        animation_time=animation_time,
        max_width=display_width,
        render_state=render_state,
    )
    block_x = origin_x + max((display_width - block.width) // 2, 0)
    block_y = max((visible_height - block.height) // 2, 0)

    for line_index, segments in enumerate(block.lines):
        screen_y = block_y + line_index
        if screen_y >= visible_height:
            break
        for segment in segments:
            available = max((origin_x + display_width) - (block_x + segment.x), 0)
            if available <= 0:
                continue
            _safe_addnstr(
                stdscr,
                screen_y,
                block_x + segment.x,
                segment.text,
                available,
                _segment_style(styles, segment.style),
            )

    if footer and height > 0:
        _safe_addnstr(stdscr, height - 1, origin_x, footer, display_width, styles["status"])
    stdscr.refresh()
    return block.animation_interval_ms


def draw_section_page(
    stdscr: curses.window,
    plan: RenderPlan,
    section: SectionTarget,
    section_index: int,
    header_scroll_offset: int,
    line_index: int,
    action_index: int,
    scroll_offset: int,
    footer: str = "",
) -> None:
    stdscr.erase()
    height, terminal_width = stdscr.getmaxyx()
    visible_height = _viewport_height(height)
    display_width = _display_width(terminal_width)
    origin_x = _display_origin_x(terminal_width)
    styles = _styles()
    body_start_y = _draw_header_grid(
        stdscr,
        plan,
        section_index,
        header_scroll_offset,
        visible_height,
        display_width,
        origin_x,
        styles,
    )
    _draw_section_body(
        stdscr,
        section,
        start_y=body_start_y,
        available_height=max(visible_height - body_start_y, 0),
        origin_x=origin_x,
        display_width=display_width,
        styles=styles,
        highlight_active_line=True,
        line_index=line_index,
        action_index=action_index,
        scroll_offset=scroll_offset,
    )

    if footer and height > 0:
        _safe_addnstr(
            stdscr,
            height - 1,
            origin_x,
            footer,
            display_width,
            styles["status"],
        )

    stdscr.refresh()


def draw_shortcuts_modal(
    stdscr: curses.window,
    *,
    footer: str = "",
) -> None:
    height, terminal_width = stdscr.getmaxyx()
    visible_height = _viewport_height(height)
    display_width = _display_width(terminal_width)
    origin_x = _display_origin_x(terminal_width)
    styles = _styles()

    inner_width = min(HELP_MODAL_MAX_WIDTH - 4, max(display_width - 8, 24))
    width = inner_width + 4
    title_text = _truncate_text("[ Shortcuts ]", inner_width)
    lines = _help_modal_lines(inner_width)
    top_border = "+-" + title_text + "-" * max(inner_width + 1 - len(title_text), 0) + "+"
    bottom_border = "+" + "-" * (width - 2) + "+"
    modal_x = origin_x + max((display_width - width) // 2, 0)
    modal_height = len(lines) + 2
    top_y = max((visible_height - modal_height) // 2, 0)

    _safe_addnstr(stdscr, top_y, modal_x, top_border, width, styles["section_title_active"])

    for index, line in enumerate(lines, start=1):
        screen_y = top_y + index
        if screen_y >= visible_height:
            break
        _safe_addnstr(stdscr, screen_y, modal_x, "| ", 2, styles["section_border"])
        _safe_addnstr(stdscr, screen_y, modal_x + 2, " " * inner_width, inner_width, styles["section_fill"])
        _safe_addnstr(stdscr, screen_y, modal_x + width - 2, " |", 2, styles["section_border"])
        _safe_addnstr(stdscr, screen_y, modal_x + 2, line, inner_width, styles["text"])

    bottom_y = top_y + modal_height - 1
    if bottom_y < visible_height:
        _safe_addnstr(stdscr, bottom_y, modal_x, bottom_border, width, styles["section_border"])

    if footer and height > 0:
        _safe_addnstr(
            stdscr,
            height - 1,
            origin_x,
            footer,
            display_width,
            styles["status"],
        )

    stdscr.refresh()


def draw_loading_overlay(
    stdscr: curses.window,
    *,
    message: str,
    frame_index: int,
) -> None:
    height, terminal_width = stdscr.getmaxyx()
    visible_height = _viewport_height(height)
    display_width = _display_width(terminal_width)
    origin_x = _display_origin_x(terminal_width)
    styles = _styles()

    del message

    max_inner_width = min(LOADING_MODAL_MAX_WIDTH - 4, max(display_width - 10, 16))
    inner_width = min(max_inner_width, LOADING_MATRIX_MAX_WIDTH)
    width = inner_width + 4
    top_border = "+" + "-" * max(width - 2, 0) + "+"
    bottom_border = "+" + "-" * (width - 2) + "+"
    modal_x = origin_x + max((display_width - width) // 2, 0)
    lines = _loading_overlay_lines(frame_index, inner_width)
    modal_height = len(lines) + 2
    top_y = max((visible_height - modal_height) // 2, 0)

    _safe_addnstr(stdscr, top_y, modal_x, top_border, width, styles["section_border"])

    for index, line in enumerate(lines, start=1):
        screen_y = top_y + index
        if screen_y >= visible_height:
            break
        _safe_addnstr(stdscr, screen_y, modal_x, "| ", 2, styles["section_border"])
        _safe_addnstr(stdscr, screen_y, modal_x + width - 2, " |", 2, styles["section_border"])
        line_style = styles["help"] if index in {1, len(lines)} else styles["header"]
        _safe_addnstr(
            stdscr,
            screen_y,
            modal_x + 2 + max((inner_width - len(line)) // 2, 0),
            line,
            len(line),
            line_style,
        )

    bottom_y = top_y + modal_height - 1
    if bottom_y < visible_height:
        _safe_addnstr(stdscr, bottom_y, modal_x, bottom_border, width, styles["section_border"])

    stdscr.refresh()


def _loading_overlay_lines(frame_index: int, inner_width: int) -> list[str]:
    matrix_width = max(min(inner_width, LOADING_MATRIX_MAX_WIDTH), LOADING_MATRIX_MIN_WIDTH)
    rows = [[" "] * matrix_width for _ in range(LOADING_MATRIX_ROWS)]
    column_count = 4 if matrix_width < 18 else 5
    positions = [
        max(
            1,
            min(
                matrix_width - 2,
                round((matrix_width - 1) * (index + 1) / (column_count + 1)),
            ),
        )
        for index in range(column_count)
    ]

    for column_index, position in enumerate(positions):
        cycle = LOADING_MATRIX_ROWS + 4 + (column_index % 2)
        head_row = ((frame_index + column_index * 2) % cycle) - 2
        head_char = LOADING_MATRIX_HEADS[(frame_index + column_index * 3) % len(LOADING_MATRIX_HEADS)]

        if 0 <= head_row < LOADING_MATRIX_ROWS:
            rows[head_row][position] = head_char

        for trail_index, trail_char in enumerate(LOADING_MATRIX_TRAILS, start=1):
            trail_row = head_row - trail_index
            if 0 <= trail_row < LOADING_MATRIX_ROWS and rows[trail_row][position] == " ":
                rows[trail_row][position] = trail_char

    for noise_index in range(2):
        x = (frame_index * (3 + noise_index) + noise_index * 5) % matrix_width
        y = ((frame_index // 2) + noise_index * 2) % LOADING_MATRIX_ROWS
        if rows[y][x] == " ":
            rows[y][x] = LOADING_MATRIX_NOISE[(frame_index + noise_index) % len(LOADING_MATRIX_NOISE)]

    for row_index, row in enumerate(rows):
        if all(char == " " for char in row):
            x = (frame_index * 2 + row_index * 3) % matrix_width
            row[x] = LOADING_MATRIX_TRAILS[row_index % len(LOADING_MATRIX_TRAILS)]

    return ["".join(row) for row in rows]


def draw_modal_overlay(
    stdscr: curses.window,
    modal: ModalTarget,
    *,
    line_index: int,
    action_index: int,
    scroll_offset: int,
) -> None:
    height, terminal_width = stdscr.getmaxyx()
    visible_height = _viewport_height(height)
    display_width = _display_width(terminal_width)
    origin_x = _display_origin_x(terminal_width)
    styles = _styles()

    block_width = min(modal.block.width, display_width)
    available_height = min(max(visible_height - 2, 3), modal.block.height)
    modal_x = origin_x + max((display_width - block_width) // 2, 0)
    top_y = max((visible_height - available_height) // 2, 0)
    content_lines = modal.block.lines[1:-1] or [[]]

    if available_height >= modal.block.height:
        visible_lines = modal.block.lines
        active_y = 1 + line_index if 0 <= line_index < len(content_lines) else None
    else:
        if available_height <= 1:
            visible_lines = [modal.block.lines[0]]
            active_y = None
        elif available_height == 2:
            visible_lines = [modal.block.lines[0], modal.block.lines[-1]]
            active_y = None
        else:
            content_viewport_height = available_height - 2
            visible_lines = [
                modal.block.lines[0],
                *content_lines[scroll_offset : scroll_offset + content_viewport_height],
                modal.block.lines[-1],
            ]
            active_y = (
                1 + line_index - scroll_offset
                if scroll_offset <= line_index < scroll_offset + content_viewport_height
                else None
            )

    for body_y, line in enumerate(visible_lines):
        screen_y = top_y + body_y
        if screen_y >= visible_height:
            break
        active_content_line = active_y == body_y
        current_line_index: int | None = None
        if body_y != 0 and body_y != len(visible_lines) - 1:
            current_line_index = body_y - 1 if available_height >= modal.block.height else scroll_offset + body_y - 1
        line_actionables = _modal_line_actionables(modal, current_line_index) if current_line_index is not None else []
        for segment in line:
            if segment.x >= block_width:
                continue
            available = max(block_width - segment.x, 0)
            if available == 0:
                continue
            style_name = "section_title_active" if segment.style == "section_title" else segment.style
            _safe_addnstr(
                stdscr,
                screen_y,
                modal_x + segment.x,
                segment.text,
                available,
                _segment_style(styles, style_name, active_content_line=active_content_line),
            )
        if _is_button_row_actionable_line(line_actionables):
            _draw_button_row_actionables(
                stdscr,
                line_segments=line,
                line_actionables=line_actionables,
                selected_index=action_index,
                origin_x=modal_x,
                screen_y=screen_y,
                max_width=block_width,
                styles=styles,
                active=active_content_line,
            )
        elif active_content_line:
            _draw_active_actionable(
                stdscr,
                line_actionables=line_actionables,
                selected_index=action_index,
                origin_x=modal_x,
                screen_y=screen_y,
                max_width=block_width,
                styles=styles,
            )
        if active_content_line:
            _safe_addnstr(
                stdscr,
                screen_y,
                max(modal_x - 1, 0),
                ">",
                1,
                styles["selection_marker_active"],
            )

    stdscr.refresh()


def _draw_header_grid(
    stdscr: curses.window,
    plan: RenderPlan,
    section_index: int,
    scroll_offset: int,
    visible_height: int,
    display_width: int,
    origin_x: int,
    styles: dict[str, int],
) -> int:
    layout = _header_grid_layout(plan, display_width)
    start_y = 0
    section_start = min(max(scroll_offset, 0), max(len(plan.sections) - layout.visible_slots, 0))
    section_end = min(section_start + layout.visible_slots, len(plan.sections))
    visible_sections = plan.sections[section_start:section_end]
    cell_inner_widths = [
        _header_cell_inner_width(layout, section.title)
        for section in visible_sections
    ]
    cell_widths = [inner_width + 4 for inner_width in cell_inner_widths]
    row_width = sum(cell_widths) + max(len(cell_widths) - 1, 0) * HEADER_CELL_GAP
    row_origin_x = origin_x + max((display_width - row_width) // 2, 0)

    cursor_x = row_origin_x
    for slot, section_pos in enumerate(range(section_start, section_end)):
        _draw_header_cell(
            stdscr,
            x=cursor_x,
            y=start_y,
            title=plan.sections[section_pos].title,
            inner_width=cell_inner_widths[slot],
            active=section_pos == section_index,
            styles=styles,
        )
        cursor_x += cell_widths[slot] + HEADER_CELL_GAP

    return start_y + HEADER_CELL_ROW_HEIGHT + 1


def _draw_header_cell(
    stdscr: curses.window,
    *,
    x: int,
    y: int,
    title: str,
    inner_width: int,
    active: bool,
    styles: dict[str, int],
) -> None:
    content_width = inner_width + 2
    title_text = _truncate_text(title, content_width).center(content_width)
    border = "+" + "-" * (inner_width + 2) + "+"
    border_style = styles["section_border"]
    fill_style = styles["section_fill"] | curses.A_REVERSE if active else styles["section_fill"]
    title_style = styles["section_title_active"] if active else styles["section_title"]

    _safe_addnstr(stdscr, y, x, border, len(border), border_style)
    _safe_addnstr(stdscr, y + 1, x, "|", 1, border_style)
    _safe_addnstr(stdscr, y + 1, x + 1, " " * content_width, content_width, fill_style)
    _safe_addnstr(stdscr, y + 1, x + 1, title_text, len(title_text), title_style)
    _safe_addnstr(stdscr, y + 1, x + 1 + content_width, "|", 1, border_style)
    _safe_addnstr(stdscr, y + 2, x, border, len(border), border_style)


def _draw_section_body(
    stdscr: curses.window,
    section: SectionTarget,
    *,
    start_y: int,
    available_height: int,
    origin_x: int,
    display_width: int,
    styles: dict[str, int],
    highlight_active_line: bool,
    line_index: int,
    action_index: int,
    scroll_offset: int,
) -> None:
    if available_height <= 0:
        return

    block_width = min(section.block.width, display_width)
    block_x = origin_x + max((display_width - block_width) // 2, 0)
    content_lines = section.block.lines[1:-1] or [[]]

    if available_height >= section.block.height:
        top_y = start_y
        visible_lines = section.block.lines
        active_y = 1 + line_index if highlight_active_line and 0 <= line_index < len(content_lines) else None
    else:
        if available_height <= 1:
            visible_lines = [section.block.lines[0]]
            active_y = None
        elif available_height == 2:
            visible_lines = [section.block.lines[0], section.block.lines[-1]]
            active_y = None
        else:
            content_viewport_height = available_height - 2
            visible_lines = [
                section.block.lines[0],
                *content_lines[scroll_offset : scroll_offset + content_viewport_height],
                section.block.lines[-1],
            ]
            active_y = (
                1 + line_index - scroll_offset
                if highlight_active_line and scroll_offset <= line_index < scroll_offset + content_viewport_height
                else None
            )
        top_y = start_y

    for body_y, line in enumerate(visible_lines):
        screen_y = top_y + body_y
        if screen_y >= start_y + available_height:
            break
        active_content_line = active_y == body_y
        current_line_index: int | None = None
        if body_y != 0 and body_y != len(visible_lines) - 1:
            current_line_index = body_y - 1 if available_height >= section.block.height else scroll_offset + body_y - 1
        line_actionables = _section_line_actionables(section, current_line_index) if current_line_index is not None else []
        for segment in line:
            if segment.x >= block_width:
                continue
            available = max(block_width - segment.x, 0)
            if available == 0:
                continue
            _safe_addnstr(
                stdscr,
                screen_y,
                block_x + segment.x,
                segment.text,
                available,
                _segment_style(styles, segment.style, active_content_line=active_content_line),
            )
        if _is_button_row_actionable_line(line_actionables):
            _draw_button_row_actionables(
                stdscr,
                line_segments=line,
                line_actionables=line_actionables,
                selected_index=action_index,
                origin_x=block_x,
                screen_y=screen_y,
                max_width=block_width,
                styles=styles,
                active=active_content_line,
            )
        elif active_content_line:
            _draw_active_actionable(
                stdscr,
                line_actionables=line_actionables,
                selected_index=action_index,
                origin_x=block_x,
                screen_y=screen_y,
                max_width=block_width,
                styles=styles,
            )
        if active_content_line:
            _safe_addnstr(stdscr, screen_y, max(block_x - 1, 0), ">", 1, styles["selection_marker"])


class _RuntimeSession:
    def __init__(self, app: ErzaApp | RemoteApp | StaticScreenApp) -> None:
        self.app = app
        self.history: list[ErzaApp | RemoteApp | StaticScreenApp] = []
        self._screen: Screen | None = None
        self._last_plan: RenderPlan | None = None
        self._pending_section_index: int | None = -1
        self.active_modal_id: str | None = None
        self.modal_base_mode = "page"
        self.modal_line_index = 0
        self.modal_scroll_offset = 0
        self.modal_action_index = 0
        self.modal_messages: dict[str, str] = {}
        self.body_section_index = 0
        self.mode = "page"
        self.show_help = False
        self.section_index = 0
        self.scroll_offset = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.section_action_index = 0
        self.form_values: dict[str, dict[str, str]] = {}
        self.edit_state: EditState | None = None
        self.pending_g = False
        self.animation_epoch = time.monotonic()
        self._seen_splash_locations: set[str] = set()
        self._active_splash_location: str | None = None
        self._active_splash_started_at: float | None = None
        self.status = ""

    def run(self, stdscr: curses.window) -> None:
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        try:
            curses.assume_default_colors(-1, -1)
        except (AttributeError, curses.error):
            pass
        stdscr.keypad(True)

        while True:
            screen = self._current_screen(stdscr)
            splash = self._active_splash(screen)
            animation_time = time.monotonic() - self.animation_epoch
            plan = build_render_plan(
                screen,
                animation_time=animation_time,
                form_values=self.form_values,
                edit_state=self.edit_state,
                modal_messages=self.modal_messages,
            )
            self._sync_state(plan)
            self._last_plan = plan
            footer = self._footer_text()
            if splash is not None:
                splash_interval_ms = draw_splash_screen(
                    stdscr,
                    splash,
                    animation_time=animation_time,
                    footer=footer,
                )
                remaining_ms = self._active_splash_remaining_ms(screen)
                timeout_options = [remaining_ms]
                if splash_interval_ms is not None:
                    timeout_options.append(splash_interval_ms)
                stdscr.timeout(max(min(timeout_options), 1))
            else:
                self._draw_active_view(stdscr, plan, footer)
                stdscr.timeout(plan.animation_interval_ms if plan.animation_interval_ms is not None else -1)
            key = stdscr.getch()
            if key == -1:
                continue
            if splash is not None:
                if key == ord("q"):
                    return
                continue
            if self.mode == "edit":
                self.pending_g = False
                key = _decode_edit_key(stdscr, key)
                self._handle_edit_key(key, stdscr)
                continue
            if key == ord("q"):
                return
            if self.show_help:
                if key in {ord("?"), 27}:
                    self.show_help = False
                continue
            if self.active_modal_id is not None and key in {curses.KEY_BACKSPACE, 127, 8}:
                self._close_modal()
                continue
            if key in {curses.KEY_BACKSPACE, 127, 8}:
                self._go_back()
                continue
            if key == ord("?"):
                self.show_help = True
                self.pending_g = False
                continue
            if key == 27:
                if self.active_modal_id is not None:
                    self._close_modal()
                elif self.mode == "section":
                    self._exit_section_mode()
                continue
            if key == ord("g"):
                if self.pending_g:
                    if self.active_modal_id is not None:
                        self._jump_to_first_modal_line(plan)
                    elif self.mode == "section":
                        self._jump_to_first_line(plan)
                    else:
                        self._jump_to_first_section(plan)
                else:
                    self.pending_g = True
                continue
            if key == ord("G"):
                self.pending_g = False
                if self.active_modal_id is not None:
                    self._jump_to_last_modal_line(plan)
                elif self.mode == "section":
                    self._jump_to_last_line(plan)
                else:
                    self._jump_to_last_section(plan)
                continue

            self.pending_g = False
            if self.active_modal_id is not None:
                if key in {ord("h"), curses.KEY_LEFT}:
                    self._move_modal_action(plan, -1)
                    continue
                if key in {ord("l"), curses.KEY_RIGHT}:
                    self._move_modal_action(plan, 1)
                    continue
                if key in {ord("j"), curses.KEY_DOWN}:
                    self._move_modal_line(plan, 1)
                    continue
                if key in {ord("k"), curses.KEY_UP}:
                    self._move_modal_line(plan, -1)
                    continue
                if key == CTRL_D:
                    self._scroll_modal_half_page(plan, stdscr.getmaxyx()[0], 1)
                    continue
                if key == CTRL_U:
                    self._scroll_modal_half_page(plan, stdscr.getmaxyx()[0], -1)
                    continue
                if key in {curses.KEY_ENTER, ord("\n"), ord("\r"), ord(" ")}:
                    self._activate_modal(plan, stdscr)
                    continue
                continue
            if self.mode == "page":
                if key in {ord("h"), curses.KEY_LEFT}:
                    self._move_header_selection(plan, stdscr.getmaxyx()[1], "left")
                    continue
                if key in {ord("l"), curses.KEY_RIGHT}:
                    self._move_header_selection(plan, stdscr.getmaxyx()[1], "right")
                    continue
                if key in {ord("j"), curses.KEY_DOWN}:
                    self._move_header_selection(plan, stdscr.getmaxyx()[1], "down")
                    continue
                if key in {ord("k"), curses.KEY_UP}:
                    self._move_header_selection(plan, stdscr.getmaxyx()[1], "up")
                    continue
                if key in {curses.KEY_ENTER, ord("\n"), ord(" ")}:
                    self._enter_section_mode(plan, stdscr)
                    continue
            if key in {ord("j"), curses.KEY_DOWN}:
                if self.mode == "section":
                    self._move_section_line(plan, 1)
                continue
            if key in {ord("k"), curses.KEY_UP}:
                if self.mode == "section":
                    self._move_section_line(plan, -1)
                continue
            if key in {ord("h"), curses.KEY_LEFT}:
                if self.mode == "section":
                    self._move_section_action(plan, -1)
                continue
            if key in {ord("l"), curses.KEY_RIGHT}:
                if self.mode == "section":
                    self._move_section_action(plan, 1)
                continue
            if key == CTRL_D and self.mode == "section":
                self._scroll_section_half_page(plan, stdscr.getmaxyx()[0], 1)
                continue
            if key == CTRL_U and self.mode == "section":
                self._scroll_section_half_page(plan, stdscr.getmaxyx()[0], -1)
                continue
            if key in {curses.KEY_ENTER, ord("\n"), ord("\r")} and self.mode == "section":
                self._activate(plan, stdscr)
                continue

    def _draw_active_view(self, stdscr: curses.window, plan: RenderPlan, footer: str) -> None:
        base_mode = self.modal_base_mode if self.active_modal_id is not None else self.mode
        if base_mode in {"section", "edit"} and plan.sections:
            self._sync_section_scroll(plan, stdscr.getmaxyx()[0])
            draw_section_page(
                stdscr,
                plan,
                plan.sections[self.section_index],
                self.section_index,
                self.scroll_offset,
                self.section_line_index,
                self.section_action_index,
                self.section_scroll_offset,
                footer,
            )
        else:
            screen_height, terminal_width = stdscr.getmaxyx()
            self._sync_page_scroll(plan, screen_height, terminal_width)
            draw_plan(
                stdscr,
                plan,
                self.section_index if plan.sections else None,
                self.body_section_index if plan.sections else None,
                self.scroll_offset,
                footer,
            )
        active_modal = self._active_modal(plan)
        if active_modal is not None:
            self._sync_modal_scroll(plan, stdscr.getmaxyx()[0])
            draw_modal_overlay(
                stdscr,
                active_modal,
                line_index=self.modal_line_index,
                action_index=self.modal_action_index,
                scroll_offset=self.modal_scroll_offset,
            )
        if self.show_help:
            draw_shortcuts_modal(stdscr, footer=footer)

    def _current_screen(self, stdscr: curses.window | None = None) -> Screen:
        if self._screen is None:
            if stdscr is None:
                self._screen = self.app.build_screen()
            else:
                self._screen = self._run_with_loading(
                    stdscr,
                    lambda: self.app.build_screen(),
                    message="Loading app",
                    plan=self._last_plan,
                )
            self._apply_pending_page_reset(self._screen)
        return self._screen

    def _schedule_page_reset(self, section_index: int | None = None) -> None:
        self._pending_section_index = -1 if section_index is None else max(section_index, 0)

    def _apply_pending_page_reset(self, screen: Screen) -> None:
        if self._pending_section_index is None:
            return
        if self._pending_section_index < 0:
            self.section_index = _default_section_index(_normalize_sections(screen.children))
        else:
            self.section_index = self._pending_section_index
        self.scroll_offset = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.section_action_index = 0
        self._pending_section_index = None

    def _run_with_loading(
        self,
        stdscr: curses.window | None,
        operation: Callable[[], object],
        *,
        message: str,
        plan: RenderPlan | None = None,
    ) -> object:
        if stdscr is None:
            return operation()

        outcome: dict[str, object] = {}
        finished = threading.Event()

        def worker() -> None:
            try:
                outcome["result"] = operation()
            except BaseException as exc:  # noqa: BLE001
                outcome["error"] = exc
            finally:
                finished.set()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        if not finished.wait(LOADING_DISPLAY_DELAY_SECONDS):
            frame_index = 0
            self._draw_loading_frame(stdscr, message=message, frame_index=frame_index, plan=plan)
            while not finished.wait(LOADING_FRAME_INTERVAL_MS / 1000):
                frame_index += 1
                self._draw_loading_frame(stdscr, message=message, frame_index=frame_index, plan=plan)

        thread.join()

        error = outcome.get("error")
        if isinstance(error, BaseException):
            raise error
        return outcome.get("result")

    def _draw_loading_frame(
        self,
        stdscr: curses.window,
        *,
        message: str,
        frame_index: int,
        plan: RenderPlan | None,
    ) -> None:
        footer = self._footer_text()
        if plan is not None:
            self._draw_active_view(stdscr, plan, footer)
        else:
            stdscr.erase()
            height, terminal_width = stdscr.getmaxyx()
            display_width = _display_width(terminal_width)
            origin_x = _display_origin_x(terminal_width)
            styles = _styles()
            if footer and height > 0:
                _safe_addnstr(stdscr, height - 1, origin_x, footer, display_width, styles["status"])
            stdscr.refresh()
        draw_loading_overlay(stdscr, message=message, frame_index=frame_index)

    def _invalidate_screen(self, *, reset_animation: bool = False) -> None:
        self._screen = None
        if reset_animation:
            self.animation_epoch = time.monotonic()

    def _sync_state(self, plan: RenderPlan) -> None:
        if not plan.sections:
            self.mode = "page"
            self.section_index = 0
            self.body_section_index = 0
            self.scroll_offset = 0
            self.section_line_index = 0
            self.section_scroll_offset = 0
            self.section_action_index = 0
            self.edit_state = None
            self.active_modal_id = None
            self.modal_line_index = 0
            self.modal_scroll_offset = 0
            self.modal_action_index = 0
            return

        self.section_index = min(self.section_index, len(plan.sections) - 1)
        active_body_index = self._resolved_body_section_index(plan)
        active_section = plan.sections[self.section_index]
        if self._is_overlay_section(active_section):
            self.body_section_index = active_body_index
        else:
            self.body_section_index = self.section_index
        active_section = plan.sections[self.section_index]
        self.section_line_index = min(
            self.section_line_index,
            max(_section_content_line_count(active_section) - 1, 0),
        )
        self.section_action_index = min(
            self.section_action_index,
            max(len(_section_line_actionables(active_section, self.section_line_index)) - 1, 0),
        )
        active_modal = self._active_modal(plan)
        if self.active_modal_id is not None and active_modal is None:
            self.active_modal_id = None
            self.modal_line_index = 0
            self.modal_scroll_offset = 0
            self.modal_action_index = 0
            if self.mode != "edit":
                self.mode = self.modal_base_mode
        elif active_modal is not None:
            self.modal_line_index = min(
                self.modal_line_index,
                max(_modal_content_line_count(active_modal) - 1, 0),
            )
            self.modal_action_index = min(
                self.modal_action_index,
                max(len(_modal_line_actionables(active_modal, self.modal_line_index)) - 1, 0),
            )
        if self.mode == "edit":
            if active_modal is not None:
                active_target = _selected_actionable(
                    _modal_line_actionables(active_modal, self.modal_line_index),
                    self.modal_action_index,
                )
                if active_target is None or not isinstance(active_target.actionable, InputControl):
                    self.mode = "modal"
                    self.edit_state = None
                return
            active_target = _selected_actionable(
                _section_line_actionables(active_section, self.section_line_index),
                self.section_action_index,
            )
            if active_target is None or not isinstance(active_target.actionable, InputControl):
                self.mode = "section"
                self.edit_state = None

    def _sync_page_scroll(self, plan: RenderPlan, screen_height: int, terminal_width: int) -> None:
        self.scroll_offset = compute_scroll_offset(
            plan,
            self.section_index,
            screen_height,
            terminal_width,
            self.scroll_offset,
        )

    def _sync_section_scroll(self, plan: RenderPlan, screen_height: int) -> None:
        if not plan.sections:
            self.section_scroll_offset = 0
            return
        self.section_scroll_offset = compute_section_scroll_offset(
            plan.sections[self.section_index],
            self.section_line_index,
            screen_height,
            self.section_scroll_offset,
        )

    def _sync_modal_scroll(self, plan: RenderPlan, screen_height: int) -> None:
        modal = self._active_modal(plan)
        if modal is None:
            self.modal_scroll_offset = 0
            return
        self.modal_scroll_offset = compute_modal_scroll_offset(
            modal,
            self.modal_line_index,
            screen_height,
            self.modal_scroll_offset,
        )

    def _move_section(self, plan: RenderPlan, delta: int) -> None:
        if not plan.sections:
            return
        next_index = next_section_index(plan, self.section_index, delta)
        if next_index == self.section_index:
            return
        self.section_index = next_index
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.section_action_index = 0
        self.status = ""

    def _move_header_selection(self, plan: RenderPlan, terminal_width: int, direction: str) -> None:
        if not plan.sections:
            return
        next_index = self.section_index
        if direction in {"left", "up"}:
            next_index = (self.section_index - 1) % len(plan.sections)
        elif direction in {"right", "down"}:
            next_index = (self.section_index + 1) % len(plan.sections)

        if next_index == self.section_index:
            return
        self.section_index = next_index
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.section_action_index = 0
        self.status = ""

    def _move_section_line(self, plan: RenderPlan, delta: int) -> None:
        if not plan.sections:
            return
        self.section_line_index = next_section_line_index(
            plan.sections[self.section_index],
            self.section_line_index,
            delta,
        )
        self.section_action_index = 0
        self.status = ""

    def _move_modal_line(self, plan: RenderPlan, delta: int) -> None:
        modal = self._active_modal(plan)
        if modal is None:
            return
        line_count = _modal_content_line_count(modal)
        self.modal_line_index = min(max(self.modal_line_index + delta, 0), max(line_count - 1, 0))
        self.modal_action_index = 0
        self.status = ""

    def _move_section_action(self, plan: RenderPlan, delta: int) -> None:
        if not plan.sections:
            return
        actionables = _section_line_actionables(plan.sections[self.section_index], self.section_line_index)
        if len(actionables) <= 1:
            return
        self.section_action_index = min(
            max(self.section_action_index + delta, 0),
            len(actionables) - 1,
        )
        self.status = ""

    def _move_modal_action(self, plan: RenderPlan, delta: int) -> None:
        modal = self._active_modal(plan)
        if modal is None:
            return
        actionables = _modal_line_actionables(modal, self.modal_line_index)
        if len(actionables) <= 1:
            return
        self.modal_action_index = min(
            max(self.modal_action_index + delta, 0),
            len(actionables) - 1,
        )
        self.status = ""

    def _jump_to_first_section(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        self.section_index = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.section_action_index = 0
        self.status = ""

    def _jump_to_last_section(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        self.section_index = len(plan.sections) - 1
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.section_action_index = 0
        self.status = ""

    def _jump_to_first_line(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        self.section_line_index = 0
        self.section_action_index = 0
        self.status = ""

    def _jump_to_last_line(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        self.section_line_index = max(_section_content_line_count(plan.sections[self.section_index]) - 1, 0)
        self.section_action_index = 0
        self.status = ""

    def _jump_to_first_modal_line(self, plan: RenderPlan) -> None:
        if self._active_modal(plan) is None:
            return
        self.modal_line_index = 0
        self.modal_action_index = 0
        self.status = ""

    def _jump_to_last_modal_line(self, plan: RenderPlan) -> None:
        modal = self._active_modal(plan)
        if modal is None:
            return
        self.modal_line_index = max(_modal_content_line_count(modal) - 1, 0)
        self.modal_action_index = 0
        self.status = ""

    def _scroll_section_half_page(self, plan: RenderPlan, screen_height: int, direction: int) -> None:
        if not plan.sections:
            return
        section = plan.sections[self.section_index]
        content_height = _section_content_viewport_height(screen_height)
        step = max(content_height // 2, 1)
        self.section_line_index = next_section_line_index(section, self.section_line_index, direction * step)
        self.section_action_index = 0
        self.status = ""

    def _scroll_modal_half_page(self, plan: RenderPlan, screen_height: int, direction: int) -> None:
        modal = self._active_modal(plan)
        if modal is None:
            return
        content_height = max(min(_viewport_height(screen_height) - 2, modal.block.height) - 2, 1)
        step = max(content_height // 2, 1)
        line_count = _modal_content_line_count(modal)
        self.modal_line_index = min(
            max(self.modal_line_index + direction * step, 0),
            max(line_count - 1, 0),
        )
        self.modal_action_index = 0
        self.status = ""

    def _enter_section_mode(self, plan: RenderPlan, stdscr: curses.window | None = None) -> None:
        if not plan.sections:
            self.status = "page has no sections"
            return
        if self._is_direct_action_section(plan.sections[self.section_index]):
            self.section_line_index = 0
            self._activate(plan, stdscr)
            return
        self.mode = "section"
        self.show_help = False
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.section_action_index = 0
        self.status = ""

    def _exit_section_mode(self) -> None:
        self.mode = "page"
        self.show_help = False
        self.section_scroll_offset = 0
        self.section_action_index = 0
        self.edit_state = None
        self.status = ""

    def _open_modal(self, plan: RenderPlan, modal_id: str, stdscr: curses.window | None = None) -> None:
        if modal_id not in plan.modals:
            self.status = f"unknown modal: {modal_id}"
            return
        self.active_modal_id = modal_id
        self.modal_base_mode = "section" if self.mode in {"section", "edit"} else "page"
        self.modal_line_index = 0
        self.modal_scroll_offset = 0
        self.modal_action_index = 0
        self.modal_messages.pop(modal_id, None)
        self.mode = "modal"
        self.show_help = False
        self.pending_g = False
        self.status = ""
        self._focus_first_modal_input(plan.modals[modal_id], stdscr)

    def _close_modal(self) -> None:
        self.active_modal_id = None
        self.modal_line_index = 0
        self.modal_scroll_offset = 0
        self.modal_action_index = 0
        self.edit_state = None
        self.mode = self.modal_base_mode
        self.show_help = False
        self.pending_g = False
        self.status = ""

    def _go_back(self) -> None:
        if not self.history:
            self.status = "no previous page"
            return
        self.app = self.history.pop()
        self._invalidate_screen(reset_animation=True)
        self.mode = "page"
        self.show_help = False
        self.section_index = 0
        self.body_section_index = 0
        self.scroll_offset = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.section_action_index = 0
        self.form_values = {}
        self.edit_state = None
        self.active_modal_id = None
        self.modal_line_index = 0
        self.modal_scroll_offset = 0
        self.modal_action_index = 0
        self.modal_messages = {}
        self.pending_g = False
        self.status = "went back"

    def _footer_text(self) -> str:
        return _app_location(self.app)

    def _active_splash(self, screen: Screen) -> Splash | None:
        splash = screen.splash
        location = _app_location(self.app)
        if splash is None:
            if self._active_splash_location == location:
                self._active_splash_location = None
                self._active_splash_started_at = None
            return None
        if location in self._seen_splash_locations:
            return None
        if self._active_splash_location != location or self._active_splash_started_at is None:
            self._active_splash_location = location
            self._active_splash_started_at = time.monotonic()
            return splash
        if self._active_splash_remaining_ms(screen) <= 0:
            self._seen_splash_locations.add(location)
            self._active_splash_location = None
            self._active_splash_started_at = None
            return None
        return splash

    def _active_splash_remaining_ms(self, screen: Screen) -> int:
        splash = screen.splash
        if splash is None or self._active_splash_started_at is None:
            return 0
        elapsed_ms = int((time.monotonic() - self._active_splash_started_at) * 1000)
        return max(splash.duration_ms - elapsed_ms, 0)

    def _active_modal(self, plan: RenderPlan) -> ModalTarget | None:
        if self.active_modal_id is None:
            return None
        return plan.modals.get(self.active_modal_id)

    def _resolved_body_section_index(self, plan: RenderPlan) -> int:
        if not plan.sections:
            return 0
        if 0 <= self.body_section_index < len(plan.sections):
            candidate = plan.sections[self.body_section_index]
            if not self._is_overlay_section(candidate):
                return self.body_section_index
        for index, section in enumerate(plan.sections):
            if not self._is_overlay_section(section):
                return index
        return min(self.section_index, len(plan.sections) - 1)

    def _is_overlay_section(self, section: SectionTarget) -> bool:
        return self._is_direct_action_section(section)

    def _is_direct_action_section(self, section: SectionTarget) -> bool:
        if _section_content_line_count(section) != 1 or len(section.block.actionables) != 1:
            return False
        target = section.block.actionables[0]
        return target.y == 1 and isinstance(target.actionable, Button)

    def _activate(self, plan: RenderPlan, stdscr: curses.window | None = None) -> None:
        if not plan.sections:
            return
        section = plan.sections[self.section_index]
        target = _selected_actionable(
            _section_line_actionables(section, self.section_line_index),
            self.section_action_index,
        )
        if target is None:
            self.status = f"line {self.section_line_index + 1} has nothing to open"
            return

        self._activate_actionable(plan, target.actionable, stdscr)

    def _activate_modal(self, plan: RenderPlan, stdscr: curses.window | None = None) -> None:
        modal = self._active_modal(plan)
        if modal is None:
            return
        target = _selected_actionable(
            _modal_line_actionables(modal, self.modal_line_index),
            self.modal_action_index,
        )
        if target is None:
            self.status = f"line {self.modal_line_index + 1} has nothing to open"
            return

        self._activate_actionable(plan, target.actionable, stdscr)

    def _activate_actionable(
        self,
        plan: RenderPlan,
        actionable: Button | Link | InputControl | SubmitControl,
        stdscr: curses.window | None = None,
    ) -> None:
        if isinstance(actionable, InputControl):
            self._begin_edit(actionable, stdscr)
            return
        if isinstance(actionable, SubmitControl):
            self._submit_form(plan, actionable, stdscr)
            return
        if isinstance(actionable, Button):
            if actionable.action == "ui.open_modal":
                modal_id = str(actionable.params.get("modal_id", "")).strip()
                if not modal_id:
                    self.status = "ui.open_modal requires modal_id"
                    return
                self._open_modal(plan, modal_id, stdscr)
                return
            try:
                self._run_with_loading(
                    stdscr,
                    lambda: self.app.dispatch_action(actionable.action, actionable.params)
                    if hasattr(self.app, "dispatch_action")
                    else self.app.backend.call(actionable.action, **actionable.params),
                    message="Running action",
                    plan=plan,
                )
            except RuntimeError as exc:
                self.status = str(exc)
                return
            self._invalidate_screen(reset_animation=True)
            self.status = f"ran {actionable.action}"
            return

        try:
            next_app = self.app.follow_link(actionable.href)
        except RuntimeError as exc:
            self.status = str(exc)
            return

        self.history.append(self.app)
        self.app = next_app
        self._invalidate_screen(reset_animation=True)
        self.mode = "page"
        self.show_help = False
        self._schedule_page_reset()
        self.pending_g = False
        self.form_values = {}
        self.edit_state = None
        self.active_modal_id = None
        self.modal_line_index = 0
        self.modal_scroll_offset = 0
        self.status = f"opened {actionable.href}"
        return

    def _begin_edit(self, target: InputControl, stdscr: curses.window | None = None) -> None:
        current_value = self.form_values.setdefault(target.form_key, {}).get(target.input_name, target.initial_value)
        self.form_values[target.form_key][target.input_name] = current_value
        if target.input_type == "ascii-art":
            if stdscr is None:
                self._set_editor_error("ascii-art inputs require an interactive terminal")
                return
            try:
                updated_value = _edit_external_text(stdscr, current_value, suffix=".ascii")
            except RuntimeError as exc:
                self._set_editor_error(str(exc))
                return
            self.form_values[target.form_key][target.input_name] = updated_value
            self.edit_state = None
            self.mode = "modal" if self.active_modal_id is not None else "section"
            self.show_help = False
            self.status = ""
            return
        self.edit_state = EditState(
            form_key=target.form_key,
            input_name=target.input_name,
            cursor_index=len(current_value),
            original_value=current_value,
        )
        self.mode = "edit"
        self.show_help = False
        self.status = ""

    def _handle_edit_key(self, key: int, stdscr: curses.window | None = None) -> None:
        if self.edit_state is None:
            self.mode = "modal" if self.active_modal_id is not None else "section"
            return

        value = self.form_values.setdefault(self.edit_state.form_key, {}).get(
            self.edit_state.input_name,
            self.edit_state.original_value,
        )
        cursor = min(max(self.edit_state.cursor_index, 0), len(value))

        if key == 27:
            self.form_values[self.edit_state.form_key][self.edit_state.input_name] = self.edit_state.original_value
            self.edit_state = None
            self.mode = "modal" if self.active_modal_id is not None else "section"
            self.status = ""
            return
        if key in {curses.KEY_ENTER, ord("\n"), ord("\r")}:
            self.form_values[self.edit_state.form_key][self.edit_state.input_name] = value
            previous_edit = self.edit_state
            self.edit_state = None
            self.mode = "modal" if self.active_modal_id is not None else "section"
            if self.active_modal_id is not None:
                if self._advance_modal_edit(previous_edit, stdscr):
                    self.status = ""
                    return
                self.modal_line_index += 1
                self.modal_action_index = 0
            else:
                if self._advance_section_edit(previous_edit, stdscr):
                    self.status = ""
                    return
                self.section_line_index += 1
                self.section_action_index = 0
            self.status = ""
            return
        if key == CTRL_W:
            new_cursor = _move_cursor_backward_word(value, cursor)
            value = value[:new_cursor] + value[cursor:]
            cursor = new_cursor
        elif key == ALT_B:
            cursor = _move_cursor_backward_word(value, cursor)
        elif key == ALT_F:
            cursor = _move_cursor_forward_word(value, cursor)
        elif key in {curses.KEY_BACKSPACE, 127, 8}:
            if cursor > 0:
                value = value[: cursor - 1] + value[cursor:]
                cursor -= 1
        elif key in {curses.KEY_LEFT}:
            cursor = max(cursor - 1, 0)
        elif key in {curses.KEY_RIGHT}:
            cursor = min(cursor + 1, len(value))
        elif key in {CTRL_A, curses.KEY_HOME}:
            cursor = 0
        elif key in {CTRL_E, curses.KEY_END}:
            cursor = len(value)
        elif 32 <= key <= 126:
            value = value[:cursor] + chr(key) + value[cursor:]
            cursor += 1
        else:
            return

        self.form_values[self.edit_state.form_key][self.edit_state.input_name] = value
        self.edit_state.cursor_index = cursor
        self.status = ""

    def _focus_first_modal_input(self, modal: ModalTarget, stdscr: curses.window | None = None) -> None:
        for line_index, action_index, target in _ordered_modal_actionables(modal):
            if not isinstance(target.actionable, InputControl):
                continue
            self.modal_line_index = line_index
            self.modal_action_index = action_index
            self._begin_edit(target.actionable, stdscr)
            return

    def _advance_modal_edit(self, previous_edit: EditState, stdscr: curses.window | None = None) -> bool:
        plan = self._navigation_plan_snapshot()
        modal = self._active_modal(plan) if plan is not None else None
        if modal is None:
            return False

        ordered = _ordered_modal_actionables(modal)
        current_index: int | None = None
        for index, (line_index, action_index, target) in enumerate(ordered):
            actionable = target.actionable
            if not isinstance(actionable, InputControl):
                continue
            if (
                actionable.form_key == previous_edit.form_key
                and actionable.input_name == previous_edit.input_name
                and line_index == self.modal_line_index
                and action_index == self.modal_action_index
            ):
                current_index = index
                break

        if current_index is None:
            return False

        for line_index, action_index, target in ordered[current_index + 1 :]:
            self.modal_line_index = line_index
            self.modal_action_index = action_index
            if isinstance(target.actionable, InputControl):
                self._begin_edit(target.actionable, stdscr)
            return True

        return False

    def _advance_section_edit(self, previous_edit: EditState, stdscr: curses.window | None = None) -> bool:
        plan = self._navigation_plan_snapshot()
        if plan is None or not plan.sections:
            return False

        section = plan.sections[min(self.section_index, len(plan.sections) - 1)]
        ordered = _ordered_section_actionables(section)
        current_index: int | None = None
        for index, (line_index, action_index, target) in enumerate(ordered):
            actionable = target.actionable
            if not isinstance(actionable, InputControl):
                continue
            if (
                actionable.form_key == previous_edit.form_key
                and actionable.input_name == previous_edit.input_name
                and line_index == self.section_line_index
                and action_index == self.section_action_index
            ):
                current_index = index
                break

        if current_index is None:
            return False

        for line_index, action_index, target in ordered[current_index + 1 :]:
            self.section_line_index = line_index
            self.section_action_index = action_index
            if isinstance(target.actionable, InputControl):
                self._begin_edit(target.actionable, stdscr)
            return True

        return False

    def _set_editor_error(self, message: str) -> None:
        if self.active_modal_id is not None:
            self.modal_messages[self.active_modal_id] = message
        else:
            self.status = message

    def _navigation_plan_snapshot(self) -> RenderPlan | None:
        if self._last_plan is not None:
            return self._last_plan
        screen = self._screen
        if screen is None:
            try:
                screen = self.app.build_screen()
            except RuntimeError:
                return None
        return build_render_plan(
            screen,
            form_values=self.form_values,
            edit_state=self.edit_state,
            modal_messages=self.modal_messages,
        )

    def _submit_form(self, plan: RenderPlan, target: SubmitControl, stdscr: curses.window | None = None) -> None:
        if not hasattr(self.app, "submit_form"):
            self.status = "forms are not supported for this app"
            return

        active_modal_id = self.active_modal_id
        values = dict(plan.form_defaults.get(target.form_key, {}))
        values.update(self.form_values.get(target.form_key, {}))
        missing_labels = [
            label
            for name, label in plan.form_requirements.get(target.form_key, {}).items()
            if not str(values.get(name, "")).strip()
        ]
        if missing_labels:
            message = "missing required fields: " + ", ".join(missing_labels)
            if active_modal_id is not None:
                self.modal_messages[active_modal_id] = message
            else:
                self.status = message
            return
        validation_error = _validate_form_values(plan, target.form_key, values)
        if validation_error:
            if active_modal_id is not None:
                self.modal_messages[active_modal_id] = validation_error
            else:
                self.status = validation_error
            return

        try:
            result = self._run_with_loading(
                stdscr,
                lambda: self.app.submit_form(target.action, values),
                message="Submitting form",
                plan=plan,
            )
        except (RuntimeError, LocalServerError) as exc:
            if active_modal_id is not None:
                self.modal_messages[active_modal_id] = str(exc)
            else:
                self.status = str(exc)
            return

        self.edit_state = None
        self.mode = "modal" if active_modal_id is not None else "section"
        self._invalidate_screen(reset_animation=True)

        if result.type == "redirect" and result.href:
            try:
                next_app = self.app.follow_link(result.href)
            except RuntimeError as exc:
                self.status = str(exc)
                return
            self.history.append(self.app)
            self.app = next_app
            self._invalidate_screen(reset_animation=True)
            if active_modal_id is not None:
                self.modal_messages.pop(active_modal_id, None)
                self.active_modal_id = None
                self.modal_line_index = 0
                self.modal_scroll_offset = 0
            self.mode = "page"
            self._schedule_page_reset(self.section_index)
            self.form_values = {}
            self.status = f"opened {result.href}"
            return

        if result.type == "error":
            message = result.message or "form submit failed"
            if active_modal_id is not None:
                self.modal_messages[active_modal_id] = message
            else:
                self.status = message
            return

        self.form_values.pop(target.form_key, None)
        if active_modal_id is not None:
            self.modal_messages.pop(active_modal_id, None)
            self._close_modal()
        self.status = f"submitted {target.action}"


def compute_scroll_offset(
    plan: RenderPlan,
    section_index: int,
    screen_height: int,
    terminal_width: int,
    current_offset: int = 0,
) -> int:
    if not plan.sections:
        return 0

    layout = _header_grid_layout(plan, _display_width(terminal_width))
    max_offset = max(len(plan.sections) - layout.visible_slots, 0)
    offset = min(max(current_offset, 0), max_offset)
    offset = _ensure_line_visible(section_index, offset, layout.visible_slots)
    return min(max(offset, 0), max_offset)


def compute_section_scroll_offset(
    section: SectionTarget,
    line_index: int,
    screen_height: int,
    current_offset: int = 0,
) -> int:
    viewport_height = _section_content_viewport_height(screen_height)
    max_offset = max(_section_content_line_count(section) - 1, 0)
    if viewport_height <= 0:
        return 0

    offset = min(max(current_offset, 0), max_offset)
    offset = _ensure_line_visible(line_index, offset, viewport_height)
    return min(max(offset, 0), max_offset)


def compute_modal_scroll_offset(
    modal: ModalTarget,
    line_index: int,
    screen_height: int,
    current_offset: int = 0,
) -> int:
    viewport_height = max(min(_viewport_height(screen_height) - 2, modal.block.height) - 2, 1)
    max_offset = max(_modal_content_line_count(modal) - 1, 0)
    if viewport_height <= 0:
        return 0

    offset = min(max(current_offset, 0), max_offset)
    offset = _ensure_line_visible(line_index, offset, viewport_height)
    return min(max(offset, 0), max_offset)


def align_section_top_offset(plan: RenderPlan, section_index: int, screen_height: int) -> int:
    viewport_height = _viewport_height(screen_height)
    max_offset = max(len(plan.lines) - 1, 0)
    if viewport_height <= 0 or not plan.sections:
        return 0

    section = plan.sections[min(section_index, len(plan.sections) - 1)]
    return min(max(section.y, 0), max_offset)


def _ensure_line_visible(line_y: int, offset: int, viewport_height: int) -> int:
    if line_y < offset:
        return line_y
    if line_y >= offset + viewport_height:
        return line_y - viewport_height + 1
    return offset


def _viewport_height(screen_height: int) -> int:
    return max(screen_height - 1, 1)


def _header_grid_layout(plan: RenderPlan, display_width: int) -> HeaderGridLayout:
    if not plan.sections:
        return HeaderGridLayout(cell_inner_width=1, cell_width=5, visible_slots=1)
    max_title = max(len(section.title) for section in plan.sections)
    cell_inner_width = min(max_title, max(display_width - 4, 1))
    cell_width = cell_inner_width + 4
    visible_slots = max((display_width + HEADER_CELL_GAP) // (cell_width + HEADER_CELL_GAP), 1)
    return HeaderGridLayout(
        cell_inner_width=cell_inner_width,
        cell_width=cell_width,
        visible_slots=visible_slots,
    )


def _header_cell_inner_width(layout: HeaderGridLayout, title: str) -> int:
    inner_width = layout.cell_inner_width
    title_width = min(len(title), inner_width + 2)
    if inner_width > title_width and (inner_width - title_width) % 2 == 1:
        return max(title_width, inner_width - 1)
    return inner_width


def _section_content_viewport_height(screen_height: int) -> int:
    header_height = HEADER_CELL_ROW_HEIGHT + 1
    section_borders = 2
    return max(_viewport_height(screen_height) - header_height - section_borders, 1)


def _display_width(terminal_width: int) -> int:
    return min(DISPLAY_WIDTH, terminal_width)


def _display_origin_x(terminal_width: int) -> int:
    return max((terminal_width - _display_width(terminal_width)) // 2, 0)


def _section_content_line_count(section: SectionTarget) -> int:
    return max(len(section.block.lines) - 2, 1)


def _section_line_actionables(section: SectionTarget, line_index: int) -> list[ActionableTarget]:
    return sorted(
        [item for item in section.block.actionables if item.y - 1 == line_index],
        key=lambda item: item.x,
    )


def _section_line_actionable(section: SectionTarget, line_index: int) -> ActionableTarget | None:
    matching = _section_line_actionables(section, line_index)
    if not matching:
        return None
    return matching[0]


def _ordered_section_actionables(section: SectionTarget) -> list[tuple[int, int, ActionableTarget]]:
    ordered: list[tuple[int, int, ActionableTarget]] = []
    for line_index in range(_section_content_line_count(section)):
        for action_index, target in enumerate(_section_line_actionables(section, line_index)):
            ordered.append((line_index, action_index, target))
    return ordered


def _modal_content_line_count(modal: ModalTarget) -> int:
    return max(len(modal.block.lines) - 2, 1)


def _modal_line_actionables(modal: ModalTarget, line_index: int) -> list[ActionableTarget]:
    return sorted(
        [item for item in modal.actionables if item.y - 1 == line_index],
        key=lambda item: item.x,
    )


def _modal_line_actionable(modal: ModalTarget, line_index: int) -> ActionableTarget | None:
    matching = _modal_line_actionables(modal, line_index)
    if not matching:
        return None
    return matching[0]


def _ordered_modal_actionables(modal: ModalTarget) -> list[tuple[int, int, ActionableTarget]]:
    ordered: list[tuple[int, int, ActionableTarget]] = []
    for line_index in range(_modal_content_line_count(modal)):
        for action_index, target in enumerate(_modal_line_actionables(modal, line_index)):
            ordered.append((line_index, action_index, target))
    return ordered


def _normalize_sections(children: list[Component]) -> list[Section]:
    sections: list[Section] = []
    loose: list[Component] = []

    for child in children:
        if isinstance(child, Modal):
            continue
        if isinstance(child, Section):
            if loose:
                sections.append(Section(title="Main", children=loose))
                loose = []
            sections.append(child)
        else:
            loose.append(child)

    if loose:
        sections.append(Section(title="Main", children=loose))
    return _ordered_sections(sections)


def _ordered_sections(sections: list[Section]) -> list[Section]:
    if not any(section.tab_order is not None for section in sections):
        return sections
    return [
        section
        for _, section in sorted(
            enumerate(sections),
            key=lambda item: (
                item[1].tab_order is None,
                item[1].tab_order if item[1].tab_order is not None else 0,
                item[0],
            ),
        )
    ]


def _default_section_index(sections: list[Section]) -> int:
    if not sections:
        return 0
    for index, section in enumerate(sections):
        if section.default_tab:
            return index
    return 0


def _collect_modals(children: list[Component]) -> list[Modal]:
    return [child for child in children if isinstance(child, Modal)]


def _build_block(
    component: Component,
    *,
    animation_time: float,
    max_width: int,
    render_state: RenderState,
    form_key: str | None = None,
    form_action: str | None = None,
) -> Block:
    if isinstance(component, Modal):
        raise TypeError("<Modal> may only appear at the screen root")
    if isinstance(component, Section):
        return _build_embedded_section_block(
            component,
            animation_time=animation_time,
            max_width=max_width,
            render_state=render_state,
        )
    if isinstance(component, Form):
        return _build_form_block(
            component,
            animation_time=animation_time,
            max_width=max_width,
            render_state=render_state,
        )
    if isinstance(component, Column):
        return _build_column_like(
            component.children,
            gap=component.gap,
            animation_time=animation_time,
            max_width=max_width,
            render_state=render_state,
            form_key=form_key,
            form_action=form_action,
        )
    if isinstance(component, Row):
        return _build_row(
            component,
            animation_time=animation_time,
            max_width=max_width,
            render_state=render_state,
            form_key=form_key,
            form_action=form_action,
        )
    if isinstance(component, ButtonRow):
        return _build_button_row(
            component,
            animation_time=animation_time,
            max_width=max_width,
            render_state=render_state,
            form_key=form_key,
            form_action=form_action,
        )
    if isinstance(component, Header):
        return _wrapped_text_block(component.content, style="header", max_width=max_width)
    if isinstance(component, AsciiArt):
        return _build_ascii_art_block(component, max_width=max_width)
    if isinstance(component, Text):
        return _wrapped_text_block(component.content, style="text", max_width=max_width)
    if isinstance(component, Link):
        display_label = _truncate_text(f"*{component.label}*", max_width)
        active_label = _truncate_text(f"-> *{component.label}*", max_width)
        block = _leaf_block(display_label, style="action")
        block.actionables.append(
            ActionableTarget(
                x=0,
                y=0,
                width=len(active_label),
                label_text=active_label,
                actionable=component,
            )
        )
        return block
    if isinstance(component, Input):
        if form_key is None:
            raise TypeError("<Input> requires an enclosing form")
        return _build_input_block(component, form_key=form_key, max_width=max_width, render_state=render_state)
    if isinstance(component, Button):
        label = _truncate_text(f"[ {component.label} ]", max_width)
        block = _leaf_block(label, style="action")
        block.actionables.append(
            ActionableTarget(
                x=0,
                y=0,
                width=len(label),
                label_text=label,
                actionable=component,
            )
        )
        return block
    if isinstance(component, SubmitButton):
        raise TypeError("<Submit> requires a <ButtonRow> inside <Form>")
    if isinstance(component, AsciiAnimation):
        return _build_animation_block(component, animation_time=animation_time, max_width=max_width)
    if isinstance(component, SplashAnimation):
        return _build_splash_animation_block(component, animation_time=animation_time, max_width=max_width)
    raise TypeError(f"unsupported component for layout: {type(component).__name__}")


def _build_section_block(section: Section, *, animation_time: float, render_state: RenderState) -> Block:
    body = _build_column_like(
        section.children,
        gap=1,
        animation_time=animation_time,
        max_width=TOP_LEVEL_SECTION_INNER_WIDTH,
        render_state=render_state,
    )
    return _build_bordered_section_block(
        section,
        body=body,
        fixed_inner_width=TOP_LEVEL_SECTION_INNER_WIDTH,
    )


def _build_embedded_section_block(
    section: Section,
    *,
    animation_time: float,
    max_width: int,
    render_state: RenderState,
) -> Block:
    nested_inner_width = max(max_width - 4, 1)
    body = _build_column_like(
        section.children,
        gap=1,
        animation_time=animation_time,
        max_width=nested_inner_width,
        render_state=render_state,
    )
    if not body.lines:
        return _build_bordered_section_block(section, fixed_inner_width=nested_inner_width)

    return _build_bordered_section_block(section, body=body, fixed_inner_width=nested_inner_width)


def _build_modal_block(
    modal: Modal,
    *,
    animation_time: float,
    render_state: RenderState,
    message: str = "",
) -> Block:
    children: list[Component] = list(modal.children)
    if _is_form_modal_children(children):
        if not _has_valid_form_modal_children(children):
            raise TypeError("<Modal> containing a <Form> may only contain that single <Form>")
        title = modal.title if not message else f"{modal.title}: {message}"
    else:
        title = modal.title
    if message and not _is_form_modal_children(children):
        children.insert(0, Text(content=message))
    body = _build_column_like(
        children,
        gap=1,
        animation_time=animation_time,
        max_width=INTERACTIVE_MODAL_INNER_WIDTH,
        render_state=render_state,
    )
    return _build_bordered_section_block(
        Section(title=title, children=[]),
        body=body,
        fixed_inner_width=INTERACTIVE_MODAL_INNER_WIDTH,
    )


def _is_form_modal_children(children: list[Component]) -> bool:
    return any(isinstance(child, Form) for child in children)


def _has_valid_form_modal_children(children: list[Component]) -> bool:
    return len(children) == 1 and isinstance(children[0], Form)


def _build_bordered_section_block(
    section: Section,
    body: Block | None = None,
    *,
    fixed_inner_width: int | None = None,
) -> Block:
    body = body or Block(width=0, height=0)
    max_inner_width = fixed_inner_width or TOP_LEVEL_SECTION_INNER_WIDTH
    title_text = _truncate_text(f"[ {section.title} ]", max_inner_width)
    if fixed_inner_width is None:
        inner_width = min(max(body.width, len(title_text)), max_inner_width)
    else:
        inner_width = fixed_inner_width
    width = inner_width + 4
    top_border = "+-" + title_text + "-" * max(inner_width + 1 - len(title_text), 0) + "+"
    bottom_border = "+" + "-" * (width - 2) + "+"
    lines: list[list[Segment]] = [[Segment(x=0, text=top_border, style="section_title")]]
    actionables: list[ActionableTarget] = []

    if body.lines:
        for segments in body.lines:
            line = [
                Segment(x=0, text="| ", style="section_border"),
                Segment(x=2, text=" " * inner_width, style="section_fill"),
                Segment(x=inner_width + 2, text=" |", style="section_border"),
            ]
            for segment in segments:
                line.append(
                    Segment(
                        x=segment.x + 2,
                        text=segment.text,
                        style=segment.style,
                    )
                )
            lines.append(line)
    else:
        lines.append(
            [
                Segment(x=0, text="| ", style="section_border"),
                Segment(x=2, text=" " * inner_width, style="section_fill"),
                Segment(x=inner_width + 2, text=" |", style="section_border"),
            ]
        )

    lines.append([Segment(x=0, text=bottom_border, style="section_border")])

    for item in body.actionables:
        actionables.append(
            ActionableTarget(
                x=item.x + 2,
                y=item.y + 1,
                width=item.width,
                label_text=item.label_text,
                actionable=item.actionable,
                action_group=item.action_group,
                action_align=item.action_align,
            )
        )

    return Block(
        width=width,
        height=len(lines),
        lines=lines,
        actionables=actionables,
        animation_interval_ms=body.animation_interval_ms,
    )


def _build_animation_block(animation: AsciiAnimation, *, animation_time: float, max_width: int) -> Block:
    block_width = min(max_width, TOP_LEVEL_SECTION_INNER_WIDTH)
    inner_width = max(block_width - 4, 1)
    title = _truncate_text(f"~ {animation.label} ~", inner_width)
    top_border = "+-" + title + "-" * max(inner_width + 1 - len(title), 0) + "+"
    bottom_border = "+" + "-" * (block_width - 2) + "+"

    frame = _select_animation_frame(animation, animation_time)
    frame_lines = frame.splitlines() or [""]
    clamped_lines = [_truncate_text(line, inner_width) for line in frame_lines]
    frame_width = max((len(line) for line in clamped_lines), default=0)
    frame_offset = max((inner_width - frame_width) // 2, 0)

    lines: list[list[Segment]] = [[Segment(x=0, text=top_border, style="animation_title")]]
    lines.append(_boxed_content_line(inner_width))

    for frame_line in clamped_lines:
        line = _boxed_content_line(inner_width)
        line.append(Segment(x=2 + frame_offset, text=frame_line, style="animation"))
        lines.append(line)

    lines.append(_boxed_content_line(inner_width))
    lines.append([Segment(x=0, text=bottom_border, style="section_border")])

    return Block(
        width=block_width,
        height=len(lines),
        lines=lines,
        animation_interval_ms=_animation_interval_for_fps(animation.fps),
    )


def _build_splash_animation_block(animation: SplashAnimation, *, animation_time: float, max_width: int) -> Block:
    frame = _select_animation_frame(animation, animation_time)
    frame_lines = frame.splitlines() or [""]
    clamped_lines = [_truncate_text(line, max_width) for line in frame_lines]
    return Block(
        width=max((len(line) for line in clamped_lines), default=0),
        height=len(clamped_lines),
        lines=[[Segment(x=0, text=line, style="animation")] for line in clamped_lines],
        animation_interval_ms=_animation_interval_for_fps(animation.fps),
    )


def _build_ascii_art_block(ascii_art: AsciiArt, *, max_width: int) -> Block:
    art_lines = ascii_art.content.split("\n") if ascii_art.content else [""]
    clamped_lines = [_truncate_text(line, max_width) for line in art_lines]
    return Block(
        width=max((len(line) for line in clamped_lines), default=0),
        height=len(clamped_lines),
        lines=[[Segment(x=0, text=line, style="text")] for line in clamped_lines],
    )


def _build_form_block(
    form: Form,
    *,
    animation_time: float,
    max_width: int,
    render_state: RenderState,
) -> Block:
    form_key = f"form:{render_state.next_form_index}"
    render_state.next_form_index += 1
    content_width = max(max_width - FORM_FIELD_INDENT, 8)
    field_children, action_children = _split_form_children(form.children)

    lines: list[list[Segment]] = []
    actionables: list[ActionableTarget] = []
    width = 0
    cursor_y = 0
    animation_interval_ms: int | None = None

    if field_children:
        body = _build_column_like(
            field_children,
            gap=0,
            animation_time=animation_time,
            max_width=content_width,
            render_state=render_state,
            form_key=form_key,
            form_action=form.action,
        )
        _merge_block(lines, actionables, body, x=FORM_FIELD_INDENT, y=cursor_y)
        width = max(width, FORM_FIELD_INDENT + body.width)
        animation_interval_ms = _merge_animation_interval(animation_interval_ms, body.animation_interval_ms)
        cursor_y += body.height

    if action_children:
        if cursor_y > 0:
            cursor_y += 1
            lines.append([])
        action_block = _build_column_like(
            action_children,
            gap=1,
            animation_time=animation_time,
            max_width=max_width,
            render_state=render_state,
            form_key=form_key,
            form_action=form.action,
        )
        _merge_block(lines, actionables, action_block, x=0, y=cursor_y)
        width = max(width, action_block.width)
        animation_interval_ms = _merge_animation_interval(animation_interval_ms, action_block.animation_interval_ms)
    else:
        submit_block = _build_form_submit_block(
            form,
            form_key=form_key,
            max_width=max_width,
            render_state=render_state,
        )
        if cursor_y > 0:
            cursor_y += 1
            lines.append([])
        _merge_block(lines, actionables, submit_block, x=0, y=cursor_y)
        width = max(width, submit_block.width)

    return Block(
        width=width,
        height=len(lines),
        lines=lines,
        actionables=actionables,
        animation_interval_ms=animation_interval_ms,
    )


def _build_input_block(
    input_component: Input,
    *,
    form_key: str,
    max_width: int,
    render_state: RenderState,
) -> Block:
    render_state.form_defaults.setdefault(form_key, {})[input_component.name] = input_component.value
    if input_component.type == "hidden":
        return Block(width=0, height=0, lines=[])
    label = input_component.label.strip() or _input_label(input_component.name)
    if input_component.required:
        render_state.form_requirements.setdefault(form_key, {})[input_component.name] = label
    if input_component.max_cols is not None:
        render_state.form_validations.setdefault(form_key, {})[input_component.name] = InputValidation(
            label=label,
            max_cols=input_component.max_cols,
        )
    current_value = _current_input_value(form_key, input_component, render_state.form_values)
    is_editing = (
        render_state.edit_state is not None
        and render_state.edit_state.form_key == form_key
        and render_state.edit_state.input_name == input_component.name
    )
    line_text, segments = _render_input_line(
        input_component,
        current_value=current_value,
        max_width=max_width,
        edit_state=render_state.edit_state if is_editing else None,
    )
    block = Block(width=len(line_text), height=1, lines=[segments])
    block.actionables.append(
        ActionableTarget(
            x=0,
            y=0,
            width=len(line_text),
            label_text=line_text,
            actionable=InputControl(
                form_key=form_key,
                input_name=input_component.name,
                input_type=input_component.type,
                initial_value=input_component.value,
            ),
        )
    )
    return block


def _build_form_submit_block(
    form: Form,
    *,
    form_key: str,
    max_width: int,
    render_state: RenderState,
) -> Block:
    return _build_button_row(
        ButtonRow(
            children=[SubmitButton(label=form.submit_button_text, action=form.action)],
        ),
        animation_time=0,
        max_width=max_width,
        render_state=render_state,
        form_key=form_key,
        form_action=form.action,
    )


def _split_form_children(children: list[Component]) -> tuple[list[Component], list[Component]]:
    field_children: list[Component] = []
    action_children: list[Component] = []
    for child in children:
        if _is_form_action_component(child):
            action_children.append(child)
        else:
            field_children.append(child)
    return field_children, action_children


def _is_form_action_component(child: Component) -> bool:
    return isinstance(child, ButtonRow) and all(isinstance(button, SubmitButton) for button in child.children)


def _build_column_like(
    children: list[Component],
    gap: int,
    *,
    animation_time: float,
    max_width: int,
    render_state: RenderState,
    form_key: str | None = None,
    form_action: str | None = None,
) -> Block:
    lines: list[list[Segment]] = []
    actionables: list[ActionableTarget] = []
    width = 0
    cursor_y = 0
    animation_interval_ms: int | None = None

    for index, child in enumerate(children):
        block = _build_block(
            child,
            animation_time=animation_time,
            max_width=max_width,
            render_state=render_state,
            form_key=form_key,
            form_action=form_action,
        )
        _merge_block(lines, actionables, block, x=0, y=cursor_y)
        width = max(width, block.width)
        animation_interval_ms = _merge_animation_interval(animation_interval_ms, block.animation_interval_ms)
        cursor_y += block.height
        if index != len(children) - 1:
            cursor_y += gap
            for _ in range(gap):
                lines.append([])

    return Block(
        width=width,
        height=len(lines),
        lines=lines,
        actionables=actionables,
        animation_interval_ms=animation_interval_ms,
    )


def _build_row(
    row: Row,
    *,
    animation_time: float,
    max_width: int,
    render_state: RenderState,
    form_key: str | None = None,
    form_action: str | None = None,
) -> Block:
    child_blocks = [
        _build_block(
            child,
            animation_time=animation_time,
            max_width=max_width,
            render_state=render_state,
            form_key=form_key,
            form_action=form_action,
        )
        for child in row.children
    ]
    width = 0
    height = max((block.height for block in child_blocks), default=0)
    lines = [[] for _ in range(height)]
    actionables: list[ActionableTarget] = []
    cursor_x = 0
    animation_interval_ms: int | None = None

    for index, block in enumerate(child_blocks):
        _merge_block(lines, actionables, block, x=cursor_x, y=0)
        cursor_x += block.width
        width = max(width, cursor_x)
        animation_interval_ms = _merge_animation_interval(animation_interval_ms, block.animation_interval_ms)
        if index != len(child_blocks) - 1:
            cursor_x += row.gap
            width = max(width, cursor_x)

    return Block(
        width=width,
        height=height,
        lines=lines,
        actionables=actionables,
        animation_interval_ms=animation_interval_ms,
    )


def _build_button_row(
    row: ButtonRow,
    *,
    animation_time: float,
    max_width: int,
    render_state: RenderState,
    form_key: str | None = None,
    form_action: str | None = None,
) -> Block:
    actionables: list[ActionableTarget] = []
    cursor_x = 0
    inner_width = max(max_width - 4, 1)
    width = inner_width + 4
    top_border = "+" + "-" * max(width - 2, 0) + "+"
    lines = [
        [Segment(x=0, text=top_border, style="section_border")],
        _boxed_content_line(inner_width),
        [Segment(x=0, text=top_border, style="section_border")],
    ]

    for index, child in enumerate(row.children):
        label = _truncate_text(f"[ {child.label} ]", inner_width)
        if isinstance(child, SubmitButton):
            if form_key is None:
                raise TypeError("<Submit> requires an enclosing form")
            submit_action = child.action or form_action or ""
            actionable: Button | Link | InputControl | SubmitControl = SubmitControl(
                form_key=form_key,
                action=submit_action,
            )
        else:
            actionable = child
        actionables.append(
            ActionableTarget(
                x=2 + cursor_x,
                y=1,
                width=len(label),
                label_text=label,
                actionable=actionable,
                action_group="button_row",
                action_align=row.align,
            )
        )
        cursor_x += len(label)
        if index != len(row.children) - 1:
            cursor_x += row.gap

    return Block(
        width=width,
        height=3,
        lines=lines,
        actionables=actionables,
    )


def _leaf_block(text: str, *, style: str) -> Block:
    return Block(width=len(text), height=1, lines=[[Segment(x=0, text=text, style=style)]])


def _wrapped_text_block(text: str, *, style: str, max_width: int) -> Block:
    lines = textwrap.wrap(text, width=max_width) or [""]
    return Block(
        width=max((len(line) for line in lines), default=0),
        height=len(lines),
        lines=[[Segment(x=0, text=line, style=style)] for line in lines],
    )


def _truncate_text(text: str, max_width: int) -> str:
    if len(text) <= max_width:
        return text
    if max_width <= 3:
        return text[:max_width]
    return text[: max_width - 3] + "..."


def _boxed_content_line(inner_width: int) -> list[Segment]:
    return [
        Segment(x=0, text="| ", style="section_border"),
        Segment(x=2, text=" " * inner_width, style="section_fill"),
        Segment(x=inner_width + 2, text=" |", style="section_border"),
    ]


def _current_input_value(form_key: str, input_component: Input, form_values: dict[str, dict[str, str]]) -> str:
    return form_values.get(form_key, {}).get(input_component.name, input_component.value)


def _validate_form_values(plan: RenderPlan, form_key: str, values: dict[str, str]) -> str | None:
    for name, validation in plan.form_validations.get(form_key, {}).items():
        value = str(values.get(name, ""))
        if validation.max_cols is not None:
            max_cols = max(_line_column_widths(value), default=0)
            if max_cols > validation.max_cols:
                return f"{validation.label} must stay within {validation.max_cols} columns."
    return None


def _line_column_widths(value: str) -> list[int]:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return [len(line.expandtabs(4)) for line in normalized.split("\n")]


def _render_input_line(
    input_component: Input,
    *,
    current_value: str,
    max_width: int,
    edit_state: EditState | None,
) -> tuple[str, list[Segment]]:
    label = (input_component.label.strip() or _input_label(input_component.name)).strip()
    if input_component.required:
        label = f"*{label}"
    label_text = _truncate_text(f"{label}:", min(max(max_width // 3, len(label) + 1), 18))
    prefix = f"{label_text} "
    field_width = max(max_width - len(prefix), 8)
    display_value = _input_display_value(input_component, current_value)

    plain_field = display_value

    if edit_state is None:
        field_text = _truncate_text(plain_field, field_width)
        padded_field = f"{field_text:<{field_width}}"
        line_text = f"{prefix}{padded_field}"
        return (
            line_text,
            [
                Segment(x=0, text=prefix, style="text"),
                Segment(x=len(prefix), text=padded_field, style="text"),
            ],
        )

    cursor_index = min(max(edit_state.cursor_index, 0), len(display_value))
    if len(display_value) <= field_width:
        window_start = 0
    else:
        max_start = max(len(display_value) - field_width, 0)
        window_start = min(max(cursor_index - field_width + 1, 0), max_start)
    visible_window = display_value[window_start : window_start + field_width]
    relative_cursor = max(min(cursor_index - window_start, field_width - 1), 0)
    padded_window = list(f"{visible_window:<{field_width}}")
    cursor_char = padded_window[relative_cursor]
    padded_window[relative_cursor] = ""
    before_cursor = "".join(padded_window[:relative_cursor])
    after_cursor = "".join(padded_window[relative_cursor + 1 :])
    plain_window = before_cursor + " " + after_cursor
    line_text = f"{prefix}{plain_window}"

    segments = [Segment(x=0, text=prefix, style="text")]
    cursor_x = len(prefix)
    if before_cursor:
        segments.append(Segment(x=cursor_x, text=before_cursor, style="text"))
        cursor_x += len(before_cursor)
    segments.append(Segment(x=cursor_x, text=cursor_char or " ", style="cursor"))
    cursor_x += 1
    if after_cursor:
        segments.append(Segment(x=cursor_x, text=after_cursor, style="text"))
    return line_text, segments


def _input_label(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").title()


def _input_display_value(input_component: Input, current_value: str) -> str:
    if input_component.type == "password":
        return "*" * len(current_value)
    if input_component.type == "ascii-art":
        return _ascii_art_input_summary(current_value)
    return current_value


def _ascii_art_input_summary(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not normalized:
        return "Open in editor"
    lines = normalized.split("\n")
    line_count = len(lines)
    max_columns = max((len(line) for line in lines), default=0)
    line_label = "line" if line_count == 1 else "lines"
    column_label = "col" if max_columns == 1 else "cols"
    return f"{line_count} {line_label}, {max_columns} {column_label}"


def _edit_external_text(
    stdscr: curses.window,
    initial_value: str,
    *,
    suffix: str = ".txt",
) -> str:
    editor_command = _resolve_editor_command()
    fd, raw_path = tempfile.mkstemp(prefix="erza-edit-", suffix=suffix)
    temp_path = Path(raw_path)
    os.close(fd)
    temp_path.write_text(initial_value, encoding="utf-8")

    try:
        try:
            curses.def_prog_mode()
        except curses.error:
            pass
        try:
            curses.endwin()
        except curses.error:
            pass

        try:
            result = subprocess.run([*editor_command, str(temp_path)], check=False)
        except OSError as exc:
            raise RuntimeError(f"failed to launch editor: {editor_command[0]}") from exc
        finally:
            try:
                curses.reset_prog_mode()
            except curses.error:
                pass
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            stdscr.keypad(True)
            stdscr.clear()
            stdscr.refresh()

        if result.returncode != 0:
            raise RuntimeError(f"editor exited with status {result.returncode}")

        return temp_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    finally:
        temp_path.unlink(missing_ok=True)


def _resolve_editor_command() -> list[str]:
    configured = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim"
    command = shlex.split(configured)
    if not command:
        return ["vim"]
    return command


def _select_animation_frame(animation: AsciiAnimation | SplashAnimation, animation_time: float) -> str:
    if len(animation.frames) == 1:
        return animation.frames[0]

    frame_index = int(animation_time * animation.fps)
    if animation.loop:
        frame_index %= len(animation.frames)
    else:
        frame_index = min(frame_index, len(animation.frames) - 1)
    return animation.frames[frame_index]


def _animation_interval_for_fps(fps: int) -> int:
    return max(int(1000 / fps), MIN_ANIMATION_INTERVAL_MS)


def _merge_animation_interval(current: int | None, candidate: int | None) -> int | None:
    if current is None:
        return candidate
    if candidate is None:
        return current
    return min(current, candidate)


def _merge_block(
    lines: list[list[Segment]],
    actionables: list[ActionableTarget],
    block: Block,
    *,
    x: int,
    y: int,
) -> None:
    while len(lines) < y + len(block.lines):
        lines.append([])

    for line_index, segments in enumerate(block.lines):
        destination = lines[y + line_index]
        for segment in segments:
            destination.append(
                Segment(
                    x=segment.x + x,
                    text=segment.text,
                    style=segment.style,
                )
            )

    for item in block.actionables:
        actionables.append(
            ActionableTarget(
                x=item.x + x,
                y=item.y + y,
                width=item.width,
                label_text=item.label_text,
                actionable=item.actionable,
                action_group=item.action_group,
                action_align=item.action_align,
            )
        )


def _selected_actionable(actionables: list[ActionableTarget], selected_index: int) -> ActionableTarget | None:
    if not actionables:
        return None
    return actionables[min(max(selected_index, 0), len(actionables) - 1)]


def _is_button_row_actionable_line(actionables: list[ActionableTarget]) -> bool:
    return bool(actionables) and all(item.action_group == "button_row" for item in actionables)


def _button_row_gap(actionables: list[ActionableTarget]) -> int:
    if len(actionables) <= 1:
        return 2
    gap = actionables[1].x - (actionables[0].x + actionables[0].width)
    return max(gap, 0)


def _button_row_visible_window(
    actionables: list[ActionableTarget],
    *,
    inner_width: int,
    selected_index: int,
) -> list[ActionableTarget]:
    if not actionables:
        return []

    selected_index = min(max(selected_index, 0), len(actionables) - 1)
    gap = _button_row_gap(actionables)
    best_start = selected_index
    best_end = selected_index
    best_score = (-1, -1, float("-inf"), float("-inf"))

    for start in range(selected_index, -1, -1):
        for end in range(start, len(actionables)):
            if not start <= selected_index <= end:
                continue
            total_width = actionables[end].x - actionables[start].x + actionables[end].width
            if total_width > inner_width and not (start == end == selected_index):
                break
            if total_width > inner_width:
                continue
            count = end - start + 1
            midpoint = (start + end) / 2
            center_distance = abs(midpoint - selected_index)
            score = (count, total_width, -center_distance, -start)
            if score > best_score:
                best_score = score
                best_start = start
                best_end = end

    if best_score[0] < 0:
        return [actionables[selected_index]]

    visible = actionables[best_start : best_end + 1]
    if len(visible) == 1:
        return visible

    # Collapse leading or trailing items if cumulative gap inflation would push the row past the viewport.
    while visible and (visible[-1].x - visible[0].x + visible[-1].width) > inner_width:
        if selected_index - best_start > best_end - selected_index:
            visible = visible[1:]
            best_start += 1
        else:
            visible = visible[:-1]
            best_end -= 1
    return visible


def _button_row_alignment_offset(align: str, inner_width: int, visible_width: int) -> int:
    clamped_width = min(visible_width, inner_width)
    if align == "left":
        return 0
    if align == "right":
        return max(inner_width - clamped_width, 0)
    return max((inner_width - clamped_width) // 2, 0)


def _draw_button_row_actionables(
    stdscr: curses.window,
    *,
    line_segments: list[Segment],
    line_actionables: list[ActionableTarget],
    selected_index: int,
    origin_x: int,
    screen_y: int,
    max_width: int,
    styles: dict[str, int],
    active: bool,
) -> None:
    if not _is_button_row_actionable_line(line_actionables):
        return

    inner_left, inner_width = _button_row_fill_bounds(line_segments, line_actionables, max_width=max_width)
    visible = _button_row_visible_window(
        line_actionables,
        inner_width=inner_width,
        selected_index=selected_index if active else 0,
    )
    if not visible:
        return

    visible_width = visible[-1].x - visible[0].x + visible[-1].width
    align = line_actionables[0].action_align or "center"
    align_offset = _button_row_alignment_offset(align, inner_width, visible_width)
    selected = _selected_actionable(line_actionables, selected_index) if active else None

    for item in visible:
        relative_x = item.x - visible[0].x
        screen_x = origin_x + inner_left + align_offset + relative_x
        available = max(inner_width - (align_offset + relative_x), 0)
        if available == 0:
            continue
        style = styles["action_active"] if active and item is selected else styles["action"]
        _safe_addnstr(
            stdscr,
            screen_y,
            screen_x,
            item.label_text,
            available,
            style,
        )


def _button_row_fill_bounds(
    line_segments: list[Segment],
    line_actionables: list[ActionableTarget],
    *,
    max_width: int,
) -> tuple[int, int]:
    if not line_actionables:
        return 4, max(max_width - 8, 1)

    packed_left = min(item.x for item in line_actionables)
    packed_right = max(item.x + item.width for item in line_actionables)
    candidates = [
        segment
        for segment in line_segments
        if segment.style == "section_fill"
        and segment.x <= packed_left
        and segment.x + len(segment.text) >= packed_right
    ]
    if not candidates:
        return 4, max(max_width - 8, 1)
    best = min(candidates, key=lambda segment: len(segment.text))
    return best.x, max(len(best.text), 1)


def _draw_active_actionable(
    stdscr: curses.window,
    *,
    line_actionables: list[ActionableTarget],
    selected_index: int,
    origin_x: int,
    screen_y: int,
    max_width: int,
    styles: dict[str, int],
) -> None:
    selected = _selected_actionable(line_actionables, selected_index)
    if selected is None or isinstance(selected.actionable, InputControl):
        return
    available = max(max_width - selected.x, 0)
    if available == 0:
        return
    _safe_addnstr(
        stdscr,
        screen_y,
        origin_x + selected.x,
        selected.label_text,
        available,
        styles["action_active"],
    )


def _safe_addnstr(
    stdscr: curses.window,
    y: int,
    x: int,
    text: str,
    max_length: int,
    style: int,
) -> None:
    try:
        stdscr.addnstr(y, x, text, max_length, style)
    except curses.error:
        pass


def _help_modal_lines(inner_width: int) -> list[str]:
    lines: list[str] = []
    for label, description in HELP_SHORTCUTS:
        wrapped = textwrap.wrap(description, width=max(inner_width - 16, 10)) or [description]
        for index, part in enumerate(wrapped):
            prefix = f"{label:<14} " if index == 0 else " " * 15
            lines.append(_truncate_text(prefix + part, inner_width))
    return lines


def _segment_style(
    styles: dict[str, int],
    style_name: str,
    *,
    active_content_line: bool = False,
) -> int:
    if style_name == "cursor":
        return styles["cursor"]
    return styles[style_name]


def _styles() -> dict[str, int]:
    return {
        "title": curses.A_BOLD,
        "section_title": curses.A_BOLD,
        "section_title_active": curses.A_REVERSE | curses.A_BOLD,
        "animation_title": curses.A_BOLD,
        "animation": curses.A_NORMAL,
        "section_border": curses.A_DIM,
        "section_fill": curses.A_NORMAL,
        "header": curses.A_BOLD,
        "text": curses.A_NORMAL,
        "action": curses.A_NORMAL,
        "action_active": curses.A_REVERSE,
        "cursor": curses.A_REVERSE | curses.A_BOLD,
        "selection_marker": curses.A_BOLD,
        "selection_marker_active": curses.A_REVERSE | curses.A_BOLD,
        "help": curses.A_DIM,
        "status": curses.A_DIM,
    }


def _infer_backend_path(source: Path) -> Path | None:
    inferred = source.resolve().with_name("backend.py")
    if inferred.exists():
        return inferred
    return None


def _app_location(app: ErzaApp | RemoteApp | StaticScreenApp) -> str:
    if isinstance(app, RemoteApp):
        return app.current_url
    if isinstance(app, ErzaApp):
        try:
            return str(app.current_source_path.relative_to(Path.cwd()))
        except ValueError:
            return str(app.current_source_path)
    return "<screen>"
