"""Tests for the statistics documentation.

The documentation describes what the workflow does with its tokens. The
workflow itself uses the built-in `GITHUB_TOKEN` (through `actions/checkout`
and the push that follows it) and the separate, read-only `STATS_TOKEN`
secret for the GraphQL queries. The documentation must not claim otherwise.
"""

from __future__ import annotations

import os
import unittest

from tests.helpers import REPO_ROOT

DOC = os.path.join(REPO_ROOT, "docs", "stats.md")


class StatsDocTests(unittest.TestCase):
    def setUp(self):
        with open(DOC, encoding="utf-8") as handle:
            self.text = handle.read()

    def section(self, title):
        """Return the body of the section that starts with ``title``."""
        start = self.text.index(title)
        rest = self.text[start + len(title):]
        end = rest.find("\n## ")
        return rest if end == -1 else rest[:end]

    def test_the_doc_exists(self):
        self.assertTrue(os.path.exists(DOC))

    def test_the_workflow_section_does_not_claim_the_built_in_token_is_unused(self):
        section = self.section("## 5.")
        self.assertNotIn("never uses `GITHUB_TOKEN`", section)
        self.assertNotIn("never uses GITHUB_TOKEN", section)

    def test_the_workflow_section_distinguishes_the_two_tokens(self):
        section = self.section("## 5.")
        self.assertIn("GITHUB_TOKEN", section)
        self.assertIn("STATS_TOKEN", section)
        self.assertIn("read-only", section)

    def test_the_workflow_section_names_the_checkout_step(self):
        section = self.section("## 5.")
        self.assertIn("actions/checkout", section)

    def test_the_privacy_section_states_that_no_repository_name_is_logged(self):
        section = self.section("## 7.")
        self.assertIn("repository name", section)
        self.assertIn("error", section.lower())

    def test_the_privacy_section_states_that_the_upstream_text_is_not_relayed(self):
        section = self.section("## 7.")
        self.assertIn("upstream", section)
        self.assertIn("never relayed", section)

    def test_the_token_section_states_that_the_upstream_text_is_not_relayed(self):
        section = self.section("## 2.")
        self.assertIn("upstream", section)
        self.assertIn("never relayed", section)


if __name__ == "__main__":
    unittest.main()
