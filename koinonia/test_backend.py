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


if __name__ == "__main__":
    unittest.main()
