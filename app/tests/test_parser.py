from __future__ import annotations

import unittest

from _test_bootstrap import ensure_test_paths

ensure_test_paths()

from erza.model import AsciiAnimation, Button, Form, Input, Link, Screen, Section, Text
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

    def test_compiles_form_and_self_closing_inputs(self) -> None:
        markup = """
<Screen title="Sign In">
  <Section title="Account">
    <Form action="/auth/login" submit-button-text="Sign in">
      <Input name="email" type="text" label="Email" required="mandatory" />
      <Input name="password" type="password" />
    </Form>
  </Section>
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

    def test_placeholder_attribute_is_rejected(self) -> None:
        markup = """
<Screen title="Sign In">
  <Section title="Account">
    <Form action="/auth/login">
      <Input name="email" placeholder="Email" />
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
  <Section title="Search">
    <Form action="/search" method="get">
      <Input name="q" />
    </Form>
  </Section>
</Screen>
"""

        with self.assertRaises(ParseError):
            compile_markup(markup)


if __name__ == "__main__":
    unittest.main()
