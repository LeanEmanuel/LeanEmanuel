# Profile statistics cards

This repository ships **two separate, compact SVG cards** for the GitHub
profile:

| File | Content |
| --- | --- |
| `assets/stats/contributions.svg` | Contributions, commits, pull requests, issues and owned repositories, shown as coloured metric tiles. |
| `assets/stats/languages.svg` | Distribution of the languages by code volume across the owned repositories. |

Both cards follow the artboard `design/stats-variantes/01-sobria.html`: a dark
and sober palette, rounded panels, no pixel art effect, one card per topic.
They are embedded as **two inline images inside one centered paragraph**, so
they stand side by side as long as the container is wide enough.

**Every visible text is written in English**: the titles, the metric labels
and the dates.

The cards are **static files committed to this repository**. Nothing is
rendered by a third party service at read time, so the profile never depends
on an external deployment.

---

## 1. The layout: two compact cards side by side

The two cards are meant to be read **side by side**, so they are compact:

* the `viewBox` is **400 units wide** and the root element carries
  `width="100%"` plus `preserveAspectRatio`, so the card scales to any
  container;
* the contributions card shows the six real metrics as **coloured mini
  tiles** (a slim vertical bar in the colour of the metric, the label and
  the number) instead of the daily heat map: GitHub already draws that
  grid on the profile page, so the card repeated it (spec S8);
* every metric tile is marked by a **slim coloured vertical bar** at the
  left of the tile (spec S10). The coloured dot of the earlier tiles was
  replaced by a thin vertical stroke in the colour of the metric; the
  number keeps the very same colour, so a tile is read at a glance;
* the languages card is a compact list: one row per language with its share
  and its bar;
* **both cards have exactly the same height** (378 units), whatever the
  number of language rows is, so they no longer look like a staircase side
  by side (spec S9);
* the rows of the languages card are centred in the free space below the
  header and the last row always keeps the bottom padding, so no row is
  ever clipped (spec S9);
* the panel of a card is a **single rounded shape**: the background is
  painted by the rounded rectangle itself, so the four corners outside the
  radius stay transparent and no dark square shows behind the rounded
  border (spec S9);
* both cards stay below 420 units of height;
* the smallest font size is 13 units, which is **10.4 pixels** on a 320 pixel
  wide screen;
* long language names are truncated so they never collide with the bar.

In the README both cards are **two inline images inside one centered
paragraph** (`<p align="center">`), each one `width="320"`. There is no
table: a table would lock the two images into two rigid columns, while
inline images follow the ordinary flow of a paragraph and can wrap.

The two images are separated by a short run of non-breaking spaces
(`&nbsp;&nbsp;`) with a plain space on each side. The plain spaces stay
**break opportunities**, so the second card still wraps onto the next line
in a narrow container, while the gap keeps the two cards from touching in a
wide one. No CSS, no class and no table are used for it: a README has no
media queries, so nothing about the separation may depend on the width of
the screen.

### What the README can and cannot do

A GitHub README has **no media queries**: GitHub strips every `<style>`
block, so no layout can be changed with the width of the screen from CSS.

With inline images the behaviour follows the ordinary rules of an inline
format: the two cards stand **side by side** as long as the container is wide
enough for the two of them (two cards of 320 pixels plus the gap need about
665 pixels), and a renderer that constrains the images to the width of the
container lets the second one **wrap** onto the next line.

**This has not been verified in GitHub's own renderer**: the profile was
never rendered by GitHub, because neither a GitHub preview nor a network
access was available in the environment where these cards were built. A
local browser check of an HTML copy of this paragraph confirms the ordinary
inline behaviour (side by side in a wide container, the second image
wrapping in a narrow one) and that the gap between the two cards is visible,
but GitHub's own markdown and image rules were never observed. The behaviour
above is therefore described and not promised.
The README requests a width of 320 pixels for each card; a card that is
opened directly (`assets/stats/contributions.svg`) fills
the screen of the phone and is drawn at its full size.

No CSS **stacking** of the cards is claimed for a phone: without media
queries a README **cannot** guarantee it, and it has **not been verified**
here.

### What each card shows

