"""Rendering of the two responsive statistics cards.

The visual language follows the ``design/stats-variantes/01-sobria.html``
artboard: a dark and sober palette, soft rounded panels, one card for the
contributions and a second, separate card for the languages. There is no pixel
art effect (spec S4): every shape is a plain vector element.

Both cards are designed for a **narrow viewport** (a 480 unit wide view box)
so that they stay readable on a phone: the metrics are stacked vertically and
the contribution calendar is split into blocks of weeks that can be read
without zooming. Every root element carries a ``viewBox`` and a relative
width, so the very same file scales from a 320 pixel phone to a wide desktop
column.

Every visible text is written in **English** (spec S7). The header of a card
carries only its title: there is no public/private pill and no subtitle. The
contributions card ends with a single ``Updated on <date>`` line and the
languages card has no footer at all.

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
TILE_BORDER = "#37364a"
TEXT = "#eceef7"
MUTED = "#bdc3d3"
DIM = "#8a91a6"
ACCENT = "#bba2e1"
TRACK = "#303343"
OTHER_COLOR = "#91a0b9"
HEAT_COLORS = ["#272b38", "#174d36", "#23724a", "#2eaa62", "#65d48d"]

FONT = "system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

# --------------------------------------------------------------- geometry
CARD_WIDTH = 480
PADDING = 27
CONTENT_WIDTH = CARD_WIDTH - 2 * PADDING
WEEKDAY_COLUMN = 34
GRID_LEFT = PADDING + WEEKDAY_COLUMN
GRID_WIDTH = CARD_WIDTH - PADDING - GRID_LEFT
BLOCK_WEEKS = 18
CELL_GAP = 4
MAX_CELL = 24

# ------------------------------------------------------------------ type
FONT_TITLE = 27
FONT_LABEL = 17
FONT_VALUE = 20
FONT_SMALL = 16

# --------------------------------------------------------------- header
HEADER_TITLE_BASELINE = 40
HEADER_DIVIDER = 64

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

MONTH_LABELS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
WEEKDAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}


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
    return (
        rect(0, 0, width, height, BG)
        + rect(0.5, 0.5, width - 1, height - 1, "none", PANEL_BORDER, 1, radius)
    )


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
def heat_thresholds(counts):
    """Return the four intensity thresholds relative to the busiest day."""
    maximum = max(counts) if counts else 0
    return [max(1, round(maximum * factor)) for factor in (0.15, 0.35, 0.6, 0.85)]


def heat_level(count, thresholds):
    if count is None or count <= 0:
        return 0
    level = 1
    for index, threshold in enumerate(thresholds):
        if count >= threshold:
            level = index + 2
    return min(level, 4)


def month_label_of(date):
    """Return the short month name of an ISO date that starts a month."""
    if not date or not date.endswith("-01"):
        return None
    return MONTH_LABELS[int(date[5:7]) - 1]


def block_range_label(block):
    """Return the date range of a calendar block, e.g. ``Jan 2026 - Mar 2026``."""
    if not block:
        return ""
    first = (block[0].get("days") or [{}])[0].get("date") or ""
    last_days = block[-1].get("days") or []
    last = (last_days[-1].get("date") if last_days else "") or ""
    if not first or not last:
        return ""
    return "%s %s - %s %s" % (
        MONTH_LABELS[int(first[5:7]) - 1], first[:4],
        MONTH_LABELS[int(last[5:7]) - 1], last[:4],
    )


def render_contributions_card(snapshot):
    """Render the contributions card (public and private activity)."""
    contributions = snapshot.get("contributions") or {}
    weeks = contributions.get("weeks") or []
    login = snapshot.get("login") or "GitHub"

    metrics = [
        ("Contributions", contributions.get("total", 0)),
        ("Commits", contributions.get("commits", 0)),
        ("Pull requests", contributions.get("pull_requests", 0)),
        ("Issues", contributions.get("issues", 0)),
        ("Repositories", contributions.get("repositories", 0)),
    ]

    columns_per_block = max(1, min(BLOCK_WEEKS, len(weeks)))
    cell = int((GRID_WIDTH - CELL_GAP * (columns_per_block - 1)) / columns_per_block)
    cell = max(6, min(MAX_CELL, cell))
    step = cell + CELL_GAP
    grid_height = 7 * step - CELL_GAP

    blocks = [weeks[index:index + BLOCK_WEEKS]
              for index in range(0, len(weeks), BLOCK_WEEKS)] or [[]]

    # ---- vertical rhythm
    metrics_first = 108
    metrics_stride = 36
    metrics_last = metrics_first + metrics_stride * (len(metrics) - 1)
    metrics_divider = metrics_last + 24
    section_baseline = metrics_divider + 32
    block_first = section_baseline + 34
    block_stride = 34 + grid_height + 34
    last_grid_bottom = block_first + (len(blocks) - 1) * block_stride + 34 + grid_height
    legend_baseline = last_grid_bottom + 34
    footer_divider = legend_baseline + 22
    footer_first = footer_divider + 28
    height = footer_first + 24

    counts = [
        day.get("count")
        for week in weeks
        for day in (week.get("days") or [])
        if day.get("count") is not None
    ]
    thresholds = heat_thresholds(counts)

    parts = [svg_root(
        CARD_WIDTH, height,
        "Contributions of %s" % login,
        "Public and private contributions of the last %d weeks." % len(weeks),
        "contrib-card",
    )]
    parts.append(panel(CARD_WIDTH, height))
    parts.append(header("Contributions"))

    # ---- metric rows, stacked vertically
    for index, (label, value) in enumerate(metrics):
        baseline = metrics_first + index * metrics_stride
        parts.append(text(PADDING, baseline, label, FONT_LABEL, MUTED))
        parts.append(text(
            CARD_WIDTH - PADDING, baseline, format_number(value),
            FONT_VALUE, TEXT, "end", weight="bold",
        ))
    parts.append(line(PADDING, metrics_divider, CARD_WIDTH - PADDING, "#38394a"))

    # ---- calendar, split into blocks of weeks
    parts.append(text(PADDING, section_baseline, "Daily activity", FONT_LABEL, ACCENT,
                      weight="bold"))
    for block_index, block in enumerate(blocks):
        base = block_first + block_index * block_stride
        parts.append('<g class="calendar-block">')
        parts.append(text(PADDING, base, block_range_label(block), FONT_SMALL, DIM))
        last_label = -99
        for column, week in enumerate(block):
            for day in week.get("days") or []:
                label = month_label_of(day.get("date"))
                if label and (column - last_label) * step >= 46:
                    parts.append(text(
                        GRID_LEFT + column * step, base + 22, label, FONT_SMALL, MUTED
                    ))
                    last_label = column
                    break
        for column, week in enumerate(block):
            for row, day in enumerate(week.get("days") or []):
                count = day.get("count")
                if count is None:
                    continue
                parts.append(rect(
                    GRID_LEFT + column * step,
                    base + 34 + row * step,
                    cell, cell, HEAT_COLORS[heat_level(count, thresholds)],
                    None, 1, 2,
                ))
        if block_index == 0:
            for row, label in WEEKDAY_LABELS.items():
                parts.append(text(
                    GRID_LEFT - 8, base + 34 + row * step + cell - 3,
                    label, FONT_SMALL, DIM, "end",
                ))
        parts.append("</g>")

    # ---- legend
    parts.append(text(PADDING, legend_baseline, "Less", FONT_SMALL, DIM))
    for index, color in enumerate(HEAT_COLORS):
        parts.append(rect(
            PADDING + 56 + index * 22, legend_baseline - 13, 18, 14, color, None, 1, 2
        ))
    parts.append(text(PADDING + 56 + len(HEAT_COLORS) * 22 + 8, legend_baseline, "More",
                      FONT_SMALL, DIM))

    # ---- footer: only the date of the last update
    parts.append(line(PADDING, footer_divider, CARD_WIDTH - PADDING, "#38394a"))
    generated = (snapshot.get("generated_at") or "")[:10]
    parts.append(text(
        PADDING, footer_first, "Updated on %s" % generated, FONT_SMALL, MUTED,
    ))
    parts.append("</svg>")
    return "".join(parts)


# ----------------------------------------------------------- languages card
def render_languages_card(snapshot, limit=8):
    """Render the languages card (public and private repositories)."""
    percentages = language_percentages(snapshot, limit=limit)
    login = snapshot.get("login") or "GitHub"

    row_stride = 44
    first_baseline = 116
    rows = max(1, len(percentages))
    last_bottom = first_baseline + (rows - 1) * row_stride + 24
    height = last_bottom + 26

    parts = [svg_root(
        CARD_WIDTH, height,
        "Languages of %s" % login,
        "Distribution by code volume across the public and private repositories.",
        "lang-card",
    )]
    parts.append(panel(CARD_WIDTH, height))
    parts.append(header("Languages"))

    for index, (name, percentage, color) in enumerate(percentages):
        baseline = first_baseline + index * row_stride
        bar_color = OTHER_COLOR if name == "Other" else safe_color(color, OTHER_COLOR)
        parts.append(text(PADDING, baseline, truncate(name), FONT_LABEL, TEXT))
        parts.append(text(
            CARD_WIDTH - PADDING, baseline, "%.1f%%" % percentage,
            FONT_LABEL, MUTED, "end",
        ))
        parts.append(rect(PADDING, baseline + 12, CONTENT_WIDTH, 12, TRACK, None, 1, 6))
        filled = max(0.0, min(100.0, percentage)) / 100.0 * CONTENT_WIDTH
        if filled > 0:
            parts.append(rect(PADDING, baseline + 12, filled, 12, bar_color, None, 1, 6))

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
    height = 360
    parts = [svg_root(
        CARD_WIDTH, height,
        "Contributions",
        "Contributions card pending the first generation with real data.",
        "contrib-card", state="pending",
    )]
    parts.append(panel(CARD_WIDTH, height))
    parts.append(header("Contributions"))
    for index, line_text in enumerate(PENDING_LINES):
        parts.append(text(PADDING, 124 + index * 26, line_text, FONT_LABEL, MUTED))
    parts.append(rect(
        PADDING, 210, CONTENT_WIDTH, 120, "none", PANEL_BORDER, 1, 10, dash="6 6"
    ))
    parts.append("</svg>")
    return "".join(parts)


def render_pending_languages_card():
    """Placeholder card: announces the missing data, shows no number."""
    height = 318
    parts = [svg_root(
        CARD_WIDTH, height,
        "Languages",
        "Languages card pending the first generation with real data.",
        "lang-card", state="pending",
    )]
    parts.append(panel(CARD_WIDTH, height))
    parts.append(header("Languages"))
    for index, line_text in enumerate(PENDING_LINES):
        parts.append(text(PADDING, 124 + index * 26, line_text, FONT_LABEL, MUTED))
    for index in range(3):
        parts.append(rect(
            PADDING, 212 + index * 32, CONTENT_WIDTH, 12, "none",
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
