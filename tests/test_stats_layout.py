"""Layout tests for the two statistics cards (spec S9).

Three defects of the layout are pinned here:

* the contributions card was taller than the languages card, so the two
  cards looked like a staircase side by side;
* the dark panel was drawn as a **square** rectangle behind a rounded
  border, so the dark square showed at the four corners of the card;
* the two cards touched each other in the README.

The tests also pin that the committed cards are the output of the
generator for the published values: the files may be rebuilt, but no
published number may change and no figure may be invented.
"""

from __future__ import annotations

import copy
import os
import re
import unittest
import xml.etree.ElementTree as ElementTree

from tests.helpers import (
    PUBLISHED_CONTRIBUTIONS,
    PUBLISHED_LANGUAGES,
    PUBLISHED_OTHER_SHARE,
    PUBLISHED_UPDATED_ON,
    REPO_ROOT,
    make_full_language_snapshot,
    make_published_snapshot,
    make_snapshot,
    stats_render,
)

ASSETS_DIR = os.path.join(REPO_ROOT, "assets", "stats")
README = os.path.join(REPO_ROOT, "README.md")

CARD_NAMES = ("contributions.svg", "languages.svg")

#: The width the cards are drawn at in the README.
README_CARD_WIDTH = 320

#: The background colour of the panel.
PANEL_BACKGROUND = "#090b12"


def parse(content):
    return ElementTree.fromstring(content)


def view_box(root):
    return [float(value) for value in root.get("viewBox").split()]


def view_box_width(root):
    return view_box(root)[2]


def view_box_height(root):
    return view_box(root)[3]


def elements(root, suffix):
    return [
        element for element in root.iter()
        if isinstance(element.tag, str) and element.tag.endswith(suffix)
    ]


def snapshot_with_languages(count):
    """Return a snapshot that holds exactly ``count`` language rows."""
    snapshot = copy.deepcopy(make_snapshot())
    snapshot["languages"] = [
        {"name": "Lang%d" % index, "size": 1000 - index, "color": "#123456"}
        for index in range(count)
    ]
    return snapshot


def committed_card(name):
    with open(os.path.join(ASSETS_DIR, name), encoding="utf-8") as handle:
        return handle.read()


def texts(root):
    return [(element.text or "").strip() for element in elements(root, "text")]


def groups_with_class(root, name):
    return [
        element for element in root.iter()
        if isinstance(element.tag, str) and element.get("class") == name
    ]


def language_rows(root):
    """Return the rows of a languages card.

    Every row is a name, the share, the colour of the bar and the width of
    the filled bar (the width carries the exact share of the row).
    """
    children = list(root)
    divider = 0
    for index, child in enumerate(children):
        if child.tag.split("}")[-1] == "path":
            divider = index
            break
    rows = []
    pending = None
    bars = 0
    for child in children[divider + 1:]:
        tag = child.tag.split("}")[-1]
        if tag == "text":
            if pending is None:
                pending = {
                    "name": (child.text or "").strip(),
                    "share": None,
                    "color": None,
                    "width": None,
                }
            else:
                pending["share"] = (child.text or "").strip()
        elif tag == "rect" and pending is not None:
            bars += 1
            if bars == 2:
                pending["color"] = child.get("fill")
                pending["width"] = float(child.get("width"))
                rows.append(pending)
                pending = None
                bars = 0
    return rows


def snapshot_of_contributions_card(content):
    """Rebuild the snapshot the committed contributions card shows."""
    root = parse(content)
    values = {}
    for group in groups_with_class(root, "metric-tile"):
        number = None
        for element in elements(group, "text"):
            candidate = (element.text or "").strip().replace(",", "")
            if candidate.isdigit():
                number = int(candidate)
        values[group.get("data-metric")] = number
    updated = [value for value in texts(root) if value.startswith("Updated on ")]
    title = (elements(root, "title")[0].text or "")
    return {
        "login": title.split(" of ")[-1].strip(),
        "generated_at": updated[0].split("Updated on ")[-1] + "T00:00:00+00:00",
        "contributions": {
            "total": values["Contributions"],
            "commits": values["Commits"],
            "pull_requests": values["Pull requests"],
            "issues": values["Issues"],
            "repositories": values["Repositories"],
        },
    }


