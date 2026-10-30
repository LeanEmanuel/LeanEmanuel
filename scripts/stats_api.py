"""Read-only GitHub GraphQL access for the profile statistics cards.

Design rules enforced here:

* Only read-only queries are issued (profile, contributions and languages).
* The token is never logged, never written to disk and never included in an
  error message. Every message that leaves this module is scrubbed.
* No repository identifier is ever included in an error message either. The
  errors reach the public log of the GitHub workflow, so they describe the
  failure without naming the repository it happened on. The client fails
  closed: the text of an upstream error (and the reason of a network error)
  is never relayed, because it is untrusted and may carry a repository name
  that no heuristic can catch. Only the class of the failure and, for an
  HTTP answer, its status code are reported.
* The client fails closed: a missing token, an inadequate token, a transport
  error, a malformed payload or an incomplete pagination all raise
  :class:`StatsError` instead of returning partial data.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

GRAPHQL_URL = "https://api.github.com/graphql"
TOKEN_ENV = "STATS_TOKEN"

#: Classic PAT scopes that are mandatory for the private contribution data.
REQUIRED_CLASSIC_SCOPES = ("repo",)

#: Classic and fine-grained token shapes accepted by GitHub.
TOKEN_PATTERN = re.compile(
    r"^(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255})$"
)

#: Any token-looking substring is redacted, even if it is not the active token.
TOKEN_LIKE_PATTERN = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9]{10,255}|github_pat_[A-Za-z0-9_]{10,255})"
)

#: Placeholder that replaces every secret in a message.
REDACTED = "***"

#: Upper bound for any pagination loop; guards against a broken cursor.
MAX_PAGES = 500


class StatsError(Exception):
    """Base class for every error raised by the stats generator."""


class MissingTokenError(StatsError):
    """No token was provided."""


class InadequateTokenError(StatsError):
    """The token exists but cannot provide the requested data."""


class ApiError(StatsError):
    """The GitHub API answered with an error or an unusable payload."""


class TransportError(ApiError):
    """The GitHub API could not be reached at all."""


class PaginationError(StatsError):
    """Pagination did not deliver every page."""


#: The safe message of every error class. The upstream text is never part of
#: it: it is untrusted and may name a repository.
GENERIC_MESSAGES = {
    MissingTokenError: "a token is required to query the GitHub API",
    InadequateTokenError: (
        "the token was rejected by the GitHub API. Check that it is valid, "
        "not expired, and allowed to read your repositories."
    ),
    ApiError: "the GitHub API request failed",
    TransportError: "could not reach the GitHub API",
    PaginationError: "the pagination of the GitHub API did not complete",
}

#: The safe message of a GraphQL error that is not about the token.
GRAPH_ERROR_MESSAGE = "the GitHub API returned an error"


def scrub(text, token=None):
    """Return ``text`` without any token material."""
    value = "" if text is None else str(text)
    if token:
        value = value.replace(token, REDACTED)
    return TOKEN_LIKE_PATTERN.sub(REDACTED, value)


def generic_message(exc):
    """Return the safe message of ``exc``, without any upstream text."""
    return GENERIC_MESSAGES.get(type(exc), GENERIC_MESSAGES[ApiError])


def resolve_token(environ=None):
    """Return the token from ``STATS_TOKEN`` or fail closed."""
    env = os.environ if environ is None else environ
    raw = env.get(TOKEN_ENV) or ""
    token = raw.strip()
    if not token:
        raise MissingTokenError(
            "%s is not set. Export a GitHub token with read access to your "
            "repositories before running the generator." % TOKEN_ENV
        )
    if not TOKEN_PATTERN.match(token):
        raise InadequateTokenError(
            "%s does not look like a GitHub token (expected a classic "
            "'ghp_'/'gho_' token or a fine-grained 'github_pat_' token)."
            % TOKEN_ENV
        )
    return token


@dataclass
class HttpResponse:
    """Minimal HTTP response used by the transport."""

    status: int
    headers: dict = field(default_factory=dict)
    body: str = ""


def default_transport(url, payload, headers):
    """POST ``payload`` as JSON to ``url`` using the standard library only."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return HttpResponse(
                response.status, dict(response.headers), response.read().decode("utf-8")
            )
    except urllib.error.HTTPError as exc:  # non 2xx answers are still payload
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:  # pragma: no cover - defensive
            body = ""
        return HttpResponse(exc.code, dict(exc.headers or {}), body)
    except urllib.error.URLError:
        # The reason of a network error can carry a URL: it is never relayed.
        raise TransportError("could not reach the GitHub API")