| Card | Header | Body | Footer |
| --- | --- | --- | --- |
| Contributions | `Contributions` (no subtitle, no tag) | Six metric tiles: `Contributions`, `Commits`, `Pull requests`, `Issues`, `Repositories` and `Stars` | A single `Updated on <date>` line |
| Languages | `Languages` (no subtitle, no tag) | The language rows with their share | No footer |

The six tiles are drawn in **three rows of two tiles of the same size**, so
the card keeps the height it had with five tiles and both cards stay
exactly as tall as each other (spec S9).

The `Stars` tile shows the sum of the stargazers of the owned repositories.
When that figure is not known — a snapshot written before the stars were
added — the tile shows an em dash (`—`) and **no number at all**: a card
never invents a figure it can not prove.

---

## 2. Token requirements

The generator talks to the GitHub GraphQL API and needs a token that can read
**your own private repositories**. Public data alone is not enough: private
contributions and private repository languages are only visible to a token
that owns (or can read) them.

The token is read from the environment variable **`STATS_TOKEN`**.

### Recommended: fine-grained personal access token (`github_pat_…`)

Create it in *GitHub → Settings → Developer settings → Personal access
tokens → Fine-grained tokens* with exactly these permissions:

| Scope | Permission | Level | Why |
| --- | --- | --- | --- |
| Repository access | All repositories | – | The token must see every repository you own. |
| Repository permissions | **Contents** | **Read-only** | Reads the language breakdown of each repository. |
| Repository permissions | **Metadata** | **Read-only** | Required by GitHub for every repository (granted implicitly). |
| Account permissions | **Profile** | **Read-only** | Reads the profile and its contribution collection. |

Nothing else is needed: no write permissions, no `workflow` scope, no
organization access.

### Alternative: classic personal access token (`ghp_…`)

The classic token needs the **`repo`** scope, because it is the scope that
grants read access to private repositories. The **`read:user`** scope is
recommended but not mandatory.

`repo` is broader than needed (it also allows writing). Prefer the fine
grained token above.

### Rules the generator enforces

* The token must be present, non empty and shaped like a GitHub token
  (`ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` or `github_pat_`). Otherwise the run
  stops immediately.
* For classic tokens the `X-OAuth-Scopes` header is verified: a token without
  `repo` is rejected as *inadequate* instead of silently reporting zero
  private data.
* An expired or revoked token is reported as *inadequate* (`Bad credentials`).
* **The token is never logged.** It is only sent in the `Authorization`
  header, every error message is scrubbed of any token material, and it is
  never written to the repository.
* **No error message names a repository.** The errors of the generator reach
  the public log of the workflow, so they describe the failure without the
  name of the repository it happened on. The text of an upstream error is
  never relayed: the client reports the class of the failure (and the HTTP
  status of an answer) and nothing else, because an upstream message may
  name a repository in a way that no redaction could catch.

### Fail closed

The generator never publishes partial data. It exits with a non zero status
and writes **no file** when:

* the token is missing, malformed, expired or lacks the required scope;
* the API answers with an error, a malformed body or an HTTP failure;
* the pagination of repositories or languages is incomplete or loses its
  cursor;
* a **connection is missing or malformed**. A repository connection without
  `pageInfo` or without a node list, a repository without a `languages`
  connection, a language connection without `pageInfo` and a language edge
  list that is not a list are all rejected. They are never read as "this
  repository has no data".

---

## 3. Running it locally

```bash
# Live run: reads the token from the environment and rewrites assets/stats.
STATS_TOKEN=github_pat_xxx python scripts/generate_stats.py

# Placeholder run: no token and no network; writes the "pending" cards.
python scripts/generate_stats.py --pending

# Offline run: render from a snapshot file, no token and no network needed.
python scripts/generate_stats.py --snapshot snapshot.json --out-dir /tmp/cards

# Verify that the committed cards are up to date (exit code 1 when stale).
python scripts/generate_stats.py --check

# Test suite (standard library only, no network).
python -m unittest discover -s tests -t .
```

