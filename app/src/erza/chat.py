from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import curses
import mimetypes
import os
import shlex
import shutil
import subprocess
import threading
import textwrap
import time
from typing import Any

from erza.input_edit import (
    ALT_B,
    ALT_F,
    CTRL_A,
    CTRL_B,
    CTRL_D,
    CTRL_E,
    CTRL_F,
    CTRL_H,
    CTRL_K,
    CTRL_U,
    CTRL_W,
    INPUT_ESCAPE_SEQUENCE_TIMEOUT_MS,
    apply_input_edit_key,
    clamp_input_cursor,
    decode_input_escape_key,
    move_input_cursor_backward_word,
    move_input_cursor_forward_word,
    single_line_input_view,
)
from erza.runtime import draw_loading_overlay


CTRL_N = 14
CTRL_P = 16
FILE_MODAL_HEIGHT = 7
HELP_MODAL_MAX_WIDTH = 67
LATEST_MESSAGE_CURSOR = -1
CHAT_LOADING_DISPLAY_DELAY_SECONDS = 0.12
CHAT_LOADING_FRAME_INTERVAL_MS = 90

CHAT_SHORTCUTS = [
    ("convos j / k", "Move down / up across conversations."),
    ("convos l", "Open the selected conversation."),
    ("normal i", "Enter insert mode."),
    ("insert esc", "Return to normal mode and focus the latest message."),
    ("insert ctrl+a/e", "Move to start / end of the composer."),
    ("insert ctrl+b/f", "Move backward / forward by character."),
    ("insert alt+b/f", "Move backward / forward by word."),
    ("insert ctrl+w/h", "Delete previous word / character."),
    ("insert ctrl+d/k/u", "Delete next char / to end / full line."),
    ("normal j / k", "Move line by line."),
    ("normal ctrl+n/p", "Move next / previous message."),
    ("normal g / G", "Jump first / latest message."),
    ("normal l", "Open files for the focused file button."),
    ("modal j / k", "Move inside the file picker."),
    ("modal l", "Open the selected file."),
    ("h", "Back or close modal."),
    ("r", "Refresh."),
    ("?", "Toggle shortcuts."),
    ("q", "Quit."),
]


@dataclass(slots=True)
class ChatFile:
    name: str
    file_id: str = ""
    kind: str = "file"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatEmbed:
    title: str = "Embed"
    url: str = ""
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatMessage:
    message_id: str
    sender: str
    date: str
    text: str = ""
    files: list[ChatFile] = field(default_factory=list)
    embeds: list[ChatEmbed] = field(default_factory=list)
    unread: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatConversation:
    conversation_id: str
    label: str
    date: str = ""
    kind: str = "dm"
    unread: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatCallbacks:
    load_conversations: Callable[[], list[ChatConversation]]
    load_messages: Callable[[ChatConversation], list[ChatMessage]]
    send_message: Callable[[ChatConversation, str], Any] | None = None
    mark_read: Callable[[ChatConversation, list[ChatMessage]], Any] | None = None
    open_file: Callable[[ChatConversation, ChatMessage, ChatFile], str | None] | None = None


@dataclass(slots=True)
class RenderedChatRow:
    text: str
    kind: str = "text"
    message_index: int | None = None
    file_index: int | None = None
    message_start: bool = False


@dataclass(slots=True)
class ChatModalState:
    kind: str
    message_index: int
    file_index: int = 0
    scroll: int = 0


@dataclass(slots=True)
class ChatRuntimeState:
    title: str
    callbacks: ChatCallbacks
    mode: str = "conversations"
    conversations: list[ChatConversation] = field(default_factory=list)
    conversation_index: int = 0
    conversation_scroll: int = 0
    messages: list[ChatMessage] = field(default_factory=list)
    message_scroll: int = 0
    message_view_height: int = 1
    rendered_rows: list[RenderedChatRow] = field(default_factory=list)
    cursor_row: int = 0
    input_active: bool = False
    stick_bottom: bool = True
    composer: str = ""
    composer_cursor: int = 0
    modal: ChatModalState | None = None
    show_help: bool = False
    status: str = "loading..."


