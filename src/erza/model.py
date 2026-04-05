from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Text:
    content: str


@dataclass(slots=True)
class Header:
    content: str


@dataclass(slots=True)
class Link:
    label: str
    href: str


@dataclass(slots=True)
class Button:
    label: str
    action: str
    params: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class AsciiAnimation:
    frames: list[str]
    fps: int = 4
    loop: bool = True
    label: str = "Animation"


@dataclass(slots=True)
class Column:
    children: list["Component"]
    gap: int = 0


@dataclass(slots=True)
class Row:
    children: list["Component"]
    gap: int = 1


@dataclass(slots=True)
class Section:
    title: str
    children: list["Component"]
    tone: str = "default"


@dataclass(slots=True)
class Screen:
    title: str
    children: list["Component"]


Component = Text | Header | Link | Button | AsciiAnimation | Column | Row | Section
