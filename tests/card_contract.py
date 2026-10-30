"""The contract every statistics card has to fulfil.

A statistics card is always in exactly one of two valid states:

``pending``
    the placeholder that announces the missing data; it shows no number at
    all, because a number would be a lie;
``ready``
    the card of a successful run; it holds the real data and therefore
    shows numbers.

Both states are valid.  The recurring bug this module prevents is a test
suite that only accepts the ``pending`` state: after the first successful
workflow run commits the real cards, such a suite fails on every later
scheduled run.  A card that declares an unknown state is invalid in every
case and has to be rejected.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree

PENDING_STATE = "pending"
READY_STATE = "ready"

#: The states a card is allowed to declare.
VALID_STATES = (PENDING_STATE, READY_STATE)

#: The word a pending card has to use to announce the missing data.
PENDING_KEYWORD = "pending"

#: The sentence the placeholder uses to announce the missing data.
PENDING_PLACEHOLDER_TEXT = "This card is pending"

#: Words that must never appear in a card: every visible text is English.
SPANISH_COPY = (
    "Contribuciones",
    "Lenguajes",
    "Públicas",
    "pendiente",
)

TOKEN_LIKE = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9]{10,255}|github_pat_[A-Za-z0-9_]{10,255})"
)


class CardContractError(ValueError):
    """Raised when a card does not fulfil the card contract."""


def parse(content):
    """Parse a card and return its root element."""
    return ElementTree.fromstring(content)


def text_elements(root):
    """Return every ``text`` element of a parsed card."""
    return [
        element for element in root.iter()
        if isinstance(element.tag, str) and element.tag.endswith("text")
    ]


def text_values(content):
    """Return the visible text of every ``text`` element of a card."""
    return [(element.text or "") for element in text_elements(parse(content))]


def contains_digits(content):
    """Return ``True`` when any visible text of the card holds a digit."""
    return any(
        character.isdigit() for value in text_values(content) for character in value
    )


def state_of(content, name="card"):
    """Return the state the card declares.

    Raise :class:`CardContractError` when the state is missing or unknown.
    """
    root = parse(content)
    state = root.get("data-state")
    if state not in VALID_STATES:
        raise CardContractError(
            "%s: unknown data-state %r (expected one of %s)"
            % (name, state, ", ".join(VALID_STATES))
        )
    return state


def is_pending(content, name="card"):
    """Return ``True`` when the card announces the missing data."""
    return state_of(content, name) == PENDING_STATE


def is_ready(content, name="card"):
    """Return ``True`` when the card holds the data of a successful run."""
    return state_of(content, name) == READY_STATE


def violations(content, name="card"):
    """Return the list of contract violations of a card.

    The list is empty when the card fulfils the contract.  A card in an
    unknown state always yields at least one violation.
    """
    try:
        root = parse(content)
    except ElementTree.ParseError as error:
        return ["%s: is not valid SVG: %s" % (name, error)]

    state = root.get("data-state")
    if state not in VALID_STATES:
        return [
            "%s: unknown data-state %r (expected one of %s)"
            % (name, state, ", ".join(VALID_STATES))
        ]

    problems = []
    if root.get("width") != "100%":
        problems.append("%s: the width is not relative: %r" % (name, root.get("width")))
    if not root.get("viewBox"):
        problems.append("%s: the card has no viewBox" % name)

    if state == PENDING_STATE:
        if PENDING_KEYWORD not in content.lower():
            problems.append(
                "%s: a pending card has to announce the pending state" % name
            )
        for element in text_elements(root):
            if any(character.isdigit() for character in (element.text or "")):
                problems.append(
                    "%s: a pending card must not show any number: %r"
                    % (name, element.text)
                )
    else:
        if PENDING_PLACEHOLDER_TEXT.lower() in content.lower():
            problems.append(
                "%s: a ready card must not announce the pending state" % name
            )

    for word in SPANISH_COPY:
        if word in content:
            problems.append("%s: uses the Spanish copy %r" % (name, word))
    if "assets/stats" in content or ".svg" in content:
        problems.append("%s: shows the asset path" % name)
    if TOKEN_LIKE.search(content):
        problems.append("%s: contains token material" % name)
    return problems
