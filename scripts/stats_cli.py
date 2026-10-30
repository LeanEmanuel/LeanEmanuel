"""Command line entry point of the profile statistics generator.

Usage::

    STATS_TOKEN=... python scripts/generate_stats.py
    python scripts/generate_stats.py --snapshot snapshot.json --out-dir /tmp/out

The generator fails closed: when the token is missing, inadequate, the API
answers with an error or the pagination is incomplete, nothing is written and
the process exits with a non zero status.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import xml.etree.ElementTree as ElementTree

try:  # pragma: no cover - import shim for both script and package usage
    from stats_aggregate import build_snapshot, validate_snapshot
    from stats_api import GitHubClient, StatsError, resolve_token, scrub
    from stats_render import render_cards, render_pending_cards
except ImportError:  # pragma: no cover
    from scripts.stats_aggregate import build_snapshot, validate_snapshot
    from scripts.stats_api import GitHubClient, StatsError, resolve_token, scrub
    from scripts.stats_render import render_cards, render_pending_cards

DEFAULT_LOGIN = "LeanEmanuel"
WINDOW_DAYS = 364  # 52 weeks


def repository_root():
    """Return the root of the repository (the parent of ``scripts/``)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_out_dir():
    return os.path.join(repository_root(), "assets", "stats")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="generate_stats.py",
        description="Generate the two responsive GitHub profile statistics cards.",
    )
    parser.add_argument(
        "--login",
        default=os.environ.get("STATS_LOGIN", DEFAULT_LOGIN),
        help="GitHub login to render (default: STATS_LOGIN or %s)" % DEFAULT_LOGIN,
    )
    parser.add_argument(
        "--out-dir",
        default=default_out_dir(),
        help="directory that receives the SVG cards (default: assets/stats)",
    )
    parser.add_argument(
        "--snapshot",
        default=None,
        help="render from a local snapshot JSON file instead of calling GitHub",
    )
    parser.add_argument(
        "--pending",
        action="store_true",
        help=(
            "write placeholder cards that announce the missing data; no token "
            "and no network call are needed and cards that hold real data are "
            "never overwritten"
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 when the rendered cards differ from the files on disk",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="render and print a summary without writing any file",
    )
    return parser


def load_snapshot(path):
    with open(path, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    return validate_snapshot(snapshot)


def fetch_snapshot(login, environ, transport=None):
    """Query GitHub and return the aggregated snapshot."""
    token = resolve_token(environ)
    client = GitHubClient(token, transport=transport)
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    date_to = now.isoformat()
    date_from = (now - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    collection = client.fetch_contributions(login, date_from, date_to)
    repositories = client.fetch_owned_repositories(login)
    return build_snapshot(
        login,
        collection,
        repositories,
        generated_at=now.isoformat(),
        window={"from": date_from, "to": date_to},
    )


def write_files(out_dir, cards):
    """Write the rendered cards atomically inside ``out_dir``."""
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name, content in sorted(cards.items()):
        path = os.path.join(out_dir, name)
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary, path)
        written.append((path, len(content.encode("utf-8"))))
    return written


def check_files(out_dir, cards):
    """Return the list of files that are missing or outdated."""
    outdated = []
    for name, content in sorted(cards.items()):
        path = os.path.join(out_dir, name)
        if not os.path.exists(path):
            outdated.append(path)
            continue
        with open(path, "r", encoding="utf-8") as handle:
            if handle.read() != content:
                outdated.append(path)
    return outdated


def validate_svg(documents):
    """Make sure every rendered document is well formed XML."""
    for name, content in documents.items():
        try:
            ElementTree.fromstring(content)
        except ElementTree.ParseError as exc:
            raise ValueError("the rendered %s is not valid SVG: %s" % (name, exc))


def pending_guard(out_dir, cards):
    """Refuse to replace a card that already holds real data."""
    blocked = []
    for name, content in cards.items():
        path = os.path.join(out_dir, name)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
        if 'data-state="ready"' in existing:
            blocked.append(path)
    return blocked


def run(argv=None, environ=None, transport=None):
    """Run the generator and return the process exit code."""
    environ = os.environ if environ is None else environ
    parser = build_parser()
    args = parser.parse_args(argv)

    token = None
    try:
        if args.pending:
            cards = render_pending_cards()
            blocked = pending_guard(args.out_dir, cards)
            if blocked:
                for path in blocked:
                    sys.stderr.write(
                        "error: refusing to replace the card that holds real data: %s\n"
                        % path
                    )
                return 2
        elif args.snapshot:
            snapshot = load_snapshot(args.snapshot)
            cards = render_cards(snapshot)
        else:
            token = environ.get("STATS_TOKEN") or ""
            snapshot = fetch_snapshot(args.login, environ, transport=transport)
            cards = render_cards(snapshot)
        validate_svg(cards)
    except StatsError as exc:
        sys.stderr.write("error: %s\n" % scrub(exc, token))
        return 2
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write("error: %s\n" % scrub(exc, token))
        return 2
    except Exception as exc:  # pragma: no cover - defensive, never leaks a token
        sys.stderr.write("error: unexpected failure: %s\n" % type(exc).__name__)
        return 3

    if args.check:
        outdated = check_files(args.out_dir, cards)
        if outdated:
            for path in outdated:
                sys.stderr.write("outdated: %s\n" % path)
            return 1
        print("the statistics cards are up to date")
        return 0

    if args.dry_run:
        for name in sorted(cards):
            print("would write %s" % os.path.join(args.out_dir, name))
        return 0

    for path, size in write_files(args.out_dir, cards):
        print("wrote %s (%d bytes)" % (path, size))
    return 0


def main(argv=None):
    return run(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
