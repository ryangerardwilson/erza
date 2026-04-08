from __future__ import annotations

import curses
from dataclasses import dataclass, field
from pathlib import Path
import textwrap
import time

from erza.backend import BackendBridge
from erza.model import AsciiAnimation, Button, Column, Component, Header, Link, Row, Screen, Section, Text
from erza.parser import compile_markup
from erza.remote import RemoteApp, is_remote_source, normalize_remote_url
from erza.source import SourceResolutionError, resolve_local_source_path, resolve_relative_source
from erza.template import render_template


CTRL_J = 10
CTRL_K = 11
DISPLAY_WIDTH = 79
TOP_LEVEL_SECTION_INNER_WIDTH = DISPLAY_WIDTH - 4
NESTED_SECTION_INNER_WIDTH = TOP_LEVEL_SECTION_INNER_WIDTH - 4
MIN_ANIMATION_INTERVAL_MS = 50


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
    actionable: Button | Link


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
    animation_interval_ms: int | None = None


class ErzaApp:
    def __init__(
        self,
        source_path: str | Path,
        backend: BackendBridge | None = None,
        backend_path: Path | None = None,
    ) -> None:
        self.current_source_path = resolve_local_source_path(Path(source_path))
        self.explicit_backend_path = backend_path.resolve() if backend_path else None
        self.backend_path = self.explicit_backend_path or _infer_backend_path(self.current_source_path)
        if backend is not None:
            self.backend = backend
        elif self.backend_path is not None:
            self.backend = BackendBridge.from_module_path(self.backend_path)
        else:
            self.backend = BackendBridge.empty()

    def build_screen(self) -> Screen:
        source = self.current_source_path.read_text(encoding="utf-8")
        markup = render_template(source, backend=self.backend)
        return compile_markup(markup)

    def follow_link(self, href: str) -> "ErzaApp | RemoteApp":
        if is_remote_source(href) or href.startswith(("http://", "https://")):
            return RemoteApp(normalize_remote_url(href))

        try:
            target = resolve_relative_source(self.current_source_path, href)
        except SourceResolutionError as exc:
            raise RuntimeError(str(exc)) from exc

        target_backend_path = self.explicit_backend_path or _infer_backend_path(target)
        if target_backend_path is not None and self.backend_path == target_backend_path:
            backend = self.backend
        elif target_backend_path is not None:
            backend = BackendBridge.from_module_path(target_backend_path)
        else:
            backend = BackendBridge.empty()

        return ErzaApp(target, backend=backend, backend_path=self.explicit_backend_path)


class StaticScreenApp:
    def __init__(self, screen: Screen) -> None:
        self.screen = screen
        self.backend = BackendBridge.empty()

    def build_screen(self) -> Screen:
        return self.screen

    def follow_link(self, href: str) -> "ErzaApp | RemoteApp":
        raise RuntimeError(f"static screen cannot follow link: {href}")


def run_curses_app(app: ErzaApp | RemoteApp | StaticScreenApp) -> None:
    session = _RuntimeSession(app)
    curses.wrapper(session.run)


def build_render_plan(screen: Screen, *, animation_time: float = 0.0) -> RenderPlan:
    sections = _normalize_sections(screen.children)
    lines = [
        [Segment(x=0, text=screen.title, style="title")],
        [],
    ]
    section_targets: list[SectionTarget] = []
    cursor_y = 2
    animation_interval_ms: int | None = None

    for index, section in enumerate(sections):
        block = _build_section_block(section, animation_time=animation_time)
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
    status: str = "",
) -> None:
    stdscr.erase()
    height, terminal_width = stdscr.getmaxyx()
    visible_height = _viewport_height(height)
    display_width = _display_width(terminal_width)
    origin_x = _display_origin_x(terminal_width)
    styles = _styles()

    for source_y, line in enumerate(plan.lines):
        if source_y < scroll_offset:
            continue
        y = source_y - scroll_offset
        if y >= visible_height:
            break
        for segment in line:
            if segment.x >= display_width:
                continue
            available = max(display_width - segment.x, 0)
            if available == 0:
                continue
            _safe_addnstr(
                stdscr,
                y,
                origin_x + segment.x,
                segment.text,
                available,
                styles[segment.style],
            )

    if section_index is not None and plan.sections:
        active_section = plan.sections[section_index]
        active_section_y = active_section.y - scroll_offset
        if 0 <= active_section_y < visible_height:
            _safe_addnstr(
                stdscr,
                active_section_y,
                origin_x + active_section.x,
                active_section.title_text,
                max(display_width - active_section.x, 0),
                styles["section_title_active"],
            )

    if status and height > 0:
        _safe_addnstr(
            stdscr,
            height - 1,
            origin_x,
            status,
            display_width,
            styles["status"],
        )

    stdscr.refresh()


