from __future__ import annotations

import curses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from erza.backend import BackendBridge
from erza.model import Button, Column, Component, Header, Row, Screen, Text
from erza.parser import compile_markup
from erza.template import render_template


Direction = Literal["left", "right", "up", "down"]


@dataclass(slots=True)
class Segment:
    x: int
    text: str
    style: str


@dataclass(slots=True)
class FocusTarget:
    x: int
    y: int
    width: int
    height: int
    label_text: str
    button: Button

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)


@dataclass(slots=True)
class Block:
    width: int
    height: int
    lines: list[list[Segment]] = field(default_factory=list)
    focusables: list[FocusTarget] = field(default_factory=list)


@dataclass(slots=True)
class RenderPlan:
    title: str
    lines: list[list[Segment]]
    focusables: list[FocusTarget]


class ErzaApp:
    def __init__(self, source_path: str | Path, backend: BackendBridge | None = None) -> None:
        self.source_path = Path(source_path).resolve()
        self.source = self.source_path.read_text(encoding="utf-8")
        self.backend = backend or BackendBridge.empty()

    def build_screen(self) -> Screen:
        markup = render_template(self.source, backend=self.backend)
        return compile_markup(markup)


def run_curses_app(app: ErzaApp) -> None:
    session = _RuntimeSession(app)
    curses.wrapper(session.run)


def build_render_plan(screen: Screen) -> RenderPlan:
    body = _build_column_like(screen.children, gap=0)
    lines = [
        [Segment(x=0, text=screen.title, style="title")],
        [],
    ]

    focusables = []
    for focusable in body.focusables:
        focusables.append(
            FocusTarget(
                x=focusable.x,
                y=focusable.y + 2,
                width=focusable.width,
                height=focusable.height,
                label_text=focusable.label_text,
                button=focusable.button,
            )
        )

    lines.extend(body.lines)
    lines.append([])
    lines.append(
        [Segment(x=0, text="hjkl move  enter press  arrows supported  q quit", style="help")]
    )
    return RenderPlan(title=screen.title, lines=lines, focusables=focusables)


def move_focus(plan: RenderPlan, current_index: int, direction: Direction) -> int:
    if not plan.focusables:
        return 0

    current = plan.focusables[current_index]
    current_x, current_y = current.center
    candidates: list[tuple[float, float, int]] = []

    for index, candidate in enumerate(plan.focusables):
        if index == current_index:
            continue
        candidate_x, candidate_y = candidate.center
        delta_x = candidate_x - current_x
        delta_y = candidate_y - current_y

        if direction == "left" and delta_x < 0:
            candidates.append((abs(delta_x), abs(delta_y), index))
        elif direction == "right" and delta_x > 0:
            candidates.append((abs(delta_x), abs(delta_y), index))
        elif direction == "up" and delta_y < 0:
            candidates.append((abs(delta_y), abs(delta_x), index))
        elif direction == "down" and delta_y > 0:
            candidates.append((abs(delta_y), abs(delta_x), index))

    if not candidates:
        return current_index

    candidates.sort()
    return candidates[0][2]