def run_chat_app(callbacks: ChatCallbacks, *, title: str = "erza chat") -> None:
    curses.wrapper(_run_chat_app, callbacks, title)


def _run_chat_app(stdscr: curses.window, callbacks: ChatCallbacks, title: str) -> None:
    _setup_curses(stdscr)
    state = ChatRuntimeState(title=title, callbacks=callbacks)
    _refresh_conversations(state, stdscr)
    while True:
        _draw(stdscr, state)
        key = stdscr.getch()
        key = _decode_insert_key(stdscr, state, key)
        if _handle_key(stdscr, state, key):
            return


def _decode_insert_key(stdscr: curses.window, state: ChatRuntimeState, key: int) -> int:
    if key != 27 or state.mode != "chat" or not state.input_active:
        return key
    return decode_input_escape_key(stdscr, key, timeout_ms=INPUT_ESCAPE_SEQUENCE_TIMEOUT_MS)


def _handle_key(stdscr: curses.window, state: ChatRuntimeState, key: int) -> bool:
    if state.show_help:
        if key in (ord("?"), 27, ord("h")):
            state.show_help = False
            return False
        return key == ord("q")
    if key == ord("?"):
        state.show_help = True
        return False
    if state.modal is not None:
        return _handle_modal_key(stdscr, state, key)
    if state.mode == "conversations":
        return _handle_conversations_key(stdscr, state, key)
    return _handle_chat_key(stdscr, state, key)


def _handle_modal_key(stdscr: curses.window, state: ChatRuntimeState, key: int) -> bool:
    if key in (ord("q"),):
        return True
    if key in (27, ord("h")):
        state.modal = None
        return False
    if key in (ord("j"), curses.KEY_DOWN):
        _move_modal_file(state, 1)
        return False
    if key in (ord("k"), curses.KEY_UP):
        _move_modal_file(state, -1)
        return False
    if key in (ord("l"), curses.KEY_ENTER, ord("\n"), ord("\r")):
        _open_selected_modal_file(stdscr, state)
        return False
    return False


def _handle_conversations_key(stdscr: curses.window, state: ChatRuntimeState, key: int) -> bool:
    if key in (ord("q"), 27):
        return True
    if key == ord("r"):
        _refresh_conversations(state, stdscr)
        return False
    if key == ord("g"):
        state.conversation_index = 0
        return False
    if key == ord("G"):
        state.conversation_index = max(0, len(state.conversations) - 1)
        return False
    if key in (ord("j"), curses.KEY_DOWN):
        state.conversation_index = min(max(0, len(state.conversations) - 1), state.conversation_index + 1)
        return False
    if key in (ord("k"), curses.KEY_UP):
        state.conversation_index = max(0, state.conversation_index - 1)
        return False
    if key in (ord("l"), curses.KEY_ENTER, ord("\n"), ord("\r")):
        _open_selected_conversation(state, stdscr)
        return False
    return False


def _handle_chat_key(stdscr: curses.window, state: ChatRuntimeState, key: int) -> bool:
    if state.input_active:
        if key == 27:
            state.input_active = False
            state.stick_bottom = False
            focus_latest_message(state)
            return False
        if key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
            if state.composer.strip():
                _send_composer(state, stdscr)
            return False
        result = apply_input_edit_key(state.composer, state.composer_cursor, key)
        if result.handled:
            state.composer = result.value
            state.composer_cursor = result.cursor
        return False

    if key == ord("q"):
        return True
    if key == ord("h"):
        state.mode = "conversations"
        state.status = f"{len(state.conversations)} conversations"
        return False
    if key == ord("i"):
        state.input_active = True
        state.stick_bottom = True
        return False
    if key == ord("r"):
        _refresh_messages(state, stdscr)
        return False
    if key in (ord("j"), curses.KEY_DOWN):
        move_cursor_row(state, 1)
        return False
    if key in (ord("k"), curses.KEY_UP):
        move_cursor_row(state, -1)
        return False
    if key == CTRL_N:
        move_message_row(state, 1)
        return False
    if key == CTRL_P:
        move_message_row(state, -1)
        return False
    if key == ord("G"):
        focus_latest_message(state)
        state.stick_bottom = False
        return False
    if key == ord("g"):
        first = first_message_row_index(state.rendered_rows)
        state.cursor_row = first if first is not None else 0
        state.stick_bottom = False
        return False
    if key == ord("l"):
        _open_file_modal_for_selected_row(state)
        return False
    return False


