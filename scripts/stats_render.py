"""Rendering of the two profile statistics cards.

The visual language follows the ``design/stats-variantes/01-sobria.html``
artboard: a dark and sober palette, soft rounded panels, one card for the
contributions and a second, separate card for the languages. There is no pixel
art effect (spec S4): every shape is a plain vector element.

Both cards are **compact** (spec S8) so that they can sit **side by side** in
the README: the view box is 400 units wide and the cards are less than 420
units high, which makes two of them fit into one desktop row. The
contributions card shows the real metrics as coloured mini tiles instead of a
daily heat map, because GitHub already draws that grid on the profile page
itself (spec S8).

Both cards have **exactly the same height** (spec S9): they are drawn on the
shared :data:`CARD_HEIGHT`, whatever the number of language rows is, so they
no longer look like a staircase side by side. The rows of the languages card
are centred in the free space and never leave the panel (spec S9).

The panel of a card is a **single rounded shape** (spec S9): the background is
painted by the rounded rectangle itself, so the four corners outside the
radius stay transparent instead of showing a dark square.

Every visible text is written in **English** (spec S7). The header of a card
carries only its title: there is no public/private pill and no subtitle. The
contributions card ends with a single ``Updated on <date>`` line and the
languages card has no footer at all.

Responsiveness of the README layout is **not** a property of these files: a
GitHub README has no media queries, so the two cards cannot be stacked by a
media query.  They are embedded side by side in one centered paragraph, and
every card scales with ``width="100%"`` so it stays sharp at any size.

The cards also carry a ``data-state`` attribute:

``ready``
    the card holds data of a successful run;
``pending``
    the card is a placeholder that announces the missing data and therefore
    never shows any number.
"""

from __future__ import annotations

import re

try:  # pragma: no cover - import shim for both script and package usage
    from stats_aggregate import language_percentages
except ImportError:  # pragma: no cover
    from scripts.stats_aggregate import language_percentages

# ----------------------------------------------------------------- palette
BG = "#090b12"
PANEL_BORDER = "#49405c"
TILE_BG = "#1d1e2c"
TILE_BORDER = "#37364a"
TEXT = "#eceef7"
MUTED = "#bdc3d3"
DIM = "#8a91a6"
ACCENT = "#bba2e1"
TRACK = "#303343"
OTHER_COLOR = "#91a0b9"

FONT = "system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

# --------------------------------------------------------------- geometry
CARD_WIDTH = 400
#: The height both cards share, so that they stand side by side (S9).
CARD_HEIGHT = 378
PADDING = 24
CONTENT_WIDTH = CARD_WIDTH - 2 * PADDING

#: The mini tiles of the contributions card.
TILE_GAP = 12
TILE_COLUMNS = 2
TILE_WIDTH = (CONTENT_WIDTH - TILE_GAP) // 2
TILE_HEIGHT = 80
WIDE_TILE_HEIGHT = 64

#: The rows of the languages card.
LANGUAGE_ROW_STRIDE = 30
#: The smallest stride that still leaves the rows readable.
LANGUAGE_MIN_STRIDE = 22
LANGUAGE_BAR_HEIGHT = 9
#: The distance between the baseline of a row and the top of its bar.
LANGUAGE_BAR_GAP = 7
#: The height of the label of a row above its baseline.
LANGUAGE_LABEL_HEIGHT = 13
#: The free space between the header and the first row.
LANGUAGE_TOP_GAP = 12

# ------------------------------------------------------------------ type
FONT_TITLE = 24
FONT_TILE_LABEL = 13
FONT_TILE_VALUE = 27
FONT_ROW = 14
FONT_SMALL = 13

# --------------------------------------------------------------- header
HEADER_TITLE_BASELINE = 36
HEADER_DIVIDER = 54

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

#: The colour of every metric tile: one colour per metric.
METRIC_COLORS = {
    "Contributions": "#bba2e1",
    "Commits": "#65d48d",
    "Pull requests": "#f0883e",
    "Issues": "#f778ba",
    "Repositories": "#58a6ff",
}


