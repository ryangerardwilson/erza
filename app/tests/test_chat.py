from __future__ import annotations

import unittest

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
    _draw_file_modal,
    _open_file_modal_for_selected_row,
    adjust_scroll,
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


if __name__ == "__main__":
    unittest.main()