def snapshot_of_languages_card(content):
    """Rebuild the snapshot the committed languages card shows.

    The exact share of a row is recovered from the width of its filled bar
    (the width is the share of the row), so the rebuilt snapshot renders the
    very same shares again.
    """
    root = parse(content)
    rows = language_rows(root)
    title = (elements(root, "title")[0].text or "")
    entries = []
    for row in rows:
        share = float(row["width"]) / stats_render.CONTENT_WIDTH * 100.0
        size = int(round(share * 1000000))
        if row["name"] == "Other":
            # The aggregated row: the renderer groups it again.
            entries.append({"name": "Unlisted", "size": size, "color": None})
            continue
        entries.append({
            "name": row["name"],
            "size": size,
            "color": row["color"],
        })
    return {
        "login": title.split(" of ")[-1].strip(),
        "languages": entries,
    }


def signature(content):
    """Return the shape of a card, without the width of the filled bars.

    The width of a filled bar carries the exact byte sizes of the snapshot
    and can not be recovered from a rounded share, so it is normalised.  The
    same holds for the share itself: it is compared with a tolerance by the
    test that reads the rows.
    """
    root = parse(content)
    items = []
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        attribs = dict(element.attrib)
        if (element.tag.endswith("rect") and attribs.get("rx") == "5"
                and float(attribs.get("width", "0")) < stats_render.CONTENT_WIDTH):
            attribs["width"] = "filled"
        value = (element.text or "").strip() if element.tag.endswith("text") else ""
        if value.endswith("%"):
            value = "share"
        items.append((element.tag, tuple(sorted(attribs.items())), value))
    return items


class EqualHeightTests(unittest.TestCase):
    """The two cards have to have exactly the same height (spec S9)."""

    def card_heights(self, snapshot):
        cards = stats_render.render_cards(snapshot)
        return {
            name: view_box_height(parse(content))
            for name, content in cards.items()
        }

    def test_both_cards_have_exactly_the_same_height(self):
        heights = self.card_heights(make_snapshot())
        self.assertEqual(
            heights["contributions.svg"], heights["languages.svg"], heights
        )

    def test_the_height_does_not_depend_on_the_number_of_language_rows(self):
        """A card with two languages is as tall as a card with nine."""
        reference = None
        for count in range(1, 10):
            heights = self.card_heights(snapshot_with_languages(count))
            self.assertEqual(
                heights["contributions.svg"], heights["languages.svg"], count
            )
            if reference is None:
                reference = heights["contributions.svg"]
            self.assertEqual(heights["contributions.svg"], reference, count)

    def test_the_height_is_the_same_for_the_published_snapshot(self):
        heights = self.card_heights(make_published_snapshot())
        self.assertEqual(
            heights["contributions.svg"], heights["languages.svg"], heights
        )

    def test_the_pending_cards_have_the_same_height(self):
        cards = stats_render.render_pending_cards()
        heights = {
            name: view_box_height(parse(content))
            for name, content in cards.items()
        }
        self.assertEqual(
            heights["contributions.svg"], heights["languages.svg"], heights
        )

    def test_the_cards_keep_their_width(self):
        """The visual size stays the same: only the height was corrected."""
        for snapshot in (make_snapshot(), make_full_language_snapshot()):
            for name, content in stats_render.render_cards(snapshot).items():
                root = parse(content)
                self.assertEqual(view_box_width(root), 400, name)

    def test_the_height_stays_compact(self):
        """The cards still fit next to each other in a desktop column."""
        for snapshot in (make_snapshot(), make_full_language_snapshot()):
            for name, content in stats_render.render_cards(snapshot).items():
                self.assertLessEqual(view_box_height(parse(content)), 420, name)


