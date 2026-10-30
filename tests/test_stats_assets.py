"""Tests for the committed statistics cards and their README wiring.

The committed cards live in two valid states: ``pending`` (the placeholder
that announces the missing data) and ``ready`` (the cards of a successful
workflow run).  The suite has to accept both, because the workflow commits
the real cards as soon as it succeeds and every later scheduled run must
still pass.
"""

from __future__ import annotations

import io
import json
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree
from contextlib import redirect_stderr, redirect_stdout

from tests.card_contract import (
    PENDING_PLACEHOLDER_TEXT,
    PENDING_STATE,
    READY_STATE,
    VALID_STATES,
    CardContractError,
    contains_digits,
    is_pending,
    is_ready,
    state_of,
    violations,
)
from tests.helpers import REPO_ROOT, make_snapshot, stats_cli, stats_render

ASSETS_DIR = os.path.join(REPO_ROOT, "assets", "stats")
README = os.path.join(REPO_ROOT, "README.md")

CARD_NAMES = ("contributions.svg", "languages.svg")

MOBILE_WIDTH = 320
MAX_CARD_WIDTH = 440
MIN_CARD_WIDTH = 360
OLD_CARD_WIDTH = 480
MAX_EFFECTIVE_FONT_SIZE = 10.0

TOKEN_LIKE = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9]{10,255}|github_pat_[A-Za-z0-9_]{10,255})"
)


def elements(root, suffix):
    return [
        element for element in root.iter()
        if isinstance(element.tag, str) and element.tag.endswith(suffix)
    ]


def committed_cards():
    """Return the content of the two committed cards."""
    cards = {}
    for name in CARD_NAMES:
        with open(os.path.join(ASSETS_DIR, name), encoding="utf-8") as handle:
            cards[name] = handle.read()
    return cards


def pending_cards():
    """Return the placeholder cards the generator writes without a token."""
    return stats_render.render_pending_cards()


def ready_cards():
    """Return the cards the generator writes from a real snapshot."""
    return stats_render.render_cards(make_snapshot())


class CommittedCardTests(unittest.TestCase):
    def test_both_cards_are_committed(self):
        for name in ("contributions.svg", "languages.svg"):
            self.assertTrue(os.path.exists(os.path.join(ASSETS_DIR, name)), name)

    def test_the_committed_cards_are_valid_svg(self):
        for name in ("contributions.svg", "languages.svg"):
            with open(os.path.join(ASSETS_DIR, name), encoding="utf-8") as handle:
                root = ElementTree.fromstring(handle.read())
            self.assertTrue(root.tag.endswith("svg"), name)
            self.assertEqual(root.get("width"), "100%", name)
            self.assertTrue(root.get("viewBox"), name)

    def test_the_committed_cards_use_a_compact_view_box(self):
        """The cards sit side by side, so they are narrower than before."""
        for name in ("contributions.svg", "languages.svg"):
            with open(os.path.join(ASSETS_DIR, name), encoding="utf-8") as handle:
                root = ElementTree.fromstring(handle.read())
            width = float(root.get("viewBox").split()[2])
            self.assertLessEqual(width, MAX_CARD_WIDTH, name)
            self.assertGreaterEqual(width, MIN_CARD_WIDTH, name)
            self.assertLess(width, OLD_CARD_WIDTH, name)

    def test_the_committed_cards_stay_legible_on_a_320_pixel_screen(self):
        for name in ("contributions.svg", "languages.svg"):
            with open(os.path.join(ASSETS_DIR, name), encoding="utf-8") as handle:
                root = ElementTree.fromstring(handle.read())
            width = float(root.get("viewBox").split()[2])
            sizes = [
                float(element.get("font-size")) * MOBILE_WIDTH / width
                for element in elements(root, "text")
                if element.get("font-size")
            ]
            self.assertTrue(sizes, name)
            self.assertGreaterEqual(min(sizes), MAX_EFFECTIVE_FONT_SIZE, name)

    def test_the_committed_cards_declare_a_known_state(self):
        """A committed card is either pending or ready; nothing else."""
        for name, content in committed_cards().items():
            self.assertIn(state_of(content, name), VALID_STATES, name)

    def test_the_committed_cards_fulfil_the_card_contract(self):
        """The committed cards pass the very same contract as the new ones."""
        for name, content in committed_cards().items():
            self.assertEqual(violations(content, name), [], name)

    def test_the_committed_cards_use_english_copy_only(self):
        for name in ("contributions.svg", "languages.svg"):
            with open(os.path.join(ASSETS_DIR, name), encoding="utf-8") as handle:
                content = handle.read()
            for word in ("Contribuciones", "Lenguajes", "Públicas", "pendiente"):
                self.assertNotIn(word, content, "%s: %s" % (name, word))

    def test_the_committed_cards_do_not_show_the_asset_path(self):
        for name in ("contributions.svg", "languages.svg"):
            with open(os.path.join(ASSETS_DIR, name), encoding="utf-8") as handle:
                content = handle.read()
            self.assertNotIn("assets/stats", content, name)
            self.assertNotIn(".svg", content, name)

    def test_the_committed_cards_contain_no_token_material(self):
        for name in ("contributions.svg", "languages.svg"):
            with open(os.path.join(ASSETS_DIR, name), encoding="utf-8") as handle:
                content = handle.read()
            self.assertIsNone(TOKEN_LIKE.search(content), name)


