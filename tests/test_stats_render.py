"""Tests for the SVG rendering of the two statistics cards.

The cards are compact (spec S8): the contributions card shows the real
metrics as coloured mini tiles instead of the daily calendar that GitHub
already draws itself, and the languages card is a compact list.  Both cards
are meant to sit **side by side** in the README, so they have a similar
height and a width that fits into half of a desktop column.
"""

from __future__ import annotations

import copy
import unittest
import xml.etree.ElementTree as ElementTree

from tests.helpers import (
    PRIVATE_REPO_NAME,
    PUBLIC_REPO_NAME,
    make_full_language_snapshot,
    make_snapshot,
    stats_aggregate,
    stats_render,
)

#: The width the cards have to stay readable at on a phone.
MOBILE_WIDTH = 320
#: Smallest effective font size (in screen pixels) that is still readable.
MIN_EFFECTIVE_FONT_SIZE = 10.0
#: The cards used to be 480 units wide; they have to be smaller now.
OLD_CARD_WIDTH = 480
#: Lower bound of the new, compact card width.
MIN_CARD_WIDTH = 360
#: Upper bound of the card width.
MAX_CARD_WIDTH = 440
#: Upper bound of the card height: the cards sit side by side.
MAX_CARD_HEIGHT = 420
#: Two cards side by side may differ in height by at most this many units.
MAX_HEIGHT_DIFFERENCE = 60

#: Words that must never appear in a rendered card any more: every visible
#: text is written in English.
SPANISH_COPY = (
    "Contribuciones",
    "Lenguajes",
    "Públicas",
    "privadas",
    "Actividad",
    "Menos",
    "Más",
    "Actualizado",
    "Datos agregados",
    "Datos pendientes",
    "Otros",
    "repositorios propios",
    "Sin datos todavía",
    "pendiente",
    "Ene",
    "Abr",
    "Ago",
    "Dic",
    "Lun",
    "Mié",
    "Vie",
)

#: The labels of the real metrics of the contributions card.
METRIC_LABELS = (
    "Contributions",
    "Commits",
    "Pull requests",
    "Issues",
    "Repositories",
    "Stars",
)

#: The marker a metric shows when its value can not be proven.
UNAVAILABLE = "—"


def elements(root, suffix):
    return [
        element for element in root.iter()
        if isinstance(element.tag, str) and element.tag.endswith(suffix)
    ]


def groups_with_class(root, name):
    return [
        element for element in root.iter()
        if isinstance(element.tag, str) and element.get("class") == name
    ]


def metric_bars(root):
    """Return the slim coloured bars of the metric tiles."""
    return groups_with_class(root, "metric-bar")


def view_box_width(root):
    return float(root.get("viewBox").split()[2])


def view_box_height(root):
    return float(root.get("viewBox").split()[3])


def effective_font_sizes(root):
    """Return the font size each text element has on a 320 pixel wide screen."""
    width = view_box_width(root)
    sizes = []
    for element in elements(root, "text"):
        size = element.get("font-size")
        if size is None:
            continue
        sizes.append(float(size) * MOBILE_WIDTH / width)
    return sizes


class CardStructureTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = make_snapshot()
        self.cards = stats_render.render_cards(self.snapshot)

    def test_two_separate_cards_are_rendered(self):
        self.assertEqual(
            sorted(self.cards), ["contributions.svg", "languages.svg"]
        )
        self.assertNotEqual(
            self.cards["contributions.svg"], self.cards["languages.svg"]
        )

    def test_the_cards_are_well_formed_xml(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            self.assertTrue(root.tag.endswith("svg"), name)

    def test_the_cards_are_responsive(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            self.assertEqual(root.get("width"), "100%", name)
            self.assertTrue(root.get("viewBox"), name)
            self.assertEqual(root.get("preserveAspectRatio"), "xMidYMid meet", name)

    def test_the_cards_declare_that_they_hold_real_data(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            self.assertEqual(root.get("data-state"), "ready", name)

    def test_the_contributions_card_shows_every_metric(self):
        content = self.cards["contributions.svg"]
        for label in METRIC_LABELS:
            self.assertIn(label, content)

    def test_no_card_shows_a_public_private_pill(self):
        for name, content in self.cards.items():
            self.assertNotIn("Públicas", content, name)
            self.assertNotIn("privadas", content, name)
            self.assertNotIn("#30263e", content, name)

    def test_every_visible_text_is_in_english(self):
        for name, content in self.cards.items():
            for word in SPANISH_COPY:
                self.assertNotIn(word, content, "%s: %s" % (name, word))

    def test_the_contributions_header_has_no_subtitle(self):
        root = ElementTree.fromstring(self.cards["contributions.svg"])
        labels = [
            (element.text or "").strip() for element in elements(root, "text")
        ]
        self.assertEqual(labels[0], "Contributions")
        self.assertFalse(
            any("weeks" in label for label in labels), labels
        )

    def test_the_contributions_footer_shows_only_the_update_date(self):
        root = ElementTree.fromstring(self.cards["contributions.svg"])
        labels = [
            (element.text or "").strip() for element in elements(root, "text")
        ]
        self.assertEqual(labels[-1], "Updated on 2026-10-30")
        self.assertNotIn("·", self.cards["contributions.svg"])

    def test_the_languages_header_shows_only_the_title(self):
        root = ElementTree.fromstring(self.cards["languages.svg"])
        labels = [
            (element.text or "").strip() for element in elements(root, "text")
        ]
        self.assertEqual(labels[0], "Languages")
        self.assertFalse(
            any("istribution" in label or "volume" in label for label in labels),
            labels,
        )

    def test_the_languages_card_has_no_footer(self):
        root = ElementTree.fromstring(self.cards["languages.svg"])
        labels = [
            (element.text or "").strip() for element in elements(root, "text")
        ]
        rows = len(stats_aggregate.language_percentages(self.snapshot, limit=8))
        # the title plus a name and a percentage per row, nothing else
        self.assertEqual(len(labels), 1 + 2 * rows)
        self.assertNotIn("Updated on", self.cards["languages.svg"])
        self.assertNotIn("·", self.cards["languages.svg"])

    def test_the_languages_card_lists_the_languages_with_their_share(self):
        content = self.cards["languages.svg"]
        self.assertIn("Java", content)
        self.assertIn("%", content)

    def test_the_cards_never_leak_repository_names(self):
        for content in self.cards.values():
            self.assertNotIn(PRIVATE_REPO_NAME, content)
            self.assertNotIn(PUBLIC_REPO_NAME, content)

    def test_the_cards_have_no_pixel_art_effect(self):
        for content in self.cards.values():
            self.assertNotIn("shape-rendering", content)
            self.assertNotIn("crispEdges", content)
            self.assertNotIn("<pattern", content)


class MetricTileTests(unittest.TestCase):
    """The contributions card shows the metrics as coloured mini tiles."""

    def setUp(self):
        self.snapshot = make_snapshot()
        self.root = ElementTree.fromstring(
            stats_render.render_contributions_card(self.snapshot)
        )
        self.tiles = groups_with_class(self.root, "metric-tile")

    def test_every_metric_has_its_own_tile(self):
        labels = [tile.get("data-metric") for tile in self.tiles]
        self.assertEqual(labels, list(METRIC_LABELS))

    def test_every_tile_shows_the_label_and_the_number(self):
        for tile in self.tiles:
            texts = [
                (element.text or "").strip()
                for element in elements(tile, "text")
            ]
            self.assertIn(tile.get("data-metric"), texts)
            values = [
                value for value in texts
                if value.isdigit() or value == UNAVAILABLE
            ]
            self.assertEqual(len(values), 1, texts)

    def test_tile_labels_are_larger_and_separated_from_values(self):
        for tile in self.tiles:
            label, value = elements(tile, "text")
            self.assertEqual(float(label.get("font-size")), 15)
            self.assertGreaterEqual(float(value.get("y")) - float(label.get("y")), 32)

    def test_every_tile_has_its_own_colour(self):
        colours = []
        for tile in self.tiles:
            bars = metric_bars(tile)
            self.assertEqual(len(bars), 1, tile.get("data-metric"))
            colour = bars[0].get("fill")
            self.assertRegex(colour, r"^#[0-9a-fA-F]{6}$")
            colours.append(colour)
        self.assertEqual(len(set(colours)), len(colours))

    def test_the_number_of_a_tile_is_painted_in_its_colour(self):
        for tile in self.tiles:
            colour = metric_bars(tile)[0].get("fill")
            numbers = [
                element for element in elements(tile, "text")
                if (element.text or "").strip().isdigit()
            ]
            self.assertEqual(numbers[0].get("fill"), colour)

    def test_the_tiles_show_the_real_values_of_the_snapshot(self):
        contributions = self.snapshot["contributions"]
        expected = {
            "Contributions": contributions["total"],
            "Commits": contributions["commits"],
            "Pull requests": contributions["pull_requests"],
            "Issues": contributions["issues"],
            "Repositories": contributions["repositories"],
            "Stars": self.snapshot["stars"],
        }
        for tile in self.tiles:
            numbers = [
                (element.text or "").strip()
                for element in elements(tile, "text")
                if (element.text or "").strip().isdigit()
            ]
            self.assertEqual(
                numbers[0], "{:,}".format(expected[tile.get("data-metric")])
            )

    def test_the_contributions_card_has_no_calendar(self):
        """The daily grid duplicates the one GitHub draws itself (S8)."""
        content = stats_render.render_contributions_card(self.snapshot)
        self.assertNotIn("calendar-block", content)
        self.assertNotIn("Daily activity", content)
        self.assertNotIn("Less", content)
        self.assertNotIn("More", content)
        self.assertEqual(groups_with_class(self.root, "calendar-block"), [])


class MetricBarTests(unittest.TestCase):
    """The dots of the tiles became slim vertical bars (spec S10)."""

    def setUp(self):
        self.snapshot = make_snapshot()
        self.root = ElementTree.fromstring(
            stats_render.render_contributions_card(self.snapshot)
        )
        self.bars = metric_bars(self.root)

    def test_the_tiles_hold_no_dot_any_more(self):
        self.assertEqual(elements(self.root, "circle"), [])

    def test_every_tile_holds_exactly_one_bar(self):
        self.assertEqual(len(self.bars), len(METRIC_LABELS))

    def test_the_bars_are_slim_and_vertical(self):
        for bar in self.bars:
            width = float(bar.get("width"))
            height = float(bar.get("height"))
            self.assertLessEqual(width, 8.0)
            self.assertGreater(height, width * 3)

    def test_the_bars_keep_the_colour_of_their_metric(self):
        colours = {}
        for tile in groups_with_class(self.root, "metric-tile"):
            colours[tile.get("data-metric")] = metric_bars(tile)[0].get("fill")
        self.assertEqual(len(set(colours.values())), len(colours))

    def test_the_bars_stay_inside_their_tile(self):
        for tile in groups_with_class(self.root, "metric-tile"):
            background = elements(tile, "rect")[0]
            bar = metric_bars(tile)[0]
            self.assertGreaterEqual(float(bar.get("x")), float(background.get("x")))
            self.assertLessEqual(
                float(bar.get("x")) + float(bar.get("width")),
                float(background.get("x")) + float(background.get("width")),
            )
            self.assertGreaterEqual(float(bar.get("y")), float(background.get("y")))
            self.assertLessEqual(
                float(bar.get("y")) + float(bar.get("height")),
                float(background.get("y")) + float(background.get("height")),
            )


class StarMetricTests(unittest.TestCase):
    """S10: the stars of the owned repositories are a metric of the card."""

    def setUp(self):
        self.snapshot = make_snapshot()
        self.root = ElementTree.fromstring(
            stats_render.render_contributions_card(self.snapshot)
        )
        self.tiles = groups_with_class(self.root, "metric-tile")

    def tile(self, label):
        for tile in self.tiles:
            if tile.get("data-metric") == label:
                return tile
        self.fail("the card has no %s tile" % label)

    def test_the_card_shows_a_stars_tile(self):
        self.assertIn("Stars", [tile.get("data-metric") for tile in self.tiles])

    def test_the_stars_tile_shows_the_sum_of_the_snapshot(self):
        tile = self.tile("Stars")
        values = [
            (element.text or "").strip()
            for element in elements(tile, "text")
            if (element.text or "").strip().isdigit()
        ]
        self.assertEqual(values, ["{:,}".format(self.snapshot["stars"])])

    def test_a_snapshot_without_stars_shows_the_unavailable_marker(self):
        """No star figure may be invented: the tile says it is unavailable."""
        snapshot = copy.deepcopy(self.snapshot)
        del snapshot["stars"]
        root = ElementTree.fromstring(
            stats_render.render_contributions_card(snapshot)
        )
        stars = [
            tile for tile in groups_with_class(root, "metric-tile")
            if tile.get("data-metric") == "Stars"
        ][0]
        values = [
            (element.text or "").strip()
            for element in elements(stars, "text")
            if (element.text or "").strip() != "Stars"
        ]
        self.assertEqual(values, [UNAVAILABLE])

    def test_the_unavailable_marker_is_not_a_number(self):
        snapshot = copy.deepcopy(self.snapshot)
        del snapshot["stars"]
        content = stats_render.render_contributions_card(snapshot)
        root = ElementTree.fromstring(content)
        for tile in groups_with_class(root, "metric-tile"):
            if tile.get("data-metric") != "Stars":
                continue
            for element in elements(tile, "text"):
                value = (element.text or "").strip()
                if value == "Stars":
                    continue
                self.assertFalse(any(c.isdigit() for c in value), value)

    def test_the_other_metrics_keep_their_window_semantics(self):
        """Only the stars are added: the other figures are untouched."""
        contributions = self.snapshot["contributions"]
        for label, key in (
            ("Contributions", "total"),
            ("Commits", "commits"),
            ("Pull requests", "pull_requests"),
            ("Issues", "issues"),
            ("Repositories", "repositories"),
        ):
            values = [
                (element.text or "").strip()
                for element in elements(self.tile(label), "text")
                if (element.text or "").strip().isdigit()
            ]
            self.assertEqual(values, ["{:,}".format(contributions[key])], label)


class CompactCardTests(unittest.TestCase):
    """Both cards are small enough to sit side by side (spec S8)."""

    def setUp(self):
        self.cards = stats_render.render_cards(make_full_language_snapshot())

    def test_the_cards_are_smaller_than_the_previous_480_units(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            width = view_box_width(root)
            self.assertLess(width, OLD_CARD_WIDTH, name)
            self.assertGreaterEqual(width, MIN_CARD_WIDTH, name)
            self.assertLessEqual(width, MAX_CARD_WIDTH, name)

    def test_the_cards_are_shorter_than_the_previous_layout(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            self.assertLessEqual(view_box_height(root), MAX_CARD_HEIGHT, name)

    def test_both_cards_have_a_similar_height(self):
        """Side by side, the cards must not look like a staircase."""
        heights = {}
        for name, content in self.cards.items():
            heights[name] = view_box_height(ElementTree.fromstring(content))
        difference = abs(heights["contributions.svg"] - heights["languages.svg"])
        self.assertLessEqual(difference, MAX_HEIGHT_DIFFERENCE, heights)

    def test_the_text_stays_legible_on_a_320_pixel_screen(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            sizes = effective_font_sizes(root)
            self.assertTrue(sizes, name)
            self.assertGreaterEqual(min(sizes), MIN_EFFECTIVE_FONT_SIZE, name)

    def test_the_languages_card_is_compact(self):
        """A compact list: one row per language, no empty space."""
        snapshot = make_full_language_snapshot()
        root = ElementTree.fromstring(
            stats_render.render_languages_card(snapshot)
        )
        rows = len(stats_aggregate.language_percentages(snapshot, limit=8))
        labels = [
            (element.text or "").strip() for element in elements(root, "text")
        ]
        self.assertEqual(len(labels), 1 + 2 * rows)
        self.assertLessEqual(view_box_height(root), MAX_CARD_HEIGHT)


class EscapingTests(unittest.TestCase):
    def test_untrusted_language_names_are_escaped(self):
        snapshot = copy.deepcopy(make_snapshot())
        snapshot["languages"].insert(
            0,
            {
                "name": "<b>&x</b>",
                "size": 999999,
                "color": "#123456",
            },
        )
        content = stats_render.render_languages_card(snapshot)
        self.assertNotIn("<b>", content)
        self.assertIn("&lt;b&gt;", content)
        self.assertIn("&amp;", content)
        ElementTree.fromstring(content)

    def test_untrusted_language_names_cannot_inject_a_script(self):
        snapshot = copy.deepcopy(make_snapshot())
        snapshot["languages"].insert(
            0,
            {
                "name": "<script>alert('x')</script> & \"quoted\"",
                "size": 999999,
                "color": "#123456",
            },
        )
        content = stats_render.render_languages_card(snapshot)
        self.assertNotIn("<script>", content)
        self.assertNotIn("</script>", content)
        ElementTree.fromstring(content)

    def test_long_language_names_are_truncated(self):
        snapshot = copy.deepcopy(make_snapshot())
        snapshot["languages"].insert(
            0, {"name": "A very long language name", "size": 999999, "color": "#123456"}
        )
        content = stats_render.render_languages_card(snapshot)
        self.assertNotIn("A very long language name", content)
        ElementTree.fromstring(content)

    def test_untrusted_colors_fall_back_to_a_safe_palette(self):
        snapshot = copy.deepcopy(make_snapshot())
        snapshot["languages"][0]["color"] = 'url("javascript:alert(1)")'
        content = stats_render.render_languages_card(snapshot)
        self.assertNotIn("javascript:", content)
        ElementTree.fromstring(content)

    def test_the_escape_helper_covers_the_dangerous_characters(self):
        escaped = stats_render.escape("<a href=\"x\">&'</a>")
        self.assertNotIn("<", escaped)
        self.assertNotIn(">", escaped)
        self.assertIn("&lt;", escaped)
        self.assertIn("&amp;", escaped)
        self.assertIn("&quot;", escaped)
        self.assertIn("&apos;", escaped)


class PendingCardTests(unittest.TestCase):
    def setUp(self):
        self.cards = stats_render.render_pending_cards()

    def test_two_pending_cards_are_rendered(self):
        self.assertEqual(
            sorted(self.cards), ["contributions.svg", "languages.svg"]
        )

    def test_the_pending_cards_announce_the_missing_data(self):
        for name, content in self.cards.items():
            self.assertIn("pending", content.lower(), name)
            root = ElementTree.fromstring(content)
            self.assertEqual(root.get("data-state"), "pending", name)

    def test_the_pending_cards_use_english_copy_only(self):
        for name, content in self.cards.items():
            for word in SPANISH_COPY:
                self.assertNotIn(word, content, "%s: %s" % (name, word))

    def test_the_pending_cards_have_the_width_of_the_real_ones(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            self.assertGreaterEqual(view_box_width(root), MIN_CARD_WIDTH, name)
            self.assertLessEqual(view_box_width(root), MAX_CARD_WIDTH, name)

    def test_the_pending_cards_do_not_show_the_asset_path(self):
        """The placeholder has no footer at all, not even the file path."""
        for name, content in self.cards.items():
            self.assertNotIn("assets/stats", content, name)
            self.assertNotIn(".svg", content, name)

    def test_the_pending_cards_show_no_statistics(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            for element in elements(root, "text"):
                self.assertFalse(
                    any(character.isdigit() for character in (element.text or "")),
                    "%s: %r" % (name, element.text),
                )

    def test_the_pending_cards_are_valid_and_responsive(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            self.assertEqual(root.get("width"), "100%", name)
            self.assertLessEqual(view_box_width(root), MAX_CARD_WIDTH, name)
            self.assertTrue(effective_font_sizes(root), name)

    def test_the_pending_cards_stay_legible_on_a_320_pixel_screen(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            self.assertGreaterEqual(
                min(effective_font_sizes(root)), MIN_EFFECTIVE_FONT_SIZE, name
            )


if __name__ == "__main__":
    unittest.main()
