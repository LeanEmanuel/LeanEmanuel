"""Tests for the GitHub GraphQL access layer."""

from __future__ import annotations

import json
import unittest

from tests.helpers import (
    FAKE_TOKEN,
    FakeTransport,
    PRIVATE_REPO_NAME,
    PUBLIC_REPO_NAME,
    contributions_payload,
    default_handler,
    language_edges,
    repository_node,
    repositories_payload,
    repository_languages_payload,
    stats_api,
)


class TokenResolutionTests(unittest.TestCase):
    def test_missing_token_fails_closed(self):
        with self.assertRaises(stats_api.MissingTokenError):
            stats_api.resolve_token({})

    def test_blank_token_fails_closed(self):
        with self.assertRaises(stats_api.MissingTokenError):
            stats_api.resolve_token({"STATS_TOKEN": "   "})

    def test_malformed_token_is_rejected(self):
        with self.assertRaises(stats_api.InadequateTokenError):
            stats_api.resolve_token({"STATS_TOKEN": "not-a-real-token"})

    def test_valid_token_is_returned_verbatim(self):
        self.assertEqual(
            stats_api.resolve_token({"STATS_TOKEN": FAKE_TOKEN}), FAKE_TOKEN
        )


class ScrubbingTests(unittest.TestCase):
    def test_scrub_removes_the_active_token(self):
        message = "boom %s boom" % FAKE_TOKEN
        self.assertNotIn(FAKE_TOKEN, stats_api.scrub(message, FAKE_TOKEN))

    def test_scrub_removes_foreign_token_material(self):
        message = "boom ghp_abcdefghijklmnopqrstuvwxyz0123456789 boom"
        self.assertNotIn("ghp_", stats_api.scrub(message))