def draw_section_modal(
    stdscr: curses.window,
    section: SectionTarget,
    line_index: int,
    scroll_offset: int,
    status: str = "",
) -> None:
    stdscr.erase()
    height, terminal_width = stdscr.getmaxyx()
    visible_height = _viewport_height(height)
    display_width = _display_width(terminal_width)
    origin_x = _display_origin_x(terminal_width)
    styles = _styles()

    modal_width = min(section.block.width, display_width)
    modal_x = origin_x + max((display_width - modal_width) // 2, 0)
    content_lines = section.block.lines[1:-1] or [[]]

    if visible_height >= section.block.height:
        top_y = max((visible_height - section.block.height) // 2, 0)
        visible_lines = section.block.lines
        active_modal_y = 1 + line_index if 0 <= line_index < len(content_lines) else None
    else:
        if visible_height <= 1:
            visible_lines = [section.block.lines[0]]
            active_modal_y = None
        elif visible_height == 2:
            visible_lines = [section.block.lines[0], section.block.lines[-1]]
            active_modal_y = None
        else:
            content_viewport_height = visible_height - 2
            visible_lines = [
                section.block.lines[0],
                *content_lines[scroll_offset : scroll_offset + content_viewport_height],
                section.block.lines[-1],
            ]
            active_modal_y = (
                1 + line_index - scroll_offset
                if scroll_offset <= line_index < scroll_offset + content_viewport_height
                else None
            )
        top_y = 0

    for modal_y, line in enumerate(visible_lines):
        screen_y = top_y + modal_y
        if screen_y >= visible_height:
            break
        active_content_line = active_modal_y == modal_y
        for segment in line:
            if segment.x >= modal_width:
                continue
            available = max(modal_width - segment.x, 0)
            if available == 0:
                continue
            _safe_addnstr(
                stdscr,
                screen_y,
                modal_x + segment.x,
                segment.text,
                available,
                _segment_style(styles, segment.style, active_content_line=active_content_line),
            )

    active_item = _section_line_actionable(section, line_index)
    if active_item is not None and active_modal_y is not None:
        screen_y = top_y + active_modal_y
        if 0 <= screen_y < visible_height:
            _safe_addnstr(
                stdscr,
                screen_y,
                modal_x + active_item.x,
                active_item.label_text,
                max(modal_width - active_item.x, 0),
                styles["action_active"],
            )

    if status and height > 0:
        _safe_addnstr(
            stdscr,
            height - 1,
            origin_x,
            status,
            display_width,
            styles["status"],
        )

    stdscr.refresh()


class _RuntimeSession:
    def __init__(self, app: ErzaApp | RemoteApp | StaticScreenApp) -> None:
        self.app = app
        self.history: list[ErzaApp | RemoteApp | StaticScreenApp] = []
        self._screen: Screen | None = None
        self.mode = "page"
        self.section_index = 0
        self.scroll_offset = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.snap_section_to_top = False
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
            plan = build_render_plan(screen, animation_time=animation_time)
            self._sync_state(plan)
            if self.mode == "section" and plan.sections:
                self._sync_section_scroll(plan, stdscr.getmaxyx()[0])
                draw_section_modal(
                    stdscr,
                    plan.sections[self.section_index],
                    self.section_line_index,
                    self.section_scroll_offset,
                    self.status,
                )
            else:
                self._sync_page_scroll(plan, stdscr.getmaxyx()[0])
                draw_plan(
                    stdscr,
                    plan,
                    self.section_index if plan.sections else None,
                    self.scroll_offset,
                    self.status,
                )

            stdscr.timeout(plan.animation_interval_ms if plan.animation_interval_ms is not None else -1)
            key = stdscr.getch()
            if key in {ord("q"), 27}:
                return
            if key == -1:
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
            if key in {ord("j"), curses.KEY_DOWN}:
                if self.mode == "section":
                    self._move_section_line(plan, 1)
                else:
                    self._move_section(plan, 1)
                continue
            if key in {ord("k"), curses.KEY_UP}:
                if self.mode == "section":
                    self._move_section_line(plan, -1)
                else:
                    self._move_section(plan, -1)
                continue
            if key == CTRL_J and self.mode == "section":
                self._scroll_section_half_page(plan, stdscr.getmaxyx()[0], 1)
                continue
            if key == CTRL_K and self.mode == "section":
                self._scroll_section_half_page(plan, stdscr.getmaxyx()[0], -1)
                continue
            if key in {ord("h"), curses.KEY_LEFT}:
                if self.mode == "section":
                    self._exit_section_mode()
                else:
                    self._go_back()
                continue
            if key in {ord("l"), curses.KEY_RIGHT}:
                if self.mode == "section":
                    self._activate(plan)
                else:
                    self._enter_section_mode(plan)
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
            return

        self.section_index = min(self.section_index, len(plan.sections) - 1)
        active_section = plan.sections[self.section_index]
        self.section_line_index = min(
            self.section_line_index,
            max(_section_content_line_count(active_section) - 1, 0),
        )

    def _sync_page_scroll(self, plan: RenderPlan, screen_height: int) -> None:
        if self.snap_section_to_top:
            self.scroll_offset = align_section_top_offset(plan, self.section_index, screen_height)
            self.snap_section_to_top = False
            return
        self.scroll_offset = compute_scroll_offset(
            plan,
            self.section_index,
            screen_height,
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
        self.snap_section_to_top = True
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
        self.snap_section_to_top = True
        self.status = ""

    def _jump_to_last_section(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        self.section_index = len(plan.sections) - 1
        self.snap_section_to_top = True
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
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.status = ""

    def _exit_section_mode(self) -> None:
        self.mode = "page"
        self.section_scroll_offset = 0
        self.status = ""

    def _go_back(self) -> None:
        if not self.history:
            self.status = "no previous page"
            return
        self.app = self.history.pop()
        self._invalidate_screen(reset_animation=True)
        self.mode = "page"
        self.section_index = 0
        self.scroll_offset = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.snap_section_to_top = False
        self.pending_g = False
        self.status = "went back"

    def _activate(self, plan: RenderPlan) -> None:
        if not plan.sections:
            return
        section = plan.sections[self.section_index]
        target = _section_line_actionable(section, self.section_line_index)
        if target is None:
            self.status = f"line {self.section_line_index + 1} has nothing to open"
            return

        actionable = target.actionable
        if isinstance(actionable, Button):
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
        self.section_index = 0
        self.scroll_offset = 0
        self.section_line_index = 0
        self.section_scroll_offset = 0
        self.snap_section_to_top = False
        self.pending_g = False
        self.status = f"opened {actionable.href}"


def compute_scroll_offset(
    plan: RenderPlan,
    section_index: int,
    screen_height: int,
    current_offset: int = 0,
) -> int:
    viewport_height = _viewport_height(screen_height)
    max_offset = max(len(plan.lines) - 1, 0)
    if viewport_height <= 0 or not plan.sections:
        return 0

    offset = min(max(current_offset, 0), max_offset)
    section = plan.sections[min(section_index, len(plan.sections) - 1)]

    offset = _ensure_line_visible(section.y, offset, viewport_height)

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


def _build_block(component: Component, *, animation_time: float, max_width: int) -> Block:
    if isinstance(component, Section):
        return _build_embedded_section_block(component, animation_time=animation_time, max_width=max_width)
    if isinstance(component, Column):
        return _build_column_like(
            component.children,
            gap=component.gap,
            animation_time=animation_time,
            max_width=max_width,
        )
    if isinstance(component, Row):
        return _build_row(component, animation_time=animation_time, max_width=max_width)
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


def _build_section_block(section: Section, *, animation_time: float) -> Block:
    body = _build_column_like(
        section.children,
        gap=1,
        animation_time=animation_time,
        max_width=TOP_LEVEL_SECTION_INNER_WIDTH,
    )
    return _build_bordered_section_block(
        section,
        body=body,
        fixed_inner_width=TOP_LEVEL_SECTION_INNER_WIDTH,
    )


def _build_embedded_section_block(section: Section, *, animation_time: float, max_width: int) -> Block:
    nested_inner_width = max(max_width - 4, 1)
    body = _build_column_like(
        section.children,
        gap=1,
        animation_time=animation_time,
        max_width=nested_inner_width,
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


def _build_column_like(children: list[Component], gap: int, *, animation_time: float, max_width: int) -> Block:
    lines: list[list[Segment]] = []
    actionables: list[ActionableTarget] = []
    width = 0
    cursor_y = 0
    animation_interval_ms: int | None = None

    for index, child in enumerate(children):
        block = _build_block(child, animation_time=animation_time, max_width=max_width)
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


def _build_row(row: Row, *, animation_time: float, max_width: int) -> Block:
    child_blocks = [_build_block(child, animation_time=animation_time, max_width=max_width) for child in row.children]
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


def _segment_style(
    styles: dict[str, int],
    style_name: str,
    *,
    active_content_line: bool = False,
) -> int:
    style = styles[style_name]
    if active_content_line and style_name not in {"section_border", "section_title", "animation_title"}:
        return style | curses.A_REVERSE
    return style


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
        "help": curses.A_DIM,
        "status": curses.A_DIM,
    }


def _infer_backend_path(source: Path) -> Path | None:
    inferred = source.resolve().with_name("backend.py")
    if inferred.exists():
        return inferred
    return None
