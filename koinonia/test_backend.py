from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
KOINONIA_DIR = ROOT / "koinonia"
APP_DIR = ROOT / "app"
APP_SRC = APP_DIR / "src"
for candidate in (KOINONIA_DIR, ROOT, APP_DIR, APP_SRC):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

import backend as koinonia_backend
from erza.backend import RedirectResult


class KoinoniaBackendTests(unittest.TestCase):
    def test_decode_profile_state_supports_legacy_bio_rows(self) -> None:
        state = koinonia_backend._decode_profile_state("Joined through the terminal.")

        self.assertEqual(state["description"], "Joined through the terminal.")
        self.assertEqual(state["picture"], koinonia_backend.DEFAULT_PROFILE_PICTURE)

    def test_decode_profile_state_supports_structured_payload(self) -> None:
        encoded = koinonia_backend._encode_profile_state("Builder", " /\\\\\n<__>")

        state = koinonia_backend._decode_profile_state(encoded)

        self.assertEqual(state["description"], "Builder")
        self.assertEqual(state["picture"], " /\\\\\n<__>")

    def test_update_profile_writes_encoded_description_and_picture(self) -> None:
        updates: list[dict[str, object]] = []
        status_messages: list[str] = []

        def record_update(path: str, *, query: dict[str, object], body: dict[str, object]) -> None:
            updates.append({"path": path, "query": query, "body": body})

        with (
            patch.object(koinonia_backend, "_current_account", return_value={"handle": "ryan", "display_name": "Ryan"}),
            patch.object(koinonia_backend, "_profile_row", return_value={"bio": "Joined through the terminal."}),
            patch.object(koinonia_backend, "_update", side_effect=record_update),
            patch.object(koinonia_backend, "_set_status", side_effect=status_messages.append),
        ):
            result = koinonia_backend.update_profile(
                description="Terminal builder",
                profile_picture=" /\\\\\n<__>",
            )

        self.assertIsInstance(result, RedirectResult)
        self.assertEqual(result.href, "index.erza")
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["path"], "profiles")
        self.assertEqual(updates[0]["query"], {"handle": "eq.ryan"})
        payload = str(updates[0]["body"]["bio"])
        decoded = koinonia_backend._decode_profile_state(payload)
        self.assertEqual(decoded["description"], "Terminal builder")
        self.assertEqual(decoded["picture"], " /\\\\\n<__>")
        self.assertEqual(status_messages, ["Updated @ryan's profile."])

    def test_update_profile_accepts_wide_picture_without_backend_validation(self) -> None:
        updates: list[dict[str, object]] = []

        def record_update(path: str, *, query: dict[str, object], body: dict[str, object]) -> None:
            updates.append({"path": path, "query": query, "body": body})

        wide_picture = "x" * 120
        with (
            patch.object(koinonia_backend, "_current_account", return_value={"handle": "ryan", "display_name": "Ryan"}),
            patch.object(koinonia_backend, "_profile_row", return_value={"bio": "Joined through the terminal."}),
            patch.object(koinonia_backend, "_update", side_effect=record_update),
            patch.object(koinonia_backend, "_set_status"),
        ):
            result = koinonia_backend.update_profile(
                description="Terminal builder",
                profile_picture=wide_picture,
            )

        self.assertIsInstance(result, RedirectResult)
        payload = str(updates[0]["body"]["bio"])
        decoded = koinonia_backend._decode_profile_state(payload)
        self.assertEqual(decoded["picture"], wide_picture)

    def test_attach_replies_nests_second_level_replies_under_direct_reply(self) -> None:
        posts = [
            {
                "id": 1,
                "slug": "launch-week",
                "handle": "alina",
                "body": "Root post",
                "likes": 3,
                "reply_count": 2,
                "replies": [],
            }
        ]
        reply_rows = [
            {
                "id": 10,
                "thread_slug": "launch-week",
                "parent_reply_id": None,
                "handle": "noor",
                "body": "Direct reply",
                "likes": 2,
                "reply_count": 1,
                "created_at": "2026-04-14T10:00:00Z",
            },
            {
                "id": 11,
                "thread_slug": "launch-week",
                "parent_reply_id": 10,
                "handle": "mika",
                "body": "Nested reply",
                "likes": 1,
                "reply_count": 0,
                "created_at": "2026-04-14T10:05:00Z",
            },
        ]

        with patch.object(koinonia_backend, "_rows", return_value=reply_rows):
            hydrated = koinonia_backend._attach_replies(posts)

        self.assertEqual(len(hydrated[0]["replies"]), 1)
        self.assertEqual(hydrated[0]["replies"][0]["handle"], "noor")
        self.assertEqual(len(hydrated[0]["replies"][0]["replies"]), 1)
        self.assertEqual(hydrated[0]["replies"][0]["replies"][0]["handle"], "mika")

    def test_create_thread_reply_passes_parent_reply_id_to_rpc(self) -> None:
        rpc_calls: list[dict[str, object]] = []
        status_messages: list[str] = []

        def record_rpc(name: str, **params: object) -> None:
            rpc_calls.append({"name": name, "params": params})

        with (
            patch.object(koinonia_backend, "_current_account", return_value={"handle": "ryan", "display_name": "Ryan"}),
            patch.object(koinonia_backend, "_rpc", side_effect=record_rpc),
            patch.object(koinonia_backend, "_set_status", side_effect=status_messages.append),
        ):
            result = koinonia_backend.create_thread_reply(
                thread_slug="launch-week",
                parent_reply_id="42",
                body="Nested reply",
            )

        self.assertIsInstance(result, RedirectResult)
        self.assertEqual(result.href, "index.erza")
        self.assertEqual(rpc_calls[0]["name"], "add_thread_reply")
        self.assertEqual(
            rpc_calls[0]["params"],
            {
                "thread_slug": "launch-week",
                "parent_reply_id": 42,
                "author_name": "Ryan",
                "profile_handle": "ryan",
                "body": "Nested reply",
            },
        )
        self.assertEqual(status_messages, ["Replied as @ryan."])


if __name__ == "__main__":
    unittest.main()
