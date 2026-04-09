from __future__ import annotations

import curses
from dataclasses import dataclass, field
from pathlib import Path
import textwrap
import time

from erza.backend import BackendBridge, bind_request_context
from erza.local_server import LocalFormServer, LocalServerError, SubmitResult
from erza.model import AsciiAnimation, Button, Column, Component, Form, Header, Input, Link, Row, Screen, Section, Text
from erza.parser import compile_markup
from erza.remote import RemoteApp, is_remote_source, normalize_remote_url
from erza.source import SourceResolutionError, resolve_local_source_path, resolve_relative_source
from erza.template import render_template


CTRL_D = 4
CTRL_U = 21
DISPLAY_WIDTH = 79
TOP_LEVEL_SECTION_INNER_WIDTH = DISPLAY_WIDTH - 6
NESTED_SECTION_INNER_WIDTH = TOP_LEVEL_SECTION_INNER_WIDTH - 4
FORM_FIELD_INDENT = 4
MIN_ANIMATION_INTERVAL_MS = 50
HELP_MODAL_MAX_WIDTH = 67
HEADER_CELL_GAP = 2
HEADER_CELL_ROW_HEIGHT = 3
HELP_SHORTCUTS = [
    ("Header h / k", "Move to the previous section header."),
    ("Header j / l", "Move to the next section header."),
    ("Enter", "Focus the current section body."),
    ("Header gg / G", "Jump to the first or last section."),
    ("Backspace", "Go back one page."),
    ("Section j / k", "Move line by line inside the current section."),
    ("Section Ctrl+D / Ctrl+U", "Move by half a page."),
    ("Section Enter", "Edit the current input or open the current link/action."),
    ("Edit type", "Insert text into the current input."),
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
    form_defaults: dict[str, dict[str, str]] = field(default_factory=dict)
    form_requirements: dict[str, dict[str, str]] = field(default_factory=dict)
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
) -> RenderPlan:
    sections = _normalize_sections(screen.children)
    render_state = RenderState(form_values=form_values or {}, edit_state=edit_state)
    lines = [
        [Segment(x=0, text=screen.title, style="title")],
        [],
    ]
    section_targets: list[SectionTarget] = []
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

    return RenderPlan(
        title=screen.title,
        lines=lines,
        sections=section_targets,
        form_defaults=render_state.form_defaults,
        form_requirements=render_state.form_requirements,
        animation_interval_ms=animation_interval_ms,
    )


def next_section_index(plan: RenderPlan, current_index: int, delta: int) -> int:
    if not plan.sections:
        return 0
    return min(max(current_index + delta, 0), len(plan.sections) - 1)


def next_section_line_index(section: SectionTarget, current_index: int, delta: int) -> int:
    line_count = _section_content_line_count(section)
    if line_count <= 0:
        return 0
    return min(max(current_index + delta, 0), line_count - 1)


def draw_plan(
    stdscr: curses.window,
    plan: RenderPlan,
    section_index: int | None,
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
        section_index if section_index is not None else 0,
        scroll_offset,
        visible_height,
        display_width,
        origin_x,
        styles,
    )
    active_section = plan.sections[section_index if section_index is not None else 0]
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