def _refresh_conversations(state: ChatRuntimeState, stdscr: curses.window | None = None) -> None:
    state.status = "loading..."
    state.conversations = list(
        _run_with_loading(
            stdscr,
            state,
            lambda: list(state.callbacks.load_conversations()),
            message="Loading conversations",
        )
    )
    state.conversation_index = min(state.conversation_index, max(0, len(state.conversations) - 1))
    state.status = f"{len(state.conversations)} conversations"


def _refresh_messages(state: ChatRuntimeState, stdscr: curses.window | None = None) -> None:
    conversation = selected_conversation(state)
    if conversation is None:
        state.messages = []
        state.status = "no conversation"
        return
    state.status = "loading..."
    state.messages = list(
        _run_with_loading(
            stdscr,
            state,
            lambda: list(state.callbacks.load_messages(conversation)),
            message="Loading messages",
        )
    )
    state.status = f"{len(state.messages)} messages"


def _open_selected_conversation(state: ChatRuntimeState, stdscr: curses.window | None = None) -> None:
    conversation = selected_conversation(state)
    if conversation is None:
        state.status = "no conversations"
        return
    state.mode = "chat"
    state.input_active = False
    state.stick_bottom = False
    state.message_scroll = 0
    state.cursor_row = LATEST_MESSAGE_CURSOR
    _refresh_messages(state, stdscr)
    focus_latest_message(state)
    if state.callbacks.mark_read is not None:
        _run_with_loading(
            stdscr,
            state,
            lambda: state.callbacks.mark_read(conversation, state.messages),
            message="Marking read",
        )
    conversation.unread = False


def _send_composer(state: ChatRuntimeState, stdscr: curses.window | None = None) -> None:
    conversation = selected_conversation(state)
    if conversation is None:
        state.status = "no conversation"
        return
    if state.callbacks.send_message is None:
        state.status = "send unavailable"
        return
    text = state.composer.strip()
    if not text:
        return
    state.status = "sending..."
    _run_with_loading(
        stdscr,
        state,
        lambda: state.callbacks.send_message(conversation, text),
        message="Sending message",
    )
    state.composer = ""
    state.composer_cursor = 0
    _refresh_messages(state, stdscr)
    state.stick_bottom = True
    state.status = "sent"


def _run_with_loading(
    stdscr: curses.window | None,
    state: ChatRuntimeState,
    operation: Callable[[], Any],
    *,
    message: str,
) -> Any:
    if stdscr is None:
        return operation()

    outcome: dict[str, Any] = {}
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

    if not finished.wait(CHAT_LOADING_DISPLAY_DELAY_SECONDS):
        frame_index = 0
        _draw_loading_frame(stdscr, state, message=message, frame_index=frame_index)
        while not finished.wait(CHAT_LOADING_FRAME_INTERVAL_MS / 1000):
            frame_index += 1
            _draw_loading_frame(stdscr, state, message=message, frame_index=frame_index)

    thread.join()
    error = outcome.get("error")
    if isinstance(error, BaseException):
        raise error
    return outcome.get("result")


def _draw_loading_frame(
    stdscr: curses.window,
    state: ChatRuntimeState,
    *,
    message: str,
    frame_index: int,
) -> None:
    _draw(stdscr, state)
    draw_loading_overlay(stdscr, message=message, frame_index=frame_index)