class OwnedRepositoryQueryTests(unittest.TestCase):
    """S5: every repository the account owns counts, forks included."""

    def test_the_query_filters_by_ownership(self):
        self.assertIn("ownerAffiliations: OWNER", stats_api.REPOSITORIES_QUERY)

    def test_the_query_does_not_filter_forks_out(self):
        self.assertNotIn("isFork", stats_api.REPOSITORIES_QUERY)

    def test_owned_forks_are_collected(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            return repositories_payload(
                [repository_node("my-own-fork", [("C", 10, "#555555")])],
                total_count=1,
            )

        transport = FakeTransport(handler)
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        repositories = client.fetch_owned_repositories("LeanEmanuel")
        self.assertEqual(
            [repository["name"] for repository in repositories], ["my-own-fork"]
        )

    def test_the_repository_connection_is_paginated(self):
        transport = FakeTransport(default_handler())
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        repositories = client.fetch_owned_repositories("LeanEmanuel")

        names = [repository["name"] for repository in repositories]
        self.assertEqual(
            names, [PUBLIC_REPO_NAME, PRIVATE_REPO_NAME, "kotlin-demo"]
        )
        repository_calls = [
            call for call in transport.calls if "repositories(" in call["query"]
        ]
        self.assertEqual(len(repository_calls), 2)
        self.assertIsNone(repository_calls[0]["variables"]["after"])
        self.assertEqual(repository_calls[1]["variables"]["after"], "repo-cursor-1")

    def test_the_language_connection_is_paginated(self):
        transport = FakeTransport(default_handler())
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        repositories = client.fetch_owned_repositories("LeanEmanuel")

        private = [
            repository for repository in repositories
            if repository["name"] == PRIVATE_REPO_NAME
        ][0]
        self.assertEqual(
            [edge["node"]["name"] for edge in private["language_edges"]],
            ["Java", "Shell"],
        )
        language_calls = [
            call for call in transport.calls
            if "languages(" in call["query"] and "repositories(" not in call["query"]
        ]
        self.assertEqual(len(language_calls), 1)
        self.assertEqual(language_calls[0]["variables"]["after"], "lang-cursor-0")
        self.assertEqual(language_calls[0]["variables"]["name"], PRIVATE_REPO_NAME)


class MalformedConnectionTests(unittest.TestCase):
    """A missing or malformed connection must be rejected, not read as empty."""

    def repositories_client(self, handler):
        transport = FakeTransport(handler)
        return stats_api.GitHubClient(FAKE_TOKEN, transport=transport), transport

    def test_a_missing_repository_connection_is_rejected(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            return {"data": {"user": {}}}

        client, _ = self.repositories_client(handler)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_owned_repositories("LeanEmanuel")

    def test_a_repository_connection_without_page_info_is_rejected(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            return {
                "data": {
                    "user": {
                        "repositories": {"totalCount": 1, "nodes": []}
                    }
                }
            }

        client, _ = self.repositories_client(handler)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_owned_repositories("LeanEmanuel")

    def test_a_repository_connection_without_nodes_is_rejected(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            return {
                "data": {
                    "user": {
                        "repositories": {
                            "totalCount": 1,
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }

        client, _ = self.repositories_client(handler)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_owned_repositories("LeanEmanuel")

    def test_a_repository_without_a_language_connection_is_rejected(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            return repositories_payload(
                [{"name": "no-languages"}], total_count=1
            )

        client, _ = self.repositories_client(handler)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_owned_repositories("LeanEmanuel")

    def test_a_language_connection_without_page_info_is_rejected(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            return repositories_payload(
                [
                    {
                        "name": "broken",
                        "languages": {"totalSize": 0, "edges": []},
                    }
                ],
                total_count=1,
            )

        client, _ = self.repositories_client(handler)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_owned_repositories("LeanEmanuel")

    def test_a_language_connection_with_malformed_edges_is_rejected(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            return repositories_payload(
                [
                    {
                        "name": "broken",
                        "languages": {
                            "totalSize": 0,
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "edges": "not-a-list",
                        },
                    }
                ],
                total_count=1,
            )

        client, _ = self.repositories_client(handler)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_owned_repositories("LeanEmanuel")

    def test_a_missing_language_connection_in_the_follow_up_query_is_rejected(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            if "repositories(" in document:
                return repositories_payload(
                    [
                        repository_node(
                            "one", [("Java", 10, "#b07219")],
                            has_next_languages=True, end_cursor="lang-cursor-0",
                        )
                    ],
                    total_count=1,
                )
            return {"data": {"repository": {}}}

        client, _ = self.repositories_client(handler)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_owned_repositories("LeanEmanuel")

    def test_a_language_connection_with_malformed_page_info_is_rejected(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            if "repositories(" in document:
                return repositories_payload(
                    [
                        repository_node(
                            "one", [("Java", 10, "#b07219")],
                            has_next_languages=True, end_cursor="lang-cursor-0",
                        )
                    ],
                    total_count=1,
                )
            return {
                "data": {
                    "repository": {
                        "languages": {"totalSize": 0, "edges": []}
                    }
                }
            }

        client, _ = self.repositories_client(handler)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_owned_repositories("LeanEmanuel")


class PaginationTests(unittest.TestCase):
    def test_incomplete_pagination_fails_closed(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            return repositories_payload(
                [repository_node("only-one", [])], total_count=7, has_next_page=False
            )

        transport = FakeTransport(handler)
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.PaginationError):
            client.fetch_owned_repositories("LeanEmanuel")

    def test_missing_cursor_fails_closed(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            return repositories_payload(
                [repository_node("only-one", [])],
                total_count=2,
                has_next_page=True,
                end_cursor=None,
            )

        transport = FakeTransport(handler)
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.PaginationError):
            client.fetch_owned_repositories("LeanEmanuel")

    def test_language_pagination_without_cursor_fails_closed(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            if "repositories(" in document:
                return repositories_payload(
                    [
                        repository_node(
                            "one", [("Java", 10, "#b07219")],
                            has_next_languages=True, end_cursor=None,
                        )
                    ],
                    total_count=1,
                )
            return repository_languages_payload([])

        transport = FakeTransport(handler)
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.PaginationError):
            client.fetch_owned_repositories("LeanEmanuel")


class FailureTests(unittest.TestCase):
    def test_bad_credentials_are_reported_as_an_inadequate_token(self):
        def handler(document, variables, index):
            return {"errors": [{"message": "Bad credentials"}]}

        transport = FakeTransport(handler)
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.InadequateTokenError) as caught:
            client.query("query { viewer { login } }", {})
        self.assertNotIn(FAKE_TOKEN, str(caught.exception))

    def test_api_errors_are_scrubbed(self):
        def handler(document, variables, index):
            return {"errors": [{"message": "boom %s" % FAKE_TOKEN}]}

        transport = FakeTransport(handler)
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.query("query { viewer { login } }", {})
        self.assertNotIn(FAKE_TOKEN, str(caught.exception))

    def test_http_error_status_fails_closed(self):
        transport = FakeTransport(lambda *_: stats_api.HttpResponse(500, {}, "boom"))
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.ApiError):
            client.query("query { viewer { login } }", {})

    def test_malformed_body_fails_closed(self):
        transport = FakeTransport(lambda *_: stats_api.HttpResponse(200, {}, "<html>"))
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.ApiError):
            client.query("query { viewer { login } }", {})

    def test_missing_scopes_fail_closed(self):
        def handler(document, variables, index):
            return stats_api.HttpResponse(
                200, {"X-OAuth-Scopes": "public_repo"},
                json.dumps(contributions_payload()),
            )

        transport = FakeTransport(handler)
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.InadequateTokenError):
            client.fetch_contributions(
                "LeanEmanuel", "2026-01-01T00:00:00Z", "2026-12-31T00:00:00Z"
            )

    def test_unknown_user_fails_closed(self):
        def handler(document, variables, index):
            return {"data": {"user": None}}

        transport = FakeTransport(handler)
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_contributions(
                "LeanEmanuel", "2026-01-01T00:00:00Z", "2026-12-31T00:00:00Z"
            )

    def test_empty_calendar_fails_closed(self):
        def handler(document, variables, index):
            payload = contributions_payload()
            payload["data"]["user"]["contributionsCollection"][
                "contributionCalendar"
            ]["weeks"] = []
            return payload

        transport = FakeTransport(handler)
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_contributions(
                "LeanEmanuel", "2026-01-01T00:00:00Z", "2026-12-31T00:00:00Z"
            )

    def test_a_missing_calendar_fails_closed(self):
        def handler(document, variables, index):
            payload = contributions_payload()
            del payload["data"]["user"]["contributionsCollection"][
                "contributionCalendar"
            ]
            return payload

        transport = FakeTransport(handler)
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.ApiError):
            client.fetch_contributions(
                "LeanEmanuel", "2026-01-01T00:00:00Z", "2026-12-31T00:00:00Z"
            )

    def test_network_errors_do_not_leak_the_token(self):
        def transport(url, payload, headers):
            raise stats_api.ApiError("could not reach the GitHub API: %s" % FAKE_TOKEN)

        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.query("query { viewer { login } }", {})
        self.assertNotIn(FAKE_TOKEN, str(caught.exception))

    def test_the_token_is_only_sent_as_an_authorization_header(self):
        transport = FakeTransport(default_handler())
        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        client.fetch_contributions(
            "LeanEmanuel", "2026-01-01T00:00:00Z", "2026-12-31T00:00:00Z"
        )
        headers = transport.headers_seen[0]
        self.assertEqual(headers["Authorization"], "Bearer " + FAKE_TOKEN)
        self.assertNotIn(FAKE_TOKEN, json.dumps(transport.calls[0]))


if __name__ == "__main__":
    unittest.main()
