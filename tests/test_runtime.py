from __future__ import annotations

import unittest

from erza.model import Button, Column, Row, Screen, Text
from erza.runtime import build_render_plan, move_focus


class RuntimeTests(unittest.TestCase):
    def test_build_render_plan_collects_focusables(self) -> None:
        screen = Screen(
            title="Tasks",
            children=[
                Column(
                    gap=1,
                    children=[
                        Row(
                            gap=2,
                            children=[
                                Text("First"),
                                Button(label="Complete", action="tasks.complete", params={"task_id": 1}),
                            ],
                        ),
                        Row(
                            gap=2,
                            children=[
                                Text("Second"),
                                Button(label="Complete", action="tasks.complete", params={"task_id": 2}),
                            ],
                        ),
                    ],
                )
            ],
        )

        plan = build_render_plan(screen)

        self.assertEqual(len(plan.focusables), 2)
        self.assertLess(plan.focusables[0].y, plan.focusables[1].y)

    def test_move_focus_prefers_directional_candidates(self) -> None:
        screen = Screen(
            title="Directional",
            children=[
                Column(
                    children=[
                        Row(
                            gap=2,
                            children=[
                                Button(label="Left", action="noop"),
                                Button(label="Right", action="noop"),
                            ],
                        ),
                        Row(
                            gap=2,
                            children=[
                                Button(label="Down", action="noop"),
                            ],
                        ),
                    ]
                )
            ],
        )

        plan = build_render_plan(screen)

        self.assertEqual(move_focus(plan, 0, "right"), 1)
        self.assertEqual(move_focus(plan, 0, "down"), 2)


if __name__ == "__main__":
    unittest.main()
