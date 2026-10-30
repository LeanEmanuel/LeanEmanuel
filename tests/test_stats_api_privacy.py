"""Privacy tests: no repository identifier may reach an error message.

The generator runs inside a GitHub workflow whose logs are public. Every
error message therefore has to stay free of repository names, including the
names that the upstream API embeds in its own error messages. The token
scrubbing of the previous behaviour must be preserved.
"""

from __future__ import annotations

import unittest
from unittest import mock

from tests.helpers import (
    FAKE_TOKEN,
    FakeTransport,
    PLAIN_REPO_NAME,
    PRIVATE_REPO_NAME,
    PUBLIC_REPO_NAME,
    contributions_payload,
    repositories_payload,
    repository_node,
    stats_api,
)


def client_for(handler):
    """Return a client bound to a fake transport serving ``handler``."""
    transport = FakeTransport(handler)
    return stats_api.GitHubClient(FAKE_TOKEN, transport=transport), transport


def repositories_then(nodes, follow_up):
    """Handler that serves ``nodes`` and then the ``follow_up`` payload."""

    def handler(document, variables, index):
        if "contributionsCollection" in document:
            return contributions_payload()
        if "repositories(" in document:
            return repositories_payload(nodes, total_count=len(nodes))
        return follow_up

    return handler


