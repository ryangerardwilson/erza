from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import textwrap
import unittest

from _test_bootstrap import ensure_test_paths

ensure_test_paths()

from erza.runtime import ErzaApp


class FormFlowTests(unittest.TestCase):
    def test_local_form_submit_updates_session_and_redirects(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "index.erza").write_text(
                textwrap.dedent(
                    """
                    <Screen title="Sign In">
                      <? status = backend("auth.status") ?>
                      <? email = backend("auth.email") ?>

                      <Section title="Account">
                        <Text><?= status ?></Text>
                      </Section>
                      <Modal id="auth-access" title="Sign In">
                        <Form action="/auth/login" submit-button-text="Sign in">
                          <Input name="email" type="text" label="Email" required="mandatory" value="<?= email ?>" />
                          <Input name="password" type="password" label="Password" required="mandatory" />
                        </Form>
                      </Modal>
                    </Screen>
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "done.erza").write_text(
                textwrap.dedent(
                    """
                    <Screen title="Done">
                      <Section title="Welcome">
                        <Text>Signed in.</Text>
                      </Section>
                    </Screen>
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "backend.py").write_text(
                textwrap.dedent(
                    """
                    from erza.backend import error, handler, redirect, route, session


                    @handler("auth.status")
                    def auth_status():
                        return session().get("status", "Enter your credentials.")


                    @handler("auth.email")
                    def auth_email():
                        return session().get("email", "")


                    @route("/auth/login")
                    def auth_login(email="", password=""):
                        state = session()
                        state["email"] = email
                        if email == "demo@erza.dev" and password == "terminal":
                            state["status"] = "Signed in."
                            return redirect("done.erza")
                        state["status"] = "Invalid credentials."
                        return error("Invalid credentials.")
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            app = ErzaApp(root / "index.erza")

            initial = app.build_screen()
            initial_section = initial.children[0]
            self.assertEqual(initial_section.children[0].content, "Enter your credentials.")

            result = app.submit_form(
                "/auth/login",
                {"email": "demo@erza.dev", "password": "wrong"},
            )
            self.assertEqual(result.type, "error")
            self.assertEqual(result.message, "Invalid credentials.")

            rerendered = app.build_screen()
            section = rerendered.children[0]
            self.assertEqual(section.children[0].content, "Invalid credentials.")
            form = rerendered.children[1].children[0]
            self.assertEqual(form.children[0].value, "demo@erza.dev")

            success = app.submit_form(
                "/auth/login",
                {"email": "demo@erza.dev", "password": "terminal"},
            )
            self.assertEqual(success.type, "redirect")
            self.assertEqual(success.href, "done.erza")

            next_app = app.follow_link(success.href)
            next_screen = next_app.build_screen()
            self.assertEqual(next_screen.title, "Done")


if __name__ == "__main__":
    unittest.main()