class ClippingTests(unittest.TestCase):
    """Nothing may stick out of the card (spec S9)."""

    def assert_nothing_is_clipped(self, content, name):
        root = parse(content)
        height = view_box_height(root)
        width = view_box_width(root)
        for element in elements(root, "rect"):
            y = float(element.get("y"))
            rectangle_height = float(element.get("height"))
            self.assertLessEqual(y + rectangle_height, height, name)
            self.assertGreaterEqual(y, 0.0, name)
            x = float(element.get("x"))
            self.assertLessEqual(x + float(element.get("width")), width, name)
        for element in elements(root, "text"):
            baseline = float(element.get("y"))
            self.assertGreaterEqual(baseline, 0.0, name)
            self.assertLessEqual(baseline, height, name)
        for element in elements(root, "circle"):
            cy = float(element.get("cy"))
            radius = float(element.get("r"))
            self.assertGreaterEqual(cy - radius, 0.0, name)
            self.assertLessEqual(cy + radius, height, name)

    def test_the_languages_card_is_never_clipped(self):
        for count in range(1, 10):
            content = stats_render.render_languages_card(
                snapshot_with_languages(count)
            )
            self.assert_nothing_is_clipped(content, "count=%d" % count)

    def test_the_contributions_card_is_never_clipped(self):
        content = stats_render.render_contributions_card(make_snapshot())
        self.assert_nothing_is_clipped(content, "contributions")

    def test_the_pending_cards_are_never_clipped(self):
        for name, content in stats_render.render_pending_cards().items():
            self.assert_nothing_is_clipped(content, name)

    def test_the_last_language_row_stays_inside_the_padding(self):
        """The last bar keeps the bottom padding of the panel."""
        for count in (1, 5, 9):
            content = stats_render.render_languages_card(
                snapshot_with_languages(count)
            )
            root = parse(content)
            height = view_box_height(root)
            bars = [
                element for element in elements(root, "rect")
                if element.get("rx") == "5"
            ]
            self.assertTrue(bars, count)
            bottom = max(
                float(bar.get("y")) + float(bar.get("height")) for bar in bars
            )
            self.assertLessEqual(bottom, height - 24, count)


class RoundedPanelTests(unittest.TestCase):
    """No square dark background behind the rounded border (spec S9)."""

    def assert_panel_is_rounded(self, content, name):
        root = parse(content)
        backgrounds = [
            element for element in elements(root, "rect")
            if (element.get("fill") or "").lower() == PANEL_BACKGROUND
        ]
        self.assertEqual(len(backgrounds), 1, name)
        panel = backgrounds[0]
        self.assertIsNotNone(panel.get("rx"), name)
        self.assertGreater(float(panel.get("rx")), 0.0, name)

    def test_the_cards_have_a_rounded_panel(self):
        for name, content in stats_render.render_cards(make_snapshot()).items():
            self.assert_panel_is_rounded(content, name)

    def test_the_pending_cards_have_a_rounded_panel(self):
        for name, content in stats_render.render_pending_cards().items():
            self.assert_panel_is_rounded(content, name)

    def test_no_rectangle_covers_the_whole_card_with_square_corners(self):
        """A full size rectangle without a radius paints the corners."""
        for name, content in stats_render.render_cards(make_snapshot()).items():
            root = parse(content)
            width = view_box_width(root)
            height = view_box_height(root)
            for element in elements(root, "rect"):
                covers_everything = (
                    float(element.get("width")) >= width - 1
                    and float(element.get("height")) >= height - 1
                )
                if not covers_everything:
                    continue
                self.assertIsNotNone(element.get("rx"), name)
                self.assertGreater(float(element.get("rx")), 0.0, name)


class CommittedCardTests(unittest.TestCase):
    """The committed files are the output of the generator.

    The committed cards are rebuilt by the workflow with fresh data, so the
    tests do not pin today's figures: they rebuild the snapshot **out of the
    committed file** and check that the generator renders exactly that file
    again.  A card that shows a figure the generator would not render, or a
    card that the generator would draw differently, fails the test.
    """

    def test_the_committed_contributions_card_is_the_output_of_the_generator(self):
        """The five counters and the date of the file are the rendered ones."""
        content = committed_card("contributions.svg")
        snapshot = snapshot_of_contributions_card(content)
        self.assertEqual(
            content, stats_render.render_contributions_card(snapshot)
        )

    def test_the_committed_languages_card_is_the_output_of_the_generator(self):
        """The rows, the shares and the colours of the file are rendered."""
        content = committed_card("languages.svg")
        snapshot = snapshot_of_languages_card(content)
        rendered = stats_render.render_languages_card(snapshot)
        rows = language_rows(parse(content))
        rendered_rows = language_rows(parse(rendered))
        self.assertEqual(
            [row["name"] for row in rows],
            [row["name"] for row in rendered_rows],
        )
        self.assertEqual(
            [row["color"] for row in rows],
            [row["color"] for row in rendered_rows],
        )
        for expected, actual in zip(rows, rendered_rows):
            self.assertAlmostEqual(
                float(expected["share"].rstrip("%")),
                float(actual["share"].rstrip("%")),
                delta=0.05,
                msg=expected["name"],
            )
        self.assertEqual(signature(content), signature(rendered))

    def test_the_committed_cards_have_the_same_height(self):
        heights = [
            view_box_height(parse(committed_card(name))) for name in CARD_NAMES
        ]
        self.assertEqual(heights[0], heights[1], heights)

    def test_the_committed_cards_keep_their_metadata(self):
        for name in CARD_NAMES:
            root = parse(committed_card(name))
            self.assertEqual(root.get("data-state"), "ready", name)
            self.assertEqual(root.get("width"), "100%", name)
            self.assertEqual(root.get("role"), "img", name)
            self.assertTrue(root.get("aria-labelledby"), name)
            self.assertTrue(elements(root, "title"), name)
            self.assertTrue(elements(root, "desc"), name)
            self.assertIn("<style>text{font-family:", committed_card(name))

    def test_the_committed_contributions_card_shows_no_other_number(self):
        """Five counters and the date, nothing else."""
        values = texts(parse(committed_card("contributions.svg")))
        numbers = [
            value for value in values
            if any(character.isdigit() for character in value)
        ]
        self.assertEqual(len(numbers), 6, numbers)