CONTRIBUTIONS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalRepositoryContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks {
          firstDay
          contributionDays { contributionCount date weekday }
        }
      }
    }
  }
}
"""

REPOSITORIES_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(
      first: 50
      after: $after
      ownerAffiliations: OWNER
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        isArchived
        languages(first: 100, orderBy: {field: SIZE, direction: DESC}) {
          totalSize
          pageInfo { hasNextPage endCursor }
          edges { cursor size node { name color } }
        }
      }
    }
  }
}
"""

REPOSITORY_LANGUAGES_QUERY = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    languages(first: 100, after: $after, orderBy: {field: SIZE, direction: DESC}) {
      totalSize
      pageInfo { hasNextPage endCursor }
      edges { cursor size node { name color } }
    }
  }
}
"""

_INADEQUATE_MARKERS = (
    "bad credentials",
    "requires authentication",
    "resource not accessible",
    "token expired",
    "invalid signature",
)


class GitHubClient:
    """Small GraphQL client with pagination and fail-closed semantics."""

    def __init__(self, token, transport=None, url=GRAPHQL_URL):
        if not token:
            raise MissingTokenError("a token is required to query the GitHub API")
        self._token = token
        self._transport = transport or default_transport
        self._url = url

    # ------------------------------------------------------------------ core
    def _headers(self):
        return {
            "Authorization": "Bearer " + self._token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "profile-stats-card-generator",
        }

    def _check_scopes(self, headers):
        raw = None
        for key, value in (headers or {}).items():
            if key.lower() == "x-oauth-scopes":
                raw = value
                break
        if raw is None:
            # Fine-grained tokens do not expose OAuth scopes.
            return
        scopes = {part.strip() for part in raw.split(",") if part.strip()}
        missing = [scope for scope in REQUIRED_CLASSIC_SCOPES if scope not in scopes]
        if missing:
            raise InadequateTokenError(
                "the token is missing the required scope(s): %s. A token that "
                "can read your private repositories is needed to count private "
                "contributions." % ", ".join(missing)
            )

    def query(self, document, variables):
        """Run a GraphQL document and return its ``data`` object."""
        try:
            response = self._transport(
                self._url, {"query": document, "variables": variables}, self._headers()
            )
        except StatsError as exc:
            # The text of a transport failure is untrusted: it is replaced by
            # the safe message of its class.
            raise type(exc)(generic_message(exc))
        if response.status != 200:
            raise ApiError(
                "the GitHub API answered with HTTP %s" % response.status
            )
        self._check_scopes(response.headers)
        try:
            payload = json.loads(response.body)
        except ValueError:
            raise ApiError("the GitHub API returned a malformed response")
        if not isinstance(payload, dict):
            raise ApiError("the GitHub API returned an unexpected payload")
        errors = payload.get("errors")
        if errors:
            raise self._graph_error(errors)
        data = payload.get("data")
        if data is None:
            raise ApiError("the GitHub API returned no data")
        return data

    def _graph_error(self, errors):
        """Raise the error of a GraphQL answer without relaying its text.

        The upstream message is untrusted: it may name a repository in a way
        that no redaction could catch. Only the class of the failure is
        reported.
        """
        messages = []
        for error in errors:
            if isinstance(error, dict):
                messages.append(str(error.get("message", "")))
            else:
                messages.append(str(error))
        joined = " | ".join(m for m in messages if m)
        lowered = joined.lower()
        for marker in _INADEQUATE_MARKERS:
            if marker in lowered:
                raise InadequateTokenError(
                    GENERIC_MESSAGES[InadequateTokenError]
                )
        raise ApiError(GRAPH_ERROR_MESSAGE)

    # --------------------------------------------------------------- queries
    def fetch_contributions(self, login, date_from, date_to):
        """Return the contributions collection of ``login`` for the window."""
        data = self.query(
            CONTRIBUTIONS_QUERY,
            {"login": login, "from": date_from, "to": date_to},
        )
        user = data.get("user")
        if user is None:
            raise ApiError("the GitHub user '%s' was not found" % scrub(login))
        collection = user.get("contributionsCollection")
        if not collection:
            raise ApiError(
                "no contributions data was returned for '%s'. The token is "
                "probably not allowed to read this profile." % scrub(login)
            )
        calendar = collection.get("contributionCalendar")
        if not isinstance(calendar, dict):
            raise ApiError(
                "the contribution calendar is missing for '%s'. The token is "
                "probably not allowed to read this profile." % scrub(login)
            )
        if not calendar.get("weeks"):
            raise ApiError("the contribution calendar came back empty")
        return collection

    def fetch_owned_repositories(self, login):
        """Return every repository owned by ``login`` with all languages.

        Only repositories the user owns are requested (``ownerAffiliations:
        OWNER``). Forks are **included**: a fork the user created is a
        repository they own. Both the repository connection and the per
        repository language connection are paginated until the last page and
        a missing or malformed connection is rejected instead of being read
        as an empty one.
        """
        repositories = []
        total_count = None
        after = None
        pages = 0
        while True:
            pages += 1
            if pages > MAX_PAGES:
                raise PaginationError("too many repository pages; pagination aborted")
            data = self.query(
                REPOSITORIES_QUERY, {"login": login, "after": after}
            )
            user = data.get("user")
            if user is None:
                raise ApiError(
                    "the GitHub user '%s' was not found" % scrub(login)
                )
            connection = self._require_connection(
                user, "repositories", "the repositories connection is missing"
            )
            page_info = self._require_page_info(connection, "repositories")
            nodes = self._require_nodes(connection, "repositories")
            if total_count is None:
                total_count = connection.get("totalCount")
                if not isinstance(total_count, int):
                    raise ApiError(
                        "the repositories connection has no usable totalCount"
                    )
            for node in nodes:
                self._require_repository_node(node)
                repositories.append(node)
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")
            if not after:
                raise PaginationError("the repository pagination cursor is missing")

        if isinstance(total_count, int) and len(repositories) < total_count:
            raise PaginationError(
                "the repository pagination was incomplete: got %d of %d repositories"
                % (len(repositories), total_count)
            )

        for repository in repositories:
            self._fetch_all_languages(login, repository)
        return repositories

    # ------------------------------------------------------- strict payloads
    @staticmethod
    def _require_connection(parent, key, message):
        value = parent.get(key)
        if not isinstance(value, dict):
            raise ApiError(message)
        return value

    @staticmethod
    def _require_page_info(connection, label):
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict):
            raise ApiError(
                "the %s connection has no pageInfo; the payload is malformed"
                % label
            )
        if "hasNextPage" not in page_info:
            raise ApiError(
                "the %s connection has no hasNextPage flag; the payload is malformed"
                % label
            )
        return page_info

    @staticmethod
    def _require_nodes(connection, label):
        nodes = connection.get("nodes")
        if not isinstance(nodes, list):
            raise ApiError(
                "the %s connection has no node list; the payload is malformed" % label
            )
        return nodes

    def _require_repository_node(self, node):
        if not isinstance(node, dict):
            raise ApiError("the repositories connection holds a malformed node")
        name = node.get("name")
        if not isinstance(name, str) or not name:
            raise ApiError("a repository of the connection has no name")
        languages = node.get("languages")
        if not isinstance(languages, dict):
            raise ApiError("the languages connection of a repository is missing")
        self._require_page_info(languages, "languages")
        if not isinstance(languages.get("edges"), list):
            raise ApiError(
                "the languages connection of a repository has a malformed edge list"
            )

    def _fetch_all_languages(self, login, repository):
        name = repository.get("name")
        languages = repository.get("languages") or {}
        edges = list(languages.get("edges") or [])
        page_info = languages.get("pageInfo") or {}
        cursor = page_info.get("endCursor")
        pages = 0
        while page_info.get("hasNextPage"):
            pages += 1
            if pages > MAX_PAGES:
                raise PaginationError("too many language pages; pagination aborted")
            if not cursor:
                raise PaginationError("the language pagination cursor is missing")
            data = self.query(
                REPOSITORY_LANGUAGES_QUERY,
                {"owner": login, "name": name, "after": cursor},
            )
            node = data.get("repository")
            if not isinstance(node, dict):
                raise ApiError(
                    "a repository disappeared while reading its languages"
                )
            connection = node.get("languages")
            if not isinstance(connection, dict):
                raise ApiError(
                    "the languages connection of a repository is missing"
                )
            page_info = self._require_page_info(connection, "languages")
            extra_edges = connection.get("edges")
            if not isinstance(extra_edges, list):
                raise ApiError(
                    "the languages connection of a repository has a malformed "
                    "edge list"
                )
            edges.extend(extra_edges)
            cursor = page_info.get("endCursor")
        repository["language_edges"] = edges
        return edges