# ------------------------------------------------------------------ helpers
def escape(value):
    """Escape a value so that it is safe inside SVG text and attributes."""
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def safe_color(value, fallback=OTHER_COLOR):
    """Return ``value`` when it is a plain hex colour, else ``fallback``."""
    if isinstance(value, str) and HEX_COLOR.match(value.strip()):
        return value.strip()
    return fallback


def format_number(value):
    """Format an integer with a thousands separator."""
    try:
        return "{:,}".format(int(value))
    except (TypeError, ValueError):
        return "0"


def truncate(value, limit=20):
    """Shorten a label so that it never collides with the next element."""
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def text(x, y, value, size=FONT_SMALL, fill=TEXT, anchor="start", weight=None):
    attributes = ' font-size="%s" fill="%s"' % (size, fill)
    if anchor != "start":
        attributes += ' text-anchor="%s"' % anchor
    if weight:
        attributes += ' font-weight="%s"' % weight
    return '<text x="%s" y="%s"%s>%s</text>' % (x, y, attributes, escape(value))


def rect(x, y, width, height, fill, stroke=None, stroke_width=1, radius=None,
         dash=None):
    attributes = ' x="%s" y="%s" width="%s" height="%s" fill="%s"' % (
        x, y, width, height, fill,
    )
    if stroke:
        attributes += ' stroke="%s" stroke-width="%s"' % (stroke, stroke_width)
    if radius is not None:
        attributes += ' rx="%s"' % radius
    if dash:
        attributes += ' stroke-dasharray="%s"' % dash
    return "<rect%s/>" % attributes


def circle(cx, cy, radius, fill):
    """A filled circle: the colour dot of a metric tile."""
    return '<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (cx, cy, radius, fill)


def line(x1, y1, x2, stroke, stroke_width=1):
    """Horizontal rule."""
    return '<path d="M%s %sH%s" stroke="%s" stroke-width="%s" fill="none"/>' % (
        x1, y1, x2, stroke, stroke_width,
    )


def svg_root(width, height, title, description, element_id, state="ready"):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="100%%" '
        'preserveAspectRatio="xMidYMid meet" data-state="%s" role="img" '
        'aria-labelledby="%s-title %s-desc">'
        '<title id="%s-title">%s</title><desc id="%s-desc">%s</desc>'
        '<style>text{font-family:%s}</style>'
        % (width, height, state, element_id, element_id, element_id,
           escape(title), element_id, escape(description), FONT)
    )


def panel(width, height, radius=16):
    """The rounded panel of a card.

    The background is painted by the **rounded** rectangle itself (spec S9):
    a square background behind a rounded border would let the dark square
    show at the four corners.
    """
    return rect(0.5, 0.5, width - 1, height - 1, BG, PANEL_BORDER, 1, radius)


def header(title):
    """The card header: the title and a divider, nothing else."""
    return "".join(
        [
            text(PADDING, HEADER_TITLE_BASELINE, title, FONT_TITLE, TEXT,
                 weight="bold"),
            line(PADDING, HEADER_DIVIDER, CARD_WIDTH - PADDING, PANEL_BORDER),
        ]
    )


# ------------------------------------------------------- contributions card
def metric_tile(x, y, width, height, label, value):
    """A mini tile: a coloured dot, the label and the number of a metric."""
    color = METRIC_COLORS.get(label, ACCENT)
    return "".join(
        [
            '<g class="metric-tile" data-metric="%s">' % escape(label),
            rect(x, y, width, height, TILE_BG, TILE_BORDER, 1, 12),
            circle(x + 22, y + 20, 4.5, color),
            text(x + 20, y + 44, label, FONT_TILE_LABEL, MUTED),
            text(x + 20, y + 72, format_number(value), FONT_TILE_VALUE, color,
                 weight="bold"),
            "</g>",
        ]
    )


