"""Tests for the command line entry point of the generator."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree
from contextlib import redirect_stderr, redirect_stdout

from tests.helpers import (
    FAKE_TOKEN,
    FakeTransport,
    PLAIN_REPO_NAME,
    PRIVATE_REPO_NAME,
    contributions_payload,
    default_handler,
    make_snapshot,
    repositories_payload,
    stats_api,
    stats_cli,
)


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out_dir = os.path.join(self._tmp.name, "assets", "stats")
        self.addCleanup(self._tmp.cleanup)

    def run_cli(self, argv=None, environ=None, transport=None):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = stats_cli.run(
                argv if argv is not None else ["--out-dir", self.out_dir],
                environ if environ is not None else {},
                transport=transport,
            )
        return code, out.getvalue(), err.getvalue()

    def written_files(self):
        if not os.path.isdir(self.out_dir):
            return []
        return sorted(os.listdir(self.out_dir))


class SuccessTests(CliTestCase):
    def test_both_cards_are_written(self):
        code, out, err = self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN},
            transport=FakeTransport(default_handler()),
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(self.written_files(), ["contributions.svg", "languages.svg"])
        for name in self.written_files():
            with open(os.path.join(self.out_dir, name), encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("<svg", content)
            self.assertNotIn(".tmp", content)

    def test_the_written_cards_hold_no_repository_name(self):
        self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN},
            transport=FakeTransport(default_handler()),
        )
        for name in self.written_files():
            with open(os.path.join(self.out_dir, name), encoding="utf-8") as handle:
                content = handle.read()
            self.assertNotIn("super-secret-private-project", content)

    def test_the_snapshot_mode_needs_no_token(self):
        snapshot_path = os.path.join(self._tmp.name, "snapshot.json")
        with open(snapshot_path, "w", encoding="utf-8") as handle:
            json.dump(make_snapshot(), handle)
        code, out, err = self.run_cli(
            ["--out-dir", self.out_dir, "--snapshot", snapshot_path], environ={}
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(self.written_files(), ["contributions.svg", "languages.svg"])

    def test_the_dry_run_writes_nothing(self):
        code, out, err = self.run_cli(
            ["--out-dir", self.out_dir, "--dry-run"],
            environ={"STATS_TOKEN": FAKE_TOKEN},
            transport=FakeTransport(default_handler()),
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(self.written_files(), [])
        self.assertIn("would write", out)

    def test_the_check_mode_detects_outdated_cards(self):
        code, out, err = self.run_cli(
            ["--out-dir", self.out_dir, "--check"],
            environ={"STATS_TOKEN": FAKE_TOKEN},
            transport=FakeTransport(default_handler()),
        )
        self.assertEqual(code, 1)
        self.assertIn("outdated", err)
        self.assertEqual(self.written_files(), [])

    def test_the_check_mode_accepts_up_to_date_cards(self):
        self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN},
            transport=FakeTransport(default_handler()),
        )
        code, out, err = self.run_cli(
            ["--out-dir", self.out_dir, "--check"],
            environ={"STATS_TOKEN": FAKE_TOKEN},
            transport=FakeTransport(default_handler()),
        )
        self.assertEqual(code, 0, err)
        self.assertIn("up to date", out)


class PendingModeTests(CliTestCase):
    def test_the_pending_mode_needs_no_token_and_no_network(self):
        code, out, err = self.run_cli(
            ["--out-dir", self.out_dir, "--pending"], environ={}
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(self.written_files(), ["contributions.svg", "languages.svg"])

    def test_the_pending_cards_announce_the_missing_data(self):
        self.run_cli(["--out-dir", self.out_dir, "--pending"], environ={})
        for name in self.written_files():
            with open(os.path.join(self.out_dir, name), encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn('data-state="pending"', content)
            self.assertIn("pending", content.lower())

    def test_the_pending_cards_show_no_statistics(self):
        self.run_cli(["--out-dir", self.out_dir, "--pending"], environ={})
        for name in self.written_files():
            with open(os.path.join(self.out_dir, name), encoding="utf-8") as handle:
                content = handle.read()
            root = ElementTree.fromstring(content)
            for element in root.iter():
                if isinstance(element.tag, str) and element.tag.endswith("text"):
                    self.assertFalse(
                        any(character.isdigit() for character in (element.text or "")),
                        "%s: %r" % (name, element.text),
                    )

    def test_the_pending_mode_refuses_to_overwrite_real_cards(self):
        self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN},
            transport=FakeTransport(default_handler()),
        )
        path = os.path.join(self.out_dir, "contributions.svg")
        with open(path, encoding="utf-8") as handle:
            before = handle.read()
        code, out, err = self.run_cli(
            ["--out-dir", self.out_dir, "--pending"], environ={}
        )
        self.assertEqual(code, 2)
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), before)


class FailureTests(CliTestCase):
    def test_a_missing_token_fails_closed(self):
        code, out, err = self.run_cli(environ={})
        self.assertEqual(code, 2)
        self.assertIn("STATS_TOKEN", err)
        self.assertEqual(self.written_files(), [])

    def test_an_inadequate_token_fails_closed(self):
        def handler(document, variables, index):
            return {"errors": [{"message": "Bad credentials"}]}

        code, out, err = self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN}, transport=FakeTransport(handler)
        )
        self.assertEqual(code, 2)
        self.assertEqual(self.written_files(), [])

    def test_an_api_error_fails_closed(self):
        def handler(document, variables, index):
            return stats_api.HttpResponse(503, {}, "unavailable")

        code, out, err = self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN}, transport=FakeTransport(handler)
        )
        self.assertEqual(code, 2)
        self.assertEqual(self.written_files(), [])

    def test_a_broken_snapshot_fails_closed(self):
        snapshot_path = os.path.join(self._tmp.name, "broken.json")
        with open(snapshot_path, "w", encoding="utf-8") as handle:
            json.dump({"schema": "nope"}, handle)
        code, out, err = self.run_cli(
            ["--out-dir", self.out_dir, "--snapshot", snapshot_path], environ={}
        )
        self.assertEqual(code, 2)
        self.assertEqual(self.written_files(), [])

    def test_the_token_is_never_printed(self):
        def handler(document, variables, index):
            raise stats_api.ApiError("upstream said %s" % FAKE_TOKEN)

        code, out, err = self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN}, transport=handler
        )
        self.assertEqual(code, 2)
        self.assertNotIn(FAKE_TOKEN, out)
        self.assertNotIn(FAKE_TOKEN, err)

    def test_a_repository_name_never_reaches_the_error_output(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            if "repositories(" in document:
                return repositories_payload(
                    [{"name": PRIVATE_REPO_NAME, "languages": None}], total_count=1
                )
            return {"data": {"user": {}}}

        code, out, err = self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN}, transport=FakeTransport(handler)
        )
        self.assertEqual(code, 2)
        self.assertNotIn(PRIVATE_REPO_NAME, out)
        self.assertNotIn(PRIVATE_REPO_NAME, err)
        self.assertNotIn(FAKE_TOKEN, err)
        self.assertEqual(self.written_files(), [])

    def test_an_upstream_error_naming_a_repository_never_reaches_the_output(self):
        def handler(document, variables, index):
            return {
                "errors": [
                    {
                        "message": "Could not resolve to a Repository with the "
                        "name '%s'." % PRIVATE_REPO_NAME
                    }
                ]
            }

        code, out, err = self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN}, transport=FakeTransport(handler)
        )
        self.assertEqual(code, 2)
        self.assertNotIn(PRIVATE_REPO_NAME, out)
        self.assertNotIn(PRIVATE_REPO_NAME, err)
        self.assertEqual(self.written_files(), [])

    def test_an_upstream_error_naming_a_plain_word_repository_is_not_relayed(self):
        def handler(document, variables, index):
            return {
                "errors": [
                    {
                        "message": "Could not resolve to a Repository with the "
                        "name '%s'." % PLAIN_REPO_NAME
                    }
                ]
            }

        code, out, err = self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN}, transport=FakeTransport(handler)
        )
        self.assertEqual(code, 2)
        self.assertNotIn(PLAIN_REPO_NAME, out)
        self.assertNotIn(PLAIN_REPO_NAME, err)
        self.assertNotIn("Could not resolve", err)
        self.assertEqual(self.written_files(), [])

    def test_a_url_error_is_not_relayed_to_the_output(self):
        def transport(url, payload, headers):
            raise stats_api.ApiError(
                "could not reach the GitHub API: <urlopen error "
                "https://api.github.com/repos/owner/%s>" % PLAIN_REPO_NAME
            )

        code, out, err = self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN}, transport=transport
        )
        self.assertEqual(code, 2)
        self.assertNotIn(PLAIN_REPO_NAME, out)
        self.assertNotIn(PLAIN_REPO_NAME, err)
        self.assertNotIn("https://", err)
        self.assertNotIn("urlopen", err)
        self.assertEqual(self.written_files(), [])

    def test_the_token_is_never_written_to_the_cards(self):
        def handler(document, variables, index):
            return {"errors": [{"message": "Bad credentials %s" % FAKE_TOKEN}]}

        code, out, err = self.run_cli(
            environ={"STATS_TOKEN": FAKE_TOKEN}, transport=FakeTransport(handler)
        )
        self.assertEqual(code, 2)
        for name in self.written_files():
            with open(os.path.join(self.out_dir, name), encoding="utf-8") as handle:
                self.assertNotIn(FAKE_TOKEN, handle.read())


if __name__ == "__main__":
    unittest.main()
