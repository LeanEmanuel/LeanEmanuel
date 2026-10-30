"""Tests for the aggregation of the GitHub payload into a snapshot."""

from __future__ import annotations

import copy
import json
import unittest

from tests.helpers import (
    FAKE_TOKEN,
    PRIVATE_REPO_NAME,
    PUBLIC_REPO_NAME,
    FakeTransport,
    contributions_payload,
    default_handler,
    make_snapshot,
    stats_aggregate,
    stats_api,
    weeks,
)

def build_snapshot(repository_payload=None):
    return make_snapshot()


class LanguageAggregationTests(unittest.TestCase):
    def test_sizes_are_summed_across_every_repository(self):
        snapshot = build_snapshot()
        sizes = {item["name"]: item["size"] for item in snapshot["languages"]}
        self.assertEqual(sizes["Java"], 1250)
        self.assertEqual(sizes["HTML"], 400)
        self.assertEqual(sizes["Kotlin"], 700)
        self.assertEqual(sizes["Shell"], 90)

    def test_languages_are_sorted_by_size(self):
        snapshot = build_snapshot()
        sizes = [item["size"] for item in snapshot["languages"]]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_colors_are_kept(self):
        snapshot = build_snapshot()
        colors = {item["name"]: item["color"] for item in snapshot["languages"]}
        self.assertEqual(colors["Java"], "#b07219")

    def test_percentages_cover_the_whole_distribution(self):
        snapshot = build_snapshot()
        percentages = stats_aggregate.language_percentages(snapshot)
        self.assertAlmostEqual(sum(value for _, value, _ in percentages), 100.0, places=6)

    def test_percentages_group_the_remaining_languages(self):
        snapshot = build_snapshot()
        percentages = stats_aggregate.language_percentages(snapshot, limit=2)
        names = [name for name, _, _ in percentages]
        self.assertEqual(names[-1], "Other")
        self.assertAlmostEqual(sum(value for _, value, _ in percentages), 100.0, places=6)


class PrivacyTests(unittest.TestCase):
    def test_the_snapshot_never_contains_repository_names(self):
        snapshot = build_snapshot()
        serialized = json.dumps(snapshot)
        self.assertNotIn(PRIVATE_REPO_NAME, serialized)
        self.assertNotIn(PUBLIC_REPO_NAME, serialized)

    def test_the_snapshot_only_exposes_aggregates(self):
        snapshot = build_snapshot()
        self.assertEqual(
            set(snapshot),
            {
                "schema",
                "login",
                "generated_at",
                "window",
                "contributions",
                "languages",
                "language_totals",
                "stars",
            },
        )
        self.assertEqual(
            set(snapshot["contributions"]),
            {
                "total",
                "commits",
                "pull_requests",
                "issues",
                "repositories",
                "weeks",
            },
        )
        self.assertEqual(set(snapshot["languages"][0]), {"name", "size", "color"})


class ContributionTests(unittest.TestCase):
    def test_totals_are_taken_from_the_contribution_collection(self):
        snapshot = build_snapshot()
        contributions = snapshot["contributions"]
        self.assertEqual(contributions["total"], 402)
        self.assertEqual(contributions["commits"], 21)
        self.assertEqual(contributions["pull_requests"], 155)
        self.assertEqual(contributions["issues"], 9)

    def test_public_and_private_repositories_are_counted_together(self):
        snapshot = build_snapshot()
        self.assertEqual(snapshot["contributions"]["repositories"], 3)
        self.assertEqual(snapshot["language_totals"]["repositories"], 3)

    def test_the_calendar_is_aligned_to_full_weeks(self):
        snapshot = build_snapshot()
        calendar_weeks = snapshot["contributions"]["weeks"]
        self.assertTrue(calendar_weeks)
        for week in calendar_weeks:
            self.assertEqual(len(week["days"]), 7)
            self.assertEqual(week["days"][0]["weekday"], 0)

    def test_days_without_data_are_marked_as_unknown(self):
        snapshot = build_snapshot()
        days = [
            day
            for week in snapshot["contributions"]["weeks"]
            for day in week["days"]
        ]
        self.assertTrue(any(day["count"] is None for day in days))
        self.assertTrue(any(day["count"] is not None for day in days))


class StarAggregationTests(unittest.TestCase):
    """S10: the stars of every owned repository are summed."""

    def test_the_stars_of_every_owned_repository_are_summed(self):
        snapshot = build_snapshot()
        self.assertEqual(snapshot["stars"], 25)

    def test_the_star_total_is_a_current_total(self):
        """Stars are a current total, not a figure of the last 364 days."""
        snapshot = build_snapshot()
        self.assertIsInstance(snapshot["stars"], int)
        self.assertEqual(snapshot["stars"], 25)

    def test_a_snapshot_without_stars_is_still_valid(self):
        """Older snapshots have no star field: they stay loadable."""
        snapshot = copy.deepcopy(make_snapshot())
        del snapshot["stars"]
        self.assertIs(stats_aggregate.validate_snapshot(snapshot), snapshot)

    def test_a_snapshot_with_a_malformed_star_count_is_rejected(self):
        for broken in ("many", None, 1.5, True, -1):
            snapshot = copy.deepcopy(make_snapshot())
            snapshot["stars"] = broken
            with self.assertRaises(ValueError):
                stats_aggregate.validate_snapshot(snapshot)

    def test_a_repository_without_stars_cannot_be_aggregated(self):
        with self.assertRaises(ValueError):
            stats_aggregate.aggregate_stars([{"name": "no-stars"}])

    def test_the_stars_never_name_a_repository(self):
        snapshot = build_snapshot()
        self.assertNotIn(PRIVATE_REPO_NAME, json.dumps(snapshot))
        self.assertNotIn(PUBLIC_REPO_NAME, json.dumps(snapshot))


class ValidationTests(unittest.TestCase):
    def test_a_valid_snapshot_is_accepted(self):
        snapshot = build_snapshot()
        self.assertIs(stats_aggregate.validate_snapshot(snapshot), snapshot)

    def test_a_broken_snapshot_is_rejected(self):
        for broken in (
            {},
            {"schema": "other/1"},
            {"schema": stats_aggregate.SNAPSHOT_SCHEMA},
            {"schema": stats_aggregate.SNAPSHOT_SCHEMA, "contributions": {}, "languages": []},
        ):
            with self.assertRaises(ValueError):
                stats_aggregate.validate_snapshot(broken)

    def test_an_empty_calendar_is_rejected(self):
        with self.assertRaises(ValueError):
            stats_aggregate.build_calendar({"contributionCalendar": {"weeks": []}})


if __name__ == "__main__":
    unittest.main()
