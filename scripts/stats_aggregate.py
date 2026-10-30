"""Aggregation of the GitHub payload into a publishable statistics snapshot.

The snapshot is the only artifact that reaches the renderer. It contains
aggregated numbers only: no repository names, no file names, no commit
messages and no per-repository raw data. Private repositories contribute to
the aggregates exactly like public ones, but their identity never leaves this
module.
"""

from __future__ import annotations

import datetime

SNAPSHOT_SCHEMA = "profile-stats-snapshot/1"


def _graphql_weekday(iso_date):
    """Return the GitHub weekday of an ISO date (0 = Sunday)."""
    day = datetime.date.fromisoformat(iso_date)
    return (day.weekday() + 1) % 7


def build_calendar(collection):
    """Return the contribution calendar as an aligned list of weeks.

    Each week holds seven days. Days without data are ``None`` and are not
    rendered, which keeps the heat map aligned to the real weeks of the
    contribution calendar.
    """
    calendar = collection.get("contributionCalendar") or {}
    counts = {}
    for week in calendar.get("weeks") or []:
        for day in week.get("contributionDays") or []:
            date = day.get("date")
            if not date:
                continue
            counts[date] = int(day.get("contributionCount") or 0)
    if not counts:
        raise ValueError("the contribution calendar is empty")

    dates = sorted(counts)
    first = datetime.date.fromisoformat(dates[0])
    last = datetime.date.fromisoformat(dates[-1])
    start = first - datetime.timedelta(days=_graphql_weekday(dates[0]))

    weeks = []
    current = start
    while current <= last:
        days = []
        for offset in range(7):
            day = current + datetime.timedelta(days=offset)
            iso = day.isoformat()
            days.append(
                {
                    "date": iso,
                    "count": counts.get(iso),
                    "weekday": (day.weekday() + 1) % 7,
                }
            )
        weeks.append({"first_day": current.isoformat(), "days": days})
        current += datetime.timedelta(days=7)
    return weeks


def aggregate_languages(repositories):
    """Sum the language sizes of every owned repository.

    ``repositories`` is the list returned by
    :meth:`stats_api.GitHubClient.fetch_owned_repositories`. Repository names
    are never copied into the result.
    """
    sizes = {}
    colors = {}
    for repository in repositories:
        for edge in repository.get("language_edges") or []:
            node = edge.get("node") or {}
            name = node.get("name")
            if not name:
                continue
            size = int(edge.get("size") or 0)
            sizes[name] = sizes.get(name, 0) + size
            color = node.get("color")
            if color and name not in colors:
                colors[name] = color
    languages = [
        {"name": name, "size": size, "color": colors.get(name)}
        for name, size in sizes.items()
    ]
    languages.sort(key=lambda item: (-item["size"], item["name"]))
    return languages


def aggregate_stars(repositories):
    """Sum the stargazers of every owned repository (spec S10).

    ``repositories`` is the list returned by
    :meth:`stats_api.GitHubClient.fetch_owned_repositories`.  Forks are
    included: a fork the user created is a repository they own, so its
    stars count like the stars of any other owned repository.

    The function fails closed: a repository whose star count is missing or
    malformed raises :class:`ValueError` instead of contributing zero,
    because a partial sum would be a wrong number.  Repository names are
    never copied into the result.
    """
    total = 0
    for repository in repositories:
        count = repository.get("stargazerCount")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("a repository has no usable stargazerCount")
        total += count
    return total


def build_snapshot(login, collection, repositories, generated_at=None, window=None):
    """Build the publishable snapshot from the raw GitHub payloads."""
    weeks = build_calendar(collection)
    languages = aggregate_languages(repositories)
    stars = aggregate_stars(repositories)
    calendar = collection.get("contributionCalendar") or {}
    total_bytes = sum(item["size"] for item in languages)

    snapshot = {
        "schema": SNAPSHOT_SCHEMA,
        "login": login,
        "generated_at": generated_at
        or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "window": window or {},
        "contributions": {
            "total": int(calendar.get("totalContributions") or 0),
            "commits": int(collection.get("totalCommitContributions") or 0),
            "pull_requests": int(collection.get("totalPullRequestContributions") or 0),
            "issues": int(collection.get("totalIssueContributions") or 0),
            "repositories": len(repositories),
            "weeks": weeks,
        },
        "languages": languages,
        "language_totals": {
            "languages": len(languages),
            "bytes": total_bytes,
            "repositories": len(repositories),
        },
        # The stars are a current total of the owned repositories, not a
        # figure of the contribution window (spec S10).
        "stars": stars,
    }
    return snapshot


def validate_snapshot(snapshot):
    """Validate a snapshot loaded from disk; raise ``ValueError`` if broken."""
    if not isinstance(snapshot, dict):
        raise ValueError("the snapshot must be a JSON object")
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("unsupported snapshot schema: %r" % snapshot.get("schema"))
    contributions = snapshot.get("contributions")
    if not isinstance(contributions, dict):
        raise ValueError("the snapshot has no contributions section")
    for key in ("total", "commits", "pull_requests", "issues", "repositories"):
        if not isinstance(contributions.get(key), int):
            raise ValueError("the snapshot has an invalid %s value" % key)
    if not isinstance(contributions.get("weeks"), list) or not contributions["weeks"]:
        raise ValueError("the snapshot has no contribution weeks")
    languages = snapshot.get("languages")
    if not isinstance(languages, list):
        raise ValueError("the snapshot has an invalid languages section")
    for language in languages:
        if not isinstance(language, dict) or not isinstance(language.get("name"), str):
            raise ValueError("the snapshot has an invalid language entry")
        if not isinstance(language.get("size"), int):
            raise ValueError("the snapshot has an invalid language size")
    # The star total is optional: a snapshot written before the stars were
    # added stays loadable, and the renderer then shows the stars as
    # unavailable instead of inventing a figure.  A star total that is
    # there but broken is rejected.
    if "stars" in snapshot:
        stars = snapshot["stars"]
        if isinstance(stars, bool) or not isinstance(stars, int) or stars < 0:
            raise ValueError("the snapshot has an invalid stars value")
    return snapshot


def language_percentages(snapshot, limit=None):
    """Return ``[(name, percentage, color)]`` sorted by size, biggest first."""
    languages = snapshot.get("languages") or []
    total = sum(item["size"] for item in languages)
    if total <= 0:
        return []
    entries = []
    for item in languages:
        percentage = 100.0 * item["size"] / total
        entries.append((item["name"], percentage, item.get("color")))
    if limit is not None and len(entries) > limit:
        head = entries[:limit]
        rest = entries[limit:]
        other = sum(item[1] for item in rest)
        head.append(("Other", other, None))
        return head
    return entries