| Option | Meaning |
| --- | --- |
| `--login` | Login to render. Defaults to `STATS_LOGIN`, then to `LeanEmanuel`. |
| `--out-dir` | Destination directory. Defaults to `assets/stats`. |
| `--snapshot` | Render from a local snapshot JSON file instead of calling GitHub. |
| `--pending` | Write the placeholder cards that announce the missing data. No token, no network. Cards that already hold real data are never overwritten. |
| `--check` | Do not write; exit `1` when the rendered cards differ from the files on disk. |
| `--dry-run` | Render and print what would be written, without writing. |

Requirements: Python 3.9+ and the standard library only. No dependency has to
be installed.

---

## 4. The committed cards

### The two states

Every card carries a `data-state` attribute:

| `data-state` | Meaning |
| --- | --- |
| `pending` | Placeholder. The card states that it holds no data yet and shows **no number at all**. |
| `ready` | The card was produced by a successful live run. |

A placeholder never pretends to be data: it shows the title, the pending
notice and an empty frame. It carries no footer at all: neither a number nor
the path of the file it will be written to.

The first successful run of the workflow replaces a placeholder with the real
cards. `--pending` refuses to overwrite a card whose state is `ready`, so
real data can never be replaced by a placeholder by accident.

### How the committed cards were rebuilt offline

The cards in `assets/stats` were **rebuilt offline**, without a token and
without a single network call, out of the aggregate values that the previous
committed cards had published:

* `assets/stats/contributions.svg` published the five counters
  (contributions, commits, pull requests, issues, repositories) and the date
  of the last update. Those are exactly the numbers and the date the new
  card shows.
* `assets/stats/languages.svg` published the name, the share and the colour
  of every row. Those are exactly the shares the new card shows.

Nothing was invented and no published number was replaced by a made up one.
The daily heat map was dropped (spec S8), so no daily data had to be
reconstructed. The eight published language rows were rebuilt with byte sizes
that reproduce the published shares exactly; the languages behind the
aggregated *Other* row are not published by the card, so the snapshot
represents them with unnamed entries that the renderer groups into the very
same *Other* row. The only numbers the cards show are the published ones.

The next live run of the workflow replaces both cards with fresh data.

The later corrections of the layout (spec S9: the same height for both
cards, the rounded panel without a dark square behind it) were applied to
**the very same published aggregates**: the five counters, the eight shares,
the colours and the date are unchanged. Only the geometry of the cards moved;
no published figure was replaced and no new figure was invented.

The change of spec S10 (the slim vertical bars instead of the coloured
dots, and the new `Stars` metric) was applied in the same way: the five
published counters and the date are unchanged, and the star figure was
**not** reconstructed, because no published card ever showed it. The
committed contributions card therefore shows the stars as **unavailable**
(an em dash, `—`) until the next live run of the workflow replaces it with
the real sum. Nothing was invented: the tile says that it does not know the
figure instead of showing a made up number.

---

## 5. The scheduled workflow

`.github/workflows/stats.yml` refreshes the cards every day at **04:23 UTC**,
on demand (`workflow_dispatch`) and whenever `scripts/**` changes.

* **Least privileges**: the job declares `permissions: contents: write` and
  nothing else; every other permission is `none`. `contents: write` is the
  minimum needed to push the generated SVG files.
* **Immutable pins**: every action is pinned to a commit SHA that was
  verified against the upstream tag (`actions/checkout` v4.4.0 and
  `actions/setup-python` v5.6.0). The version stays readable in the comment.
* **Two different tokens**: the *Generate the cards* step receives the
  repository secret `STATS_TOKEN` (`secrets.STATS_TOKEN`), a **read-only**
  token that is used only for the GraphQL queries. The workflow also uses
  the **built-in `GITHUB_TOKEN`** that GitHub creates automatically:
  `actions/checkout` authenticates the clone with it, and the `git push`
  that follows reuses the credentials that the checkout stored. The
  built-in token is never handed to the generator and never leaves the
  checkout step.
* The job runs the test suite before generating anything.
* Only `assets/stats` is staged and committed; the commit is skipped when
  nothing changed.

Store the token as the repository secret `STATS_TOKEN`
(*Settings → Secrets and variables → Actions → New repository secret*).

---

## 6. What exactly is counted

### Contributions card

* **Contributions**: `contributionsCollection.contributionCalendar.totalContributions`
  of the last 52 weeks, that is **public and private** activity.