class CardStateTests(unittest.TestCase):
    """The card contract holds for the committed and for the new cards."""

    def card_sets(self):
        return (
            ("committed", committed_cards()),
            ("generated pending", pending_cards()),
            ("generated ready", ready_cards()),
        )

    def test_every_card_declares_a_known_state(self):
        for label, cards in self.card_sets():
            for name, content in cards.items():
                self.assertIn(
                    state_of(content, name), VALID_STATES, "%s: %s" % (label, name)
                )

    def test_every_card_fulfils_the_contract(self):
        for label, cards in self.card_sets():
            for name, content in cards.items():
                self.assertEqual(
                    violations(content, name), [], "%s: %s" % (label, name)
                )

    def test_a_pending_card_is_honest_and_shows_no_number(self):
        pending = []
        for label, cards in self.card_sets():
            pending.extend(
                (label, name, content)
                for name, content in cards.items()
                if is_pending(content, name)
            )
        self.assertTrue(pending, "no pending card to check")
        for label, name, content in pending:
            self.assertIn("pending", content.lower(), "%s: %s" % (label, name))
            self.assertFalse(
                contains_digits(content), "%s: %s" % (label, name)
            )

    def test_a_ready_card_holds_the_real_data(self):
        """The generated ready cards show the numbers of the snapshot."""
        for name, content in ready_cards().items():
            self.assertTrue(contains_digits(content), name)

    def test_a_ready_card_never_announces_the_pending_state(self):
        ready = []
        for label, cards in self.card_sets():
            ready.extend(
                (label, name, content)
                for name, content in cards.items()
                if is_ready(content, name)
            )
        self.assertTrue(ready, "no ready card to check")
        for label, name, content in ready:
            self.assertNotIn(
                PENDING_PLACEHOLDER_TEXT.lower(), content.lower(),
                "%s: %s" % (label, name),
            )
            self.assertNotIn(
                "this card is pending", content.lower(),
                "%s: %s" % (label, name),
            )

    def test_an_unknown_state_is_rejected(self):
        broken = ready_cards()["contributions.svg"].replace(
            'data-state="ready"', 'data-state="unknown"', 1
        )
        with self.assertRaises(CardContractError):
            state_of(broken, "contributions.svg")
        self.assertNotEqual(violations(broken, "contributions.svg"), [])

    def test_a_missing_state_is_rejected(self):
        broken = ready_cards()["contributions.svg"].replace(
            ' data-state="ready"', "", 1
        )
        with self.assertRaises(CardContractError):
            state_of(broken, "contributions.svg")
        self.assertNotEqual(violations(broken, "contributions.svg"), [])

    def test_a_pending_card_that_shows_a_number_is_rejected(self):
        broken = pending_cards()["contributions.svg"].replace(
            "</svg>", '<text x="27" y="340" font-size="16">42</text></svg>', 1
        )
        problems = violations(broken, "contributions.svg")
        self.assertTrue(
            any("must not show any number" in problem for problem in problems),
            problems,
        )

    def test_a_ready_card_that_announces_the_pending_state_is_rejected(self):
        broken = ready_cards()["contributions.svg"].replace(
            "</svg>", "<desc>This card is pending</desc></svg>", 1
        )
        problems = violations(broken, "contributions.svg")
        self.assertTrue(
            any("must not announce the pending state" in problem for problem in problems),
            problems,
        )