class RepositoryNameLeakTests(unittest.TestCase):
    """Every failure path must describe the problem without the name."""

    def assert_no_repository_name(self, message):
        self.assertNotIn(PRIVATE_REPO_NAME, message)
        self.assertNotIn(PUBLIC_REPO_NAME, message)

    def test_a_missing_language_connection_does_not_name_the_repository(self):
        handler = repositories_then(
            [{"name": PRIVATE_REPO_NAME, "languages": None}], None
        )
        client, _ = client_for(handler)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.fetch_owned_repositories("LeanEmanuel")
        self.assert_no_repository_name(str(caught.exception))

    def test_a_language_connection_without_page_info_does_not_name_the_repository(
        self,
    ):
        handler = repositories_then(
            [
                {
                    "name": PRIVATE_REPO_NAME,
                    "languages": {"totalSize": 0, "edges": []},
                }
            ],
            None,
        )
        client, _ = client_for(handler)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.fetch_owned_repositories("LeanEmanuel")
        self.assert_no_repository_name(str(caught.exception))

    def test_a_language_connection_with_malformed_edges_does_not_name_the_repository(
        self,
    ):
        handler = repositories_then(
            [
                {
                    "name": PRIVATE_REPO_NAME,
                    "languages": {
                        "totalSize": 0,
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "edges": "not-a-list",
                    },
                }
            ],
            None,
        )
        client, _ = client_for(handler)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.fetch_owned_repositories("LeanEmanuel")
        self.assert_no_repository_name(str(caught.exception))

    def test_a_disappearing_repository_does_not_name_the_repository(self):
        handler = repositories_then(
            [
                repository_node(
                    PRIVATE_REPO_NAME,
                    [("Java", 10, "#b07219")],
                    has_next_languages=True,
                    end_cursor="lang-cursor-0",
                )
            ],
            {"data": {"repository": {}}},
        )
        client, _ = client_for(handler)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.fetch_owned_repositories("LeanEmanuel")
        self.assert_no_repository_name(str(caught.exception))

    def test_a_missing_language_connection_in_the_follow_up_query_does_not_name_it(self):
        handler = repositories_then(
            [
                repository_node(
                    PRIVATE_REPO_NAME,
                    [("Java", 10, "#b07219")],
                    has_next_languages=True,
                    end_cursor="lang-cursor-0",
                )
            ],
            {"data": {"repository": {"languages": None}}},
        )
        client, _ = client_for(handler)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.fetch_owned_repositories("LeanEmanuel")
        self.assert_no_repository_name(str(caught.exception))

    def test_a_follow_up_connection_without_page_info_does_not_name_the_repository(
        self,
    ):
        handler = repositories_then(
            [
                repository_node(
                    PRIVATE_REPO_NAME,
                    [("Java", 10, "#b07219")],
                    has_next_languages=True,
                    end_cursor="lang-cursor-0",
                )
            ],
            {"data": {"repository": {"languages": {"totalSize": 0, "edges": []}}}},
        )
        client, _ = client_for(handler)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.fetch_owned_repositories("LeanEmanuel")
        self.assert_no_repository_name(str(caught.exception))

    def test_a_follow_up_edge_list_that_is_not_a_list_does_not_name_the_repository(
        self,
    ):
        handler = repositories_then(
            [
                repository_node(
                    PRIVATE_REPO_NAME,
                    [("Java", 10, "#b07219")],
                    has_next_languages=True,
                    end_cursor="lang-cursor-0",
                )
            ],
            {
                "data": {
                    "repository": {
                        "languages": {
                            "totalSize": 0,
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "edges": "not-a-list",
                        }
                    }
                }
            },
        )
        client, _ = client_for(handler)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.fetch_owned_repositories("LeanEmanuel")
        self.assert_no_repository_name(str(caught.exception))

    def test_a_repository_without_a_name_is_rejected_without_a_name(self):
        handler = repositories_then([{"languages": {}}], None)
        client, _ = client_for(handler)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.fetch_owned_repositories("LeanEmanuel")
        self.assert_no_repository_name(str(caught.exception))

    def test_the_pagination_failure_does_not_name_the_repository(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            return repositories_payload(
                [repository_node(PRIVATE_REPO_NAME, [])],
                total_count=7,
                has_next_page=False,
            )

        client, _ = client_for(handler)
        with self.assertRaises(stats_api.PaginationError) as caught:
            client.fetch_owned_repositories("LeanEmanuel")
        self.assert_no_repository_name(str(caught.exception))


class FailClosedUpstreamTests(unittest.TestCase):
    """The upstream error text is never relayed.

    The text comes from an untrusted source and may name a repository in a
    way that no heuristic can catch, so the failure is reported with its
    class only.
    """

    def upstream_client(self, message):
        def handler(document, variables, index):
            return {"errors": [{"message": message}]}

        client, _ = client_for(handler)
        return client

    def test_an_upstream_error_naming_a_plain_word_repository_is_not_relayed(self):
        client = self.upstream_client(
            "Could not resolve to a Repository with the name '%s'."
            % PLAIN_REPO_NAME
        )
        with self.assertRaises(stats_api.ApiError) as caught:
            client.query("query { viewer { login } }", {})
        message = str(caught.exception)
        self.assertNotIn(PLAIN_REPO_NAME, message)
        self.assertNotIn("Could not resolve", message)

    def test_the_upstream_text_is_not_relayed_at_all(self):
        client = self.upstream_client("Something exploded on the server side")
        with self.assertRaises(stats_api.ApiError) as caught:
            client.query("query { viewer { login } }", {})
        self.assertNotIn("Something exploded", str(caught.exception))

    def test_the_class_of_the_failure_is_kept(self):
        client = self.upstream_client("Something exploded on the server side")
        with self.assertRaises(stats_api.ApiError) as caught:
            client.query("query { viewer { login } }", {})
        self.assertIn("the GitHub API returned an error", str(caught.exception))

    def test_an_inadequate_token_keeps_its_class_without_relaying_the_text(self):
        client = self.upstream_client("Bad credentials for %s" % PLAIN_REPO_NAME)
        with self.assertRaises(stats_api.InadequateTokenError) as caught:
            client.query("query { viewer { login } }", {})
        message = str(caught.exception)
        self.assertNotIn(PLAIN_REPO_NAME, message)
        self.assertNotIn("Bad credentials", message)
        self.assertIn("token", message)

    def test_an_upstream_error_naming_a_known_repository_is_not_relayed(self):
        def handler(document, variables, index):
            if "contributionsCollection" in document:
                return contributions_payload()
            if "repositories(" in document:
                return repositories_payload(
                    [
                        repository_node(
                            PRIVATE_REPO_NAME,
                            [("Java", 10, "#b07219")],
                            has_next_languages=True,
                            end_cursor="lang-cursor-0",
                        )
                    ],
                    total_count=1,
                )
            return {
                "errors": [
                    {
                        "message": "Could not resolve to a Repository with the "
                        "name %s." % PRIVATE_REPO_NAME
                    }
                ]
            }

        client, _ = client_for(handler)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.fetch_owned_repositories("LeanEmanuel")
        message = str(caught.exception)
        self.assertNotIn(PRIVATE_REPO_NAME, message)
        self.assertNotIn("Could not resolve", message)

    def test_an_upstream_error_keeps_the_token_scrubbed(self):
        client = self.upstream_client("boom %s %s" % (FAKE_TOKEN, PLAIN_REPO_NAME))
        with self.assertRaises(stats_api.ApiError) as caught:
            client.query("query { viewer { login } }", {})
        message = str(caught.exception)
        self.assertNotIn(FAKE_TOKEN, message)
        self.assertNotIn(PLAIN_REPO_NAME, message)

    def test_a_url_error_is_not_relayed(self):
        def transport(url, payload, headers):
            raise stats_api.ApiError(
                "could not reach the GitHub API: <urlopen error "
                "https://api.github.com/repos/owner/%s>" % PLAIN_REPO_NAME
            )

        client = stats_api.GitHubClient(FAKE_TOKEN, transport=transport)
        with self.assertRaises(stats_api.ApiError) as caught:
            client.query("query { viewer { login } }", {})
        message = str(caught.exception)
        self.assertNotIn(PLAIN_REPO_NAME, message)
        self.assertNotIn("https://", message)
        self.assertNotIn("urlopen", message)

    def test_the_default_transport_does_not_relay_the_url_reason(self):
        def fake_urlopen(request, timeout=None):
            raise stats_api.urllib.error.URLError(
                "urlopen error https://api.github.com/repos/owner/%s"
                % PLAIN_REPO_NAME
            )

        with mock.patch.object(stats_api.urllib.request, "urlopen", fake_urlopen):
            with self.assertRaises(stats_api.ApiError) as caught:
                stats_api.default_transport(
                    "https://api.github.com/graphql", {}, {}
                )
        message = str(caught.exception)
        self.assertNotIn(PLAIN_REPO_NAME, message)
        self.assertNotIn("https://", message)
        self.assertNotIn("urlopen", message)
        self.assertIn("could not reach the GitHub API", message)


class ScrubbingApiTests(unittest.TestCase):
    """The module level helper keeps its token scrubbing."""

    def test_scrub_still_removes_the_active_token(self):
        message = "boom %s boom" % FAKE_TOKEN
        self.assertNotIn(FAKE_TOKEN, stats_api.scrub(message, FAKE_TOKEN))

    def test_scrub_still_removes_foreign_token_material(self):
        message = "boom ghp_abcdefghijklmnopqrstuvwxyz0123456789 boom"
        self.assertNotIn("ghp_", stats_api.scrub(message))

    def test_scrub_keeps_a_message_without_a_token(self):
        self.assertEqual(stats_api.scrub("a plain message"), "a plain message")


if __name__ == "__main__":
    unittest.main()
