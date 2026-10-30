"""Shared helpers for the statistics generator tests.

The helpers provide a fake GraphQL transport so that every test is
deterministic and never touches the network or a real token.
"""

from __future__ import annotations

import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")

if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import stats_aggregate  # noqa: E402
import stats_api  # noqa: E402
import stats_cli  # noqa: E402
import stats_render  # noqa: E402
from stats_api import HttpResponse  # noqa: E402

#: A token shaped like a fine grained personal access token. It is a fake
#: value used to prove that it never reaches an output stream.
FAKE_TOKEN = "github_pat_11ABCDEFG0abcdefghijklmnopqrstuvwxyz0123456789"

PRIVATE_REPO_NAME = "super-secret-private-project"
PUBLIC_REPO_NAME = "public-showcase"

#: A repository name made of plain words: no dash, no digit, no underscore.
#: No heuristic can catch such a name, so an upstream message that carries it
#: must not be relayed at all.
PLAIN_REPO_NAME = "web"


def weeks(count=3, start="2026-01-01", per_week=7, last_week_days=3):
    """Return a deterministic contribution calendar.

    The first and the last week are partial on purpose: the real calendar
    returned by GitHub also starts and ends in the middle of a week.
    """
    import datetime

    first = datetime.date.fromisoformat(start)
    result = []
    for index in range(count):
        week_start = first + datetime.timedelta(days=7 * index)
        days = []
        length = per_week if index < count - 1 else last_week_days
        for offset in range(length):
            day = week_start + datetime.timedelta(days=offset)
            days.append(
                {
                    "contributionCount": (index + offset) % 4,
                    "date": day.isoformat(),
                    "weekday": (day.weekday() + 1) % 7,
                }
            )
        result.append({"firstDay": week_start.isoformat(), "contributionDays": days})
    return result


def contributions_payload(calendar_weeks=None):
    return {
        "data": {
            "user": {
                "login": "LeanEmanuel",
                "contributionsCollection": {
                    "totalCommitContributions": 21,
                    "totalIssueContributions": 9,
                    "totalPullRequestContributions": 155,
                    "totalRepositoryContributions": 2,
                    "restrictedContributionsCount": 380,
                    "contributionCalendar": {
                        "totalContributions": 402,
                        "weeks": calendar_weeks if calendar_weeks is not None else weeks(),
                    },
                },
            }
        }
    }


def language_edges(entries):
    """Build language edges; ``entries`` is a list of ``(name, size, color)``."""
    return [
        {
            "cursor": "lang-cursor-%d" % index,
            "size": size,
            "node": {"name": name, "color": color},
        }
        for index, (name, size, color) in enumerate(entries)
    ]


_UNSET = object()


def repository_node(name, languages, has_next_languages=False, end_cursor=_UNSET,
                    stars=0, is_fork=False):
    if end_cursor is _UNSET:
        end_cursor = "lang-cursor-%d" % max(len(languages) - 1, 0)
    return {
        "name": name,
        "isFork": is_fork,
        "isArchived": False,
        "stargazerCount": stars,
        "languages": {
            "totalSize": sum(size for _, size, _ in languages),
            "pageInfo": {
                "hasNextPage": has_next_languages,
                "endCursor": end_cursor,
            },
            "edges": language_edges(languages),
        },
    }


def repositories_payload(nodes, total_count=None, has_next_page=False, end_cursor=None):
    return {
        "data": {
            "user": {
                "repositories": {
                    "totalCount": total_count if total_count is not None else len(nodes),
                    "pageInfo": {
                        "hasNextPage": has_next_page,
                        "endCursor": end_cursor,
                    },
                    "nodes": nodes,
                }
            }
        }
    }


def repository_languages_payload(edges, has_next_page=False, end_cursor=None):
    return {
        "data": {
            "repository": {
                "languages": {
                    "totalSize": sum(edge["size"] for edge in edges),
                    "pageInfo": {
                        "hasNextPage": has_next_page,
                        "endCursor": end_cursor,
                    },
                    "edges": edges,
                }
            }
        }
    }


def make_snapshot():
    """Return a snapshot built from the deterministic default fixture."""
    transport = FakeTransport(default_handler())
    client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
    collection = client.fetch_contributions(
        "LeanEmanuel", "2026-01-01T00:00:00Z", "2026-12-31T00:00:00Z"
    )
    repositories = client.fetch_owned_repositories("LeanEmanuel")
    return stats_aggregate.build_snapshot(
        "LeanEmanuel",
        collection,
        repositories,
        generated_at="2026-10-30T00:00:00+00:00",
        window={
            "from": "2026-01-01T00:00:00+00:00",
            "to": "2026-12-31T00:00:00+00:00",
        },
    )


def make_full_year_snapshot():
    """Return a snapshot whose calendar covers a full year (53 weeks)."""
    snapshot = make_snapshot()
    snapshot["contributions"]["weeks"] = stats_aggregate.build_calendar(
        {"contributionCalendar": {"weeks": weeks(count=53, start="2025-10-26")}}
    )
    return snapshot


