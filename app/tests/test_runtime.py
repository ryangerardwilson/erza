from __future__ import annotations

import curses
import unittest
from unittest.mock import patch

from _test_bootstrap import ensure_test_paths

ensure_test_paths()

from erza.backend import BackendBridge
from erza.local_server import SubmitResult
from erza.model import AsciiAnimation, Button, ButtonRow, Form, Input, Link, Modal, Screen, Section, Text
from erza.remote import RemoteApp
from erza.runtime import (
    ALT_B,
    ALT_F,
    CTRL_A,
    CTRL_E,
    CTRL_W,
    EditState,
    InputControl,
    StaticScreenApp,
    SubmitControl,
    _RuntimeSession,
    _decode_edit_key,
    _display_origin_x,
    _header_grid_layout,
    _help_modal_lines,
    align_section_top_offset,
    build_render_plan,
    compute_scroll_offset,
    compute_section_scroll_offset,
    draw_loading_overlay,
    draw_modal_overlay,
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

    def test_nested_sections_render_as_embedded_boxes(self) -> None:
        plan = build_render_plan(
            Screen(
                title="Feed",
                children=[
                    Section(
                        title="Timeline",
                        children=[
                            Section(
                                title="Dispatch",
                                children=[
                                    Text("Hello from the feed."),
                                    Button(label="Signal", action="feed.like"),
                                ],
                            )
                        ],
                    )
                ],
            )
        )

        flattened_lines = ["".join(segment.text for segment in line) for line in plan.sections[0].block.lines]

        self.assertTrue(any("[ Dispatch ]" in line for line in flattened_lines))
        self.assertEqual(len(plan.sections[0].actionables), 1)
        self.assertEqual(plan.sections[0].actionables[0].label_text, "[ Signal ]")

    def test_button_row_renders_multiple_actionables_on_one_line(self) -> None:
        plan = build_render_plan(
            Screen(
                title="Profile",
                children=[
                    Section(
                        title="Actions",
                        children=[
                            ButtonRow(
                                children=[
                                    Button(label="New post", action="posts.open"),
                                    Button(label="Edit description", action="profile.edit"),
                                ]
                            )
                        ],
                    )
                ],
            )
        )

        flattened_lines = ["".join(segment.text for segment in line) for line in plan.sections[0].block.lines]
        line_index = plan.sections[0].block.actionables[0].y - 1
        actionables = [item for item in plan.sections[0].block.actionables if item.y - 1 == line_index]

        self.assertEqual(len(actionables), 2)
        self.assertTrue(all(item.action_group == "button_row" for item in actionables))
        self.assertTrue(any("+----------------" in line for line in flattened_lines))
        self.assertTrue(any("[ New post ]" in line and "[ Edit description ]" in line for line in flattened_lines))

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
        self.assertIn("*Email:", first_input_line)
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
        self.assertEqual(session.section_line_index, plan.sections[0].block.actionables[-1].y - 1)

        session._activate(plan)

        self.assertEqual(app.submissions, [("/auth/login", {"email": "a@b"})])
        self.assertEqual(session.status, "Invalid email")

    def test_edit_mode_enter_advances_to_next_input_line(self) -> None:
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
                                Input(name="username", label="Username"),
                                Input(name="password", label="Password"),
                            ],
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
        session._handle_edit_key(ord("a"))
        session._handle_edit_key(ord("\n"))

        next_plan = build_render_plan(screen, form_values=session.form_values, edit_state=session.edit_state)

        self.assertEqual(session.mode, "section")
        self.assertEqual(session.section_line_index, next_plan.sections[0].block.actionables[1].y - 1)

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
        self.assertTrue(any(segment.style == "cursor" and segment.text == "@" for segment in input_line))

    def test_edit_mode_ctrl_w_deletes_previous_word(self) -> None:
        screen = Screen(
            title="Sign In",
            children=[
                Section(
                    title="Account",
                    children=[Form(action="/auth/login", children=[Input(name="email", value="demo user")])],
                )
            ],
        )
        session = _RuntimeSession(StaticScreenApp(screen))
        session.edit_state = EditState(
            form_key="form:0",
            input_name="email",
            cursor_index=len("demo user"),
            original_value="demo user",
        )
        session.form_values = {"form:0": {"email": "demo user"}}

        session._handle_edit_key(CTRL_W)

        self.assertEqual(session.form_values["form:0"]["email"], "demo ")
        self.assertEqual(session.edit_state.cursor_index, len("demo "))

    def test_edit_mode_alt_word_motion_moves_cursor_by_word(self) -> None:
        screen = Screen(
            title="Sign In",
            children=[
                Section(
                    title="Account",
                    children=[Form(action="/auth/login", children=[Input(name="email", value="demo user test")])],
                )
            ],
        )
        session = _RuntimeSession(StaticScreenApp(screen))
        session.edit_state = EditState(
            form_key="form:0",
            input_name="email",
            cursor_index=0,
            original_value="demo user test",
        )
        session.form_values = {"form:0": {"email": "demo user test"}}

        session._handle_edit_key(ALT_F)
        self.assertEqual(session.edit_state.cursor_index, len("demo"))

        session._handle_edit_key(ALT_F)
        self.assertEqual(session.edit_state.cursor_index, len("demo user"))

        session._handle_edit_key(ALT_B)
        self.assertEqual(session.edit_state.cursor_index, len("demo "))

    def test_edit_mode_ctrl_a_and_ctrl_e_jump_to_bounds(self) -> None:
        screen = Screen(
            title="Sign In",
            children=[
                Section(
                    title="Account",
                    children=[Form(action="/auth/login", children=[Input(name="email", value="demo user test")])],
                )
            ],
        )
        session = _RuntimeSession(StaticScreenApp(screen))
        session.edit_state = EditState(
            form_key="form:0",
            input_name="email",
            cursor_index=5,
            original_value="demo user test",
        )
        session.form_values = {"form:0": {"email": "demo user test"}}

        session._handle_edit_key(CTRL_A)
        self.assertEqual(session.edit_state.cursor_index, 0)

        session._handle_edit_key(CTRL_E)
        self.assertEqual(session.edit_state.cursor_index, len("demo user test"))

    def test_escape_prefixed_alt_sequences_decode_in_edit_mode(self) -> None:
        self.assertEqual(_decode_edit_key(_FakeWindow([ord("b")]), 27), ALT_B)
        self.assertEqual(_decode_edit_key(_FakeWindow([ord("f")]), 27), ALT_F)
        self.assertEqual(_decode_edit_key(_FakeWindow([-1]), 27), 27)

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

        self.assertEqual(
            session._footer_text(),
            "https://erza.ryangerardwilson.com/first-run",
        )

    def test_footer_text_stays_route_only_in_section_mode(self) -> None:
        screen = Screen(
            title="Docs",
            children=[Section(title="Start Here", children=[Text("Intro")])],
        )
        session = _RuntimeSession(RemoteApp("erza.ryangerardwilson.com/first-run"))
        session.mode = "section"

        self.assertEqual(
            session._footer_text(),
            "https://erza.ryangerardwilson.com/first-run",
        )

    def test_single_action_section_acts_as_direct_action_tab(self) -> None:
        screen = Screen(
            title="Account",
            children=[
                Section(
                    title="Logout",
                    children=[Button(label="Log out", action="auth.logout")],
                )
            ],
        )
        app = _ActionApp(screen)
        session = _RuntimeSession(app)
        plan = build_render_plan(screen)
        session._sync_state(plan)

        session._enter_section_mode(plan)

        self.assertEqual(app.actions, [("auth.logout", {})])
        self.assertEqual(session.mode, "page")

    def test_direct_action_section_can_open_modal(self) -> None:
        screen = Screen(
            title="Auth",
            children=[
                Section(title="Why", children=[Text("Why")]),
                Section(
                    title="Login",
                    children=[Button(label="Open access", action="ui.open_modal", params={"modal_id": "auth-access"})],
                ),
                Modal(
                    modal_id="auth-access",
                    title="Login / Sign Up",
                    children=[
                        Form(
                            action="/auth/access",
                            submit_button_text="Enter",
                            children=[
                                Input(name="username", label="Username"),
                                Input(name="password", type="password", label="Password"),
                            ],
                        )
                    ],
                ),
            ],
        )
        session = _RuntimeSession(StaticScreenApp(screen))
        session.section_index = 1
        plan = build_render_plan(screen, form_values=session.form_values, edit_state=session.edit_state)
        session._sync_state(plan)

        session._enter_section_mode(plan)

        self.assertEqual(session.active_modal_id, "auth-access")
        self.assertEqual(session.mode, "modal")

    def test_direct_action_tab_keeps_previous_page_body_visible(self) -> None:
        screen = Screen(
            title="Auth",
            children=[
                Section(title="Why", children=[Text("Why")]),
                Section(
                    title="Login",
                    children=[Button(label="Open access", action="ui.open_modal", params={"modal_id": "auth-access"})],
                ),
                Modal(
                    modal_id="auth-access",
                    title="Login / Sign Up",
                    children=[Text("Sign in here.")],
                ),
            ],
        )
        session = _RuntimeSession(StaticScreenApp(screen))
        plan = build_render_plan(screen, form_values=session.form_values, edit_state=session.edit_state)
        session.section_index = 1
        session._sync_state(plan)

        with patch("erza.runtime.draw_plan") as draw_plan:
            session._draw_active_view(_DrawingWindow(), plan, "auth")

        self.assertEqual(session.body_section_index, 0)
        self.assertEqual(draw_plan.call_args.args[2], 1)
        self.assertEqual(draw_plan.call_args.args[3], 0)

    def test_modal_from_direct_action_tab_renders_over_previous_page(self) -> None:
        screen = Screen(
            title="Auth",
            children=[
                Section(title="Why", children=[Text("Why")]),
                Section(
                    title="Login",
                    children=[Button(label="Open access", action="ui.open_modal", params={"modal_id": "auth-access"})],
                ),
                Modal(
                    modal_id="auth-access",
                    title="Login / Sign Up",
                    children=[Text("Sign in here.")],
                ),
            ],
        )
        session = _RuntimeSession(StaticScreenApp(screen))
        session.section_index = 1
        plan = build_render_plan(screen, form_values=session.form_values, edit_state=session.edit_state)
        session._sync_state(plan)
        session._enter_section_mode(plan)

        with patch("erza.runtime.draw_plan") as draw_plan, patch("erza.runtime.draw_modal_overlay") as draw_modal:
            session._draw_active_view(_DrawingWindow(), plan, "auth")

        self.assertEqual(session.active_modal_id, "auth-access")
        self.assertEqual(draw_plan.call_args.args[2], 1)
        self.assertEqual(draw_plan.call_args.args[3], 0)
        self.assertTrue(draw_modal.called)

    def test_modal_submit_redirect_closes_modal_and_loads_target_screen(self) -> None:
        initial = Screen(
            title="Auth",
            children=[
                Section(
                    title="Login",
                    children=[Button(label="Open access", action="ui.open_modal", params={"modal_id": "auth-access"})],
                ),
                Modal(
                    modal_id="auth-access",
                    title="Login / Sign Up",
                    children=[
                        Form(
                            action="/auth/access",
                            submit_button_text="Enter",
                            children=[
                                Input(name="username", label="Username"),
                                Input(name="password", type="password", label="Password"),
                            ],
                        )
                    ],
                ),
            ],
        )
        target = Screen(title="App", children=[Section(title="Feed", children=[Text("Feed")])])
        app = _RedirectingSubmittingApp(initial, target, SubmitResult(type="redirect", href="index.erza"))
        session = _RuntimeSession(app)
        plan = build_render_plan(initial, form_values=session.form_values, edit_state=session.edit_state)
        session._sync_state(plan)
        session._enter_section_mode(plan)

        modal = plan.modals["auth-access"]
        form_key = next(
            item.actionable.form_key
            for item in modal.actionables
            if isinstance(item.actionable, InputControl)
        )
        session.form_values = {form_key: {"username": "alpha", "password": "secret"}}
        session.modal_line_index = next(
            item.y - 1
            for item in modal.actionables
            if isinstance(item.actionable, SubmitControl)
        )

        session._activate_modal(plan)

        self.assertIsNone(session.active_modal_id)
        self.assertIsNone(session._screen)

        next_screen = session._current_screen()

        self.assertEqual(next_screen.title, "App")
        self.assertEqual(session.section_index, 0)

    def test_modal_submit_error_stays_open_and_records_message(self) -> None:
        screen = Screen(
            title="Auth",
            children=[
                Section(
                    title="Login",
                    children=[Button(label="Open access", action="ui.open_modal", params={"modal_id": "auth-access"})],
                ),
                Modal(
                    modal_id="auth-access",
                    title="Login / Sign Up",
                    children=[
                        Form(
                            action="/auth/access",
                            submit_button_text="Enter",
                            children=[
                                Input(name="username", label="Username"),
                                Input(name="password", type="password", label="Password"),
                            ],
                        )
                    ],
                ),
            ],
        )
        app = _SubmittingApp(screen, SubmitResult(type="error", message="Invalid password."))
        session = _RuntimeSession(app)
        plan = build_render_plan(screen, form_values=session.form_values, edit_state=session.edit_state)
        session._sync_state(plan)
        session._enter_section_mode(plan)

        modal = plan.modals["auth-access"]
        form_key = next(
            item.actionable.form_key
            for item in modal.actionables
            if isinstance(item.actionable, InputControl)
        )
        session.form_values = {form_key: {"username": "alpha", "password": "wrong"}}
        session.modal_line_index = next(
            item.y - 1
            for item in modal.actionables
            if isinstance(item.actionable, SubmitControl)
        )

        session._activate_modal(plan)

        self.assertEqual(session.active_modal_id, "auth-access")
        self.assertEqual(session.mode, "modal")
        self.assertEqual(session.modal_messages["auth-access"], "Invalid password.")

    def test_button_row_supports_horizontal_navigation_and_activation(self) -> None:
        screen = Screen(
            title="Profile",
            children=[
                Section(
                    title="Actions",
                    children=[
                        ButtonRow(
                            children=[
                                Button(label="New post", action="posts.open"),
                                Button(label="Edit description", action="profile.edit"),
                            ]
                        )
                    ],
                )
            ],
        )
        app = _ActionApp(screen)
        session = _RuntimeSession(app)
        plan = build_render_plan(screen)
        session._sync_state(plan)
        session._enter_section_mode(plan)
        session.section_line_index = plan.sections[0].block.actionables[0].y - 1

        self.assertEqual(session.section_action_index, 0)

        session._move_section_action(plan, 1)
        self.assertEqual(session.section_action_index, 1)

        session._activate(plan)
        self.assertEqual(app.actions, [("profile.edit", {})])

    def test_redirect_submit_defers_tab_reset_until_new_screen_loads(self) -> None:
        initial = Screen(
            title="Auth",
            children=[
                Section(title="Why", children=[Text("Why")]),
                Section(
                    title="Login",
                    children=[Form(action="/auth/access", submit_button_text="Enter", children=[])],
                ),
            ],
        )
        target = Screen(
            title="App",
            children=[
                Section(title="Feed", children=[Text("Feed")]),
                Section(title="Profile", children=[Text("Profile")]),
            ],
        )
        app = _RedirectingSubmittingApp(initial, target, SubmitResult(type="redirect", href="index.erza"))
        session = _RuntimeSession(app)
        session.section_index = 1
        plan = build_render_plan(initial, form_values=session.form_values, edit_state=session.edit_state)
        session._sync_state(plan)
        session._enter_section_mode(plan)
        session.section_line_index = plan.sections[1].block.actionables[-1].y - 1

        session._activate(plan)

        self.assertEqual(session.section_index, 1)
        self.assertIsNone(session._screen)

        next_screen = session._current_screen()

        self.assertEqual(next_screen.title, "App")
        self.assertEqual(session.section_index, 0)

    def test_help_modal_lines_include_shortcuts(self) -> None:
        lines = _help_modal_lines(63)

        self.assertTrue(any("Header h / k / arrows" in line for line in lines))
        self.assertTrue(any("Section j / k / arrows" in line for line in lines))
        self.assertTrue(any("?              Toggle the shortcuts modal." in line for line in lines))

    def test_loading_overlay_draws_without_solid_fill(self) -> None:
        calls: list[tuple[int, int, str, int, int]] = []

        def capture(stdscr, y: int, x: int, text: str, max_length: int, style: int) -> None:
            calls.append((y, x, text, max_length, style))

        with patch("erza.runtime._safe_addnstr", side_effect=capture):
            draw_loading_overlay(_DrawingWindow(), message="Loading app", frame_index=0)

        self.assertTrue(any(text == "Loading app" for _, _, text, _, _ in calls))
        self.assertTrue(any(text.startswith("+-[ Working ]") for _, _, text, _, _ in calls))
        self.assertFalse(any(text and set(text) == {" "} for _, _, text, _, _ in calls))

    def test_modal_overlay_draws_fill_to_cover_underlying_page(self) -> None:
        screen = Screen(
            title="Auth",
            children=[
                Section(title="Why", children=[Text("Why")]),
                Modal(
                    modal_id="auth-access",
                    title="Login / Sign Up",
                    children=[Text("Sign in here.")],
                ),
            ],
        )
        plan = build_render_plan(screen)
        calls: list[tuple[int, int, str, int, int]] = []

        def capture(stdscr, y: int, x: int, text: str, max_length: int, style: int) -> None:
            calls.append((y, x, text, max_length, style))

        with patch("erza.runtime._safe_addnstr", side_effect=capture):
            draw_modal_overlay(
                _DrawingWindow(),
                plan.modals["auth-access"],
                line_index=0,
                action_index=0,
                scroll_offset=0,
            )

        self.assertTrue(any(text.startswith("+-[ Login / Sign Up ]") for _, _, text, _, _ in calls))
        self.assertTrue(any(text and set(text) == {" "} for _, _, text, _, _ in calls))
        marker_styles = [style for _, _, text, _, style in calls if text == ">"]
        self.assertTrue(marker_styles)
        self.assertTrue(all(style & curses.A_REVERSE for style in marker_styles))


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


class _ActionApp(_CountingApp):
    def __init__(self, screen: Screen) -> None:
        super().__init__(screen)
        self.actions: list[tuple[str, dict[str, object]]] = []

    def dispatch_action(self, action: str, params: dict[str, object]) -> object:
        self.actions.append((action, params))
        return None


class _RedirectingSubmittingApp(_SubmittingApp):
    def __init__(self, screen: Screen, target: Screen, result: SubmitResult) -> None:
        super().__init__(screen, result)
        self.target = target

    def follow_link(self, href: str) -> "_RedirectingSubmittingApp":
        return _RedirectingSubmittingApp(self.target, self.target, self.result)


class _FakeWindow:
    def __init__(self, keys: list[int]) -> None:
        self.keys = list(keys)
        self.timeouts: list[int] = []

    def timeout(self, value: int) -> None:
        self.timeouts.append(value)

    def getch(self) -> int:
        if self.keys:
            return self.keys.pop(0)
        return -1


class _DrawingWindow:
    def getmaxyx(self) -> tuple[int, int]:
        return (24, 79)

    def refresh(self) -> None:
        return


if __name__ == "__main__":
    unittest.main()