class GeneratorPipelineTests(unittest.TestCase):
    """The generator writes cards that the card contract accepts."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out_dir = os.path.join(self._tmp.name, "assets", "stats")
        self.pending_out_dir = os.path.join(self._tmp.name, "pending", "assets", "stats")

    def run_cli(self, argv):
        """Run the generator and return its exit code."""
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return stats_cli.run(argv, environ={})

    def committed_bytes(self):
        contents = {}
        for name in CARD_NAMES:
            with open(os.path.join(ASSETS_DIR, name), "rb") as handle:
                contents[name] = handle.read()
        return contents

    def test_the_generator_writes_ready_cards_that_fulfil_the_contract(self):
        snapshot_path = os.path.join(self._tmp.name, "snapshot.json")
        with open(snapshot_path, "w", encoding="utf-8") as handle:
            json.dump(make_snapshot(), handle)
        exit_code = self.run_cli(
            ["--snapshot", snapshot_path, "--out-dir", self.out_dir]
        )
        self.assertEqual(exit_code, 0)
        for name in CARD_NAMES:
            path = os.path.join(self.out_dir, name)
            self.assertTrue(os.path.exists(path), name)
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertEqual(state_of(content, name), READY_STATE, name)
            self.assertEqual(violations(content, name), [], name)

    def test_the_generator_writes_pending_cards_that_fulfil_the_contract(self):
        exit_code = self.run_cli(
            ["--pending", "--out-dir", self.pending_out_dir]
        )
        self.assertEqual(exit_code, 0)
        for name in CARD_NAMES:
            path = os.path.join(self.pending_out_dir, name)
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertEqual(state_of(content, name), PENDING_STATE, name)
            self.assertEqual(violations(content, name), [], name)

    def test_the_committed_cards_are_never_mutated_by_the_tests(self):
        before = self.committed_bytes()
        pending_cards()
        ready_cards()
        snapshot_path = os.path.join(self._tmp.name, "snapshot.json")
        with open(snapshot_path, "w", encoding="utf-8") as handle:
            json.dump(make_snapshot(), handle)
        self.run_cli(["--snapshot", snapshot_path, "--out-dir", self.out_dir])
        self.run_cli(["--pending", "--out-dir", self.pending_out_dir])
        self.assertEqual(self.committed_bytes(), before)


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        with open(README, encoding="utf-8") as handle:
            self.readme = handle.read()

    def test_the_readme_shows_both_cards(self):
        self.assertIn("assets/stats/contributions.svg", self.readme)
        self.assertIn("assets/stats/languages.svg", self.readme)

    def test_the_readme_shows_the_cards_in_one_centered_paragraph(self):
        """Both cards are inline images of a single centered paragraph."""
        paragraph = self._stats_paragraph()
        self.assertIsNotNone(paragraph)
        self.assertTrue(paragraph.startswith("<p align=\"center\">"), paragraph)
        self.assertIn("assets/stats/contributions.svg", paragraph)
        self.assertIn("assets/stats/languages.svg", paragraph)

    def test_the_readme_does_not_use_a_table_for_the_cards(self):
        """A table would forbid the natural wrapping of the two images."""
        paragraph = self._stats_paragraph()
        self.assertIsNotNone(paragraph)
        for markup in ("<table", "<tr", "<td"):
            self.assertNotIn(markup, paragraph, markup)

    def test_the_readme_cards_keep_a_fixed_width(self):
        """A fixed width keeps the cards legible on a narrow screen."""
        for path in ("assets/stats/contributions.svg", "assets/stats/languages.svg"):
            tag = self._img_tag(path)
            match = re.search(r'width="(\d+)"', tag)
            self.assertIsNotNone(match, tag)
            width = int(match.group(1))
            self.assertEqual(width, 320, path)

    def test_the_readme_does_not_promise_a_mobile_stack(self):
        """The README must not promise a behaviour that was not verified."""
        paragraph = (self._stats_paragraph() or "").lower()
        for promise in ("stack", "one below the other", "responsive",
                        "guaranteed"):
            self.assertNotIn(promise, paragraph)

    def test_the_readme_no_longer_uses_the_external_stats_service(self):
        self.assertNotIn("github-readme-stats", self.readme)

    def _img_tag(self, path):
        index = self.readme.index(path)
        start = self.readme.rindex("<img", 0, index)
        end = self.readme.index(">", index)
        return self.readme[start:end]

    def _stats_paragraph(self):
        """Return the paragraph that holds both cards, or ``None``."""
        for block in self.readme.split("<p")[1:]:
            paragraph = "<p" + block.split("</p>")[0]
            if ("assets/stats/contributions.svg" in paragraph
                    and "assets/stats/languages.svg" in paragraph):
                return paragraph
        return None


if __name__ == "__main__":
    unittest.main()