def clamp_composer_cursor(state: ChatRuntimeState) -> int:
    state.composer_cursor = clamp_input_cursor(state.composer, state.composer_cursor)
    return state.composer_cursor


def insert_composer_text(state: ChatRuntimeState, value: str) -> None:
    for character in value:
        result = apply_input_edit_key(state.composer, state.composer_cursor, ord(character))
        if result.handled:
            state.composer = result.value
            state.composer_cursor = result.cursor


def delete_composer_backward(state: ChatRuntimeState) -> None:
    result = apply_input_edit_key(state.composer, state.composer_cursor, CTRL_H)
    state.composer = result.value
    state.composer_cursor = result.cursor


def delete_composer_forward(state: ChatRuntimeState) -> None:
    result = apply_input_edit_key(state.composer, state.composer_cursor, CTRL_D)
    state.composer = result.value
    state.composer_cursor = result.cursor


def delete_composer_previous_word(state: ChatRuntimeState) -> None:
    result = apply_input_edit_key(state.composer, state.composer_cursor, CTRL_W)
    state.composer = result.value
    state.composer_cursor = result.cursor


def move_cursor_backward_word(value: str, cursor: int) -> int:
    return move_input_cursor_backward_word(value, cursor)


def move_cursor_forward_word(value: str, cursor: int) -> int:
    return move_input_cursor_forward_word(value, cursor)


def composer_prompt_view(composer: str, cursor: int, width: int) -> tuple[str, int]:
    return single_line_input_view(composer, cursor, width, prompt="> ")


def selected_conversation(state: ChatRuntimeState) -> ChatConversation | None:
    if not state.conversations:
        return None
    state.conversation_index = min(max(state.conversation_index, 0), len(state.conversations) - 1)
    return state.conversations[state.conversation_index]


def selected_row(state: ChatRuntimeState) -> RenderedChatRow | None:
    if not state.rendered_rows:
        return None
    state.cursor_row = min(max(state.cursor_row, 0), len(state.rendered_rows) - 1)
    return state.rendered_rows[state.cursor_row]


def move_cursor_row(state: ChatRuntimeState, delta: int) -> None:
    if not state.rendered_rows:
        return
    state.cursor_row = min(max(state.cursor_row + delta, 0), len(state.rendered_rows) - 1)
    state.stick_bottom = False


def focus_latest_message(state: ChatRuntimeState) -> None:
    state.cursor_row = LATEST_MESSAGE_CURSOR


def message_start_row_indices(rows: list[RenderedChatRow]) -> list[int]:
    return [index for index, row in enumerate(rows) if row.message_start]


def first_message_row_index(rows: list[RenderedChatRow]) -> int | None:
    starts = message_start_row_indices(rows)
    return starts[0] if starts else None


def last_message_row_index(rows: list[RenderedChatRow]) -> int | None:
    starts = message_start_row_indices(rows)
    return starts[-1] if starts else None


def move_message_row(state: ChatRuntimeState, delta: int) -> None:
    starts = message_start_row_indices(state.rendered_rows)
    if not starts:
        return
    cursor = min(max(state.cursor_row, 0), len(state.rendered_rows) - 1)
    if delta > 0:
        target = next((index for index in starts if index > cursor), starts[-1])
    else:
        previous = [index for index in starts if index < cursor]
        target = previous[-1] if previous else starts[0]
    state.cursor_row = target
    state.stick_bottom = False