def wide_metric_tile(x, y, width, height, label, value):
    """The wide variant of a tile: label on the left, number on the right."""
    color = METRIC_COLORS.get(label, ACCENT)
    middle = y + height // 2
    return "".join(
        [
            '<g class="metric-tile" data-metric="%s">' % escape(label),
            rect(x, y, width, height, TILE_BG, TILE_BORDER, 1, 12),
            circle(x + 20, middle, 5, color),
            text(x + 34, middle + 5, label, FONT_TILE_LABEL, MUTED),
            text(x + width - 20, middle + 10, format_number(value),
                 FONT_TILE_VALUE, color, "end", weight="bold"),
            "</g>",
        ]
    )


def render_contributions_card(snapshot):
    """Render the contributions card (public and private activity)."""
    contributions = snapshot.get("contributions") or {}
    login = snapshot.get("login") or "GitHub"

    metrics = [
        ("Contributions", contributions.get("total", 0)),
        ("Commits", contributions.get("commits", 0)),
        ("Pull requests", contributions.get("pull_requests", 0)),
        ("Issues", contributions.get("issues", 0)),
        ("Repositories", contributions.get("repositories", 0)),
    ]

    # ---- vertical rhythm
    tiles_top = HEADER_DIVIDER + 16
    row_two = tiles_top + TILE_HEIGHT + TILE_GAP
    wide_row = row_two + TILE_HEIGHT + TILE_GAP
    tiles_bottom = wide_row + WIDE_TILE_HEIGHT
    footer_divider = tiles_bottom + 20
    footer_first = footer_divider + 22
    height = CARD_HEIGHT

    parts = [svg_root(
        CARD_WIDTH, height,
        "Contributions of %s" % login,
        "Public and private contributions of the owned repositories.",
        "contrib-card",
    )]
    parts.append(panel(CARD_WIDTH, height))
    parts.append(header("Contributions"))

    # ---- the metrics as coloured mini tiles
    for index, (label, value) in enumerate(metrics[:-1]):
        column = index % TILE_COLUMNS
        row = index // TILE_COLUMNS
        x = PADDING + column * (TILE_WIDTH + TILE_GAP)
        y = tiles_top + row * (TILE_HEIGHT + TILE_GAP)
        parts.append(metric_tile(x, y, TILE_WIDTH, TILE_HEIGHT, label, value))

    last_label, last_value = metrics[-1]
    parts.append(wide_metric_tile(
        PADDING, wide_row, CONTENT_WIDTH, WIDE_TILE_HEIGHT,
        last_label, last_value,
    ))

    # ---- footer: only the date of the last update
    parts.append(line(PADDING, footer_divider, CARD_WIDTH - PADDING, "#38394a"))
    generated = (snapshot.get("generated_at") or "")[:10]
    parts.append(text(
        PADDING, footer_first, "Updated on %s" % generated, FONT_SMALL, MUTED,
    ))
    parts.append("</svg>")
    return "".join(parts)