def draw_section_page(
    stdscr: curses.window,
    plan: RenderPlan,
    section: SectionTarget,
    section_index: int,
    header_scroll_offset: int,
    line_index: int,
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
    items_in_row = section_end - section_start
    row_width = items_in_row * layout.cell_width + max(items_in_row - 1, 0) * HEADER_CELL_GAP
    row_origin_x = origin_x + max((display_width - row_width) // 2, 0)

    for slot, section_pos in enumerate(range(section_start, section_end)):
        x = row_origin_x + slot * (layout.cell_width + HEADER_CELL_GAP)
        _draw_header_cell(
            stdscr,
            x=x,
            y=start_y,
            title=plan.sections[section_pos].title,
            inner_width=layout.cell_inner_width,
            active=section_pos == section_index,
            styles=styles,
        )

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
    title_text = _truncate_text(title, inner_width).center(inner_width)
    border = "+" + "-" * (inner_width + 2) + "+"
    border_style = styles["section_border"]
    fill_style = styles["section_fill"] | curses.A_REVERSE if active else styles["section_fill"]
    title_style = styles["section_title_active"] if active else styles["section_title"]

    _safe_addnstr(stdscr, y, x, border, len(border), border_style)
    _safe_addnstr(stdscr, y + 1, x, "| ", 2, border_style)
    _safe_addnstr(stdscr, y + 1, x + 2, " " * inner_width, inner_width, fill_style)
    _safe_addnstr(stdscr, y + 1, x + 2, title_text, len(title_text), title_style)
    _safe_addnstr(stdscr, y + 1, x + 2 + len(title_text), " |", 2, border_style)
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
        if active_content_line:
            _safe_addnstr(stdscr, screen_y, max(block_x - 1, 0), ">", 1, styles["selection_marker"])


class _RuntimeSession:
    def __init__(self, app: ErzaApp | RemoteApp | StaticScreenApp) -> None:
        self.app = app
        self.history: list[ErzaApp | RemoteApp | StaticScreenApp] = []
        self._screen: Screen | None = None
        self.mode = "page"
        self.show_help = False
        self.section_index = 0
        self.scroll_offset = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.form_values: dict[str, dict[str, str]] = {}
        self.edit_state: EditState | None = None
        self.pending_g = False
        self.animation_epoch = time.monotonic()
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
        stdscr.keypad(True)

        while True:
            screen = self._current_screen()
            animation_time = time.monotonic() - self.animation_epoch
            plan = build_render_plan(
                screen,
                animation_time=animation_time,
                form_values=self.form_values,
                edit_state=self.edit_state,
            )
            self._sync_state(plan)
            footer = self._footer_text(plan)
            if self.mode in {"section", "edit"} and plan.sections:
                self._sync_section_scroll(plan, stdscr.getmaxyx()[0])
                draw_section_page(
                    stdscr,
                    plan,
                    plan.sections[self.section_index],
                    self.section_index,
                    self.scroll_offset,
                    self.section_line_index,
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
                    self.scroll_offset,
                    footer,
                )
            if self.show_help:
                draw_shortcuts_modal(stdscr, footer=footer)

            stdscr.timeout(plan.animation_interval_ms if plan.animation_interval_ms is not None else -1)
            key = stdscr.getch()
            if key == -1:
                continue
            if self.mode == "edit":
                self.pending_g = False
                self._handle_edit_key(key)
                continue
            if key == ord("q"):
                return
            if self.show_help:
                if key in {ord("?"), 27}:
                    self.show_help = False
                continue
            if key in {curses.KEY_BACKSPACE, 127, 8}:
                self._go_back()
                continue
            if key == ord("?"):
                self.show_help = True
                self.pending_g = False
                continue
            if key == 27:
                if self.mode == "section":
                    self._exit_section_mode()
                continue
            if key == ord("g"):
                if self.pending_g:
                    if self.mode == "section":
                        self._jump_to_first_line(plan)
                    else:
                        self._jump_to_first_section(plan)
                else:
                    self.pending_g = True
                continue
            if key == ord("G"):
                self.pending_g = False
                if self.mode == "section":
                    self._jump_to_last_line(plan)
                else:
                    self._jump_to_last_section(plan)
                continue

            self.pending_g = False
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
                    self._enter_section_mode(plan)
                    continue
            if key in {ord("j"), curses.KEY_DOWN}:
                if self.mode == "section":
                    self._move_section_line(plan, 1)
                continue
            if key in {ord("k"), curses.KEY_UP}:
                if self.mode == "section":
                    self._move_section_line(plan, -1)
                continue
            if key == CTRL_D and self.mode == "section":
                self._scroll_section_half_page(plan, stdscr.getmaxyx()[0], 1)
                continue
            if key == CTRL_U and self.mode == "section":
                self._scroll_section_half_page(plan, stdscr.getmaxyx()[0], -1)
                continue
            if key in {curses.KEY_ENTER, ord("\n"), ord("\r")} and self.mode == "section":
                self._activate(plan)
                continue

    def _current_screen(self) -> Screen:
        if self._screen is None:
            self._screen = self.app.build_screen()
        return self._screen

    def _invalidate_screen(self, *, reset_animation: bool = False) -> None:
        self._screen = None
        if reset_animation:
            self.animation_epoch = time.monotonic()

    def _sync_state(self, plan: RenderPlan) -> None:
        if not plan.sections:
            self.mode = "page"
            self.section_index = 0
            self.scroll_offset = 0
            self.section_line_index = 0
            self.section_scroll_offset = 0
            self.edit_state = None
            return

        self.section_index = min(self.section_index, len(plan.sections) - 1)
        active_section = plan.sections[self.section_index]
        self.section_line_index = min(
            self.section_line_index,
            max(_section_content_line_count(active_section) - 1, 0),
        )
        if self.mode == "edit":
            active_target = _section_line_actionable(active_section, self.section_line_index)
            if not isinstance(active_target.actionable, InputControl):
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

    def _move_section(self, plan: RenderPlan, delta: int) -> None:
        if not plan.sections:
            return
        next_index = next_section_index(plan, self.section_index, delta)
        if next_index == self.section_index:
            return
        self.section_index = next_index
        self.section_line_index = 0
        self.section_scroll_offset = 0
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
        self.status = ""

    def _move_section_line(self, plan: RenderPlan, delta: int) -> None:
        if not plan.sections:
            return
        self.section_line_index = next_section_line_index(
            plan.sections[self.section_index],
            self.section_line_index,
            delta,
        )
        self.status = ""

    def _jump_to_first_section(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        self.section_index = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.status = ""

    def _jump_to_last_section(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        self.section_index = len(plan.sections) - 1
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.status = ""

    def _jump_to_first_line(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        self.section_line_index = 0
        self.status = ""

    def _jump_to_last_line(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        self.section_line_index = max(_section_content_line_count(plan.sections[self.section_index]) - 1, 0)
        self.status = ""

    def _scroll_section_half_page(self, plan: RenderPlan, screen_height: int, direction: int) -> None:
        if not plan.sections:
            return
        section = plan.sections[self.section_index]
        content_height = _section_content_viewport_height(screen_height)
        step = max(content_height // 2, 1)
        self.section_line_index = next_section_line_index(section, self.section_line_index, direction * step)
        self.status = ""

    def _enter_section_mode(self, plan: RenderPlan) -> None:
        if not plan.sections:
            self.status = "page has no sections"
            return
        self.mode = "section"
        self.show_help = False
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.status = ""

    def _exit_section_mode(self) -> None:
        self.mode = "page"
        self.show_help = False
        self.section_scroll_offset = 0
        self.edit_state = None
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
        self.scroll_offset = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.form_values = {}
        self.edit_state = None
        self.pending_g = False
        self.status = "went back"

    def _footer_text(self, plan: RenderPlan) -> str:
        location = _app_location(self.app)
        if self.mode in {"section", "edit"} and plan.sections:
            location = f"{location} -> {plan.sections[self.section_index].title}"
        if self.status:
            return f"{location} | {self.status}"
        return location

    def _activate(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        section = plan.sections[self.section_index]
        target = _section_line_actionable(section, self.section_line_index)
        if target is None:
            self.status = f"line {self.section_line_index + 1} has nothing to open"
            return

        actionable = target.actionable
        if isinstance(actionable, InputControl):
            self._begin_edit(plan, actionable)
            return
        if isinstance(actionable, SubmitControl):
            self._submit_form(plan, actionable)
            return
        if isinstance(actionable, Button):
            if hasattr(self.app, "dispatch_action"):
                self.app.dispatch_action(actionable.action, actionable.params)
            else:
                self.app.backend.call(actionable.action, **actionable.params)
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
        self.section_index = 0
        self.scroll_offset = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.pending_g = False
        self.form_values = {}
        self.edit_state = None
        self.status = f"opened {actionable.href}"

    def _begin_edit(self, plan: RenderPlan, target: InputControl) -> None:
        current_value = self.form_values.setdefault(target.form_key, {}).get(target.input_name, target.initial_value)
        self.form_values[target.form_key][target.input_name] = current_value
        self.edit_state = EditState(
            form_key=target.form_key,
            input_name=target.input_name,
            cursor_index=len(current_value),
            original_value=current_value,
        )
        self.mode = "edit"
        self.show_help = False
        self.status = ""

    def _handle_edit_key(self, key: int) -> None:
        if self.edit_state is None:
            self.mode = "section"
            return

        value = self.form_values.setdefault(self.edit_state.form_key, {}).get(
            self.edit_state.input_name,
            self.edit_state.original_value,
        )
        cursor = min(max(self.edit_state.cursor_index, 0), len(value))

        if key == 27:
            self.form_values[self.edit_state.form_key][self.edit_state.input_name] = self.edit_state.original_value
            self.edit_state = None
            self.mode = "section"
            self.status = ""
            return
        if key in {curses.KEY_ENTER, ord("\n"), ord("\r")}:
            self.form_values[self.edit_state.form_key][self.edit_state.input_name] = value
            self.edit_state = None
            self.mode = "section"
            self.status = ""
            return
        if key in {curses.KEY_BACKSPACE, 127, 8}:
            if cursor > 0:
                value = value[: cursor - 1] + value[cursor:]
                cursor -= 1
        elif key in {curses.KEY_LEFT}:
            cursor = max(cursor - 1, 0)
        elif key in {curses.KEY_RIGHT}:
            cursor = min(cursor + 1, len(value))
        elif key in {curses.KEY_HOME}:
            cursor = 0
        elif key in {curses.KEY_END}:
            cursor = len(value)
        elif 32 <= key <= 126:
            value = value[:cursor] + chr(key) + value[cursor:]
            cursor += 1
        else:
            return

        self.form_values[self.edit_state.form_key][self.edit_state.input_name] = value
        self.edit_state.cursor_index = cursor
        self.status = ""

    def _submit_form(self, plan: RenderPlan, target: SubmitControl) -> None:
        if not hasattr(self.app, "submit_form"):
            self.status = "forms are not supported for this app"
            return

        values = dict(plan.form_defaults.get(target.form_key, {}))
        values.update(self.form_values.get(target.form_key, {}))
        missing_labels = [
            label
            for name, label in plan.form_requirements.get(target.form_key, {}).items()
            if not str(values.get(name, "")).strip()
        ]
        if missing_labels:
            self.status = "missing required fields: " + ", ".join(missing_labels)
            return

        try:
            result = self.app.submit_form(target.action, values)
        except (RuntimeError, LocalServerError) as exc:
            self.status = str(exc)
            return

        self.edit_state = None
        self.mode = "section"
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
            self.mode = "page"
            self.section_index = 0
            self.scroll_offset = 0
            self.section_line_index = 0
            self.section_scroll_offset = 0
            self.form_values = {}
            self.status = f"opened {result.href}"
            return

        if result.type == "error":
            self.status = result.message or "form submit failed"
            return

        self.form_values.pop(target.form_key, None)
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


def _section_content_viewport_height(screen_height: int) -> int:
    return max(_viewport_height(screen_height) - 2, 1)


def _display_width(terminal_width: int) -> int:
    return min(DISPLAY_WIDTH, terminal_width)


def _display_origin_x(terminal_width: int) -> int:
    return max((terminal_width - _display_width(terminal_width)) // 2, 0)


def _section_content_line_count(section: SectionTarget) -> int:
    return max(len(section.block.lines) - 2, 1)


def _section_line_actionable(section: SectionTarget, line_index: int) -> ActionableTarget | None:
    matching = [item for item in section.block.actionables if item.y - 1 == line_index]
    if not matching:
        return None
    return min(matching, key=lambda item: item.x)


def _normalize_sections(children: list[Component]) -> list[Section]:
    sections: list[Section] = []
    loose: list[Component] = []

    for child in children:
        if isinstance(child, Section):
            if loose:
                sections.append(Section(title="Main", children=loose))
                loose = []
            sections.append(child)
        else:
            loose.append(child)

    if loose:
        sections.append(Section(title="Main", children=loose))
    return sections


def _build_block(
    component: Component,
    *,
    animation_time: float,
    max_width: int,
    render_state: RenderState,
    form_key: str | None = None,
) -> Block:
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
        )
    if isinstance(component, Row):
        return _build_row(
            component,
            animation_time=animation_time,
            max_width=max_width,
            render_state=render_state,
            form_key=form_key,
        )
    if isinstance(component, Header):
        return _wrapped_text_block(component.content, style="header", max_width=max_width)
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
    if isinstance(component, AsciiAnimation):
        return _build_animation_block(component, animation_time=animation_time, max_width=max_width)
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

    lines: list[list[Segment]] = []
    actionables: list[ActionableTarget] = []
    width = 0
    cursor_y = 0
    animation_interval_ms: int | None = None

    if form.children:
        body = _build_column_like(
            form.children,
            gap=0,
            animation_time=animation_time,
            max_width=content_width,
            render_state=render_state,
            form_key=form_key,
        )
        _merge_block(lines, actionables, body, x=FORM_FIELD_INDENT, y=cursor_y)
        width = max(width, FORM_FIELD_INDENT + body.width)
        animation_interval_ms = _merge_animation_interval(animation_interval_ms, body.animation_interval_ms)
        cursor_y += body.height

    submit_block = _build_form_submit_block(form, form_key=form_key, max_width=max_width)
    submit_x = max(max_width - submit_block.width, 0)
    _merge_block(lines, actionables, submit_block, x=submit_x, y=cursor_y)
    width = max(width, submit_x + submit_block.width)

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
    if input_component.required:
        render_state.form_requirements.setdefault(form_key, {})[input_component.name] = (
            input_component.label.strip() or _input_label(input_component.name)
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


def _build_form_submit_block(form: Form, *, form_key: str, max_width: int) -> Block:
    label = _truncate_text(f"[ {form.submit_button_text} ]", max_width)
    block = _leaf_block(label, style="action")
    block.actionables.append(
        ActionableTarget(
            x=0,
            y=0,
            width=len(label),
            label_text=label,
            actionable=SubmitControl(form_key=form_key, action=form.action),
        )
    )
    return block


def _build_column_like(
    children: list[Component],
    gap: int,
    *,
    animation_time: float,
    max_width: int,
    render_state: RenderState,
    form_key: str | None = None,
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
) -> Block:
    child_blocks = [
        _build_block(
            child,
            animation_time=animation_time,
            max_width=max_width,
            render_state=render_state,
            form_key=form_key,
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


def _render_input_line(
    input_component: Input,
    *,
    current_value: str,
    max_width: int,
    edit_state: EditState | None,
) -> tuple[str, list[Segment]]:
    label = (input_component.label.strip() or _input_label(input_component.name)).strip()
    if input_component.required:
        label = f"* {label}"
    label_text = _truncate_text(f"{label}:", min(max(max_width // 3, len(label) + 1), 18))
    prefix = f"{label_text} "
    field_width = max(max_width - len(prefix), 8)
    display_value = "*" * len(current_value) if input_component.type == "password" else current_value

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
    segments.append(Segment(x=cursor_x, text="█", style="cursor"))
    cursor_x += 1
    if after_cursor:
        segments.append(Segment(x=cursor_x, text=after_cursor, style="text"))
    return line_text, segments


def _input_label(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").title()


def _select_animation_frame(animation: AsciiAnimation, animation_time: float) -> str:
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
            )
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
        "cursor": curses.A_BOLD,
        "selection_marker": curses.A_BOLD,
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
