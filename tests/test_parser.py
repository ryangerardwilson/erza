from __future__ import annotations

import unittest

from erza.model import Button, Link, Screen, Section, Text
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


if __name__ == "__main__":
    unittest.main()
