from __future__ import annotations

import unittest

from _test_bootstrap import ensure_test_paths

ensure_test_paths()

from erza.backend import BackendBridge
from erza.local_server import SubmitResult
from erza.model import AsciiAnimation, Button, Form, Input, Link, Screen, Section, Text
from erza.remote import RemoteApp
from erza.runtime import (
    EditState,
    InputControl,
    StaticScreenApp,
    SubmitControl,
    _RuntimeSession,
    _display_origin_x,
    _header_grid_layout,
    _help_modal_lines,
    align_section_top_offset,
    build_render_plan,
    compute_scroll_offset,
    compute_section_scroll_offset,
    next_section_index,
    next_section_line_index,
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
        self.assertEqual(plan.sections[0].width, 77)
        self.assertEqual(plan.sections[1].width, 77)
        self.assertTrue(plan.sections[0].title_text.startswith("+-[ Open ]"))
        self.assertTrue(
            plan.lines[plan.sections[0].y + plan.sections[0].height - 1][0].text.startswith("+---")
        )
        link_line = " ".join(segment.text for segment in plan.lines[plan.sections[1].y + 1])
        self.assertIn("*Protocol*", link_line)
        self.assertEqual(plan.sections[1].actionables[0].label_text, "-> *Protocol*")

    def test_page_and_section_navigation_clamp_at_boundaries(self) -> None:
        screen = Screen(
            title="Directional",
            children=[
                Section(
                    title="Primary",
                    children=[Text("One"), Text("Two"), Link(label="Docs", href="https://example.com")],
                ),
                Section(
                    title="Secondary",
                    children=[Text("Three")],
                ),
            ],
        )

        plan = build_render_plan(screen)

        self.assertEqual(next_section_index(plan, 0, -1), 0)
        self.assertEqual(next_section_index(plan, 1, 1), 1)
        self.assertEqual(next_section_index(plan, 0, 1), 1)
        self.assertEqual(next_section_line_index(plan.sections[0], 0, -1), 0)
        self.assertEqual(
            next_section_line_index(plan.sections[0], len(plan.sections[0].block.lines) - 3, 1),
            len(plan.sections[0].block.lines) - 3,
        )

    def test_scroll_offset_moves_to_reveal_active_section(self) -> None:
        sections = [
            Section(title=f"Section {index}", children=[Text(f"Body {index}")])
            for index in range(8)
        ]
        plan = build_render_plan(Screen(title="Long", children=sections))

        offset = compute_scroll_offset(plan, 5, screen_height=8, terminal_width=79)

        self.assertGreater(offset, 0)
        layout = _header_grid_layout(plan, 79)
        self.assertLessEqual(5, offset + layout.visible_slots - 1)

    def test_section_scroll_offset_reveals_active_line_within_modal(self) -> None:
        lines = [Text(f"Line {index}") for index in range(10)]
        plan = build_render_plan(
            Screen(
                title="Deep",
                children=[Section(title="Actions", children=lines)],
            )
        )

        offset = compute_section_scroll_offset(plan.sections[0], 8, screen_height=8)

        self.assertGreater(offset, 0)
        visible_height = 5
        self.assertLessEqual(8, offset + visible_height - 1)

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

        session._jump_to_last_section(plan)
        self.assertEqual(session.section_index, len(plan.sections) - 1)

    def test_header_grid_navigation_moves_across_rows_and_columns(self) -> None:
        screen = Screen(
            title="Grid",
            children=[
                Section(title=f"Section Title {index}", children=[Text(f"Body {index}")])
                for index in range(7)
            ],
        )
        plan = build_render_plan(screen)
        session = _RuntimeSession(StaticScreenApp(screen))

        session._move_header_selection(plan, 79, "right")
        self.assertEqual(session.section_index, 1)

        session._move_header_selection(plan, 79, "down")
        self.assertEqual(session.section_index, 2)

        session._move_header_selection(plan, 79, "left")
        self.assertEqual(session.section_index, 1)

    def test_header_strip_navigation_wraps_at_edges(self) -> None:
        screen = Screen(
            title="Grid",
            children=[
                Section(title=f"Section Title {index}", children=[Text(f"Body {index}")])
                for index in range(7)
            ],
        )
        plan = build_render_plan(screen)
        session = _RuntimeSession(StaticScreenApp(screen))

        session.section_index = len(plan.sections) - 1
        session._move_header_selection(plan, 79, "right")
        self.assertEqual(session.section_index, 0)

        session.section_index = 0
        session._move_header_selection(plan, 79, "left")
        self.assertEqual(session.section_index, len(plan.sections) - 1)

        session.section_index = len(plan.sections) - 1
        session._move_header_selection(plan, 79, "down")
        self.assertEqual(session.section_index, 0)

        session.section_index = 0
        session._move_header_selection(plan, 79, "up")
        self.assertEqual(session.section_index, len(plan.sections) - 1)

    def test_jump_to_line_boundaries_updates_active_line(self) -> None:
        screen = Screen(
            title="Bounds",
            children=[
                Section(
                    title="One",
                    children=[Text("First"), Text("Second"), Text("Third"), Text("Fourth")],
                )
            ],
        )
        plan = build_render_plan(screen)
        session = _RuntimeSession(StaticScreenApp(screen))
        session.mode = "section"
        session.section_line_index = 2

        session._jump_to_first_line(plan)
        self.assertEqual(session.section_line_index, 0)

        session._jump_to_last_line(plan)
        self.assertEqual(session.section_line_index, len(plan.sections[0].block.lines) - 3)

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

    def test_runtime_session_caches_screen_between_page_navigation_steps(self) -> None:
        screen = Screen(
            title="Cached",
            children=[
                Section(title="One", children=[Text("Install")]),
                Section(title="Two", children=[Text("Next")]),
            ],
        )
        app = _CountingApp(screen)
        session = _RuntimeSession(app)

        first = session._current_screen()
        second = session._current_screen()
        plan = build_render_plan(second)
        session._sync_state(plan)
        session._move_section(plan, 1)
        third = session._current_screen()

        self.assertIs(first, second)
        self.assertIs(second, third)
        self.assertEqual(app.build_calls, 1)

    def test_build_render_plan_collects_form_input_and_submit_targets(self) -> None:
        screen = Screen(
            title="Sign In",
            children=[
                Section(
                    title="Account",
                    children=[
                        Form(
                            action="/auth/login",
                            submit_button_text="Sign in",
                            children=[
                                Input(name="email", label="Email", required=True),
                                Input(name="password", type="password", label="Password", required=True),
                            ],
                        )
                    ],
                )
            ],
        )

        plan = build_render_plan(screen)
        targets = plan.sections[0].actionables

        self.assertEqual(len(targets), 3)
        self.assertIsInstance(targets[0].actionable, InputControl)
        self.assertIsInstance(targets[1].actionable, InputControl)
        self.assertIsInstance(targets[2].actionable, SubmitControl)
        self.assertEqual(targets[2].label_text, "[ Sign in ]")
        first_input_line = "".join(segment.text for segment in plan.sections[0].block.lines[1])
        self.assertIn("* Email:", first_input_line)
        self.assertNotIn("[ ", first_input_line)
        self.assertEqual(targets[0].x, 6)
        self.assertEqual(targets[1].x, 6)
        self.assertEqual(targets[1].y, targets[0].y + 1)
        self.assertEqual(targets[2].y, targets[1].y + 1)
        self.assertGreater(targets[2].x, targets[0].x)

    def test_form_input_activation_enters_edit_mode_and_submits(self) -> None:
        screen = Screen(
            title="Sign In",
            children=[
                Section(
                    title="Account",
                    children=[
                        Form(
                            action="/auth/login",
                            submit_button_text="Sign in",
                            children=[Input(name="email", label="Email")],
                        )
                    ],
                )
            ],
        )
        app = _SubmittingApp(screen, SubmitResult(type="error", message="Invalid email"))
        session = _RuntimeSession(app)

        plan = build_render_plan(screen, form_values=session.form_values, edit_state=session.edit_state)
        session._sync_state(plan)
        session._enter_section_mode(plan)
        session.section_line_index = plan.sections[0].block.actionables[0].y - 1
        session._activate(plan)

        self.assertEqual(session.mode, "edit")

        session._handle_edit_key(ord("a"))
        session._handle_edit_key(ord("@"))
        session._handle_edit_key(ord("b"))
        self.assertEqual(session.form_values["form:0"]["email"], "a@b")

        session._handle_edit_key(ord("\n"))
        self.assertEqual(session.mode, "section")

        plan = build_render_plan(screen, form_values=session.form_values, edit_state=session.edit_state)
        session.section_line_index = plan.sections[0].block.actionables[-1].y - 1
        session._activate(plan)

        self.assertEqual(app.submissions, [("/auth/login", {"email": "a@b"})])
        self.assertEqual(session.status, "Invalid email")

    def test_edit_mode_escape_restores_original_value(self) -> None:
        screen = Screen(
            title="Sign In",
            children=[
                Section(
                    title="Account",
                    children=[
                        Form(
                            action="/auth/login",
                            submit_button_text="Sign in",
                            children=[Input(name="email", value="seed@example.com")],
                        )
                    ],
                )
            ],
        )
        session = _RuntimeSession(StaticScreenApp(screen))
        plan = build_render_plan(screen, form_values=session.form_values, edit_state=session.edit_state)
        session._sync_state(plan)
        session._enter_section_mode(plan)
        session.section_line_index = plan.sections[0].block.actionables[0].y - 1
        session._activate(plan)
        session._handle_edit_key(ord("!"))
        session._handle_edit_key(27)

        self.assertEqual(session.mode, "section")
        self.assertEqual(session.form_values["form:0"]["email"], "seed@example.com")

    def test_mandatory_inputs_block_submit_when_empty(self) -> None:
        screen = Screen(
            title="Sign In",
            children=[
                Section(
                    title="Account",
                    children=[
                        Form(
                            action="/auth/login",
                            submit_button_text="Sign in",
                            children=[Input(name="email", label="Email", required=True)],
                        )
                    ],
                )
            ],
        )
        app = _SubmittingApp(screen, SubmitResult(type="refresh"))
        session = _RuntimeSession(app)

        plan = build_render_plan(screen, form_values=session.form_values, edit_state=session.edit_state)
        session._sync_state(plan)
        session._enter_section_mode(plan)
        session.section_line_index = plan.sections[0].block.actionables[-1].y - 1
        session._activate(plan)

        self.assertEqual(app.submissions, [])
        self.assertEqual(session.status, "missing required fields: Email")

    def test_edit_mode_uses_block_cursor_segment_instead_of_pipe_character(self) -> None:
        screen = Screen(
            title="Sign In",
            children=[
                Section(
                    title="Account",
                    children=[
                        Form(
                            action="/auth/login",
                            submit_button_text="Sign in",
                            children=[Input(name="email", value="demo@erza.dev")],
                        )
                    ],
                )
            ],
        )

        plan = build_render_plan(
            screen,
            form_values={"form:0": {"email": "demo@erza.dev"}},
            edit_state=EditState(
                form_key="form:0",
                input_name="email",
                cursor_index=4,
                original_value="demo@erza.dev",
            ),
        )
        input_line = plan.sections[0].block.lines[1]

        self.assertTrue(any(segment.style == "cursor" for segment in input_line))
        self.assertFalse(any(segment.text == "|" for segment in input_line))
        self.assertTrue(any(segment.style == "cursor" and segment.text == "█" for segment in input_line))

    def test_go_back_from_section_mode_returns_to_page_mode(self) -> None:
        screen = Screen(
            title="Docs",
            children=[Section(title="Open", children=[Text("Install"), Link(label="Next", href="next")])],
        )
        session = _RuntimeSession(StaticScreenApp(screen))
        session.mode = "section"

        session._go_back()
        self.assertEqual(session.status, "no previous page")

        session.mode = "section"
        session._exit_section_mode()
        self.assertEqual(session.mode, "page")

    def test_link_activation_from_section_mode_invalidates_cached_screen(self) -> None:
        initial = Screen(
            title="Initial",
            children=[Section(title="Open", children=[Text("Install"), Link(label="Install", href="install")])],
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
        session._enter_section_mode(plan)
        session.section_line_index = plan.sections[0].block.actionables[0].y - 1
        session._activate(plan)
        next_screen = session._current_screen()

        self.assertEqual(app.build_calls, 1)
        self.assertEqual(session.app.build_calls, 1)
        self.assertEqual(next_screen.title, "Install")
        self.assertEqual(session.mode, "page")

    def test_section_half_page_scroll_advances_line_index(self) -> None:
        screen = Screen(
            title="Scroll",
            children=[
                Section(
                    title="Long",
                    children=[Text(f"Line {index}") for index in range(12)],
                )
            ],
        )
        plan = build_render_plan(screen)
        session = _RuntimeSession(StaticScreenApp(screen))
        session.mode = "section"

        session._scroll_section_half_page(plan, screen_height=12, direction=1)

        self.assertGreater(session.section_line_index, 0)

    def test_footer_text_shows_only_route_in_page_mode(self) -> None:
        screen = Screen(
            title="Docs",
            children=[Section(title="Start Here", children=[Text("Intro")])],
        )
        session = _RuntimeSession(RemoteApp("erza.ryangerardwilson.com/first-run"))
        plan = build_render_plan(screen)

        self.assertEqual(
            session._footer_text(plan),
            "https://erza.ryangerardwilson.com/first-run",
        )

    def test_footer_text_shows_route_and_section_in_section_mode(self) -> None:
        screen = Screen(
            title="Docs",
            children=[Section(title="Start Here", children=[Text("Intro")])],
        )
        session = _RuntimeSession(RemoteApp("erza.ryangerardwilson.com/first-run"))
        session.mode = "section"
        plan = build_render_plan(screen)

        self.assertEqual(
            session._footer_text(plan),
            "https://erza.ryangerardwilson.com/first-run -> Start Here",
        )

    def test_help_modal_lines_include_shortcuts(self) -> None:
        lines = _help_modal_lines(63)

        self.assertTrue(any("Header h / k" in line for line in lines))
        self.assertTrue(any("Header j / l" in line for line in lines))
        self.assertTrue(any("?              Toggle the shortcuts modal." in line for line in lines))


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


class _SubmittingApp(_CountingApp):
    def __init__(self, screen: Screen, result: SubmitResult) -> None:
        super().__init__(screen)
        self.result = result
        self.submissions: list[tuple[str, dict[str, str]]] = []

    def submit_form(self, action: str, values: dict[str, str]) -> SubmitResult:
        self.submissions.append((action, values))
        return self.result


if __name__ == "__main__":
    unittest.main()