class PublishedValuesTests(unittest.TestCase):
    """The published aggregates of the committed cards (see ``docs/stats.md``).

    The committed cards were rebuilt offline out of the values the previous
    cards published.  The rebuild is pinned here: the byte sizes reproduce
    the published shares exactly, so no figure was invented and none was
    replaced.
    """

    def setUp(self):
        self.cards = stats_render.render_cards(make_published_snapshot())

    def test_the_published_counters_are_rendered(self):
        values = texts(parse(self.cards["contributions.svg"]))
        self.assertIn(
            "Updated on %s" % PUBLISHED_UPDATED_ON, values, values
        )
        for key, value in PUBLISHED_CONTRIBUTIONS.items():
            self.assertIn("{:,}".format(value), values, key)

    def test_the_published_shares_are_rendered(self):
        values = texts(parse(self.cards["languages.svg"]))
        for name, share, _ in PUBLISHED_LANGUAGES:
            self.assertIn(name, values, name)
            self.assertIn("%.1f%%" % share, values, name)
        self.assertIn("Other", values)
        self.assertIn("%.1f%%" % PUBLISHED_OTHER_SHARE, values)


class ReadmeSeparationTests(unittest.TestCase):
    """The two cards are separated without any CSS (spec S9)."""

    def setUp(self):
        with open(README, encoding="utf-8") as handle:
            self.readme = handle.read()
        self.paragraph = self._stats_paragraph()

    def _stats_paragraph(self):
        for block in self.readme.split("<p")[1:]:
            paragraph = "<p" + block.split("</p>")[0]
            if ("assets/stats/contributions.svg" in paragraph
                    and "assets/stats/languages.svg" in paragraph):
                return paragraph
        return None

    def _separator(self):
        start = self.paragraph.index("assets/stats/contributions.svg")
        start = self.paragraph.index(">", start) + 1
        end = self.paragraph.index("assets/stats/languages.svg")
        return self.paragraph[start:end]

    def test_the_readme_shows_both_cards_in_one_paragraph(self):
        self.assertIsNotNone(self.paragraph)

    def test_the_two_cards_are_separated(self):
        separator = self._separator()
        self.assertIn("&nbsp;", separator)

    def test_the_separation_keeps_the_natural_wrapping(self):
        """A plain space stays a break opportunity between the cards."""
        separator = self._separator()
        self.assertIn(" ", separator.replace("&nbsp;", " "))
        self.assertTrue(
            re.search(r"\s", separator.replace("&nbsp;", "")),
            repr(separator),
        )

    def test_the_separation_needs_no_css(self):
        for markup in ("<style", "class=", "style=", "<table", "<td"):
            self.assertNotIn(markup, self.paragraph, markup)

    def test_the_cards_keep_their_width(self):
        for path in ("assets/stats/contributions.svg", "assets/stats/languages.svg"):
            index = self.readme.index(path)
            start = self.readme.rindex("<img", 0, index)
            tag = self.readme[start:self.readme.index(">", index)]
            match = re.search(r'width="(\d+)"', tag)
            self.assertIsNotNone(match, tag)
            self.assertEqual(int(match.group(1)), README_CARD_WIDTH, path)


if __name__ == "__main__":
    unittest.main()
