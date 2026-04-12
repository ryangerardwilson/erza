from __future__ import annotations

import unittest

from _test_bootstrap import ensure_test_paths

ensure_test_paths()

from erza.model import AsciiAnimation, AsciiArt, Button, ButtonRow, Form, Input, Link, Modal, Screen, Section, Splash, SubmitButton, Text
from erza.parser import ParseError, compile_markup


class ParserTests(unittest.TestCase):
    def test_compiles_sectional_components(self) -> None:
        markup = """
<Screen title="Docs">
  <Section title="Overview">
    <Text>Intro</Text>
    <Link href="/protocol/">Protocol</Link>
    <Action on:press="docs.open" doc:id="7">Open</Action>
  </Section>
</Screen>
"""

        screen = compile_markup(markup)

        self.assertIsInstance(screen, Screen)
        self.assertEqual(screen.title, "Docs")
        self.assertEqual(len(screen.children), 1)
        section = screen.children[0]
        self.assertIsInstance(section, Section)
        self.assertEqual(section.title, "Overview")
        self.assertIsInstance(section.children[0], Text)
        self.assertIsInstance(section.children[1], Link)
        self.assertEqual(section.children[1].href, "/protocol/")
        self.assertIsInstance(section.children[2], Button)
        self.assertEqual(section.children[2].action, "docs.open")
        self.assertEqual(section.children[2].params["doc_id"], 7)

    def test_section_requires_title(self) -> None:
        markup = """
<Screen title="Docs">
  <Section>
    <Text>Intro</Text>
  </Section>
</Screen>
"""

        with self.assertRaises(ParseError):
            compile_markup(markup)

    def test_compiles_section_tab_metadata(self) -> None:
        markup = """
<Screen title="App">
  <Section title="Feed" tab-order="1" default-tab="true">
    <Text>Feed</Text>
  </Section>
</Screen>
"""

        screen = compile_markup(markup)

        section = screen.children[0]
        self.assertIsInstance(section, Section)
        self.assertEqual(section.tab_order, 1)
        self.assertTrue(section.default_tab)

    def test_compiles_screen_splash(self) -> None:
        markup = """
<Screen title="App">
  <Splash duration-ms="1200">
    <AsciiArt>APP</AsciiArt>
  </Splash>
  <Section title="Feed">
    <Text>Ready</Text>
  </Section>
</Screen>
"""

        screen = compile_markup(markup)

        self.assertIsInstance(screen.splash, Splash)
        self.assertEqual(screen.splash.duration_ms, 1200)
        self.assertIsInstance(screen.splash.children[0], AsciiArt)

    def test_compiles_ascii_animation_frames(self) -> None:
        markup = """
<Screen title="Lab">
  <Section title="Motion">
    <AsciiAnimation fps="5" loop="false" label="Pulse">
      <Frame>
o
      </Frame>
      <Frame>
oo
      </Frame>
    </AsciiAnimation>
  </Section>
</Screen>
"""

        screen = compile_markup(markup)

        animation = screen.children[0].children[0]
        self.assertIsInstance(animation, AsciiAnimation)
        self.assertEqual(animation.fps, 5)
        self.assertFalse(animation.loop)
        self.assertEqual(animation.label, "Pulse")
        self.assertEqual(animation.frames, ["o", "oo"])

    def test_compiles_ascii_art_component(self) -> None:
        markup = """
<Screen title="Profile">
  <Section title="Resident">
    <AsciiArt>&lt;o_o&gt;
 /|\\
 / \\
</AsciiArt>
  </Section>
</Screen>
"""

        screen = compile_markup(markup)

        art = screen.children[0].children[0]
        self.assertIsInstance(art, AsciiArt)
        self.assertEqual(art.content, "<o_o>\n /|\\\n / \\")

    def test_compiles_form_and_self_closing_inputs(self) -> None:
        markup = """
<Screen title="Sign In">
  <Modal id="auth-access" title="Sign In">
    <Form action="/auth/login" submit-button-text="Sign in">
      <Input name="email" type="text" label="Email" required="mandatory" />
      <Input name="password" type="password" />
    </Form>
  </Modal>
</Screen>
"""

        screen = compile_markup(markup)

        form = screen.children[0].children[0]
        self.assertIsInstance(form, Form)
        self.assertEqual(form.action, "/auth/login")
        self.assertEqual(form.submit_button_text, "Sign in")
        self.assertEqual(form.method, "post")
        self.assertIsInstance(form.children[0], Input)
        self.assertEqual(form.children[0].name, "email")
        self.assertEqual(form.children[0].label, "Email")
        self.assertTrue(form.children[0].required)
        self.assertIsInstance(form.children[1], Input)
        self.assertEqual(form.children[1].type, "password")

    def test_compiles_ascii_art_input_type(self) -> None:
        markup = """
<Screen title="Profile">
  <Modal id="profile-edit" title="Edit Profile">
    <Form action="/profile/edit">
      <Input name="profile_picture" type="ascii-art" label="Profile Picture" />
    </Form>
  </Modal>
</Screen>
"""

        screen = compile_markup(markup)

        form = screen.children[0].children[0]
        self.assertIsInstance(form.children[0], Input)
        self.assertEqual(form.children[0].type, "ascii-art")

    def test_compiles_button_row(self) -> None:
        markup = """
<Screen title="Feed">
  <Section title="Actions">
    <ButtonRow align="right">
      <Action on:press="posts.open">New post</Action>
      <Action on:press="profile.edit">Edit description</Action>
    </ButtonRow>
  </Section>
</Screen>
"""

        screen = compile_markup(markup)

        row = screen.children[0].children[0]
        self.assertIsInstance(row, ButtonRow)
        self.assertEqual(len(row.children), 2)
        self.assertEqual(row.align, "right")
        self.assertIsInstance(row.children[0], Button)
        self.assertEqual(row.children[0].action, "posts.open")

    def test_compiles_form_button_row_with_submit_children(self) -> None:
        markup = """
<Screen title="Compose">
  <Modal id="post-editor" title="New Post">
    <Form action="/posts/publish">
      <Input name="body" label="Body" />
      <ButtonRow align="right">
        <Submit action="/posts/draft">Save draft</Submit>
        <Submit>Publish post</Submit>
      </ButtonRow>
    </Form>
  </Modal>
</Screen>
"""

        screen = compile_markup(markup)

        form = screen.children[0].children[0]
        row = form.children[1]
        self.assertIsInstance(row, ButtonRow)
        self.assertEqual(row.align, "right")
        self.assertEqual(len(row.children), 2)
        self.assertIsInstance(row.children[0], SubmitButton)
        self.assertEqual(row.children[0].action, "/posts/draft")
        self.assertEqual(row.children[1].action, "")

    def test_form_button_row_rejects_non_submit_children(self) -> None:
        markup = """
<Screen title="Compose">
  <Modal id="post-editor" title="New Post">
    <Form action="/posts/publish">
      <ButtonRow>
        <Action on:press="posts.publish">Publish</Action>
      </ButtonRow>
    </Form>
  </Modal>
</Screen>
"""

        with self.assertRaises(ParseError):
            compile_markup(markup)

    def test_button_row_align_must_be_supported_value(self) -> None:
        markup = """
<Screen title="Feed">
  <Section title="Actions">
    <ButtonRow align="diagonal">
      <Action on:press="posts.open">New post</Action>
    </ButtonRow>
  </Section>
</Screen>
"""

        with self.assertRaises(ParseError):
            compile_markup(markup)

    def test_compiles_nested_sections_for_embedded_panels(self) -> None:
        markup = """
<Screen title="Feed">
  <Section title="Timeline">
    <Section title="Dispatch">
      <Text>Hello</Text>
    </Section>
  </Section>
</Screen>
"""

        screen = compile_markup(markup)

        timeline = screen.children[0]
        self.assertIsInstance(timeline, Section)
        dispatch = timeline.children[0]
        self.assertIsInstance(dispatch, Section)
        self.assertEqual(dispatch.title, "Dispatch")
        self.assertIsInstance(dispatch.children[0], Text)
        self.assertEqual(dispatch.children[0].content, "Hello")

    def test_compiles_top_level_modal(self) -> None:
        markup = """
<Screen title="Auth">
  <Section title="Login">
    <Action on:press="ui.open_modal" modal:id="auth-access">Open</Action>
  </Section>
  <Modal id="auth-access" title="Login / Sign Up">
    <Form action="/auth/access">
      <Input name="username" />
    </Form>
  </Modal>
</Screen>
"""

        screen = compile_markup(markup)

        modal = screen.children[1]
        self.assertIsInstance(modal, Modal)
        self.assertEqual(modal.modal_id, "auth-access")
        self.assertEqual(modal.title, "Login / Sign Up")
        self.assertIsInstance(modal.children[0], Form)

    def test_modal_must_be_top_level(self) -> None:
        markup = """
<Screen title="Auth">
  <Section title="Login">
    <Modal id="auth-access" title="Login / Sign Up">
      <Text>Inner</Text>
    </Modal>
  </Section>
</Screen>
"""

        with self.assertRaises(ParseError):
            compile_markup(markup)

    def test_placeholder_attribute_is_rejected(self) -> None:
        markup = """
<Screen title="Sign In">
  <Modal id="auth-access" title="Sign In">
    <Form action="/auth/login">
      <Input name="email" placeholder="Email" />
    </Form>
  </Modal>
</Screen>
"""

        with self.assertRaises(ParseError):
            compile_markup(markup)

    def test_form_outside_modal_is_rejected(self) -> None:
        markup = """
<Screen title="Sign In">
  <Section title="Account">
    <Form action="/auth/login">
      <Input name="email" />
    </Form>
  </Section>
</Screen>
"""

        with self.assertRaises(ParseError):
            compile_markup(markup)

    def test_input_outside_form_is_rejected(self) -> None:
        markup = """
<Screen title="Sign In">
  <Section title="Account">
    <Input name="email" />
  </Section>
</Screen>
"""

        with self.assertRaises(ParseError):
            compile_markup(markup)

    def test_form_only_supports_post_method(self) -> None:
        markup = """
<Screen title="Search">
  <Modal id="search" title="Search">
    <Form action="/search" method="get">
      <Input name="q" />
    </Form>
  </Modal>
</Screen>
"""

        with self.assertRaises(ParseError):
            compile_markup(markup)


if __name__ == "__main__":
    unittest.main()