def draw_plan(
    stdscr: curses.window,
    plan: RenderPlan,
    focus_index: int | None,
    status: str = "",
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    styles = _styles()

    for y, line in enumerate(plan.lines):
        if y >= height:
            break
        for segment in line:
            if segment.x >= width:
                continue
            available = max(width - segment.x, 0)
            if available == 0:
                continue
            _safe_addnstr(
                stdscr,
                y,
                segment.x,
                segment.text,
                available,
                styles[segment.style],
            )

    if focus_index is not None and plan.focusables:
        focus = plan.focusables[focus_index]
        if 0 <= focus.y < height and focus.x < width:
            available = max(width - focus.x, 0)
            if available > 0:
                _safe_addnstr(
                    stdscr,
                    focus.y,
                    focus.x,
                    focus.label_text,
                    available,
                    styles["button_focus"],
                )

    if status and height > 0:
        _safe_addnstr(
            stdscr,
            height - 1,
            0,
            status,
            width,
            styles["status"],
        )

    stdscr.refresh()


class _RuntimeSession:
    def __init__(self, app: ErzaApp) -> None:
        self.app = app
        self.focus_index = 0
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
            screen = self.app.build_screen()
            plan = build_render_plan(screen)
            if plan.focusables:
                self.focus_index = min(self.focus_index, len(plan.focusables) - 1)
            else:
                self.focus_index = 0
            draw_plan(
                stdscr,
                plan,
                self.focus_index if plan.focusables else None,
                self.status,
            )

            key = stdscr.getch()
            if key in {ord("q"), 27}:
                return
            if key in {ord("h"), curses.KEY_LEFT}:
                self.focus_index = move_focus(plan, self.focus_index, "left")
                continue
            if key in {ord("l"), curses.KEY_RIGHT}:
                self.focus_index = move_focus(plan, self.focus_index, "right")
                continue
            if key in {ord("k"), curses.KEY_UP}:
                self.focus_index = move_focus(plan, self.focus_index, "up")
                continue
            if key in {ord("j"), curses.KEY_DOWN}:
                self.focus_index = move_focus(plan, self.focus_index, "down")
                continue
            if key in {ord("\n"), ord(" ")} and plan.focusables:
                target = plan.focusables[self.focus_index]
                self.app.backend.call(target.button.action, **target.button.params)
                self.status = f"ran {target.button.action}"


def _build_block(component: Component) -> Block:
    if isinstance(component, Column):
        return _build_column_like(component.children, gap=component.gap)
    if isinstance(component, Row):
        return _build_row(component)
    if isinstance(component, Header):
        return _leaf_block(component.content, style="header")
    if isinstance(component, Text):
        return _leaf_block(component.content, style="text")
    if isinstance(component, Button):
        label = f"[ {component.label} ]"
        block = _leaf_block(label, style="button")
        block.focusables.append(
            FocusTarget(
                x=0,
                y=0,
                width=len(label),
                height=1,
                label_text=label,
                button=component,
            )
        )
        return block
    raise TypeError(f"unsupported component for layout: {type(component).__name__}")


def _build_column_like(children: list[Component], gap: int) -> Block:
    lines: list[list[Segment]] = []
    focusables: list[FocusTarget] = []
    width = 0
    cursor_y = 0

    for index, child in enumerate(children):
        block = _build_block(child)
        _merge_block(lines, focusables, block, x=0, y=cursor_y)
        width = max(width, block.width)
        cursor_y += block.height
        if index != len(children) - 1:
            cursor_y += gap
            for _ in range(gap):
                lines.append([])

    return Block(width=width, height=len(lines), lines=lines, focusables=focusables)


def _build_row(row: Row) -> Block:
    child_blocks = [_build_block(child) for child in row.children]
    width = 0
    height = max((block.height for block in child_blocks), default=0)
    lines = [[] for _ in range(height)]
    focusables: list[FocusTarget] = []
    cursor_x = 0

    for index, block in enumerate(child_blocks):
        _merge_block(lines, focusables, block, x=cursor_x, y=0)
        cursor_x += block.width
        width = max(width, cursor_x)
        if index != len(child_blocks) - 1:
            cursor_x += row.gap
            width = max(width, cursor_x)

    return Block(width=width, height=height, lines=lines, focusables=focusables)


def _leaf_block(text: str, *, style: str) -> Block:
    return Block(width=len(text), height=1, lines=[[Segment(x=0, text=text, style=style)]])


def _merge_block(
    lines: list[list[Segment]],
    focusables: list[FocusTarget],
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

    for focusable in block.focusables:
        focusables.append(
            FocusTarget(
                x=focusable.x + x,
                y=focusable.y + y,
                width=focusable.width,
                height=focusable.height,
                label_text=focusable.label_text,
                button=focusable.button,
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


def _styles() -> dict[str, int]:
    return {
        "title": curses.A_BOLD,
        "header": curses.A_BOLD,
        "text": curses.A_NORMAL,
        "button": curses.A_NORMAL,
        "button_focus": curses.A_REVERSE,
        "help": curses.A_DIM,
        "status": curses.A_DIM,
    }
