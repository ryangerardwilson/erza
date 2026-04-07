from __future__ import annotations

from erza.backend import handler


_CHOICES = [
    {"key": "hello", "label": "Hello", "message": "Hello from erza."},
    {"key": "namaste", "label": "Namaste", "message": "Namaste from erza."},
    {"key": "yo", "label": "Yo", "message": "Yo from erza."},
]

_current_key = "hello"


@handler("greetings.current")
def greetings_current() -> dict[str, str]:
    for choice in _CHOICES:
        if choice["key"] == _current_key:
            return {"message": choice["message"]}
    return {"message": "Hello from erza."}


@handler("greetings.choices")
def greetings_choices() -> list[dict[str, str]]:
    return [{"key": choice["key"], "label": choice["label"]} for choice in _CHOICES]


@handler("greetings.select")
def greetings_select(greeting_key: str) -> None:
    global _current_key
    for choice in _CHOICES:
        if choice["key"] == greeting_key:
            _current_key = greeting_key
            return
