from __future__ import annotations

import unittest

from _test_bootstrap import ensure_test_paths

ensure_test_paths()

from erza.backend import BackendBridge
from erza.model import AsciiAnimation, Button, Link, Screen, Section, Text
from erza.runtime import (
    StaticScreenApp,
    _RuntimeSession,
    _display_origin_x,
    align_section_top_offset,
    build_render_plan,
    compute_scroll_offset,
    next_item_index,
    next_section_index,
)


class RuntimeTests(unittest.TestCase):
    def test_build_render_plan_collects_sections_and_actionables(self) -> None:
        screen = Screen(
            title="Tasks",
            children=[
                Section(
                    title="Open",
                    children=[
                        Text("First"),
                        Button(label="Complete", action="tasks.complete", params={"task_id": 1}),
                    ],
                ),
                Section(
                    title="Links",
                    children=[
                        Link(label="Protocol", href="https://example.com/protocol"),
                    ],
                ),
            ],
        )

        plan = build_render_plan(screen)

        self.assertEqual(len(plan.sections), 2)
        self.assertEqual(plan.sections[0].title, "Open")
        self.assertEqual(len(plan.sections[0].actionables), 1)
        self.assertEqual(len(plan.sections[1].actionables), 1)
        self.assertLess(plan.sections[0].y, plan.sections[1].y)
        self.assertEqual(plan.sections[0].width, 79)
        self.assertEqual(plan.sections[1].width, 79)
        self.assertTrue(plan.sections[0].title_text.startswith("+-[ Open ]"))
        self.assertTrue(
            plan.lines[plan.sections[0].y + plan.sections[0].height - 1][0].text.startswith("+---")
        )
        link_line = " ".join(segment.text for segment in plan.lines[plan.sections[1].y + 1])
        self.assertIn("*Protocol*", link_line)
        self.assertEqual(plan.sections[1].actionables[0].label_text, "-> *Protocol*")

    def test_section_and_item_navigation_wraps(self) -> None:
        screen = Screen(
            title="Directional",
            children=[
                Section(
                    title="Primary",
                    children=[
                        Button(label="One", action="noop"),
                        Button(label="Two", action="noop"),
                    ],
                ),
                Section(
                    title="Secondary",
                    children=[Link(label="Docs", href="https://example.com")],
                ),
            ],
        )

        plan = build_render_plan(screen)

        self.assertEqual(next_section_index(plan, 0, 1), 1)
        self.assertEqual(next_section_index(plan, 1, 1), 0)
        self.assertEqual(next_item_index(plan, 0, 0, 1), 1)
        self.assertEqual(next_item_index(plan, 0, 1, 1), 0)

    def test_scroll_offset_moves_to_reveal_active_section(self) -> None:
        sections = [
            Section(title=f"Section {index}", children=[Text(f"Body {index}")])
            for index in range(8)
        ]
        plan = build_render_plan(Screen(title="Long", children=sections))

        offset = compute_scroll_offset(plan, 5, [0] * len(plan.sections), screen_height=8)

        self.assertGreater(offset, 0)
        visible_height = 7
        self.assertLessEqual(plan.sections[5].y, offset + visible_height - 1)

    def test_scroll_offset_reveals_active_item_within_section(self) -> None:
        actions = [Button(label=f"Action {index}", action="noop") for index in range(6)]
        plan = build_render_plan(
            Screen(
                title="Deep",
                children=[Section(title="Actions", children=actions)],
            )
        )

        offset = compute_scroll_offset(plan, 0, [5], screen_height=6)

        self.assertGreater(offset, 0)
        visible_height = 5
        self.assertLessEqual(plan.sections[0].actionables[5].y, offset + visible_height - 1)

    def test_align_section_top_offset_snaps_header_to_top(self) -> None:
        sections = [
            Section(title=f"Section {index}", children=[Text(f"Body {index}")])
            for index in range(8)
        ]
        plan = build_render_plan(Screen(title="Long", children=sections))

        offset = align_section_top_offset(plan, 3, screen_height=8)

        self.assertEqual(offset, plan.sections[3].y)

    def test_align_section_top_offset_allows_blank_space_below_last_section(self) -> None:
        sections = [
            Section(title=f"Section {index}", children=[Text(f"Body {index}")])
            for index in range(4)
        ]
        plan = build_render_plan(Screen(title="Short", children=sections))

        offset = align_section_top_offset(plan, len(plan.sections) - 1, screen_height=24)

        self.assertEqual(offset, plan.sections[-1].y)

    def test_jump_to_section_boundaries_updates_active_section(self) -> None:
        screen = Screen(
            title="Bounds",
            children=[
                Section(title=f"Section {index}", children=[Text(f"Body {index}")])
                for index in range(4)
            ],
        )
        plan = build_render_plan(screen)
        session = _RuntimeSession(StaticScreenApp(screen))
        session.section_index = 2

        session._jump_to_first_section(plan)
        self.assertEqual(session.section_index, 0)
        self.assertTrue(session.snap_section_to_top)

        session.snap_section_to_top = False
        session._jump_to_last_section(plan)
        self.assertEqual(session.section_index, len(plan.sections) - 1)
        self.assertTrue(session.snap_section_to_top)

    def test_display_origin_centers_79_column_canvas(self) -> None:
        self.assertEqual(_display_origin_x(79), 0)
        self.assertEqual(_display_origin_x(101), 11)

    def test_ascii_animation_selects_frame_and_sets_interval(self) -> None:
        screen = Screen(
            title="Motion",
            children=[
                Section(
                    title="Lab",
                    children=[
                        AsciiAnimation(
                            label="Pulse",
                            fps=5,
                            loop=True,
                            frames=["o", "oo"],
                        )
                    ],
                )
            ],
        )

        first = build_render_plan(screen, animation_time=0.0)
        second = build_render_plan(screen, animation_time=0.25)
        frame_y = first.sections[0].y + 3

        self.assertEqual(first.animation_interval_ms, 200)
        self.assertIn("o", " ".join(segment.text for segment in first.lines[frame_y]))
        self.assertIn("oo", " ".join(segment.text for segment in second.lines[frame_y]))

    def test_runtime_session_caches_screen_between_navigation_steps(self) -> None:
        screen = Screen(
            title="Cached",
            children=[
                Section(title="One", children=[Link(label="Install", href="install")]),
                Section(title="Two", children=[Link(label="Next", href="next")]),
            ],
        )
        app = _CountingApp(screen)
        session = _RuntimeSession(app)

        first = session._current_screen()
        second = session._current_screen()
        plan = build_render_plan(second)
        session._sync_state(plan)
        session._move_item(plan, 1)
        third = session._current_screen()

        self.assertIs(first, second)
        self.assertIs(second, third)
        self.assertEqual(app.build_calls, 1)

    def test_link_activation_invalidates_cached_screen(self) -> None:
        initial = Screen(
            title="Initial",
            children=[Section(title="Open", children=[Link(label="Install", href="install")])],
        )
        target = Screen(
            title="Install",
            children=[Section(title="Install", children=[Text("Install docs")])],
        )
        app = _NavigatingApp(initial, target)
        session = _RuntimeSession(app)

        initial_screen = session._current_screen()
        plan = build_render_plan(initial_screen)
        session._sync_state(plan)
        session._activate(plan)
        next_screen = session._current_screen()

        self.assertEqual(app.build_calls, 1)
        self.assertEqual(session.app.build_calls, 1)
        self.assertEqual(next_screen.title, "Install")


class _CountingApp:
    def __init__(self, screen: Screen) -> None:
        self.screen = screen
        self.backend = BackendBridge.empty()
        self.build_calls = 0

    def build_screen(self) -> Screen:
        self.build_calls += 1
        return self.screen

    def follow_link(self, href: str) -> "_CountingApp":
        raise RuntimeError(f"unexpected link follow: {href}")


class _NavigatingApp(_CountingApp):
    def __init__(self, initial: Screen, target: Screen) -> None:
        super().__init__(initial)
        self.target = target

    def follow_link(self, href: str) -> "_NavigatingApp":
        return _NavigatingApp(self.target, self.target)


if __name__ == "__main__":
    unittest.main()