def make_full_language_snapshot():
    """Return a snapshot with nine languages.

    The real profile reports more than eight languages, so the languages
    card shows eight rows plus the aggregated ``Other`` row.  The fixture of
    the default snapshot is smaller; this one has the size of the real card.
    """
    snapshot = make_snapshot()
    snapshot["languages"] = list(snapshot["languages"]) + [
        {"name": "Language%d" % index, "size": 1000 - index, "color": "#123456"}
        for index in range(5)
    ]
    return snapshot


#: The values that the committed cards publish today.  They are the
#: aggregates of the last live run; the committed files are rebuilt from
#: them offline, so the numbers are preserved and never invented.
PUBLISHED_CONTRIBUTIONS = {
    "total": 393,
    "commits": 21,
    "pull_requests": 0,
    "issues": 0,
    "repositories": 38,
}

PUBLISHED_UPDATED_ON = "2026-10-30"

#: The published language rows: name, share (in percent) and colour.
PUBLISHED_LANGUAGES = (
    ("C#", 25.0, "#7355dd"),
    ("HTML", 23.9, "#e34c26"),
    ("Python", 17.5, "#3572A5"),
    ("Java", 7.7, "#b07219"),
    ("Kotlin", 5.7, "#A97BFF"),
    ("C++", 3.5, "#f34b7d"),
    ("Dart", 3.1, "#00B4AB"),
    ("CMake", 2.8, "#DA3434"),
)

#: The share of the languages that do not fit in the eight rows.
PUBLISHED_OTHER_SHARE = 10.9

#: The total number of bytes the published shares were computed from.
PUBLISHED_TOTAL_BYTES = 8000


def make_published_snapshot():
    """Return the snapshot that reproduces the committed cards exactly.

    The eight published language rows are rebuilt with byte sizes that
    reproduce the published shares exactly; the languages behind the
    aggregated ``Other`` row are unnamed entries that the renderer groups
    into the very same row.  No published number is replaced by a made up
    one.
    """
    sizes = {
        "C#": 1999,
        "HTML": 1911,
        "Python": 1399,
        "Java": 615,
        "Kotlin": 455,
        "C++": 279,
        "Dart": 247,
        "CMake": 223,
    }
    languages = [
        {"name": name, "size": size, "color": color}
        for name, size, color in (
            (name, sizes[name], color)
            for name, _, color in PUBLISHED_LANGUAGES
        )
    ]
    # The languages behind the "Other" row: five small entries that add up
    # to the published share of the row.
    for index, size in enumerate((200, 200, 180, 150, 142)):
        languages.append(
            {"name": "Unlisted%d" % index, "size": size, "color": None}
        )
    return {
        "schema": "profile-stats-snapshot/1",
        "login": "LeanEmanuel",
        "generated_at": PUBLISHED_UPDATED_ON + "T00:00:00+00:00",
        "window": {},
        "contributions": dict(
            PUBLISHED_CONTRIBUTIONS,
            weeks=[
                {
                    "first_day": "2026-01-05",
                    "days": [
                        {"date": "2026-01-05", "count": 0, "weekday": 1},
                    ],
                }
            ],
        ),
        "languages": languages,
        "language_totals": {
            "languages": len(languages),
            "bytes": PUBLISHED_TOTAL_BYTES,
            "repositories": PUBLISHED_CONTRIBUTIONS["repositories"],
        },
    }


class FakeTransport:
    """GraphQL transport double.

    ``handler`` receives ``(document, variables, call_index)`` and returns
    either a GraphQL payload (dict) or a ready :class:`HttpResponse`.
    """

    def __init__(self, handler):
        self.handler = handler
        self.calls = []
        self.headers_seen = []

    def __call__(self, url, payload, headers):
        self.calls.append(payload)
        self.headers_seen.append(headers)
        result = self.handler(
            payload["query"], payload.get("variables") or {}, len(self.calls)
        )
        if isinstance(result, HttpResponse):
            return result
        return HttpResponse(200, {}, json.dumps(result))


def default_handler(calendar_weeks=None):
    """Return a handler that serves a small but complete GitHub payload.

    The fixture contains two repository pages and one repository whose
    languages are split across two pages, so that every pagination path is
    exercised.
    """
    first_page = [
        repository_node(
            PUBLIC_REPO_NAME,
            [("Java", 1000, "#b07219"), ("HTML", 400, "#e34c26")],
            stars=12,
        ),
        repository_node(
            PRIVATE_REPO_NAME,
            [("Java", 250, "#b07219")],
            has_next_languages=True,
            end_cursor="lang-cursor-0",
            stars=5,
        ),
    ]
    second_page = [
        repository_node("kotlin-demo", [("Kotlin", 700, "#A97BFF")], stars=8),
    ]

    def handler(document, variables, index):
        if "contributionsCollection" in document:
            return contributions_payload(calendar_weeks)
        if "repositories(" in document:
            if variables.get("after") is None:
                return repositories_payload(
                    first_page, total_count=3, has_next_page=True, end_cursor="repo-cursor-1"
                )
            return repositories_payload(second_page, total_count=3, has_next_page=False)
        if "languages(" in document:
            return repository_languages_payload(
                language_edges([("Shell", 90, "#89e051")]),
                has_next_page=False,
            )
        raise AssertionError("unexpected GraphQL document")

    return handler
