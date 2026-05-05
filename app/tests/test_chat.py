from __future__ import annotations

import unittest
from unittest import mock

from _test_bootstrap import ensure_test_paths

ensure_test_paths()

from erza.chat import (
    ChatCallbacks,
    ChatConversation,
    ChatEmbed,
    ChatFile,
    ChatMessage,
    ChatModalState,
    ChatRuntimeState,
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
    LATEST_MESSAGE_CURSOR,
    _draw_chat,
    _draw_file_modal,
    _draw_loading_frame,
    _handle_chat_key,
    _handle_key,
    _open_selected_conversation,
    _open_file_modal_for_selected_row,
    _resolve_open_command,
    _run_with_loading,
    adjust_scroll,
    composer_prompt_view,
    conversation_line,
    first_message_row_index,
    last_message_row_index,
    message_start_row_indices,
    move_message_row,
    render_message_rows,
    selected_conversation,
    transcript_status,
)


class ChatRuntimeTests(unittest.TestCase):
    def test_render_message_rows_boxes_messages_embeds_and_file_button(self) -> None:
        rows = render_message_rows(
            [
                ChatMessage(
                    message_id="D1:100.000100",
                    sender="Maanas",
                    date="2026-04-27 10:00:00",
                    text="files",
                    embeds=[ChatEmbed(title="spec", url="https://example.com/spec", text="embedded doc preview")],
                    files=[ChatFile(name="note.txt", file_id="F1")],
                )
            ],
            80,
        )

        rendered = "\n".join(row.text for row in rows)

        self.assertTrue(rows[0].text.startswith("+-[ Maanas  2026-04-27"))
        self.assertIn("[ Embed ]", rendered)
        self.assertIn("spec", rendered)
        self.assertIn("embedded doc preview", rendered)
        self.assertIn("| <<<1 Files>>>", rendered)
        self.assertEqual([row.kind for row in rows].count("file_button"), 1)

    def test_message_navigation_targets_message_starts(self) -> None:
        rows = render_message_rows(
            [
                ChatMessage(message_id="1", sender="a", date="one", text="one"),
                ChatMessage(message_id="2", sender="b", date="two", text="two"),
                ChatMessage(message_id="3", sender="c", date="three", text="three"),
            ],
            80,
        )
        starts = message_start_row_indices(rows)
        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(lambda: [], lambda _conversation: []),
            rendered_rows=rows,
            cursor_row=starts[-1],
        )

        self.assertEqual(len(starts), 3)
        self.assertEqual(first_message_row_index(rows), starts[0])
        self.assertEqual(last_message_row_index(rows), starts[-1])
        move_message_row(state, -1)
        self.assertEqual(state.cursor_row, starts[1])
        move_message_row(state, 1)
        self.assertEqual(state.cursor_row, starts[2])
        self.assertFalse(state.stick_bottom)

    def test_file_modal_opens_only_from_file_button(self) -> None:
        messages = [
            ChatMessage(
                message_id="1",
                sender="a",
                date="one",
                text="one",
                files=[ChatFile(name="note.txt")],
            )
        ]
        rows = render_message_rows(messages, 80)
        file_row_index = next(index for index, row in enumerate(rows) if row.kind == "file_button")
        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(lambda: [], lambda _conversation: []),
            messages=messages,
            rendered_rows=rows,
            cursor_row=0,
        )

        self.assertFalse(_open_file_modal_for_selected_row(state))
        state.cursor_row = file_row_index
        self.assertTrue(_open_file_modal_for_selected_row(state))
        self.assertIsNotNone(state.modal)
        self.assertEqual(state.modal.message_index, 0)

    def test_file_modal_uses_fixed_height_and_scrolls(self) -> None:
        added: list[tuple[int, int, str, int, int]] = []

        class FakeWindow:
            def getmaxyx(self) -> tuple[int, int]:
                return (20, 80)

            def addnstr(self, y: int, x: int, text: str, limit: int, attr: int = 0) -> None:
                added.append((y, x, text[:limit], limit, attr))

        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(lambda: [], lambda _conversation: []),
            messages=[
                ChatMessage(
                    message_id="1",
                    sender="a",
                    date="one",
                    files=[ChatFile(name=f"file-{index}.txt") for index in range(10)],
                )
            ],
        )
        state.modal = ChatModalState(kind="files", message_index=0, file_index=9)

        _draw_file_modal(FakeWindow(), state)  # type: ignore[arg-type]

        self.assertEqual(state.modal.scroll, 3)
        body_fill_calls = [item for item in added if item[2] == "| "]
        self.assertEqual(len(body_fill_calls), 7)
        self.assertTrue(any(text == ">" for _, _, text, _, _ in added))
        self.assertFalse(any("file-0.txt" in text for _, _, text, _, _ in added))
        self.assertTrue(any("file-9.txt" in text for _, _, text, _, _ in added))

    def test_conversation_line_and_transcript_status_are_compact(self) -> None:
        line = conversation_line(
            ChatConversation(
                conversation_id="D1",
                label="Maanas",
                date="2026-04-27 10:00:00",
                kind="dm",
                unread=True,
            ),
            80,
        )

        self.assertIn("* dm", line)
        self.assertIn("Maanas", line)
        self.assertEqual(transcript_status([ChatMessage("1", "a", "d")], 20, 5, 10), "1 messages  lines 11-15/20")
        self.assertEqual(adjust_scroll(9, 0, 7, 10), 3)

    def test_selected_conversation_clamps_index(self) -> None:
        conversation = ChatConversation(conversation_id="D1", label="Maanas")
        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(lambda: [], lambda _conversation: []),
            conversations=[conversation],
            conversation_index=10,
        )

        self.assertIs(selected_conversation(state), conversation)
        self.assertEqual(state.conversation_index, 0)

    def test_opening_conversation_starts_in_normal_mode_at_latest_message(self) -> None:
        conversation = ChatConversation(conversation_id="D1", label="Maanas")
        messages = [
            ChatMessage("1", "a", "one", "one"),
            ChatMessage("2", "b", "two", "two"),
        ]
        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(lambda: [conversation], lambda _conversation: messages),
            conversations=[conversation],
        )

        _open_selected_conversation(state)

        self.assertFalse(state.input_active)
        self.assertEqual(state.cursor_row, LATEST_MESSAGE_CURSOR)

        added: list[tuple[int, int, str, int, int]] = []

        class FakeWindow:
            def getmaxyx(self) -> tuple[int, int]:
                return (14, 80)

            def addnstr(self, y: int, x: int, text: str, limit: int, attr: int = 0) -> None:
                added.append((y, x, text[:limit], limit, attr))

            def move(self, y: int, x: int) -> None:
                pass

        _draw_chat(FakeWindow(), state, 14, 80)  # type: ignore[arg-type]

        self.assertEqual(state.cursor_row, last_message_row_index(state.rendered_rows))
        self.assertTrue(any(text == "[normal]" for _, _, text, _, _ in added))

    def test_opening_conversation_keeps_unread_when_mark_read_fails(self) -> None:
        conversation = ChatConversation(conversation_id="G1", label="Group", kind="group_dm", unread=True)
        messages = [ChatMessage("1", "a", "one", "one")]
        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(
                lambda: [conversation],
                lambda _conversation: messages,
                mark_read=lambda _conversation, _messages: "missing_scope:add mpim:write to user token",
            ),
            conversations=[conversation],
        )

        _open_selected_conversation(state)

        self.assertTrue(conversation.unread)
        self.assertIn("mark_read:missing_scope:add mpim:write", state.status)

    def test_insert_escape_returns_to_normal_mode_latest_message(self) -> None:
        rows = render_message_rows(
            [
                ChatMessage("1", "a", "one", "one"),
                ChatMessage("2", "b", "two", "two"),
            ],
            80,
        )
        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(lambda: [], lambda _conversation: []),
            rendered_rows=rows,
            input_active=False,
            cursor_row=0,
        )

        _handle_chat_key(None, state, ord("i"))  # type: ignore[arg-type]
        self.assertTrue(state.input_active)

        _handle_chat_key(None, state, 27)  # type: ignore[arg-type]
        self.assertFalse(state.input_active)
        self.assertEqual(state.cursor_row, LATEST_MESSAGE_CURSOR)

    def test_leader_mra_marks_all_conversations_read(self) -> None:
        conversations = [
            ChatConversation(conversation_id="D1", label="Maanas", unread=True),
            ChatConversation(conversation_id="G1", label="Group", kind="group_dm", unread=True),
        ]
        seen: list[list[ChatConversation]] = []

        def mark_all_read(items: list[ChatConversation]) -> int:
            seen.append(items)
            return len(items)

        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(
                lambda: conversations,
                lambda _conversation: [],
                mark_all_read=mark_all_read,
            ),
            conversations=conversations,
            messages=[ChatMessage("1", "a", "one", "one", unread=True)],
        )

        _handle_chat_key(None, state, ord(","))  # type: ignore[arg-type]
        _handle_chat_key(None, state, ord("m"))  # type: ignore[arg-type]
        _handle_chat_key(None, state, ord("r"))  # type: ignore[arg-type]
        _handle_chat_key(None, state, ord("a"))  # type: ignore[arg-type]

        self.assertEqual(seen, [conversations])
        self.assertFalse(any(conversation.unread for conversation in conversations))
        self.assertFalse(any(message.unread for message in state.messages))
        self.assertEqual(state.status, "marked_read=2")

    def test_leader_mra_works_from_conversation_list(self) -> None:
        conversations = [
            ChatConversation(conversation_id="D1", label="Maanas", unread=True),
            ChatConversation(conversation_id="G1", label="Group", kind="group_dm", unread=True),
        ]
        seen: list[list[ChatConversation]] = []

        def mark_all_read(items: list[ChatConversation]) -> int:
            seen.append(items)
            return len(items)

        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(
                lambda: conversations,
                lambda _conversation: [],
                mark_all_read=mark_all_read,
            ),
            conversations=conversations,
            mode="conversations",
        )

        _handle_key(None, state, ord(","))  # type: ignore[arg-type]
        _handle_key(None, state, ord("m"))  # type: ignore[arg-type]
        _handle_key(None, state, ord("r"))  # type: ignore[arg-type]
        _handle_key(None, state, ord("a"))  # type: ignore[arg-type]

        self.assertEqual(seen, [conversations])
        self.assertFalse(any(conversation.unread for conversation in conversations))
        self.assertEqual(state.status, "marked_read=2")

    def test_file_open_command_defaults_pdf_and_images_to_viewers(self) -> None:
        def fake_which(command: str) -> str | None:
            return f"/usr/bin/{command}" if command in {"zathura", "swayimg", "vim"} else None

        with mock.patch("erza.chat.shutil.which", side_effect=fake_which):
            pdf_command, pdf_wait = _resolve_open_command("/tmp/report.pdf")
            image_command, image_wait = _resolve_open_command("/tmp/photo.png")
            text_command, text_wait = _resolve_open_command("/tmp/note.txt")

        self.assertEqual(pdf_command, ["zathura", "/tmp/report.pdf"])
        self.assertFalse(pdf_wait)
        self.assertEqual(image_command, ["swayimg", "/tmp/photo.png"])
        self.assertFalse(image_wait)
        self.assertEqual(text_command, ["vim", "/tmp/note.txt"])
        self.assertTrue(text_wait)

    def test_insert_mode_supports_emacs_style_composer_movement(self) -> None:
        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(lambda: [], lambda _conversation: []),
            input_active=True,
            composer="hello brave world",
            composer_cursor=len("hello brave world"),
        )

        _handle_chat_key(None, state, ALT_B)  # type: ignore[arg-type]
        self.assertEqual(state.composer_cursor, len("hello brave "))

        _handle_chat_key(None, state, CTRL_W)  # type: ignore[arg-type]
        self.assertEqual(state.composer, "hello world")
        self.assertEqual(state.composer_cursor, len("hello "))

        _handle_chat_key(None, state, CTRL_A)  # type: ignore[arg-type]
        _handle_chat_key(None, state, ord(">"))  # type: ignore[arg-type]
        self.assertEqual(state.composer, ">hello world")
        self.assertEqual(state.composer_cursor, 1)

        _handle_chat_key(None, state, CTRL_E)  # type: ignore[arg-type]
        _handle_chat_key(None, state, CTRL_H)  # type: ignore[arg-type]
        self.assertEqual(state.composer, ">hello worl")
        self.assertEqual(state.composer_cursor, len(">hello worl"))

        _handle_chat_key(None, state, CTRL_A)  # type: ignore[arg-type]
        _handle_chat_key(None, state, ALT_F)  # type: ignore[arg-type]
        self.assertEqual(state.composer_cursor, len(">hello"))

        _handle_chat_key(None, state, CTRL_K)  # type: ignore[arg-type]
        self.assertEqual(state.composer, ">hello")

        _handle_chat_key(None, state, CTRL_E)  # type: ignore[arg-type]
        _handle_chat_key(None, state, CTRL_B)  # type: ignore[arg-type]
        self.assertEqual(state.composer_cursor, len(">hell"))

        _handle_chat_key(None, state, CTRL_F)  # type: ignore[arg-type]
        self.assertEqual(state.composer_cursor, len(">hello"))

        _handle_chat_key(None, state, CTRL_A)  # type: ignore[arg-type]
        _handle_chat_key(None, state, CTRL_D)  # type: ignore[arg-type]
        self.assertEqual(state.composer, "hello")
        self.assertEqual(state.composer_cursor, 0)

        _handle_chat_key(None, state, CTRL_U)  # type: ignore[arg-type]
        self.assertEqual(state.composer, "")
        self.assertEqual(state.composer_cursor, 0)

    def test_composer_prompt_view_keeps_cursor_visible(self) -> None:
        text, cursor_col = composer_prompt_view("abcdefghijklmnopqrstuvwxyz", 25, 12)

        self.assertEqual(text, "> qrstuvwxyz")
        self.assertEqual(cursor_col, 11)

    def test_loading_frame_uses_erza_loading_overlay(self) -> None:
        calls: list[tuple[str, int]] = []
        rendered_text: list[str] = []

        class FakeWindow:
            def erase(self) -> None:
                pass

            def refresh(self) -> None:
                pass

            def getmaxyx(self) -> tuple[int, int]:
                return (14, 80)

            def addnstr(self, y: int, x: int, text: str, limit: int, attr: int = 0) -> None:
                rendered_text.append(str(text[:limit]))

            def move(self, y: int, x: int) -> None:
                pass

        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(lambda: [], lambda _conversation: []),
            status="loading...",
        )

        def fake_overlay(_stdscr, *, message: str, frame_index: int) -> None:
            calls.append((message, frame_index))

        with mock.patch("erza.chat.draw_loading_overlay", side_effect=fake_overlay):
            _draw_loading_frame(FakeWindow(), state, message="Loading messages", frame_index=4)  # type: ignore[arg-type]

        self.assertEqual(calls, [("Loading messages", 4)])
        self.assertNotIn("No messages.", rendered_text)
        self.assertFalse(any("0 messages" in text for text in rendered_text))
        self.assertFalse(any("loading..." in text.lower() for text in rendered_text))
        self.assertEqual(state.loading_message, "")

    def test_run_with_loading_draws_initial_chat_loading_frame(self) -> None:
        calls: list[tuple[str, int]] = []

        class FakeWindow:
            def erase(self) -> None:
                pass

            def refresh(self) -> None:
                pass

            def getmaxyx(self) -> tuple[int, int]:
                return (14, 80)

            def addnstr(self, y: int, x: int, text: str, limit: int, attr: int = 0) -> None:
                pass

            def move(self, y: int, x: int) -> None:
                pass

        state = ChatRuntimeState(
            title="test",
            callbacks=ChatCallbacks(lambda: [], lambda _conversation: []),
        )

        def fake_overlay(_stdscr, *, message: str, frame_index: int) -> None:
            calls.append((message, frame_index))

        with mock.patch("erza.chat.draw_loading_overlay", side_effect=fake_overlay):
            result = _run_with_loading(
                FakeWindow(),  # type: ignore[arg-type]
                state,
                lambda: "ok",
                message="Loading messages",
            )

        self.assertEqual(result, "ok")
        self.assertTrue(calls)
        self.assertEqual(calls[0], ("Loading messages", 0))


if __name__ == "__main__":
    unittest.main()
