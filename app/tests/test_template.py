from __future__ import annotations

import unittest

from _test_bootstrap import ensure_test_paths

ensure_test_paths()

from erza.backend import BackendBridge
from erza.template import render_template


class TemplateRenderTests(unittest.TestCase):
    def test_renders_backend_data_and_loops(self) -> None:
        bridge = BackendBridge(
            handlers={
                "tasks.list": lambda: [
                    {"id": 1, "title": "Write parser"},
                    {"id": 2, "title": "Build runtime"},
                ]
            }
        )
        source = """
<Screen title="Tasks">
  <? tasks = backend("tasks.list") ?>
  <Column gap="1">
    <? for task in tasks ?>
      <Text><?= task.title ?></Text>
    <? endfor ?>
  </Column>
</Screen>
"""

        rendered = render_template(source, backend=bridge)

        self.assertIn("<Text>Write parser</Text>", rendered)
        self.assertIn("<Text>Build runtime</Text>", rendered)

    def test_renders_if_else_blocks(self) -> None:
        source = """
<Screen title="Tasks">
  <? tasks = [] ?>
  <Column>
    <? if tasks ?>
      <Text>Has tasks</Text>
    <? else ?>
      <Text>Empty</Text>
    <? endif ?>
  </Column>
</Screen>
"""

        rendered = render_template(source)

        self.assertIn("<Text>Empty</Text>", rendered)
        self.assertNotIn("Has tasks", rendered)


if __name__ == "__main__":
    unittest.main()
