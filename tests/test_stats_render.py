"""Tests for the SVG rendering of the two statistics cards."""

from __future__ import annotations

import copy
import unittest
import xml.etree.ElementTree as ElementTree

from tests.helpers import (
    PRIVATE_REPO_NAME,
    PUBLIC_REPO_NAME,
    make_full_year_snapshot,
    make_snapshot,
    stats_aggregate,
    stats_render,
    weeks,
)

#: The width the cards have to stay readable at on a phone.
MOBILE_WIDTH = 320
#: Smallest effective font size (in screen pixels) that is still readable.
MIN_EFFECTIVE_FONT_SIZE = 10.0
#: The cards used to be 360 units wide; they have to be bigger now.
OLD_CARD_WIDTH = 360
#: Lower bound of the new, larger card width.
MIN_CARD_WIDTH = 440
#: Upper bound of the card width.
MAX_CARD_WIDTH = 520

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


def elements(root, suffix):
    return [
        element for element in root.iter()
        if isinstance(element.tag, str) and element.tag.endswith(suffix)
    ]


def view_box_width(root):
    return float(root.get("viewBox").split()[2])


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
        for label in (
            "Contributions", "Commits", "Pull requests", "Issues", "Repositories"
        ):
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


class MobileLegibilityTests(unittest.TestCase):
    def setUp(self):
        self.cards = stats_render.render_cards(make_full_year_snapshot())

    def test_the_cards_are_bigger_than_the_previous_360_units(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            width = view_box_width(root)
            self.assertGreaterEqual(width, MIN_CARD_WIDTH, name)
            self.assertLessEqual(width, MAX_CARD_WIDTH, name)
            self.assertGreater(width, OLD_CARD_WIDTH, name)

    def test_the_text_stays_legible_on_a_320_pixel_screen(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            sizes = effective_font_sizes(root)
            self.assertTrue(sizes, name)
            self.assertGreaterEqual(min(sizes), MIN_EFFECTIVE_FONT_SIZE, name)

    def test_the_metrics_are_stacked_vertically(self):
        root = ElementTree.fromstring(self.cards["contributions.svg"])
        positions = {}
        for element in elements(root, "text"):
            content = (element.text or "").strip()
            if content in ("Contributions", "Commits", "Pull requests", "Issues",
                           "Repositories"):
                positions[content] = float(element.get("y"))
        self.assertEqual(len(positions), 5)
        self.assertEqual(len(set(positions.values())), 5)

    def test_the_calendar_is_split_into_readable_blocks(self):
        root = ElementTree.fromstring(self.cards["contributions.svg"])
        blocks = [
            element for element in root.iter()
            if isinstance(element.tag, str)
            and element.get("class") == "calendar-block"
        ]
        self.assertGreaterEqual(len(blocks), 2)

    def test_a_full_year_calendar_is_split_into_several_blocks(self):
        snapshot = make_full_year_snapshot()
        root = ElementTree.fromstring(
            stats_render.render_contributions_card(snapshot)
        )
        blocks = [
            element for element in root.iter()
            if isinstance(element.tag, str)
            and element.get("class") == "calendar-block"
        ]
        self.assertGreaterEqual(len(blocks), 3)


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

    def test_the_pending_cards_are_as_big_as_the_real_ones(self):
        for name, content in self.cards.items():
            root = ElementTree.fromstring(content)
            self.assertGreaterEqual(view_box_width(root), MIN_CARD_WIDTH, name)

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
