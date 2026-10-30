"""Tests for the scheduled workflow: pinning, least privilege and safety."""

from __future__ import annotations

import os
import re
import unittest

from tests.helpers import REPO_ROOT

WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "stats.yml")

SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        with open(WORKFLOW, encoding="utf-8") as handle:
            self.text = handle.read()

    def test_the_workflow_exists(self):
        self.assertTrue(os.path.exists(WORKFLOW))

    def test_every_action_is_pinned_to_an_immutable_commit_sha(self):
        uses = re.findall(r"uses:\s*([^\s#]+)", self.text)
        self.assertTrue(uses)
        for reference in uses:
            self.assertIn("@", reference, reference)
            name, _, sha = reference.partition("@")
            self.assertRegex(sha, SHA_PATTERN, reference)
            # the human readable version stays in a comment next to the pin
            self.assertRegex(
                self.text,
                r"%s@[0-9a-f]{40}\s*#\s*v[0-9]" % re.escape(name),
                "the pinned action %s must document its version" % name,
            )

    def test_the_workflow_keeps_the_least_privileges(self):
        blocks = re.findall(r"^permissions:\s*$", self.text, re.M)
        self.assertTrue(blocks)
        permissions = re.findall(
            r"permissions:\s*\n((?:\s{2,}[a-z-]+:\s*[a-z]+\n)+)", self.text
        )
        self.assertTrue(permissions)
        for block in permissions:
            keys = re.findall(r"^\s+([a-z-]+):", block, re.M)
            self.assertEqual(keys, ["contents"], block)
            self.assertIn("contents: write", block)

    def test_no_other_token_is_exposed(self):
        for line in self.text.splitlines():
            if "GITHUB_TOKEN" in line and "secrets.GITHUB_TOKEN" not in line:
                self.fail("the workflow must not use GITHUB_TOKEN: %s" % line)

    def test_the_token_is_only_taken_from_the_secret(self):
        self.assertIn("STATS_TOKEN: ${{ secrets.STATS_TOKEN }}", self.text)

    def test_the_workflow_only_commits_the_cards(self):
        self.assertIn("git add assets/stats", self.text)
        self.assertNotIn("git add .", self.text)
        self.assertNotIn("git add -A", self.text)

    def test_the_workflow_runs_the_tests_before_generating(self):
        self.assertLess(
            self.text.index("unittest discover"),
            self.text.index("generate_stats.py"),
        )


if __name__ == "__main__":
    unittest.main()
