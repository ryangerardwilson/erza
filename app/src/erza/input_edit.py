from __future__ import annotations

from dataclasses import dataclass
import curses


CTRL_A = 1
CTRL_B = 2
CTRL_D = 4
CTRL_E = 5
CTRL_F = 6
CTRL_H = 8
CTRL_K = 11
CTRL_U = 21
CTRL_W = 23
ALT_B = -1001
ALT_F = -1002
INPUT_ESCAPE_SEQUENCE_TIMEOUT_MS = 25


@dataclass(slots=True)
class InputEditResult:
    value: str
    cursor: int
    handled: bool


def decode_input_escape_key(stdscr: curses.window, key: int, *, timeout_ms: int = INPUT_ESCAPE_SEQUENCE_TIMEOUT_MS) -> int:
    if key != 27:
        return key
    try:
        stdscr.timeout(timeout_ms)
        next_key = stdscr.getch()
    except curses.error:
        next_key = -1
    finally:
        try:
            stdscr.timeout(-1)
        except curses.error:
            pass
    if next_key in {ord("b"), ord("B")}:
        return ALT_B
    if next_key in {ord("f"), ord("F")}:
        return ALT_F
    return key


def apply_input_edit_key(value: str, cursor: int, key: int) -> InputEditResult:
    cursor = clamp_input_cursor(value, cursor)

    if key == CTRL_W:
        new_cursor = move_input_cursor_backward_word(value, cursor)
        return InputEditResult(value=value[:new_cursor] + value[cursor:], cursor=new_cursor, handled=True)
    if key == CTRL_U:
        return InputEditResult(value="", cursor=0, handled=True)
    if key == CTRL_K:
        return InputEditResult(value=value[:cursor], cursor=cursor, handled=True)
    if key in {curses.KEY_BACKSPACE, 127, CTRL_H}:
        if cursor <= 0:
            return InputEditResult(value=value, cursor=cursor, handled=True)
        return InputEditResult(value=value[: cursor - 1] + value[cursor:], cursor=cursor - 1, handled=True)
    if key == CTRL_D:
        if cursor >= len(value):
            return InputEditResult(value=value, cursor=cursor, handled=True)
        return InputEditResult(value=value[:cursor] + value[cursor + 1 :], cursor=cursor, handled=True)
    if key in {CTRL_A, curses.KEY_HOME}:
        return InputEditResult(value=value, cursor=0, handled=True)
    if key in {CTRL_E, curses.KEY_END}:
        return InputEditResult(value=value, cursor=len(value), handled=True)
    if key in {CTRL_B, curses.KEY_LEFT}:
        return InputEditResult(value=value, cursor=max(cursor - 1, 0), handled=True)
    if key in {CTRL_F, curses.KEY_RIGHT}:
        return InputEditResult(value=value, cursor=min(cursor + 1, len(value)), handled=True)
    if key == ALT_B:
        return InputEditResult(value=value, cursor=move_input_cursor_backward_word(value, cursor), handled=True)
    if key == ALT_F:
        return InputEditResult(value=value, cursor=move_input_cursor_forward_word(value, cursor), handled=True)
    if 32 <= key <= 126:
        inserted = chr(key)
        return InputEditResult(
            value=value[:cursor] + inserted + value[cursor:],
            cursor=cursor + len(inserted),
            handled=True,
        )
    return InputEditResult(value=value, cursor=cursor, handled=False)


def clamp_input_cursor(value: str, cursor: int) -> int:
    return min(max(cursor, 0), len(value))


def move_input_cursor_backward_word(value: str, cursor: int) -> int:
    cursor = clamp_input_cursor(value, cursor)
    while cursor > 0 and value[cursor - 1].isspace():
        cursor -= 1
    while cursor > 0 and not value[cursor - 1].isspace():
        cursor -= 1
    return cursor


def move_input_cursor_forward_word(value: str, cursor: int) -> int:
    cursor = clamp_input_cursor(value, cursor)
    while cursor < len(value) and value[cursor].isspace():
        cursor += 1
    while cursor < len(value) and not value[cursor].isspace():
        cursor += 1
    return cursor


def single_line_input_view(value: str, cursor: int, width: int, *, prompt: str = "") -> tuple[str, int]:
    width = max(1, width)
    if width <= len(prompt):
        return prompt[:width], min(width - 1, len(prompt))
    field_width = max(1, width - len(prompt))
    cursor = clamp_input_cursor(value, cursor)
    max_start = max(len(value) - field_width, 0)
    if len(value) <= field_width:
        start = 0
    elif cursor >= field_width:
        start = min(cursor - field_width + 1, max_start)
    else:
        start = 0
    visible = value[start : start + field_width]
    text = prompt + visible
    cursor_col = len(prompt) + cursor - start
    return text[:width], min(max(cursor_col, 0), width - 1)