def render_message_rows(messages: list[ChatMessage], width: int) -> list[RenderedChatRow]:
    rows: list[RenderedChatRow] = []
    box_width = max(24, width)
    inner_width = max(10, box_width - 4)
    for message_index, message in enumerate(messages):
        header = f"{message.sender}  {message.date}".strip()
        rows.append(
            RenderedChatRow(
                text=box_top(header, inner_width),
                kind="message_box",
                message_index=message_index,
                message_start=True,
            )
        )
        text = (message.text or "").strip() or "-"
        for paragraph in str(text).splitlines() or [""]:
            for line in textwrap.wrap(paragraph, inner_width) or [""]:
                rows.append(
                    RenderedChatRow(
                        text=box_content(line, inner_width),
                        kind="message_text",
                        message_index=message_index,
                    )
                )
        for embed in message.embeds:
            for line in embed_box_rows(embed, inner_width):
                rows.append(
                    RenderedChatRow(
                        text=box_content(line, inner_width),
                        kind="embed_box",
                        message_index=message_index,
                    )
                )
        if message.files:
            top, button, bottom = nested_file_box_rows(message.files, inner_width)
            rows.append(RenderedChatRow(text=box_content(top, inner_width), kind="file_box", message_index=message_index))
            rows.append(
                RenderedChatRow(
                    text=box_content(button, inner_width),
                    kind="file_button",
                    message_index=message_index,
                    file_index=0,
                )
            )
            rows.append(RenderedChatRow(text=box_content(bottom, inner_width), kind="file_box", message_index=message_index))
        rows.append(RenderedChatRow(text=box_bottom(box_width), kind="message_box", message_index=message_index))
        rows.append(RenderedChatRow(text="", kind="spacer"))
    if rows:
        return rows[:-1]
    return [RenderedChatRow(text="No messages.", kind="empty")]


def _open_file_modal_for_selected_row(state: ChatRuntimeState) -> bool:
    row = selected_row(state)
    if row is None or row.kind != "file_button" or row.message_index is None:
        state.status = "select a file button"
        return False
    message = state.messages[row.message_index]
    if not message.files:
        state.status = "no files"
        return False
    state.modal = ChatModalState(kind="files", message_index=row.message_index)
    state.status = f"{len(message.files)} files"
    return True


def _move_modal_file(state: ChatRuntimeState, delta: int) -> None:
    if state.modal is None or state.modal.kind != "files":
        return
    files = _modal_files(state)
    if not files:
        return
    state.modal.file_index = min(max(state.modal.file_index + delta, 0), len(files) - 1)


def _open_selected_modal_file(stdscr: curses.window, state: ChatRuntimeState) -> None:
    if state.modal is None or state.modal.kind != "files":
        return
    conversation = selected_conversation(state)
    if conversation is None:
        state.status = "no conversation"
        return
    if not 0 <= state.modal.message_index < len(state.messages):
        state.status = "no message"
        return
    message = state.messages[state.modal.message_index]
    files = _modal_files(state)
    if not files:
        state.status = "no files"
        return
    file_item = files[min(max(state.modal.file_index, 0), len(files) - 1)]
    if state.callbacks.open_file is None:
        state.status = "file open unavailable"
        return
    path = _run_with_loading(
        stdscr,
        state,
        lambda: state.callbacks.open_file(conversation, message, file_item),
        message="Opening file",
    )
    if path:
        _open_path(stdscr, path)
        state.status = f"opened {path}"


def _modal_files(state: ChatRuntimeState) -> list[ChatFile]:
    if state.modal is None or state.modal.message_index >= len(state.messages):
        return []
    return state.messages[state.modal.message_index].files


def conversation_line(conversation: ChatConversation, width: int) -> str:
    unread = "*" if conversation.unread else " "
    kind = conversation.kind or "dm"
    return clip(f"{unread} {kind:<3} {conversation.label}  {conversation.date}", width)


def transcript_status(messages: list[ChatMessage], rendered_line_count: int, view_height: int, scroll: int) -> str:
    message_count = len(messages)
    if not message_count:
        return "0 messages"
    rendered_line_count = max(1, rendered_line_count)
    view_height = max(1, view_height)
    scroll = max(0, min(scroll, max(0, rendered_line_count - view_height)))
    visible_end = min(rendered_line_count, scroll + view_height)
    return f"{message_count} messages  lines {scroll + 1}-{visible_end}/{rendered_line_count}"