# ----------------------------------------------------------- languages card
def language_layout(rows):
    """Return the first baseline and the stride of the language rows.

    The rows are centred in the free space below the header, so the card
    looks balanced whatever the number of languages is (spec S9).  The
    stride shrinks when there are many rows, so that the last row always
    stays inside the panel and is never clipped.
    """
    top = HEADER_DIVIDER + LANGUAGE_TOP_GAP
    bottom = CARD_HEIGHT - PADDING
    available = bottom - top
    block = LANGUAGE_LABEL_HEIGHT + LANGUAGE_BAR_GAP + LANGUAGE_BAR_HEIGHT

    if rows > 1:
        stride = min(
            LANGUAGE_ROW_STRIDE, int((available - block) // (rows - 1))
        )
        stride = max(LANGUAGE_MIN_STRIDE, stride)
    else:
        stride = LANGUAGE_ROW_STRIDE

    block_height = (rows - 1) * stride + block
    offset = max(0, (available - block_height) // 2)
    first_baseline = top + offset + LANGUAGE_LABEL_HEIGHT
    return first_baseline, stride


def render_languages_card(snapshot, limit=8):
    """Render the languages card (public and private repositories)."""
    percentages = language_percentages(snapshot, limit=limit)
    login = snapshot.get("login") or "GitHub"

    rows = max(1, len(percentages))
    first_baseline, stride = language_layout(rows)
    height = CARD_HEIGHT

    parts = [svg_root(
        CARD_WIDTH, height,
        "Languages of %s" % login,
        "Distribution by code volume across the public and private repositories.",
        "lang-card",
    )]
    parts.append(panel(CARD_WIDTH, height))
    parts.append(header("Languages"))

    for index, (name, percentage, color) in enumerate(percentages):
        baseline = first_baseline + index * stride
        bar_color = OTHER_COLOR if name == "Other" else safe_color(color, OTHER_COLOR)
        parts.append(text(PADDING, baseline, truncate(name), FONT_ROW, TEXT))
        parts.append(text(
            CARD_WIDTH - PADDING, baseline, "%.1f%%" % percentage,
            FONT_ROW, MUTED, "end",
        ))
        parts.append(rect(PADDING, baseline + LANGUAGE_BAR_GAP, CONTENT_WIDTH,
                          LANGUAGE_BAR_HEIGHT, TRACK, None, 1, 5))
        filled = max(0.0, min(100.0, percentage)) / 100.0 * CONTENT_WIDTH
        if filled > 0:
            parts.append(rect(PADDING, baseline + LANGUAGE_BAR_GAP, filled,
                              LANGUAGE_BAR_HEIGHT, bar_color, None, 1, 5))

    parts.append("</svg>")
    return "".join(parts)


# ------------------------------------------------------------ pending cards
PENDING_LINES = [
    "This card is pending: it holds no real data yet.",
    "It is generated automatically by the next",
    "workflow run with a valid token.",
]


def render_pending_contributions_card():
    """Placeholder card: announces the missing data, shows no number."""
    height = CARD_HEIGHT
    parts = [svg_root(
        CARD_WIDTH, height,
        "Contributions",
        "Contributions card pending the first generation with real data.",
        "contrib-card", state="pending",
    )]
    parts.append(panel(CARD_WIDTH, height))
    parts.append(header("Contributions"))
    for index, line_text in enumerate(PENDING_LINES):
        parts.append(text(PADDING, 118 + index * 26, line_text, FONT_ROW, MUTED))
    parts.append(rect(
        PADDING, 210, CONTENT_WIDTH, 120, "none", PANEL_BORDER, 1, 10, dash="6 6"
    ))
    parts.append("</svg>")
    return "".join(parts)


def render_pending_languages_card():
    """Placeholder card: announces the missing data, shows no number."""
    height = CARD_HEIGHT
    parts = [svg_root(
        CARD_WIDTH, height,
        "Languages",
        "Languages card pending the first generation with real data.",
        "lang-card", state="pending",
    )]
    parts.append(panel(CARD_WIDTH, height))
    parts.append(header("Languages"))
    for index, line_text in enumerate(PENDING_LINES):
        parts.append(text(PADDING, 118 + index * 26, line_text, FONT_ROW, MUTED))
    for index in range(4):
        parts.append(rect(
            PADDING, 210 + index * 32, CONTENT_WIDTH, 12, "none",
            PANEL_BORDER, 1, 6, dash="6 6",
        ))
    parts.append("</svg>")
    return "".join(parts)


def render_pending_cards():
    """Return the two placeholder cards, keyed by file name."""
    return {
        "contributions.svg": render_pending_contributions_card(),
        "languages.svg": render_pending_languages_card(),
    }


def render_cards(snapshot):
    """Return the two SVG documents, keyed by file name."""
    return {
        "contributions.svg": render_contributions_card(snapshot),
        "languages.svg": render_languages_card(snapshot),
    }