* **Commits / Pull requests / Issues**: the contributions of the same window
  (`totalCommitContributions`, `totalPullRequestContributions`,
  `totalIssueContributions`), not only the open ones.
* **Repositories**: the number of repositories the account owns.
* **Stars**: the sum of `stargazerCount` of every repository the account
  owns, **forks included** (spec S10). The repositories connection is
  already paginated, so the sum covers **every page** of it. The stars are
  a **current total**, not a figure of the last 364 days: a star that was
  given before the window opened still counts. The field is read from the
  same `Metadata` (read-only) permission as the rest of the repository
  data.
* **No heat map**: the daily grid is not drawn any more (spec S8), because
  GitHub already shows that grid on the profile page.
* **Pull requests and Issues keep the window**: their figures are the ones
  of the last **364 days** (52 weeks), exactly as before. Only the stars
  were added; no other metric changed its semantics.

### Languages card

* Every repository **owned** by the account is requested with
  `ownerAffiliations: OWNER`.
* **Forks are included**: a fork the account created is a repository the
  account owns, so it counts like any other owned repository. No `isFork`
  filter is applied.
* The language breakdown of every repository is **fully paginated** and the
  sizes are summed per language.
* Percentages are shares of the total number of bytes reported by GitHub
  Linguist; the languages that do not fit in the first eight rows are grouped
  under *Other*.

---

## 7. Privacy

* Only **aggregated numbers** reach the cards: counters and percentages.
  The star total is an aggregate as well: no repository name, no star and
  no owner ever reaches a card.
* **No repository name, file name, commit message or branch ever appears** in
  a card or in the snapshot. The aggregation step drops the repository
  identity before anything is rendered.
* Private repositories contribute to the counters and to the language totals,
  exactly like the public ones, but they stay anonymous.
* **No repository name reaches the log.** The workflow log is public, so the
  error messages of the generator are free of repository names: the
  validation and pagination errors describe what failed without naming the
  repository, and the upstream error text is never relayed — only the class
  of the failure and the HTTP status are reported. The token is scrubbed at
  the same time.
* The snapshot format (`profile-stats-snapshot/1`) is the only artifact that
  can be stored or shared; it contains no repository identifiers. It holds
  the star total as a plain number, next to the other aggregates. The field
  is optional: a snapshot written before the stars were added stays
  loadable, and the card then shows the stars as unavailable instead of
  guessing a figure.

---

## 8. Limitations

* **Window**: the counters cover the last 52 weeks (364 days). Older
  activity is not shown. The stars are the exception: they are a current
  total of the owned repositories.
* **Layout**: the two cards are inline images in one centered paragraph. They
  stand side by side while the container is wide enough; a renderer that
  constrains them to the container lets the second one wrap onto the next
  line. The gap between the two cards is a run of non-breaking spaces with
  a plain space on each side, so it never depends on CSS. The layout was
  checked in a local browser with an HTML copy of the paragraph; GitHub's
  own renderer was **not verified**.
* **Visibility depends on the token**: a token that cannot read a private
  repository reports that repository as empty, and its private contributions
  are not counted. The cards can therefore differ from what the owner sees
  in the GitHub UI.
* **Linguist semantics**: sizes are bytes of code as detected by GitHub
  Linguist, not lines of code. Vendored, generated or documentation files are
  excluded by Linguist, and the language set of a repository can change over
  time.
* **Language colours** are the ones published by Linguist; unknown languages
  fall back to a neutral grey.
* **Rate limits**: the GraphQL API bills each query by node count. Accounts
  with hundreds of repositories may hit the secondary rate limit; in that
  case the run fails closed and the previous cards stay in place.
* **Caching**: GitHub computes the contribution calendar lazily, so the
  numbers can lag behind the profile page by minutes or hours.
* **Pending cards**: as long as no live run succeeded, the committed cards
  are placeholders that show no statistics on purpose. The cards that are
  committed right now hold real data (see section 4).
* **The committed stars are unavailable**: the committed contributions card
  shows `—` for the stars, because no published card ever showed a star
  figure. The next live run of the workflow replaces it with the real sum.
* The cards are plain SVG files served from this repository. GitHub renders
  them through `<img>`, so no script inside an SVG can ever run.