def adjust_scroll(index: int, scroll: int, height: int, length: int) -> int:
    if height <= 0:
        return 0
    index = max(0, min(index, max(0, length - 1)))
    if index < scroll:
        return index
    if index >= scroll + height:
        return index - height + 1
    return max(0, min(scroll, max(0, length - height)))


def _draw(stdscr: curses.window, state: ChatRuntimeState) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    if height < 8 or width < 32:
        safe_addstr(stdscr, 0, 0, "Terminal too small for erza chat.")
    elif state.mode == "chat":
        _draw_chat(stdscr, state, height, width)
    else:
        _draw_conversations(stdscr, state, height, width)
    if state.modal is not None:
        _draw_file_modal(stdscr, state)
    if state.show_help:
        _draw_help_modal(stdscr)
    stdscr.refresh()


def _draw_conversations(stdscr: curses.window, state: ChatRuntimeState, height: int, width: int) -> None:
    safe_addstr(stdscr, 0, 0, clip(f"{state.title}  conversations  {state.status}", width - 1))
    safe_addstr(stdscr, 1, 0, "-" * max(0, width - 1))
    visible_rows = max(1, height - 2)
    state.conversation_scroll = adjust_scroll(
        state.conversation_index,
        state.conversation_scroll,
        visible_rows,
        len(state.conversations),
    )
    for row_offset in range(visible_rows):
        index = state.conversation_scroll + row_offset
        if index >= len(state.conversations):
            break
        if index == state.conversation_index:
            safe_addstr(stdscr, 2 + row_offset, 0, ">")
        safe_addstr(stdscr, 2 + row_offset, 2, conversation_line(state.conversations[index], width - 3))


def _draw_chat(stdscr: curses.window, state: ChatRuntimeState, height: int, width: int) -> None:
    conversation = selected_conversation(state)
    label = conversation.label if conversation is not None else "-"
    rendered = render_message_rows(state.messages, width - 3)
    message_height = max(1, height - 4)
    state.message_view_height = message_height
    state.rendered_rows = rendered
    max_scroll = max(0, len(rendered) - message_height)
    if state.input_active and state.stick_bottom:
        scroll = max_scroll
        state.cursor_row = max(0, len(rendered) - 1)
    elif not state.input_active:
        if state.cursor_row == LATEST_MESSAGE_CURSOR:
            latest = last_message_row_index(rendered)
            state.cursor_row = latest if latest is not None else max(0, len(rendered) - 1)
            scroll = max_scroll
        else:
            state.cursor_row = max(0, min(state.cursor_row, max(0, len(rendered) - 1)))
            scroll = adjust_scroll(state.cursor_row, state.message_scroll, message_height, len(rendered))
    else:
        scroll = max(0, min(state.message_scroll, max_scroll))
    state.message_scroll = scroll

    safe_addstr(
        stdscr,
        0,
        0,
        clip(f"{state.title}  {label}  {transcript_status(state.messages, len(rendered), message_height, scroll)}  {state.status}", width - 1),
    )
    safe_addstr(stdscr, 1, 0, "-" * max(0, width - 1))
    safe_addstr(stdscr, height - 2, 0, "-" * max(0, width - 1))
    for row_offset in range(message_height):
        index = scroll + row_offset
        if index >= len(rendered):
            break
        row = rendered[index]
        if not state.input_active and index == state.cursor_row:
            safe_addstr(stdscr, 2 + row_offset, 0, ">")
        safe_addstr(stdscr, 2 + row_offset, 2, clip(row.text, width - 3))

    prompt_width = max(1, width - 1)
    if state.input_active:
        visible_prompt, cursor_col = composer_prompt_view(state.composer, state.composer_cursor, prompt_width)
    else:
        visible_prompt, cursor_col = "[normal]", 0
    safe_addstr(stdscr, height - 1, 0, clip(visible_prompt, prompt_width))
    if state.input_active:
        safe_move(stdscr, height - 1, cursor_col)


