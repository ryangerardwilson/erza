from __future__ import annotations

from erza.backend import handler


_TASKS = [
    {"id": 1, "title": "Define the first erza parser", "done": False},
    {"id": 2, "title": "Prove template output tags", "done": False},
    {"id": 3, "title": "Wire button events through Python", "done": False},
]


@handler("tasks.list")
def tasks_list() -> list[dict[str, object]]:
    return [
        {"id": task["id"], "title": task["title"]}
        for task in _TASKS
        if not task["done"]
    ]


@handler("tasks.complete")
def tasks_complete(task_id: int) -> None:
    for task in _TASKS:
        if task["id"] == task_id:
            task["done"] = True
            return
