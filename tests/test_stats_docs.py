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

    def test_the_layout_section_describes_the_side_by_side_layout(self):
        section = self.section("## 1.")
        self.assertIn("side by side", section)
        self.assertIn("tile", section)

    def test_the_layout_section_describes_the_inline_images(self):
        section = self.section("## 1.")
        self.assertIn("inline", section)
        self.assertIn("wrap", section)
        self.assertNotIn("<table", section)

    def test_the_layout_section_states_the_equal_height_of_both_cards(self):
        section = self.section("## 1.")
        self.assertIn("same height", section)
        self.assertIn("378", section)

    def test_the_layout_section_describes_the_rounded_panel(self):
        """No dark square may show behind the rounded border."""
        section = self.section("## 1.")
        self.assertIn("rounded", section)
        self.assertIn("transparent", section)

    def test_the_layout_section_describes_the_separation_of_the_cards(self):
        section = self.section("## 1.")
        self.assertIn("&nbsp;", section)
        self.assertIn("break opportunities", section)

    def test_the_layout_section_states_that_the_separation_needs_no_css(self):
        section = self.section("## 1.")
        self.assertIn("No CSS", section)

    def test_the_layout_section_states_that_the_github_rendering_is_not_verified(self):
        """The behaviour of the profile was not observed: do not claim it."""
        section = self.section("## 1.")
        self.assertIn("no media quer", section)
        self.assertIn("not been verified", section)

    def test_the_doc_does_not_claim_that_the_cards_stack_on_a_phone(self):
        """Every mention of stacking has to be a negation, never a promise."""
        self.assertNotIn("stack on top of each other", self.text)
        self.assertNotIn("stacked on a phone", self.text)
        for paragraph in self.text.split("\n\n"):
            if "stack" not in paragraph.lower():
                continue
            self.assertIn("cannot", paragraph.lower(), paragraph)
            self.assertIn("not been verified", paragraph.lower(), paragraph)

    def test_the_doc_describes_the_offline_regeneration(self):
        """The committed cards were rebuilt from the published aggregates."""
        section = self.section("## 4.")
        self.assertIn("offline", section.lower())
        self.assertIn("assets/stats/contributions.svg", section)


if __name__ == "__main__":
    unittest.main()