def _draw_file_modal(stdscr: curses.window, state: ChatRuntimeState) -> None:
    if state.modal is None or state.modal.kind != "files":
        return
    files = _modal_files(state)
    if not files:
        return
    height, _width = stdscr.getmaxyx()
    list_height = min(FILE_MODAL_HEIGHT, max(1, height - 4))
    state.modal.file_index = min(max(state.modal.file_index, 0), len(files) - 1)
    state.modal.scroll = adjust_scroll(state.modal.file_index, state.modal.scroll, list_height, len(files))
    visible = files[state.modal.scroll : state.modal.scroll + list_height]
    lines = [f"{item.kind or 'file'}  {item.name or 'attachment'}" for item in visible]
    _draw_modal_box(
        stdscr,
        f"{len(files)} Files",
        lines,
        selected_index=state.modal.file_index,
        item_offset=state.modal.scroll,
        body_height=FILE_MODAL_HEIGHT,
    )


def _draw_help_modal(stdscr: curses.window) -> None:
    height, width = stdscr.getmaxyx()
    inner_width = min(HELP_MODAL_MAX_WIDTH - 4, max(24, width - 8))
    lines = []
    for label, description in CHAT_SHORTCUTS:
        wrapped = textwrap.wrap(description, width=max(10, inner_width - 15)) or [description]
        for index, part in enumerate(wrapped):
            prefix = f"{label:<13} " if index == 0 else " " * 14
            lines.append(clip(prefix + part, inner_width))
    _draw_modal_box(stdscr, "Shortcuts", lines, body_height=min(len(lines), max(1, height - 4)))


def _draw_modal_box(
    stdscr: curses.window,
    title: str,
    lines: list[str],
    *,
    selected_index: int | None = None,
    item_offset: int = 0,
    body_height: int | None = None,
) -> None:
    height, width = stdscr.getmaxyx()
    if height < 6 or width < 24:
        return
    inner_width = min(max(24, max((len(line) for line in lines), default=0)), max(24, width - 8))
    box_width = inner_width + 4
    max_body_height = max(1, height - 4)
    effective_body_height = min(len(lines), max_body_height) if body_height is None else min(max(1, body_height), max_body_height)
    body_lines = list(lines[:effective_body_height])
    if len(body_lines) < effective_body_height:
        body_lines.extend([""] * (effective_body_height - len(body_lines)))
    box_height = effective_body_height + 2
    y = max(0, (height - box_height) // 2)
    x = max(0, (width - box_width) // 2)
    safe_addstr(stdscr, y, x, box_top(title, inner_width))
    for offset, line in enumerate(body_lines, start=1):
        screen_y = y + offset
        safe_addstr(stdscr, screen_y, x, "| ")
        safe_addstr(stdscr, screen_y, x + 2, " " * inner_width)
        safe_addstr(stdscr, screen_y, x + box_width - 2, " |")
        safe_addstr(stdscr, screen_y, x + 2, clip(line, inner_width))
        if selected_index is not None and item_offset + offset - 1 == selected_index:
            safe_addstr(stdscr, screen_y, max(0, x - 2), ">")
    safe_addstr(stdscr, y + box_height - 1, x, box_bottom(box_width))


def box_top(title: str, inner_width: int) -> str:
    title_text = clip(f"[ {title} ]", max(1, inner_width))
    return "+-" + title_text + "-" * max(inner_width + 1 - len(title_text), 0) + "+"


def box_bottom(box_width: int) -> str:
    return "+" + "-" * max(0, box_width - 2) + "+"


def box_content(value: str, inner_width: int) -> str:
    return f"| {str(value or '')[:inner_width]:<{inner_width}} |"


def file_button_label(count: int) -> str:
    return f"<<<{count} Files>>>"


def nested_file_box_rows(files: list[ChatFile], inner_width: int) -> tuple[str, str, str]:
    button = file_button_label(len(files))
    title = "[ Files ]"
    nested_inner = max(12, min(inner_width - 4, max(len(button), len(title)) + 2))
    nested_width = nested_inner + 4
    top = "+-" + title + "-" * max(nested_inner + 1 - len(title), 0) + "+"
    bottom = "+" + "-" * max(0, nested_width - 2) + "+"
    return top, f"| {button:<{nested_inner}} |", bottom


def embed_box_rows(embed: ChatEmbed, inner_width: int) -> list[str]:
    title = "[ Embed ]"
    raw_lines = [item for item in (embed.title, embed.url, embed.text) if str(item or "").strip()]
    if not raw_lines:
        raw_lines = ["embed"]
    nested_inner = max(12, min(inner_width - 4, max(len(title), *(len(str(item)) for item in raw_lines)) + 2))
    rows = ["+-" + title + "-" * max(nested_inner + 1 - len(title), 0) + "+"]
    for raw_line in raw_lines:
        for line in textwrap.wrap(str(raw_line), nested_inner) or [""]:
            rows.append(f"| {line:<{nested_inner}} |")
    rows.append("+" + "-" * max(0, nested_inner + 2) + "+")
    return rows


def clip(value: str, width: int) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ")
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def delete_previous_word(value: str) -> str:
    stripped = value.rstrip()
    if not stripped:
        return ""
    return stripped[: stripped.rfind(" ") + 1] if " " in stripped else ""


def safe_addstr(window: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    try:
        height, width = window.getmaxyx()
        if y < 0 or y >= height or x >= width:
            return
        window.addnstr(y, x, str(text), max(0, width - x - 1), attr)
    except curses.error:
        return


def safe_move(window: curses.window, y: int, x: int) -> None:
    try:
        height, width = window.getmaxyx()
        if y < 0 or y >= height:
            return
        window.move(y, max(0, min(x, width - 1)))
    except curses.error:
        return


def _setup_curses(stdscr: curses.window) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    try:
        curses.noecho()
        curses.raw()
        curses.nonl()
    except curses.error:
        pass
    try:
        curses.start_color()
        curses.use_default_colors()
        assume_default = getattr(curses, "assume_default_colors", None)
        if assume_default:
            assume_default(-1, -1)
        curses.init_pair(1, -1, -1)
        stdscr.bkgd(" ", curses.color_pair(1))
    except curses.error:
        pass


def _open_path(stdscr: curses.window, path: str) -> None:
    command, wait = _resolve_open_command(path)
    try:
        curses.def_prog_mode()
    except curses.error:
        pass
    try:
        curses.endwin()
    except curses.error:
        pass
    try:
        if wait:
            subprocess.run(command, check=False)
        else:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
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


def _resolve_open_command(path: str) -> tuple[list[str], bool]:
    mime_type, _encoding = mimetypes.guess_type(path)
    if mime_type == "application/pdf":
        command = _first_available_command(
            os.environ.get("ERZA_PDF_VIEWER"),
            "zathura",
            "evince",
            "xdg-open",
        )
        if command:
            return _expand_open_command(command, path), False
    if mime_type and mime_type.startswith("image/"):
        command = _first_available_command(
            os.environ.get("ERZA_IMAGE_VIEWER"),
            "swayimg",
            "imv",
            "feh",
            "xdg-open",
        )
        if command:
            return _expand_open_command(command, path), False
    return [*_resolve_editor_command(), path], True


def _first_available_command(*commands: str | None) -> list[str] | None:
    for raw_command in commands:
        command = shlex.split(raw_command or "")
        if command and shutil.which(command[0]):
            return command
    return None


def _expand_open_command(command: list[str], path: str) -> list[str]:
    if any("{file}" in token for token in command):
        return [token.replace("{file}", path) for token in command]
    return [*command, path]


def _resolve_editor_command() -> list[str]:
    command = shlex.split(os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim")
    return command or ["vim"]
